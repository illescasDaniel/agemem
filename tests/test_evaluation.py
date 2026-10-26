import unittest
import tempfile
from pathlib import Path

from amem_lab.core import Hit, Record, Retrieved, TOKEN, chunks, load_data, pack, render, score, visible


class EvaluationTests(unittest.TestCase):
    def test_truncated_gold_is_not_credited(self):
        question = {"evidence": [{"id": "a", "any_of": ["required fact"]}]}
        hits = pack([Hit(["a"], "irrelevant " * 30 + "required fact", "source")], 15)
        self.assertEqual(score(question, Retrieved(hits))["evidence_coverage"], 0)

    def test_rejected_ingestion_does_not_shrink_gold(self):
        q = {"evidence": [{"id": "kept", "any_of": ["first"]}, {"id": "rejected", "any_of": ["second"]}]}
        self.assertEqual(score(q, Retrieved([Hit(["kept"], "first", "s")]))["evidence_coverage"], 0.5)

    def test_unknown_without_sufficiency_is_not_called_abstention(self):
        result = score({"evidence": []}, Retrieved([Hit(["x"], "irrelevant", "s")]))
        self.assertIsNone(result["evidence_coverage"])
        self.assertIsNone(result["sufficient"])
        self.assertFalse(result["false_sufficient"])

    def test_visibility(self):
        records = [Record("good", "ok", "s", "a"), Record("other", "x", "s", "b"),
                   Record("branch", "x", "s", "a", branch="feature"),
                   Record("future", "x", "s", "a", observed_at="2027-01-01T00:00:00Z")]
        q = {"project": "a", "branch": "main", "as_of": "2026-10-26T12:00:00Z"}
        self.assertEqual([r.id for r in visible(records, q)], ["good"])

    def test_budget_includes_citations(self):
        for budget in range(100):
            kept = pack([Hit(["a"], "hello world " * 100, "source/file.py")], budget)
            self.assertLessEqual(sum(len(TOKEN.findall(render(h))) for h in kept), budget)

    def test_overlap_and_unicode(self):
        record = Record("a", "café α β gamma delta epsilon", "s", "p")
        result = chunks([record], size=4, overlap=1)
        self.assertEqual(result[0].text, "café α β gamma")
        self.assertTrue(result[1].text.startswith("gamma"))

    def test_checked_in_gold_exists_in_original_source(self):
        data, records = load_data("data/coding_memory.json")
        lookup = {r.id: r for r in records}
        for q in data["questions"]:
            for e in q["evidence"]:
                self.assertTrue(any(p in lookup[e["id"]].text for p in e["any_of"]))
                self.assertIn(lookup[e["id"]], visible(records, q))

    def test_failed_backend_writes_status_and_exits_nonzero(self):
        from argparse import Namespace
        from amem_lab.cli import run
        import json
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "run.json")
            args = Namespace(experiment=None, data="data/coding_memory.json", project="controlled",
                             questions=None, budget=100, cache=folder, methods="not-a-method",
                             output=path, allow_api=False, raw_checkout="missing")
            with self.assertRaises(SystemExit) as error:
                run(args)
            self.assertEqual(error.exception.code, 1)
            result = json.loads(Path(path).read_text())
            self.assertEqual(result["methods"]["not-a-method"]["status"], "failed")
            self.assertEqual(result["rows"], [])


if __name__ == "__main__":
    unittest.main()
