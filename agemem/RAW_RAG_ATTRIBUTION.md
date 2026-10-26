# RAW-RAG attribution

`raw_rag.py` adapts the overlapping token-window algorithm and dense candidate /
reranking pipeline from RAW-RAG, MIT License, copyright 2026 RAW-RAG contributors.
Full upstream license: `LICENSE.raw-rag`, included in this package.

Upstream: https://github.com/Litmeb/RAW-RAG
Revision: `95639191e9547219b426710e50fe1a36235e26fc`
Reference: `methods/EverCore/evaluation/src/adapters/rag_adapter.py`
Reference file SHA256: `997c35db93feea77eed897b3d5640bd9cd6f114da40bff5128efae65a6466637`

This is a deliberate adaptation, not an upstream reproduction. Source records
are chunked separately (256 cl100k tokens, overlap32), with exact source IDs.
The original conversation headers, cross-turn windows, temporal filters,
remote embedding/reranking/answer clients, incremental conversation ingestion,
dynamic selection and optional PostgreSQL support are omitted. Agemem filters
project, branch and current snapshot visibility before calling this adapter.
BGE/MiniLM run locally; dense cosine top128 feeds rerank top15, followed by
Agemem's context budget. Model licenses remain separate from source licensing.

The live service uses only this adapted implementation; no upstream checkout or
comparison harness is required.
