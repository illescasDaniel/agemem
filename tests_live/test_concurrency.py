import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from agemem.project import initialize

WORKERS, ROUNDS = 6, 40
WORKER = Path(__file__).with_name("_stress_worker.py")


class ConcurrentProcessTests(unittest.TestCase):
    """Several processes (one per worktree session) share one .agemem/local through the real Engine."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agemem stress ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], check=True)
        initialize(self.root, "bm25", "hash")
        (self.root / "README.md").write_text("Atlas stress project\n")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)

    def test_parallel_processes_neither_lock_nor_lose_writes(self):
        go = self.root / "go"
        environment = {**os.environ, "AGEMEM_CONFIG": str(self.root / "user.yaml")}
        workers = [subprocess.Popen([sys.executable, str(WORKER), str(self.root), str(i), str(ROUNDS), str(go)],
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
                   for i in range(WORKERS)]
        for worker in workers:
            self.addCleanup(worker.kill)
        started = time.time()
        go.write_text("go")
        results = []
        for worker in workers:
            out, err = worker.communicate(timeout=120)
            self.assertEqual(worker.returncode, 0, err)
            self.assertNotIn("locked", err)
            results.append(json.loads(out.strip().splitlines()[-1]))
        elapsed = time.time() - started
        self.assertLess(elapsed, 45)

        sources = [s for r in results for s in r["sources"]]
        notes = [n for r in results for n in r["notes"]]
        self.assertEqual(len(sources), WORKERS * ROUNDS)
        self.assertEqual(len(set(notes)), len(notes), "two processes were given the same note id")
        self.assertGreater(len(notes), WORKERS * ROUNDS // 2)
        local = self.root / ".agemem/local"
        with sqlite3.connect(local / "sources.sqlite") as db:
            stored = {r[0] for r in db.execute("SELECT id FROM sources WHERE kind='event'")}
        self.assertEqual(stored, set(sources))
        with sqlite3.connect(local / "notes.sqlite") as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual({r[0] for r in db.execute("SELECT id FROM nodes")}, set(notes))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM fts").fetchone()[0], len(notes))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM nodes WHERE type_scores IS NULL").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT value FROM meta WHERE key='max_node_id'").fetchone()[0], str(max(notes)))
            self.assertEqual(db.execute("PRAGMA journal_mode").fetchone()[0], "wal")
