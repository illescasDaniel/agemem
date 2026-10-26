"""Budget and chunk boundaries for runtime evidence retrieval."""
import unittest

from agemem.evidence import Hit, Record, TOKEN, chunks, pack, render


class EvidenceTests(unittest.TestCase):
    def test_budget_includes_citations(self):
        for budget in range(100):
            kept = pack([Hit(["a"], "hello world " * 100, "source/file.py")], budget)
            self.assertLessEqual(sum(len(TOKEN.findall(render(h))) for h in kept), budget)

    def test_overlap_and_unicode(self):
        record = Record("a", "café α β gamma delta epsilon", "s", "p")
        result = chunks([record], size=4, overlap=1)
        self.assertEqual(result[0].text, "café α β gamma")
        self.assertTrue(result[1].text.startswith("gamma"))
