"""Local RAW retrieval contracts without downloading models or tokenizer."""
import tempfile
import os
from unittest.mock import patch
import unittest

import numpy as np

from agemem.raw_rag import RawRag, tokenizer
from agemem.evidence import Record, TOKEN, render


class Encoding:
    def encode(self, text, **kwargs):
        return list(text.encode())

    def decode(self, values):
        return bytes(values).decode()


class Embedding:
    model_name = 'test-model'

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        return [np.array([1., 1. if 'Ansible' in text else 0.]) for text in texts]


class Rerank:
    name = 'test-reranker'

    def scores(self, query, texts):
        return [1. if 'Ansible' in text else 0. for text in texts]


class InternalRawTests(unittest.TestCase):
    def test_offline_missing_tokenizer_fails_without_importing_tiktoken(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'TIKTOKEN_CACHE_DIR': folder}):
                with self.assertRaisesRegex(ValueError, 'valid cl100k_base'):
                    tokenizer(offline=True)

    def test_source_boundaries_budget_notes_excluded_and_disk_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            provider = Embedding()
            kwargs = dict(cache=folder, embedder=provider, encoding=Encoding(), reranker=Rerank())
            raw = RawRag(**kwargs)
            records = [Record('a', 'Ansible ' + 'a' * 550, 'README', 'p'),
                       Record('b', 'Fabric source', 'history', 'p'),
                       Record('n', 'SECRET NOTE', 'notes', 'p', kind='note')]
            result = raw.retrieve(records, {'query': 'Ansible'}, 60)
            self.assertTrue(result.hits)
            self.assertEqual(result.hits[0].ids, ['a'])
            self.assertTrue(all(len(h.ids) == 1 for h in result.hits))
            self.assertFalse(any('SECRET' in h.text for h in result.hits))
            self.assertLessEqual(sum(len(TOKEN.findall(render(h))) for h in result.hits), 60)
            self.assertFalse(result.metadata['answer_generation'])
            raw.close()
            provider.calls.clear()
            raw = RawRag(**kwargs)
            raw.retrieve(records, {'query': 'Ansible'}, 60)
            self.assertEqual(provider.calls, [['Ansible']])
            # Changed source content cannot reuse the old index.
            provider.calls.clear()
            changed = [Record('a', 'Terraform replacement', 'README', 'p')]
            result = raw.retrieve(changed, {'query': 'deploy'}, 60)
            self.assertEqual(len(provider.calls), 2)
            self.assertNotIn('Ansible', result.hits[0].text)

    def test_empty_corpus_needs_no_models(self):
        with tempfile.TemporaryDirectory() as folder:
            provider = Embedding()
            result = RawRag(folder, provider, encoding=Encoding()).retrieve([], {'query': 'x'}, 20)
            self.assertEqual(result.hits, [])
            self.assertEqual(provider.calls, [])

    def test_short_reranker_response_fails_instead_of_losing_citations(self):
        with tempfile.TemporaryDirectory() as folder:
            rerank = Rerank()
            rerank.scores = lambda query, texts: []
            raw = RawRag(folder, Embedding(), encoding=Encoding(), reranker=rerank)
            with self.assertRaisesRegex(ValueError, 'invalid scores'):
                raw.retrieve([Record('a', 'Ansible', 'README', 'p')], {'query': 'x'}, 50)
