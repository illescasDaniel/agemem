"""Compatibility with actual jev-mem 0.4.0 databases, when compatibility extra exists."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

from agemem.notes.store import Store, HashEmbedder


class NoteCompatibilityTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec('jevmem'), 'requires compatibility extra for upstream comparison')
    def test_upstream_database_roundtrip_preserves_all_rows_and_ids(self):
        from jevmem.store import Store as OriginalStore
        from jevmem.store import HashEmbedder as OriginalEmbedder
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / 'notes.sqlite')
            original = OriginalStore(path, embedder=OriginalEmbedder(), index='matrix')
            first = original.add_node('Use Ansible for resumable deployment.', scope='project:atlas',
                                      source='src:deployment', branch='main', commit='abc123')
            second = original.add_node('Unscreened deployment claim.', scope='project:atlas', branch='feature')
            original.queue_pending(second, 'unscreened')
            original.add_edge(first, second, 'semantic', .8)
            original.add_flag(second, 'superseded_by', first, .9)
            def snapshot(db):
                tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
                return {name: [tuple(row) for row in db.execute(f'SELECT * FROM "{name}" ')]
                        for name in tables}
            before = snapshot(original.db)
            original.db.close()
            adapted = Store(path, embedder=HashEmbedder(), index='matrix')
            self.assertEqual(snapshot(adapted.db), before)
            self.assertEqual(adapted.pending('unscreened'), [second])
            third = adapted.add_node('New locally owned note.', scope='project:atlas')
            self.assertGreater(third, second)
            adapted.db.close()
            reopened = OriginalStore(path, embedder=OriginalEmbedder(), index='matrix')
            self.assertEqual([node.id for node in reopened.nodes()], [first, second, third])
            self.assertEqual(reopened.pending('unscreened'), [second])
            reopened.db.close()
