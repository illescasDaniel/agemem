# RAW-RAG source retrieval through agemem MCP

RAW-RAG is an optional local source retriever. It does not replace SQLite,
screened note retrieval or the Markdown memory bank. Jev remains the default
decision provider; QSIV is optional. No paid API is required for RAW retrieval;
hosted Jev decisions have their own cost.

The live service uses `agemem.raw_rag`, adapted from MIT-licensed RAW-RAG revision
`95639191e9547219b426710e50fe1a36235e26fc`. Its full license and attribution ship
inside the package. It requires no upstream checkout and creates no remote model
clients. The historical upstream comparison harness has been removed.

## Pipeline and deliberate differences

Each visible source is split into 256 cl100k token windows with overlap32.
Local BGE embeddings select128 candidates by cosine similarity, local MiniLM
reranks them to15, then Agemem packs the cited passages within the context budget.
Unlike upstream conversation windows, each window belongs to exactly one source
record. Source IDs remain exact and no conversation headers are synthesized.
The Engine applies project, branch and current-file-snapshot scope first.
Notes are excluded from this source retriever and retrieved by the note engine.

The adaptation excludes answer generation, remote providers, dynamic selection,
PostgreSQL and incremental conversation ingestion. It is not a paper reproduction
or a claim that RAW retrieval is better than hybrid. Cached vectors are disposable;
SQLite remains authoritative. A changed source/model fingerprint creates a new
cache index. No database migration is required. Existing `raw_rag_directory` /
`AGEMEM_RAW_RAG_DIR` values are no longer needed by live retrieval.

## Setup

Install optional tokenizer support in the environment launching the MCP:

```bash
uv pip install --python .venv/bin/python -e '.[raw]'
.venv/bin/python -m scripts.prepare_raw_rag
```

Use `.venv-qsiv/bin/python` instead when launching from the isolated QSIV runtime.
Preparation explicitly downloads/caches the tokenizer, BGE embedding model and
MiniLM reranker, then runs each locally. It makes no paid API calls. Its default
caches are `.cache/embeddings/` and `.cache/tiktoken/` relative to the working
directory. Keep cache paths absolute in an MCP server's environment.

For a new project, configure RAW retrieval without changing the default provider:

```bash
export AGEMEM_MODEL_CACHE="$PWD/.cache/embeddings"
export TIKTOKEN_CACHE_DIR="$PWD/.cache/tiktoken"
.venv/bin/agemem --project /path/to/project init --retrieval raw-rag
.venv/bin/agemem --project /path/to/project index
.venv/bin/agemem --project /path/to/project recall 'What should I know?'
```

For an existing project, set `retrieval` to `raw-rag` in `.agemem/config.json`.
`init` preserves existing config. Keep project ID and other settings unchanged;
never put API keys in project files. MCP uses the same project configuration.

## Offline operation and verification

Pass `--offline` before a CLI command or before `mcp` in server arguments. This
disables hosted Jev; select QSIV for local note decisions. With default Jev
offline, new notes remain pending and hidden until decisions are available.
Captures, bank and original-source retrieval remain local.

Offline requires cached BGE/MiniLM models and the verified cl100k_base tokenizer
file under `TIKTOKEN_CACHE_DIR`. Missing/corrupt tokenizer data fails before any
tokenizer download. Models use `local_files_only=True`. No silent word-tokenizer
or hybrid substitution occurs. An empty corpus does not validate model setup.

The historical reports `raw-rag-offline-mcp.json` and
`internal-notes-offline-mcp.json` cover the earlier upstream adapter. Do not cite
those reports as proof of the new adapted backend. The unit tests in
`tests_live/test_internal_raw_rag.py` verify exact source boundaries, note
exclusion, budget bounds, persisted vector reuse, source-change invalidation and
rejection of incomplete reranker responses without downloading models. A larger
source-grounded coding/retrieval quality comparison remains open.

The bundled backend's real local QSIV/BGE/MiniLM/MCP smoke passed with network
clients blocked in a local maintainer run. It checks layered
recall, citations, branch scope and stale snapshots, not retrieval quality gains.
