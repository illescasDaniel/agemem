"""Actual upstream adapters, kept optional and isolated from the local baselines."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from .core import Hit, Local, Retrieved, digest, hit, pack

RAW_SHA = "95639191e9547219b426710e50fe1a36235e26fc"
TENCENT_SHA = "65730e979a5a590c54adc181ba8a375055410b84"


def require_checkout(path, sha):
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if actual != sha:
        raise ValueError(f"Upstream revision mismatch; expected {sha}")
    dirty = subprocess.check_output(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], text=True)
    if dirty:
        raise ValueError("Upstream checkout has tracked modifications")


class Reranker:
    name = "Xenova/ms-marco-MiniLM-L-6-v2"

    def __init__(self, cache):
        self.cache, self.model = Path(cache), None

    def scores(self, query, texts):
        if self.model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self.model = TextCrossEncoder(self.name, cache_dir=str(self.cache / "models"), threads=2)
        return list(self.model.rerank(query, texts))


class UpstreamRaw:
    """Reuse upstream chunking, indexing, search, selection and provenance.

    Override only model-provider I/O with local BGE + MiniLM. This is NOT a paper
    reproduction: model choices differ. No answer endpoint is called here.
    """
    def __init__(self, checkout, cache, embedder=None):
        require_checkout(checkout, RAW_SHA)
        sys.path.insert(0, str(Path(checkout) / "methods/EverCore"))
        from evaluation.src.adapters.rag_adapter import RAGAdapter
        from evaluation.src.core.data_models import Conversation, Message
        self.Conversation, self.Message = Conversation, Message
        self.embedder = embedder or Local("dense", cache)
        self.reranker = Reranker(cache)
        embedding, reranker = self.embedder, self.reranker

        class LocalProviders(RAGAdapter):
            async def _embed_texts(self, texts, **kwargs):
                return [v.tolist() for v in embedding.embed(texts)]

            async def _rerank_candidates(self, query, candidates, top_n, **kwargs):
                scores = reranker.scores(query, [x["content"] for x in candidates])
                response = {"results": [{"index": i, "relevance_score": float(s)}
                                         for i, s in enumerate(scores)]}
                return self._parse_rerank_results(response, candidates, top_n)

        self.adapter_class, self.cache = LocalProviders, Path(cache)
        self.groups = {}
        self.loop = asyncio.new_event_loop()

    def retrieve(self, records, question, budget):
        records = sorted((r for r in records if r.kind != "note"), key=lambda r: (r.observed_at, r.id))
        key = digest([r.__dict__ for r in records])[:16]
        started = time.perf_counter()
        if key not in self.groups:
            config = {"chunking": {"strategy": "token", "chunk_size": 256, "chunk_overlap": 32,
                                   "expand_turns_on_display": False},
                      "embedding": {"api_key": "unused-local-provider", "model": self.embedder.model_name},
                      "llm": {"api_key": "unused-retrieval-only", "model": "not-called"},
                      "rerank": {"enabled": True, "model": self.reranker.name},
                      "search": {"embedding_top_k": 128, "rerank_top_k": 15}}
            adapter = self.adapter_class(config, self.cache / "raw-upstream" / key)
            if adapter._encoding is None:
                raise RuntimeError("Upstream tokenizer unavailable; refusing silent word-chunk fallback")
            messages = [self.Message(sender_id="source", sender_name=r.source, content=r.text,
                                    timestamp=datetime.fromisoformat(r.observed_at.replace("Z", "+00:00")))
                        for r in records]
            conversation = self.Conversation(key, messages)
            index = self.loop.run_until_complete(adapter.add([conversation]))
            self.groups[key] = adapter, index
        adapter, index = self.groups[key]
        build_seconds = time.perf_counter() - started
        result = self.loop.run_until_complete(adapter.search(question["query"], key, index,
                                                            question_id=question["id"]))
        hits = []
        for item in result.results:
            meta = item["metadata"]
            if meta.get("start_turn") is None or meta.get("end_turn") is None:
                raise RuntimeError("Upstream chunk lacks source-turn provenance")
            covered = records[int(meta["start_turn"]):int(meta["end_turn"]) + 1]
            hits.append(Hit([r.id for r in covered], item["content"],
                            f"upstream-token-window:{meta['chunk_id']}", item["score"]))
        return Retrieved(pack(hits, budget), metadata={"upstream_commit": RAW_SHA,
                         "embedding": self.embedder.model_name, "reranker": self.reranker.name,
                         "build_or_cache_seconds": build_seconds, "paper_reproduction": False})


class Jev:
    """Real jev-mem Writer/Consolidator/Retriever, with an explicit session budget."""
    def __init__(self, cache, max_calls=32, max_input_tokens=80000):
        from jevmem.decider import JevDecider
        key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY")
        if not key and not os.environ.get("JEVMEM_BASE_URL"):
            raise ValueError("Set TYPESAFE_API_KEY, JEV_API_KEY, or JEVMEM_BASE_URL")
        self.decider = JevDecider(api_key=key, timeout=15)
        from typesafe_sdk import TypeSafeClient
        from typesafe_sdk._core.retry import RetryPolicy
        self.decider._client = TypeSafeClient(api_key=key, base_url=os.environ.get("JEVMEM_BASE_URL"),
                                               retry=RetryPolicy(max_retries=0), timeout=15)
        self.cache, self.groups = Path(cache), {}
        self.max_calls, self.max_input_tokens = max_calls, max_input_tokens
        owner = self

        class Budgeted:
            @property
            def calls(self):
                return owner.decider.calls

            def ask(self, state, questions):
                # Conservative byte bound for the supplied text plus format overhead.
                estimate = len(json.dumps(state, ensure_ascii=False).encode()) + sum(
                    len(q.instructions.encode()) + 128 for q in questions.values()) + 2048
                if (owner.decider.calls >= owner.max_calls or
                        owner.decider.input_tokens + estimate > owner.max_input_tokens):
                    raise RuntimeError("Jev experiment request/token budget reached")
                return owner.decider.ask(state, questions)

        self.budgeted = Budgeted()

    def retrieve(self, records, question, budget):
        from jevmem.config import Config
        from jevmem.consolidate import Consolidator
        from jevmem.retrieve import Retriever
        from jevmem.store import Store
        from jevmem.write import Writer
        records = [r for r in records if r.kind != "note"]
        key = digest([r.__dict__ for r in records])
        before = self.decider.calls
        if key not in self.groups:
            # SQLite lives in RAM, never ~/.jevmem; imports bypass user config/Service.
            import numpy as np
            local = Local("dense", self.cache)

            class Embedder:
                spec = "fastembed:BAAI/bge-small-en-v1.5"

                def embed(self, texts):
                    vectors = np.asarray(local.embed(texts), dtype=np.float32)
                    return vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)

            store = Store(":memory:", embedder=Embedder())
            config = Config(max_jev_calls=6, write_candidates=2, max_depth=2, time_budget_s=8)
            writer = Writer(store, self.budgeted, config)
            mapping, rejected = {}, []
            for record in records:
                result = writer.write(record.text, f"project:{record.project}", timestamp=record.observed_at,
                                      source=record.source, branch=record.branch)
                if result.degraded:
                    raise RuntimeError("Jev unavailable during write; refusing to score fallback")
                if result.rejected:
                    rejected.append({"source_id": record.id, "reason": result.reason})
                elif result.node_id is not None:
                    mapping[result.node_id] = record
            # Small controlled corpus; include actual consolidation, not simulated flags.
            consolidator = Consolidator(store, self.budgeted, writer, config)
            report = consolidator.run(max_nodes=len(records))
            if report.degraded:
                raise RuntimeError("Jev consolidation degraded; refusing to score fallback")
            self.groups[key] = store, Retriever(store, self.budgeted, config), mapping, rejected
        store, retriever, mapping, rejected = self.groups[key]
        result = retriever.recall(question["query"], [f"project:{question['project']}"], k=8, mode="auto")
        if result.degraded:
            raise RuntimeError("Jev recall degraded; refusing to score fallback")
        hits = [hit(mapping[e.id], e.content, e.score) for e in result.evidence]
        return Retrieved(pack(hits, budget), result.sufficient, {"rejected": rejected,
                         "calls_including_build": self.decider.calls - before,
                         "total_calls": self.decider.calls, "total_input_tokens": self.decider.input_tokens,
                         "stop_reason": result.stop_reason, "profile": "bounded pilot, not stock defaults"})


class TencentClient:
    """Small v3 data-plane client, not a replacement for Tencent's extraction engine."""
    def __init__(self, endpoint=None):
        self.endpoint = (endpoint or os.environ.get("TENCENT_MEMORY_URL", "http://127.0.0.1:8420")).rstrip("/")

    def call(self, path, payload=None):
        headers = {"Content-Type": "application/json", "x-tdai-service-id": os.environ.get("TENCENT_INSTANCE", "amem-lab")}
        key = os.environ.get("TENCENT_MEMORY_KEY")
        if key:
            headers["Authorization"] = f"Bearer {key}"
        elif payload is not None:
            raise ValueError("Set TENCENT_MEMORY_KEY; v3 requires a Bearer header even when the gateway gate is disabled")
        if payload is not None:
            payload = {"team_id": os.environ.get("TENCENT_TEAM", "amem-lab"),
                       "agent_id": os.environ.get("TENCENT_AGENT", "coding-experiment"),
                       "user_id": os.environ.get("TENCENT_USER", "local-researcher"), **payload}
        request = urllib.request.Request(self.endpoint + path, headers=headers,
                                         data=json.dumps(payload).encode() if payload is not None else None)
        with urllib.request.urlopen(request, timeout=15) as response:
            result = json.load(response)
        if payload is not None and result.get("code") != 0:
            raise RuntimeError(f"Tencent returned error code {result.get('code')}")
        return result.get("data", result)

    def health(self):
        return self.call("/health")

    def capture(self, session, records):
        # One record per message; keep every returned server ID in a local manifest.
        mapping = {}
        for record in records:
            if len(record.text) > 8192:
                raise ValueError("Tencent message exceeds 8192 characters; split it before upload")
            result = self.call("/v3/conversation/add", {"session_id": session, "messages": [
                {"role": "user", "content": record.text, "timestamp": record.observed_at}]})
            mapping.update({server_id: record.id for server_id in result["accepted_ids"]})
        return mapping

    def search(self, query, session, limit=15):
        return self.call("/v3/conversation/search", {"query": query, "session_id": session, "limit": limit})


class TencentL0:
    """Exercise the real L0 keyword API. No claim about L1-L3 extraction quality."""
    def __init__(self):
        import uuid
        self.client = TencentClient()
        health = self.client.health()
        if not health.get("stores", {}).get("ftsAvailable"):
            raise RuntimeError("Tencent FTS5 is unavailable; refusing silent degraded recall")
        self.groups, self.run_id = {}, uuid.uuid4().hex[:12]

    def retrieve(self, records, question, budget):
        from dataclasses import replace
        from .core import chunks
        records = [r for r in records if r.kind != "note"]
        key = digest([r.__dict__ for r in records])[:16]
        sources = {r.id: r.source for r in records}
        if key not in self.groups:
            session = f"amem-{self.run_id}-{key}"
            by_id = {r.id: r for r in records}
            split_records = [replace(by_id[h.ids[0]], text=h.text) for h in chunks(records, 500, 40)]
            mapping = self.client.capture(session, split_records)
            self.groups[key] = session, mapping
        session, mapping = self.groups[key]
        result = self.client.search(question["query"], session)
        hits = [Hit([mapping[m["id"]]], m["content"], sources[mapping[m["id"]]], m.get("score", 0))
                for m in result["messages"] if m["id"] in mapping]
        return Retrieved(pack(hits, budget), metadata={"service": "Tencent MemoryCore", "layer": "L0",
                         "upstream_commit": TENCENT_SHA, "extraction_evaluated": False,
                         "session": session, "server_id_mapping": mapping})
