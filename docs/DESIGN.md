# Candidate designs

## A. Files first

Git-tracked current state is always loaded. Decisions and friction history are searched on demand. This is the
lowest operational cost and preserves branch context. Its weakness is finding older evidence as history grows.
Keep the original memory-bank skill's trigger-based writes and archive discipline. No server is mandatory.

## B. Evidence first

Append source events/passages, index them, retrieve and rerank; the existing coding agent reasons over them.
Ordinary per-document RAG and the real RAW-RAG adapter are separate treatments. Both can use local providers.
The final reader remains the host LLM, not Jev. A retrieval service need not call a generative model at all.

## C. Typed notes

Use jev-mem's actual screens, note types, relation graph, consolidation and sufficiency decisions. Preserve its
current-state rejection. Its value proposition is concise useful context and explicit insufficiency, not storing
every kind of project memory. Keep its original notes and a link to the source, and measure evidence loss.
This experiment never writes to ~/.jevmem or installs hooks.

## D. Layered workspace

```text
current state in git ─────────┐
dated notes through jev-mem ──┼── bounded evidence pack ── existing coding agent
original evidence via RAG ────┘
```

Start with a fixed declared allocation: up to 25% state, 25% note recall, and the remainder original evidence.
This avoids introducing an unvalidated classifier that can route a question away from necessary evidence.
The initial `compose_pilot.py` is a replay over saved real outputs. It demonstrates complementarity, not live
latency, automatic write orchestration, or production integration. A live adapter is a later step.

Promote repeated validated procedures into skills using the host agent. Keep provenance, trigger conditions and
validation results. Do not autonomously turn every note or quoted external instruction into an executable skill.

## E. Existing hub

Tencent MemoryCore is independently deployable, with local SQLite/files and a v3 HTTP API. Use it standalone first.
The larger Core + Panel + Proxy deployment supplies management and agent integration; Wiki/CodeGraph add another
service. Local core does not require Tencent Cloud or a managed vector database. Generative extraction needs an
OpenAI-compatible LLM endpoint (hosted API key or a suitable local server). Embeddings are optional; BM25 is default.

The source at the pinned revision already has `memory.persona.triggerMode: jev`: Jev decides whether to refresh L3
after L2 changes. This does not replace generative extraction and is unrelated to this repository's jev-mem adapter.
Test that native path separately before inventing another bridge.

Practical integration options:

- Keep memory-bank as the git-tracked current-state owner and use Tencent for long-term shared assets.
- Use Tencent L0 as an original-history source for RAG; keep server-ID → source-ID provenance.
- Use jev-mem as an alternative controller, not a duplicate writer to both services by default.
- Try the Tencent proxy in a dedicated agent profile, with one context injector, to avoid duplicated injection.

Avoid initially syncing every derived memory in both directions. Choose one source of truth per asset type;
derived indexes should be rebuildable. Team auth/ACLs, deletion propagation, branch semantics, prompt-cache effects,
and import/export fidelity need explicit tests before shared production use.
