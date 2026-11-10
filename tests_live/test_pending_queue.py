"""Pending-queue tools (Track B, scenarios S1-S11 in sdd/pending-queue.html).

Real temporary SQLite stores with a scripted decider; no model quality is tested here.
"""
import subprocess
import tempfile
import unittest
from pathlib import Path

from agemem.engine import Engine
from agemem.notes import consolidate
from agemem.notes.decider import FakeDecider
from agemem.project import initialize


def quiet(state, key, question):
    return 0.0


class PendingQueueBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-b", "main", str(self.root)], check=True, capture_output=True)
        initialize(self.root, "bm25", "hash")
        self.fake = FakeDecider(quiet)
        self.engine = Engine(self.root, offline=True, decider=self.fake)
        self.store = self.engine._notes()[0]

    def tearDown(self):
        self.engine.close()
        self.temp.cleanup()

    def seed(self, kind="conflict", texts=("Deploys run from main.", "Deploys run from release branches.")):
        ids = [self.store.add_node(t, "global") for t in texts]
        return self.store.add_synth(kind, ids, 0.9), ids


class ListingTests(PendingQueueBase):
    def test_s1_lists_oldest_first_capped_with_total(self):
        made = [self.seed(texts=(f"fact {i} a", f"fact {i} b"))[0] for i in range(12)]
        page = self.engine.pending()
        self.assertEqual(page["total"], 12)
        self.assertEqual([item["id"] for item in page["items"]], made[:10])
        first = page["items"][0]
        self.assertEqual({"id", "kind", "p", "memories", "instruction"}, set(first) & {"id", "kind", "p", "memories", "instruction"})
        self.assertEqual(len(first["memories"]), 2)
        self.assertEqual(len(self.engine.pending(limit=3)["items"]), 3)

    def test_s2_empty_queue_and_bad_limit(self):
        self.assertEqual(self.engine.pending(), {"items": [], "total": 0})
        self.seed()
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                self.engine.pending(limit=bad)

    def test_s3_listing_never_builds_or_asks_a_provider(self):
        self.seed()
        self.fake.down = True
        engine = Engine(self.root, offline=True)

        def forbidden():
            raise AssertionError("listing must not build a decision provider")
        engine._decision = forbidden
        try:
            self.assertEqual(engine.pending()["total"], 1)
        finally:
            engine.close()
        self.assertEqual(self.fake.calls, 0)


class ResolveTests(PendingQueueBase):
    def test_s4_resolve_conflict_writes_one_stamped_linked_note(self):
        item, (a, b) = self.seed("conflict")
        before = self.store.count()
        result = self.engine.resolve(item, "As of 2026-11-10 deploys run from release branches.")
        self.assertTrue(result["ok"], result)
        self.assertEqual(self.store.count(), before + 1)
        node = self.store.get(result["node_id"])
        self.assertEqual(node.source, f"consolidation:{item}")
        self.assertIsNotNone(node.timestamp)
        self.assertEqual(node.branch, self.engine.branch)
        linked = {other for _, other in self.store.neighbors(node.id, ["semantic"])}
        self.assertTrue({a, b} <= linked)
        for old in (a, b):
            self.assertIsNotNone(self.store.get(old))
            self.assertIn(("merged_into", node.id), [(f, o) for f, o, _ in self.store.flags_of(old)])
        self.assertEqual(self.engine.pending()["total"], 0)

    def test_s5_resolve_promote_does_not_flag_episodes(self):
        item, (a, b) = self.seed("promote", ("Fixed flaky test on Monday by pinning a seed.",
                                             "Fixed flaky test on Friday by pinning a seed."))
        result = self.engine.resolve(item, "Flaky tests in this project are fixed by pinning a random seed.")
        self.assertTrue(result["ok"], result)
        for old in (a, b):
            self.assertNotIn("merged_into", [f for f, _, _ in self.store.flags_of(old)])
        self.assertEqual(self.engine.pending()["total"], 0)

    def test_s9_refused_text_leaves_item_pending_and_retry_works(self):
        item, (a, b) = self.seed()
        before = self.store.count()
        for text in ("", "   ", "api key sk-ant-api03-" + "x" * 40):
            result = self.engine.resolve(item, text)
            self.assertFalse(result["ok"], text)
            self.assertTrue(result["error"])
        for screened in ("injection", "status"):
            self.fake.rule = lambda s, k, q, screened=screened: 0.99 if k == screened else 0.0
            result = self.engine.resolve(item, "Some statement that the screen refuses.")
            self.assertFalse(result["ok"], screened)
        self.fake.rule = quiet
        self.assertEqual(self.store.count(), before)
        self.assertEqual(self.store.flags_of(a), [])
        self.assertEqual(self.engine.pending()["total"], 1)
        self.assertTrue(self.engine.resolve(item, "As of 2026-11-10 deploys run from release branches.")["ok"])

    def test_s10_provider_down_rolls_back_and_retry_makes_one_note(self):
        item, (a, b) = self.seed()
        before = self.store.count()
        self.fake.down = True
        result = self.engine.resolve(item, "As of 2026-11-10 deploys run from release branches.")
        self.assertFalse(result["ok"])
        self.assertIn("agemem doctor", result["error"])
        self.assertEqual(self.store.count(), before)
        self.assertEqual(self.store.pending(), [])
        self.assertEqual(self.store.flags_of(a), [])
        self.assertEqual(self.store.edges_of(a), [])
        self.assertEqual(self.engine.pending()["total"], 1)
        self.fake.down = False
        self.assertTrue(self.engine.resolve(item, "As of 2026-11-10 deploys run from release branches.")["ok"])
        self.assertEqual(self.store.count(), before + 1)

    def test_s7_resolve_unknown_or_closed_id(self):
        item, _ = self.seed()
        before = self.store.count()
        self.assertEqual(self.engine.resolve(99, "x")["error"], "no such pending synthesis")
        self.engine.dismiss(item)
        self.assertFalse(self.engine.resolve(item, "As of 2026-11-10 something.")["ok"])
        self.assertEqual(self.store.count(), before)


class DismissTests(PendingQueueBase):
    def test_s6_dismiss_closes_without_writing(self):
        item, (a, b) = self.seed()
        before = self.store.count()
        self.assertEqual(self.engine.dismiss(item), {"ok": True})
        self.assertEqual(self.store.count(), before)
        self.assertEqual(self.store.flags_of(a), [])
        self.assertEqual(self.engine.pending()["total"], 0)

    def test_s8_dismiss_unknown_or_closed_id(self):
        item, _ = self.seed()
        self.assertEqual(self.engine.dismiss(99), {"ok": False, "error": "no such pending synthesis"})
        self.engine.dismiss(item)
        self.assertFalse(self.engine.dismiss(item)["ok"])


class InstructionTextTests(unittest.TestCase):
    def test_s11_instruction_names_only_real_tools(self):
        text = " ".join(consolidate._INSTRUCTION.values())
        self.assertNotIn("memory_forget", text)
        import re
        allowed = {"project_memory_resolve", "project_memory_dismiss"}
        self.assertTrue(set(re.findall(r"\b\w*memory_\w+", text)) <= allowed)
        self.assertIn("project_memory_dismiss", text)
        self.assertIn("project_memory_resolve", text)


if __name__ == "__main__":
    unittest.main()
