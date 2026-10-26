# agemem

Experimental coding-project memory: a readable Markdown memory bank, live jev-mem notes, and cited original evidence. Jev is the default decision model. QSIV, local ollaya `jevk5:4b`, and a QSIV → Jev confidence cascade are optional.

The answering agent receives current context, selected durable notes and source excerpts. Decision models screen, classify and select memories; your coding agent writes the final answer. No automatic conversation capture or automatic bank rewriting is installed.

## Install and use

```bash
cd /home/daniel/Projects/Code/Python/agemem
uv venv
uv pip install --python .venv/bin/python -e .
export JEV_API_KEY='your-key' # or TYPESAFE_API_KEY; never commit credentials
.venv/bin/agemem --project /path/to/project init
.venv/bin/agemem --project /path/to/project index
.venv/bin/agemem --project /path/to/project remember 'We chose PostgreSQL because settlement writes need transactions.'
.venv/bin/agemem --project /path/to/project recall 'Why PostgreSQL?'
```

First indexing downloads the local BGE embedding model. `index` snapshots selected Git-tracked text files and the bank. Run it again after relevant changes. `capture` archives explicit original text; `remember` runs actual jev-mem screens and persistence. Edit `memory/*.md` to maintain current focus, progress and decisions; existing bank files are preserved by initialization.

See [installation and MCP setup](docs/INSTALLATION.md), [local backends](docs/LOCAL_BACKENDS.md), and [live findings](reports/LIVE_FINDINGS.md). [HANDOFF.md](HANDOFF.md) contains the next-agent prompt.

## Retrieval and storage

The default is local BM25 + dense retrieval, combined with bank context and jev-mem notes. Actual upstream RAW-RAG is an optional explicit retrieval backend. The default incorporates original evidence without depending on RAW-RAG's entire pipeline.

Project config and bank files are readable; SQLite notes, source snapshots and vectors live under ignored `.agemem/local/`. Notes are project- and branch-scoped, unless explicitly shared. Source excerpts include provenance; obsolete snapshots require `--history`. Recall always searches raw sources, even when the note-only sufficiency check succeeds. Its context budget uses regex units, not an exact model tokenizer count.

Indexing applies file selection, size and secret filters. Filters are best-effort: inspect material before calling hosted decisions. Retrieved text is untrusted data. Hosted Jev can receive selected memory/source context during screening and recall; indexing itself makes no hosted calls.

## Evaluation

On 50 author-labeled synthetic typed decisions: Jev 49/50, QSIV 42/50, cascade 49/50. At a fixed 0.90 native confidence cutoff the cascade kept 16 locally and sent 34 to Jev. This is an exploratory decision test, not proof of improved coding-task outcomes. The cascade is slower in this run and remains experimental.

A new controlled coding-memory selection evaluation and the clean QSIV installation are documented in [current findings](reports/CODING_MEMORY_FINDINGS.md). The ten final fixtures scored Jev 9/10, QSIV 7/10 and cascade 10/10; QSIV accepted 5/6 unsupported proposed memories. These author-created fixtures do not establish end-to-end coding improvement. See [standalone QSIV setup](docs/QSIV_INSTALLATION.md).

The inherited research harness is retained in `amem_lab/`, `experiments/` and historical reports. [Historical research README](docs/RESEARCH_README.md) describes that earlier workspace; use this README for the live implementation.

## Checks

```bash
.venv/bin/python -m unittest discover -s tests_live -q
.venv/bin/python -m unittest discover -s tests -q
```
