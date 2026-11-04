import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agemem.engine import Engine
from agemem.project import initialize


class EmbeddingCacheTests(unittest.TestCase):
    def test_shared_cache_legacy_fallback_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / "project"
            project.mkdir()
            initialize(project, "bm25", "hash")
            shared = root / "data/agemem/models/embeddings"
            legacy = project / ".agemem/local/models"
            with patch.dict(os.environ, {"XDG_DATA_HOME": str(root / "data"),
                                         "XDG_CONFIG_HOME": str(root / "config")}, clear=True):
                engine = Engine(project, offline=True)
                self.assertEqual(engine.embedder.cache, shared)
                engine.db.close()

                legacy.mkdir(parents=True)
                engine = Engine(project, offline=True)
                self.assertEqual(engine.embedder.cache, legacy)
                engine.db.close()

                shared.mkdir(parents=True)
                engine = Engine(project, offline=True)
                self.assertEqual(engine.embedder.cache, legacy)
                engine.db.close()

                with patch.dict(os.environ, {"AGEMEM_MODEL_CACHE": str(root / "custom")}):
                    engine = Engine(project, offline=True)
                    self.assertEqual(engine.embedder.cache, root / "custom")
                    engine.db.close()


if __name__ == "__main__":
    unittest.main()
