# MCP product and implementation boundaries

The intended product is a coding-project memory MCP with readable working state,
screened durable notes and cited original evidence. The MCP interface is the part
agents use; retrieval algorithms, storage libraries and decision models are
implementation choices. This is an experimental implementation, not yet a
versioned compatibility commitment or a published release.

Current public tools are `project_memory_recall`, `project_memory_remember`,
`project_memory_capture`, `project_memory_index` and `project_memory_maintain`.
Capture/remember calls are explicit; the server does not automatically record
conversations. MCP configuration is project-scoped and installed explicitly.

Current implementation:

| Responsibility | Implementation |
|---|---|
| Working state | Markdown memory bank |
| Persistence | Local SQLite sources/vectors and internal note store |
| Source retrieval | Hybrid/BM25 or bundled adapted RAW-RAG with local providers |
| Note write/retrieval/maintenance | Internal Writer, Retriever and Consolidator adapted from jev-mem |
| Typed model decisions | Jev by default; QSIV, local ollaya or cascade optional |
| Final answer or code | The calling coding agent |

RAW-RAG changes source retrieval only. It operates on branch-filtered source
records selected by agemem; it does not own the note database. Jev/QSIV screen
injection and temporary status, classify notes, judge relations/consolidation,
select relevant notes and assess note evidence. Those are typed decisions, not
final answer generation. Deterministic code also enforces scopes, source linkage,
secret filters, budgets and pending-note visibility.

The live MCP now owns its note engine in `agemem/notes/`, adapted from
`jevmem==0.4.0`. Full MIT notice and original source hashes ship with the package.
The external package is optional (`.[compatibility]`) for upstream database
compatibility tests only. Hosted decisions use agemem's existing bounded
Jev adapter; no upstream global settings, hooks or service are loaded. Only the
local exact matrix vector index is supported by this internal note engine.

SQLite schema, note IDs, pending flags, source linkage and prompt thresholds are
preserved. A roundtrip test opens an upstream database, checks all table contents,
writes with the adapted engine and reopens with upstream. This is a bounded
compatibility check, not a promise for every historical jev-mem version.

For a standalone release, separate storage, note policy, typed-decider and source
retriever interfaces; retain the behavioral tests as migration contracts. Preserve
existing note IDs, source citations, project/branch scopes, pending flags and
schema compatibility, or provide explicit migrations. Shared evidence types, BM25, chunking and context budgeting live in
`agemem.evidence`; the live RAW adapter lives in `agemem.raw_rag`. The historical
comparison harness and its old `amem` command have been removed.
Keep all model/provider dependencies optional where feasible; never silently
switch paid/local providers or change the default backend during setup.

RAW-RAG's needed token-window/dense/rerank pipeline is now adapted in
`agemem.raw_rag`, with its MIT notice and adaptation details bundled in the wheel.
No upstream checkout is required. Per-source windows
provide exact source IDs; this is a deliberate change from conversation windows.
Dependency/model licenses and hosted service terms remain separate.
See THIRD_PARTY.md. Publishing remains separate work.
