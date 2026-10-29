"""SQLite connections that are safe for several processes sharing one `.agemem/local` directory.

Every read-write connection uses WAL (readers never block the writer), a long busy timeout, and explicit
`BEGIN IMMEDIATE` write transactions taken through `Connection.tx()`: the write lock is acquired up front, so a
read-then-write sequence cannot fail halfway with a lock upgrade error, and callers keep transactions short.
Connections are in autocommit mode (`isolation_level=None`); nothing is written outside a `tx()` block except
single statements, which SQLite already runs atomically.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

BUSY_TIMEOUT_MS = 30000


class Connection(sqlite3.Connection):
    """sqlite3.Connection with a re-entrant `BEGIN IMMEDIATE` context manager."""

    _depth = 0

    @contextmanager
    def tx(self):
        """Run the block in one write transaction. Nested blocks join the outer one (the outermost commits)."""
        if self._depth:
            self._depth += 1
            try:
                yield self
            finally:
                self._depth -= 1
            return
        self.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self
        except BaseException:
            self._depth = 0
            if self.in_transaction:
                self.execute("ROLLBACK")
            raise
        self._depth = 0
        self.execute("COMMIT")


def _enable_wal(db: sqlite3.Connection, attempts: int = 5) -> bool:
    """True if the database is in WAL mode. Falls back (returns False) where WAL is impossible, e.g. read-only
    or network file systems, leaving the default rollback journal."""
    for attempt in range(attempts):
        try:
            mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            return str(mode).lower() == "wal"
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                time.sleep(0.05 * (attempt + 1))      # another process is converting the file right now
                continue
            return False
    return False


def connect(path, *, check_same_thread: bool = False, foreign_keys: bool = False) -> Connection:
    """Open a multi-process-safe read-write connection (Row factory is left to the caller)."""
    target = path if str(path) == ":memory:" else str(Path(path))
    db = sqlite3.connect(target, timeout=BUSY_TIMEOUT_MS / 1000, isolation_level=None,
                         check_same_thread=check_same_thread, factory=Connection)
    db.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    if target != ":memory:":
        _enable_wal(db)
    db.execute("PRAGMA synchronous=NORMAL")
    if foreign_keys:
        db.execute("PRAGMA foreign_keys=ON")
    return db


def run_script(db: Connection, script: str) -> None:
    """Run a multi-statement DDL script inside one write transaction (executescript would commit first and
    run each statement separately, racing other processes)."""
    statements, current = [], ""
    for line in script.splitlines(keepends=True):
        current += line
        if sqlite3.complete_statement(current):
            statements.append(current)
            current = ""
    if current.strip():
        statements.append(current)
    with db.tx():
        for statement in statements:
            db.execute(statement)
