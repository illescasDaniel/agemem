# Tests for the scoped-recall feature: summaries tier (L0) and the recall path argument.
# Scenarios S1–S7 from sdd/scoped-recall.html; S8 lives in test_mcp_recall, S9 is a manual doc review.
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agemem.engine import Engine
from agemem.project import initialize

ABSENT = object()


def make_project(temp):
    root = Path(temp)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    initialize(root, "bm25", "hash")
    return root


def summaries_for(packet, relative):
    for entry in packet["summaries"]:
        if entry["path"] == relative:
            return entry
    return None


class SeedingTests(unittest.TestCase):
    def test_s6_fresh_init_seeds_abstract_first_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            root = make_project(temp)
            for name in ("activeContext.md", "progress.md", "decisions.md", "archive.md"):
                first = (root / "memory" / name).read_text(encoding="utf-8").splitlines()[0]
                self.assertTrue(first.startswith("> "), f"{name} first line is not a blockquote: {first!r}")
                self.assertLess(len(first), 200, f"{name} abstract should be one line")

    def test_s7_initialize_preserves_existing_files_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temp:
            root = make_project(temp)
            before = (root / "memory/activeContext.md").read_text(encoding="utf-8")
            (root / "memory/decisions.md").write_text("# Decisions\n\nCustom content without an abstract.\n", encoding="utf-8")
            custom = (root / "memory/decisions.md").read_text(encoding="utf-8")
            initialize(root, "bm25", "hash")
            self.assertEqual((root / "memory/activeContext.md").read_text(encoding="utf-8"), before)
            self.assertEqual((root / "memory/decisions.md").read_text(encoding="utf-8"), custom)


class SummariesTests(unittest.TestCase):
    def build(self):
        self.root = make_project(self.temp.name)
        (self.root / "memory/payments").mkdir()
        (self.root / "memory/payments/refunds.md").write_text(
            "> Refund settlement: 3-day hold, then Payout API.\n\n# Refunds\n\nDetails.\n", encoding="utf-8")
        (self.root / "memory/payments/chargebacks.md").write_text(
            "# Chargebacks\n\nNo abstract on the first line.\n", encoding="utf-8")
        self.engine = Engine(self.root, offline=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.build()

    def tearDown(self):
        self.engine.close()

    def test_s1_no_path_recall_returns_summaries_for_every_memory_file_sorted(self):
        packet = self.engine.recall("current state")
        paths = [entry["path"] for entry in packet["summaries"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), 6, paths)   # 4 seeded bank files + 2 payments topic files
        self.assertTrue(all(p.startswith("memory/") for p in paths))
        refunds = summaries_for(packet, "memory/payments/refunds.md")
        self.assertEqual(refunds["abstract"], "Refund settlement: 3-day hold, then Payout API.")
        self.assertNotIn("missing_abstract", refunds)

    def test_s1_no_path_layers_match_today(self):
        packet = self.engine.recall("current state")
        bank_ids = [hit["ids"] for hit in packet["layers"]["bank"]]
        self.assertEqual(bank_ids, [["bank:activeContext.md"], ["bank:progress.md"]])
        self.assertNotIn("scoped", packet)

    def test_s5_missing_abstract_is_flagged_and_recall_succeeds(self):
        packet = self.engine.recall("chargebacks")
        entry = summaries_for(packet, "memory/payments/chargebacks.md")
        self.assertEqual(entry["abstract"], "(no summary)")
        self.assertTrue(entry["missing_abstract"])

    def test_s5_bank_file_without_abstract_still_recalled_normally(self):
        packet = self.engine.recall("chargebacks")
        bank_sources = [hit["source"] for hit in packet["layers"]["bank"]]
        self.assertIn("memory/activeContext.md", bank_sources)   # default bank unaffected by F3


class ScopedRecallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = make_project(self.temp.name)
        (self.root / "memory/payments").mkdir()
        (self.root / "memory/payments/refunds.md").write_text(
            "> Refund settlement details.\n\n# Refunds\n\nRefunds retry three times.\n", encoding="utf-8")
        (self.root / "memory/other.md").write_text("> Unrelated topic.\n\nNothing here.\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, capture_output=True)
        self.engine = Engine(self.root, offline=True)
        self.engine.index()
        self.scoped = self.engine.recall("refunds", path="memory/payments")
        self.global_packet = self.engine.recall("refunds")

    def tearDown(self):
        self.engine.close()

    def test_s2_bank_layer_holds_only_files_under_the_path(self):
        sources = [hit["source"] for hit in self.scoped["layers"]["bank"]]
        self.assertEqual(sources, ["memory/payments/refunds.md"])
        self.assertTrue(all(s.startswith("memory/payments") for s in sources))

    def test_s2_sources_layer_holds_only_records_under_the_path(self):
        sources = [hit["source"] for hit in self.scoped["layers"]["sources"]]
        self.assertTrue(sources, "expected at least one source record under memory/payments")
        for source in sources:
            path = source.rsplit("@", 1)[0].replace("\\", "/")
            self.assertTrue(path == "memory/payments" or path.startswith("memory/payments/"), source)

    def test_s2_notes_layer_identical_with_and_without_path(self):
        self.assertEqual(self.scoped["layers"]["notes"], self.global_packet["layers"]["notes"])

    def test_s2_scoped_block_reports_match_counts(self):
        self.assertEqual(self.scoped["scoped"]["path"], "memory/payments")
        self.assertEqual(self.scoped["scoped"]["bank_files"], 1)
        self.assertGreaterEqual(self.scoped["scoped"]["source_records"], 1)

    def test_s2_scoped_file_path_scopes_to_one_file(self):
        packet = self.engine.recall("refunds", path="memory/payments/refunds.md")
        self.assertEqual([h["source"] for h in packet["layers"]["bank"]], ["memory/payments/refunds.md"])
        self.assertEqual(packet["scoped"]["bank_files"], 1)

    def test_s3_traversal_path_rejected_before_reads(self):
        with self.assertRaises(ValueError):
            self.engine.recall("refunds", path="../secrets")

    def test_s3_symlink_escape_rejected(self):
        outside = self.temp.name + "_outside"
        Path(outside).mkdir()
        (Path(outside) / "secret.md").write_text("secret\n", encoding="utf-8")
        (self.root / "memory/link").symlink_to(outside)
        with self.assertRaises(ValueError):
            self.engine.recall("refunds", path="memory/link/secret.md")

    def test_s3_absolute_path_outside_project_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.recall("refunds", path=str(Path(self.temp.name + "_outside") / "memory"))

    def test_s3_absolute_path_inside_project_also_rejected(self):
        with self.assertRaises(ValueError):   # C2: the path argument is project-relative
            self.engine.recall("refunds", path=str(self.root / "memory" / "payments"))

    def test_s3_path_outside_memory_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.recall("refunds", path="src")

    def test_s4_no_match_returns_explicit_empty(self):
        packet = self.engine.recall("refunds", path="memory/does-not-exist")
        self.assertEqual(packet["layers"]["bank"], [])
        self.assertEqual(packet["layers"]["sources"], [])
        self.assertEqual(packet["scoped"]["bank_files"], 0)
        self.assertEqual(packet["scoped"]["source_records"], 0)
        self.assertEqual(len(packet["summaries"]), 6)   # summaries are unaffected by scoping

    def test_s4_prefix_boundary_does_not_over_match(self):
        (self.root / "memory/payments-extra.md").write_text("> Adjacent topic.\n", encoding="utf-8")
        packet = self.engine.recall("refunds", path="memory/payments")
        sources = {h["source"].rsplit("@", 1)[0].replace("\\", "/") for h in packet["layers"]["sources"]}
        self.assertNotIn("memory/payments-extra.md", sources)

    def test_g2_symlink_escape_excluded_from_summaries_and_bank(self):
        outside = self.temp.name + "_outside2"
        Path(outside).mkdir()
        (Path(outside) / "leaked.md").write_text("> Leaked first line.\n", encoding="utf-8")
        (self.root / "memory/link.md").symlink_to(Path(outside) / "leaked.md")
        packet = self.engine.recall("refunds")
        self.assertIsNone(summaries_for(packet, "memory/link.md"))
        scoped = self.engine.recall("refunds", path="memory")
        self.assertIsNone(summaries_for(scoped, "memory/link.md"))
        self.assertNotIn("bank:link.md", [h["ids"][0] for h in scoped["layers"]["bank"]])

    def test_g4_scoped_bank_files_counts_matches_before_filters(self):
        (self.root / "memory/payments/creds.md").write_text(
            "> Credential notes.\n\napi_key = \"sk-live-0000000000000000\"\n", encoding="utf-8")
        packet = self.engine.recall("refunds", path="memory/payments")
        bank_sources = [h["source"] for h in packet["layers"]["bank"]]
        self.assertEqual(bank_sources, ["memory/payments/refunds.md"])   # creds.md filtered out of the layer
        self.assertEqual(packet["scoped"]["bank_files"], 2)   # but counted as a match


if __name__ == "__main__":
    unittest.main()
