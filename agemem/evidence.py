"""Evidence records, retrieval primitives and citation-aware context budgeting."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field, replace

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
