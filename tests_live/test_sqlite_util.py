import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agemem import sqlite_util
from agemem.notes.store import HashEmbedder, Store
from agemem.sqlite_util import BUSY_TIMEOUT_MS, connect, run_script


class SqliteUtilTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agemem sqlite ")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.sqlite"

    def open(self):
        db = connect(self.path)
        self.addCleanup(db.close)
        return db

    def test_connection_uses_wal_busy_timeout_and_normal_synchronous(self):
        db = self.open()
        self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(db.execute("PRAGMA busy_timeout").fetchone()[0], BUSY_TIMEOUT_MS)
        self.assertGreaterEqual(BUSY_TIMEOUT_MS, 30000)
        self.assertEqual(db.execute("PRAGMA synchronous").fetchone()[0], 1)    # NORMAL
        self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 0)
        self.assertEqual(connect(self.path, foreign_keys=True).execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_wal_failure_falls_back_to_the_default_journal(self):
        real = sqlite_util.Connection.execute
        def refuse(self, sql, *args):
            if "journal_mode" in sql:
                raise sqlite3.OperationalError("unable to open database file")
            return real(self, sql, *args)
        with patch.object(sqlite_util.Connection, "execute", refuse):
            db = connect(self.path)
        self.addCleanup(db.close)
        self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        with db.tx():
            db.execute("CREATE TABLE t(x)")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0], 0)

    def test_wal_that_stays_unavailable_returns_false_without_raising(self):
        db = sqlite3.connect(":memory:")
        self.assertFalse(sqlite_util._enable_wal(db))     # in-memory databases answer "memory"

    def test_busy_wal_switch_is_retried(self):
        calls = []
        class Flaky:
            def execute(self, sql):
                calls.append(sql)
                if len(calls) < 3:
                    raise sqlite3.OperationalError("database is locked")
                class Row:
                    def fetchone(self): return ("wal",)
                return Row()
        with patch.object(sqlite_util.time, "sleep"):
            self.assertTrue(sqlite_util._enable_wal(Flaky()))
        self.assertEqual(len(calls), 3)

    def test_tx_takes_the_write_lock_up_front_but_readers_continue(self):
        writer, other = self.open(), self.open()
        writer.execute("CREATE TABLE t(x)")
        other.execute("PRAGMA busy_timeout=0")
        with writer.tx():
            self.assertTrue(writer.in_transaction)
            with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                other.execute("BEGIN IMMEDIATE")            # a second writer is refused immediately...
            self.assertEqual(other.execute("SELECT COUNT(*) FROM t").fetchone()[0], 0)    # ...a reader is not
            writer.execute("INSERT INTO t VALUES(1)")
        self.assertFalse(writer.in_transaction)
        with other.tx():
            self.assertEqual(other.execute("SELECT COUNT(*) FROM t").fetchone()[0], 1)

    def test_tx_rolls_back_on_error_and_nested_blocks_join_the_outer_one(self):
        db = self.open()
        db.execute("CREATE TABLE t(x)")
        with self.assertRaises(ValueError):
            with db.tx():
                db.execute("INSERT INTO t VALUES(1)")
                with db.tx():
                    db.execute("INSERT INTO t VALUES(2)")
                    self.assertTrue(db.in_transaction)
                self.assertTrue(db.in_transaction)           # inner block did not commit
                raise ValueError("boom")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0], 0)
        with db.tx():
            with db.tx():
                db.execute("INSERT INTO t VALUES(3)")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM t").fetchone()[0], 1)
        with db.tx():                                         # usable again after a failure
            db.execute("INSERT INTO t VALUES(4)")

    def test_run_script_is_one_transaction(self):
        db = self.open()
        with self.assertRaises(sqlite3.OperationalError):
            run_script(db, "CREATE TABLE a(x);\nCREATE TABLE b(y);\nCREATE TABLE a(x);")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 0)
        run_script(db, "CREATE TABLE a(x);\nCREATE TABLE IF NOT EXISTS a(x);\nCREATE TABLE b(y);")
        self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0], 2)

    def test_store_allocates_distinct_ids_across_connections_and_counts_writes_atomically(self):
        one = Store(str(self.path), embedder=HashEmbedder(), index="matrix")
        two = Store(str(self.path), embedder=HashEmbedder(), index="matrix")
        self.addCleanup(one.db.close)
        self.addCleanup(two.db.close)
        ids = [store.add_node(f"note {i} {store is one}") for i in range(5) for store in (one, two)]
        self.assertEqual(len(set(ids)), 10)
        for store in (one, two, one, two):
            store.bump_writes()
        self.assertEqual(one.meta_get("writes_since_consolidation"), 4)
        one.meta_raise("mark", 5); two.meta_raise("mark", 3)
        self.assertEqual(two.meta_get("mark"), 5)
        self.assertEqual(two.meta_add("writes_since_consolidation", -10), 0)
        self.assertEqual(len(two.nodes_after(0, 100)), 10)           # sees the other connection's rows


class IgnoreRuleTests(unittest.TestCase):
    def test_project_init_ignores_the_local_store_and_sqlite_sidecars_once(self):
        from agemem.project import initialize
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / ".agemem").mkdir()
            (root / ".agemem/.gitignore").write_text("/local/\n")      # written by an earlier release
            initialize(root, "bm25", "hash")
            initialize(root, "bm25", "hash")
            rules = (root / ".agemem/.gitignore").read_text().splitlines()
            for rule in ("/local/", "*.sqlite-wal", "*.sqlite-shm", "*.sqlite-journal"):
                self.assertEqual(rules.count(rule), 1)
