"""Evaluator integrity checks: labels never go to providers, failures stay counted."""
import json
import unittest
from pathlib import Path
from evaluation.coding_memory import digest, tasks
from scripts.coding_memory_benchmark import summarize


class CodingMemoryEvaluationTests(unittest.TestCase):
    def test_frozen_fixtures_and_split(self):
        snapshot=json.loads((Path(__file__).resolve().parents[1]/'evaluation/fixtures-v1.json').read_text())
        self.assertEqual(snapshot['sha256'],digest())
        self.assertEqual([t['split'] for t in tasks()].count('calibration'),6)
        self.assertEqual([t['split'] for t in tasks()].count('final'),10)
        for task in tasks():
            self.assertNotIn('gold',task['state'])
            self.assertIn(task['gold']['choice'],task['options'])

    def test_failures_count_and_first_request_is_not_warm(self):
        row=dict(split='final',expected={'choice':'abstain','accept':False},
                 error='DeciderUnavailable',correct=False,seconds=10)
        summary=summarize([row])['final']
        self.assertEqual(summary['total'],1)
        self.assertEqual(summary['errors'],1)
        self.assertEqual(summary['correct'],0)
        self.assertIsNone(summary['warm_median_seconds'])
