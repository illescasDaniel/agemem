"""Local source retrieval adapted from RAW-RAG's token-window/dense/rerank pipeline.

See LICENSE.raw-rag and RAW_RAG_ATTRIBUTION.md. This deliberately omits upstream
conversation formatting, remote providers, answer generation and dynamic top-k.
The caller must supply only project/branch/current-snapshot-visible records.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import replace
from pathlib import Path

import numpy as np

from .evidence import Hit, Retrieved, digest, pack

RAW_SHA = "95639191e9547219b426710e50fe1a36235e26fc"
TOKENIZER_URL = "https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken"
TOKENIZER_SHA = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"


def tokenizer(offline=False):
    """Fail before tiktoken can download on an offline cache miss."""
    if offline:
        cache = os.environ.get("TIKTOKEN_CACHE_DIR")
        path = Path(cache or ".") / hashlib.sha1(TOKENIZER_URL.encode()).hexdigest()
        if not cache or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != TOKENIZER_SHA:
            raise ValueError("Offline RAW-RAG requires a valid cl100k_base cache in TIKTOKEN_CACHE_DIR; run scripts.prepare_raw_rag first")
    try:
        import tiktoken
    except ImportError as exc:
        raise ValueError("RAW-RAG requires the optional dependency: install agemem[raw]") from exc
    return tiktoken.get_encoding("cl100k_base")


class Reranker:
    name = "Xenova/ms-marco-MiniLM-L-6-v2"

    def __init__(self, cache, offline=False):
        self.cache, self.offline, self.model = Path(cache), offline, None

    def scores(self, query, texts):
        if self.model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self.model = TextCrossEncoder(self.name, cache_dir=os.environ.get("AGEMEM_MODEL_CACHE", str(self.cache / "models")), threads=2, local_files_only=self.offline)
        return list(self.model.rerank(query, texts))


class RawRag:
    """Retrieval-only local adapter; no upstream checkout or API clients required.

    Each source gets its own overlapping token windows, preventing adjacent-source
    citation ambiguity. SQLite remains authoritative; cached vectors are disposable.
    """

    def __init__(self, cache, embedder, offline=False, *, encoding=None, reranker=None):
        self.cache, self.embedder = Path(cache), embedder
        self.encoding = encoding if encoding is not None else tokenizer(offline)
        self.reranker = reranker if reranker is not None else Reranker(cache, offline)
        self.groups = {}

    def _chunks(self, records):
        result = []
        for record in records:
            tokens = self.encoding.encode(record.text, disallowed_special=())
            for start in range(0, len(tokens), 224):
                end = min(start + 256, len(tokens))
                result.append(Hit([record.id], self.encoding.decode(tokens[start:end]),
                                  f"raw-token-window:{record.source}:{start}:{end}"))
                if end == len(tokens):
                    break
        return result

    @staticmethod
    def _vectors(values, count):
        matrix = np.asarray(values, dtype=np.float32)
        if matrix.ndim != 2 or len(matrix) != count or not matrix.shape[1] or not np.isfinite(matrix).all():
            raise ValueError("RAW-RAG provider returned invalid embeddings")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-9)

    def retrieve(self, records, question, budget):
        records = sorted((r for r in records if r.kind != "note"), key=lambda r: (r.observed_at, r.id))
        key = digest({"version": 1, "model": self.embedder.model_name,
                      "records": [r.__dict__ for r in records]})
        started = time.perf_counter()
        if key not in self.groups:
            chunks = self._chunks(records)
            vectors = None
            path = self.cache / "raw-local" / f"{key}.json"
            if chunks:
                try:
                    data = json.loads(path.read_text())
                    if data["key"] == key:
                        vectors = self._vectors(data["vectors"], len(chunks))
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                if vectors is None:
                    vectors = self._vectors(self.embedder.embed([h.text for h in chunks]), len(chunks))
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_suffix(f".{uuid.uuid4().hex}.tmp")
                    try:
                        temporary.write_text(json.dumps({"key": key, "vectors": vectors.tolist()}))
                        temporary.replace(path)
                    finally:
                        temporary.unlink(missing_ok=True)
            self.groups[key] = chunks, vectors
        chunks, vectors = self.groups[key]
        build_seconds = time.perf_counter() - started
        ranked = []
        if chunks:
            query = self._vectors(self.embedder.embed([question["query"]]), 1)[0]
            if vectors.shape[1] != len(query):
                raise ValueError("RAW-RAG query and source embedding dimensions differ")
            similarities = vectors @ query
            indices = np.argsort(-similarities, kind="stable")[:128]
            candidates = [chunks[int(i)] for i in indices]
            scores = list(self.reranker.scores(question["query"], [h.text for h in candidates]))
            if len(scores) != len(candidates) or not np.isfinite(np.asarray(scores, dtype=float)).all():
                raise ValueError("RAW-RAG reranker returned invalid scores")
            ranked = sorted((replace(h, score=float(s)) for h, s in zip(candidates, scores)), key=lambda h: -h.score)[:15]
        return Retrieved(pack(ranked, budget), metadata={
            "implementation": "agemem-adapted-raw-rag-v1", "upstream_commit": RAW_SHA,
            "local_providers": True, "answer_generation": False,
            "embedding": self.embedder.model_name, "reranker": self.reranker.name,
            "build_or_cache_seconds": build_seconds, "paper_reproduction": False,
            "chunking": "per-source-cl100k-256-overlap32", "selection": "dense128-rerank15"})

    def close(self):
        self.groups.clear()
