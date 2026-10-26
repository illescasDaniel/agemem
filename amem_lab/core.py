"""Shared evidence format, visibility, context budget and local retrieval baselines."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
WORD = re.compile(r"[a-z0-9]+")
STOP = set("a an the is are was were to of for in on at and or what which how why do does should we our it this with from".split())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def terms(text):
    # Split camelCase and snake_case so source symbols are searchable.
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    return [t for t in WORD.findall(text.lower()) if t not in STOP]


@dataclass(frozen=True)
class Record:
    id: str
    text: str
    source: str
    project: str
    kind: str = "raw"
    branch: str = "main"
    observed_at: str = "2026-10-26T12:00:00Z"
    current: bool = False
    origins: tuple[str, ...] = ()


@dataclass
class Hit:
    ids: list[str]
    text: str
    source: str
    score: float = 0.0


@dataclass
class Retrieved:
    hits: list[Hit]
    sufficient: bool | None = None
    metadata: dict = field(default_factory=dict)


def load_data(path):
    data = json.loads(Path(path).read_text())
    records = [Record(**{**r, "origins": tuple(r.get("origins", []))}) for r in data["records"]]
    ids = [r.id for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate record IDs")
    known = set(ids)
    for q in data["questions"]:
        for e in q["evidence"]:
            if e["id"] not in known:
                raise ValueError(f"Unknown gold source: {e['id']}")
        if not q.get("split"):
            raise ValueError("Each question needs an explicit split")
    return data, records


def visible(records, question):
    """Visibility is shared infrastructure, not a measured backend capability."""
    return [r for r in records if r.project == question["project"]
            and r.branch in ("shared", question.get("branch", "main"))
            and r.observed_at <= question["as_of"]]


def hit(record, text=None, score=0.0):
    return Hit(list(record.origins or (record.id,)), text if text is not None else record.text,
               record.source, score)


def chunks(records, size=160, overlap=24):
    if not 0 <= overlap < size:
        raise ValueError("Require 0 <= overlap < size")
    out = []
    for r in records:
        matches = list(TOKEN.finditer(r.text))
        for start in range(0, len(matches), size - overlap):
            end = min(start + size, len(matches))
            text = r.text[matches[start].start():matches[end - 1].end()]
            out.append(hit(r, text))
            if end == len(matches):
                break
    return out


def render(item):
    return f"[{','.join(item.ids)} | {item.source}]\n{item.text}"


def pack(items, budget):
    """Hard common budget in regex units (words + punctuation), including citations.

    These are deliberately NOT called model tokens. Score only the packed text.
    """
    if budget < 0:
        raise ValueError("Budget must be nonnegative")
    out, seen, used = [], set(), 0
    for item in items:
        key = (tuple(item.ids), item.text)
        if key in seen:
            continue
        seen.add(key)
        header_cost = len(TOKEN.findall(render(replace(item, text=""))))
        remaining = budget - used - header_cost
        if remaining <= 0:
            break
        matches = list(TOKEN.finditer(item.text))
        if not matches:
            continue
        text = item.text[:matches[min(len(matches), remaining) - 1].end()]
        kept = replace(item, text=text)
        cost = len(TOKEN.findall(render(kept)))
        assert used + cost <= budget
        out.append(kept)
        used += cost
        if len(matches) > remaining:
            break
    return out


def bm25(query, items):
    query_terms = set(terms(query))
    docs = [Counter(terms(x.text)) for x in items]
    if not docs or not query_terms:
        return []
    df = Counter(t for doc in docs for t in doc)
    avg = sum(sum(d.values()) for d in docs) / len(docs) or 1
    scored = []
    for item, doc in zip(items, docs):
        length = sum(doc.values())
        score = sum(math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
                    * doc[t] * 2.2 / (doc[t] + 1.2 * (0.25 + 0.75 * length / avg))
                    for t in query_terms if doc[t])
        if score > 0:
            scored.append(replace(item, score=score))
    return sorted(scored, key=lambda x: (-x.score, x.ids, x.text))


class Local:
    def __init__(self, mode, cache_dir, model="BAAI/bge-small-en-v1.5"):
        self.mode, self.cache_dir, self.model_name = mode, Path(cache_dir), model
        self.model = None
        self.embeddings = {}

    def embed(self, texts):
        if self.model is None:
            from fastembed import TextEmbedding
            self.model = TextEmbedding(self.model_name, cache_dir=str(self.cache_dir / "models"), threads=2)
        missing = list(dict.fromkeys(t for t in texts if t not in self.embeddings))
        if missing:
            for text, vector in zip(missing, self.model.embed(missing)):
                self.embeddings[text] = vector
        return [self.embeddings[t] for t in texts]

    def retrieve(self, records, question, budget):
        current = [r for r in records if r.current]
        if self.mode == "bank":
            # Session-start baseline: files in explicit order, read whole under the budget.
            ordered = sorted(current, key=lambda r: ("activeContext" not in r.source, r.source, r.id))
            return Retrieved(pack([hit(r) for r in ordered], budget))
        candidates = chunks([r for r in records if r.kind != "note"])
        if self.mode in ("bm25", "bank-search", "layered"):
            if self.mode == "bank-search":
                candidates = chunks([r for r in records if r.kind == "bank"])
            ranked = bm25(question["query"], candidates)
        elif self.mode in ("dense", "hybrid", "dense-rerank"):
            import numpy as np
            query_vector = self.embed([question["query"]])[0]
            vectors = self.embed([x.text for x in candidates])
            ranked = sorted((replace(x, score=float(np.dot(query_vector, v) /
                            max(float(np.linalg.norm(query_vector) * np.linalg.norm(v)), 1e-9)))
                             for x, v in zip(candidates, vectors)), key=lambda x: -x.score)
            if self.mode == "dense-rerank":
                from .integrations import Reranker
                if not hasattr(self, "reranker"):
                    self.reranker = Reranker(self.cache_dir)
                candidates = ranked[:128]
                scores = self.reranker.scores(question["query"], [x.text for x in candidates])
                ranked = sorted((replace(x, score=float(s)) for x, s in zip(candidates, scores)),
                                key=lambda x: -x.score)[:15]
            if self.mode == "hybrid":
                ranks, values = {}, {}
                for ranking in (ranked, bm25(question["query"], candidates)):
                    for rank, item in enumerate(ranking, 1):
                        key = (tuple(item.ids), item.text)
                        ranks[key] = ranks.get(key, 0) + 1 / (60 + rank)
                        values[key] = item
                ranked = [replace(values[k], score=ranks[k]) for k in sorted(ranks, key=lambda k: -ranks[k])]
        else:
            raise ValueError(f"Unknown local mode: {self.mode}")
        if self.mode == "layered":
            # Fixed allocation is declared in advance; no gold labels or query-type routing.
            state = pack([hit(r) for r in current], budget // 4)
            notes = pack(bm25(question["query"], [hit(r) for r in records if r.kind == "note"]), budget // 4)
            ranked = [*state, *notes, *ranked]
        return Retrieved(pack(ranked, budget), metadata={"selection": self.mode, "model": self.model_name
                         if self.mode in ("dense", "hybrid", "dense-rerank") else None})


def score(question, result):
    evidence = question["evidence"]
    found = []
    for e in evidence:
        found.append(any(e["id"] in h.ids and any(p.casefold() in h.text.casefold()
                         for p in e["any_of"]) for h in result.hits))
    return {
        "evidence_coverage": sum(found) / len(found) if found else None,
        "all_evidence": all(found) if found else None,
        "evidence_found": found,
        "context_units": sum(len(TOKEN.findall(render(h))) for h in result.hits),
        "context_items": len(result.hits),
        "sufficient": result.sufficient,
        "false_sufficient": result.sufficient is True and (not found or not all(found)),
        "unknown_context_items": len(result.hits) if not evidence else None,
    }


def serialize(result):
    return {"hits": [asdict(h) for h in result.hits], "sufficient": result.sufficient,
            "metadata": result.metadata}
