> Historical research workspace documentation. Use ../README.md for the live package.

# amem — coding memory experiments

Working name. A research workspace comparing memory for **resuming and changing coding projects**.
This does not install hooks, change agent settings, or write to your existing jev-mem database.

| Folder | Question | Implemented experiment |
|---|---|---|
| [01_memory_bank](../experiments/01_memory_bank/) | How far do small state files and searchable decision logs get us? | Session-start and bank-search baselines |
| [02_normal_rag](../experiments/02_normal_rag/) | Is ordinary retrieval enough? | BM25, BGE dense search, reciprocal-rank fusion, MiniLM reranking |
| [03_raw_rag](../experiments/03_raw_rag/) | Can we reuse RAW-RAG directly? | Pinned upstream `RAGAdapter`; local model providers |
| [04_jev_mem](../experiments/04_jev_mem/) | What do typed decisions add? | Actual jev-mem write, consolidation and recall; bounded paid pilot |
| [05_layered_memory](../experiments/05_layered_memory/) | Can state, notes and original evidence complement each other? | Local allocation baseline and cached bank + Jev + RAW-RAG composition |
| [06_tencent](../experiments/06_tencent/) | Does an existing memory service solve more of this? | Actual v3 L0 adapter plus a real L1 extraction smoke test |

Start with [the findings](../reports/FINDINGS.md), [the evaluation design](EVALUATION.md),
and [the architecture choices](DESIGN.md). Results are exploratory, not a general memory leaderboard.

## Run locally

Python 3.12+; `uv` is optional. No API key is needed for the local baselines.

```bash
uv venv --python 3.12
uv pip install -e '.[dense,upstream,jev]'
python -m unittest discover -s tests -v
python -m amem_lab.cli run --methods bank,bank-search,bm25,layered --output reports/lexical.json
python -m amem_lab.cli run --methods dense,hybrid --output reports/semantic.json
python -m amem_lab.cli run --experiment experiments/02_normal_rag/experiment.json
```

With uv's environment use `uv run --no-sync python ...`, or activate `.venv` first.
BGE (~70 MB) and MiniLM reranker (~80 MB) download on first use. CPU execution is supported.
The minimal standard-library baseline works with `python -m amem_lab.cli run --methods bm25`.

Fetch original source at pinned commits before running RAW-RAG or Tencent:

```bash
python scripts/fetch_upstreams.py
python -m amem_lab.cli run --methods raw-upstream --output reports/raw-upstream.json
```

The RAW-RAG experiment **uses its actual implementation**, overriding only embedding/reranker provider calls.
It uses BGE-small and MiniLM locally, so it is **not a reproduction of the paper's model configuration**.
Provider placeholders in that adapter are unused; it never calls an answering API.

## Data and cost boundaries

`data/coding_memory.json` contains an allowlisted **committed** srxy snapshot plus clearly separate synthetic
Atlas cases. It excludes local environment files, keys, user chats, git credentials, and uncommitted work.
The imported instruction files are evidence to search, not instructions for this repository.
Provenance and exact upstream commits are stored in the dataset manifest.

Local retrieval and RAW-RAG send no corpus data to an external inference provider. Jev and OpenAI calls require
explicit commands. The shipped paid pilot defaults to synthetic data and refuses repository-data egress unless
`--allow-source-egress` is explicitly given after user permission. Keys are read from environment variables and never
written into experiment files. See `.env.example` for variable names; these scripts do not auto-load `.env`.

The first session used isolated `/tmp` environments and services. They are stopped after testing. Recreate your own
environment with the commands above; the saved reports do not require those temporary paths.

## What remains

Extend to independently authored tasks, multiple repositories, real interrupted coding sessions, and patch outcomes.
Test Tencent's higher layers, agent proxy and native Jev persona gate separately. Add a live layered adapter only
after the replay establishes value. QSIV remains an optional future decision-backend experiment.
