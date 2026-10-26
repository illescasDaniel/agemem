"""Offline provider guards without downloading model weights in unit tests."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agemem.raw_rag import Reranker, tokenizer


class RawRagOfflineTests(unittest.TestCase):
    def test_missing_or_corrupt_tokenizer_cache_fails_before_provider_import(self):
        with tempfile.TemporaryDirectory() as folder:
            for cache in ('', folder):
                with patch.dict(os.environ, {'TIKTOKEN_CACHE_DIR': cache}):
                    with self.assertRaisesRegex(ValueError, 'TIKTOKEN_CACHE_DIR'):
                        tokenizer(offline=True)
            import hashlib
            url = 'https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken'
            (Path(folder)/hashlib.sha1(url.encode()).hexdigest()).write_text('corrupt cache')
            with patch.dict(os.environ, {'TIKTOKEN_CACHE_DIR':folder}):
                with self.assertRaisesRegex(ValueError, 'valid cl100k_base'):
                    tokenizer(offline=True)

    def test_offline_reranker_only_loads_local_files(self):
        with patch('fastembed.rerank.cross_encoder.TextCrossEncoder') as model:
            model.return_value.rerank.return_value = [.8]
            with patch.dict(os.environ, {'AGEMEM_MODEL_CACHE':'/configured-cache'}):
                self.assertEqual(Reranker('/cache', offline=True).scores('query', ['text']), [.8])
            self.assertTrue(model.call_args.kwargs['local_files_only'])
            self.assertEqual(model.call_args.kwargs['cache_dir'], '/configured-cache')
