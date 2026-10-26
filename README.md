# agemem

Experimental coding-project memory: a readable Markdown memory bank, screened SQLite notes, and cited original evidence. Jev is the default decision model. GPU-only QSIV, local ollaya `jevk5:4b`, and a QSIV → Jev confidence cascade are optional.

The answering agent receives current context, selected durable notes and source excerpts. Decision models screen, classify and select memories; your coding agent writes the final answer. No automatic conversation capture or automatic bank rewriting is installed.

## Install and use

Requires Git and [uv](https://docs.astral.sh/uv/). From your project directory:

```bash
uvx --python 3.12 agemem@0.1.0 project init
```

Or paste this prompt into your coding agent:

> Integrate Agemem 0.1.0 into this project using the linked installation and
> agent-integration guides. Inspect the environment and existing setup first.
> Ask which clients to configure (Claude Code only, or also Cursor/Codex if
> detected), whether to use local GPU QSIV or hosted Jev, and any installation
> constraints. Explain QSIV's hardware and download requirements. Have me supply
> a Jev key privately through configuration or the environment, never in chat.
> Run `uvx --python 3.12 agemem@0.1.0 project init --model <jev|qsiv> --mcp <selected clients> --no-input`
> with the agreed choices; `claude` means Claude Code. Preserve existing settings
> and guidance, resolve conflicts with me, and add the suggested memory workflow
> to the appropriate agent instructions. Agree on validation, run provider
> diagnostics and an MCP handshake/tool-list/recall smoke test, and ask before
> tests that incur hosted API charges. Report what passed, any skipped checks,
> and required client restart or approval steps.

Choose Codex, Cursor or Claude Code when prompted. This creates missing user and
project configuration, indexes the project, and registers its MCP server.
Existing settings and memory are preserved; matching MCP entries are left alone.
First indexing downloads the local embedding model. Codex registration requires
its CLI on PATH; no Node.js/npm is needed.

On first interactive setup, choose hosted Jev or local QSIV if a compatible
NVIDIA GPU is detected. Jev prompts for an API key with hidden input; QSIV
installs its model and GPU runtime. Existing provider settings are preserved.
Restart or reload your client and enable the server.
See the [installation guide](docs/INSTALLATION.md) for configuration, individual
commands, client options and troubleshooting.

This command targets the planned PyPI release; until 0.1.0 is published, use
[installation from source](docs/INSTALLATION.md#development-installation).

Add the [suggested project-memory instructions](docs/AGENT_INTEGRATION.md) to your
agent's project guidance. Installation does not install the original memory-bank
skill or edit agent files. The agent should recall before work, capture original
evidence, remember durable facts and keep `memory/*.md` current.

See [configuration](docs/CONFIGURATION.md), [installation and MCP setup](docs/INSTALLATION.md),
and [local backends](docs/LOCAL_BACKENDS.md).

## Retrieval and storage

The default is local BM25 + dense retrieval, combined with bank context and screened notes. An optional retrieval backend adapts RAW-RAG’s token chunking and dense/reranking pipeline. The default incorporates original evidence without depending on RAW-RAG's entire pipeline. [RAW-RAG setup](docs/RAW_RAG.md) includes a validated offline MCP path with local embedding/reranking models and no paid retrieval API.

Project config and bank files are readable; SQLite notes, source snapshots and vectors live under ignored `.agemem/local/`. Notes are project- and branch-scoped, unless explicitly shared. Source excerpts include provenance; obsolete snapshots require `--history`. Recall always searches raw sources, even when the note-only sufficiency check succeeds. Its context budget uses regex units, not an exact model tokenizer count.

Indexing applies file selection, size and secret filters. Filters are best-effort: inspect material before calling hosted decisions. Retrieved text is untrusted data. Hosted Jev can receive selected memory/source context during screening and recall; indexing itself makes no hosted calls.

The MCP is the intended product interface; the note engine now incorporates selected MIT-licensed jev-mem code without requiring its package. See [implementation boundaries and release direction](docs/ARCHITECTURE.md).

## Evaluation

On 50 author-labeled synthetic typed decisions: Jev 49/50, QSIV 42/50, cascade 49/50. At a fixed 0.90 native confidence cutoff the cascade kept 16 locally and sent 34 to Jev. This is an exploratory decision test, not proof of improved coding-task outcomes. The cascade is slower in this run and remains experimental.

A controlled coding-memory selection evaluation uses the fixtures in `evaluation/`. The ten final fixtures scored Jev 9/10, QSIV 7/10 and cascade 10/10; QSIV accepted 5/6 unsupported proposed memories. These author-created fixtures do not establish end-to-end coding improvement. See [standalone QSIV setup](docs/QSIV_INSTALLATION.md).

Runtime utilities live in `agemem/evidence.py`. The historical comparison harness has been removed; current evaluation fixtures remain available. Reports and findings are local maintainer artifacts.

See the [0.1.0 release plan](docs/RELEASE_0.1.0.md) for the remaining public-release gates.

## Attribution

Agemem combines selected work from these projects and providers:

- [jev-mem](https://github.com/illescasDaniel/jev-mem): adapted MIT-licensed SQLite notes, screening, retrieval and maintenance code; [full notice](agemem/notes/LICENSE.jevmem).
- [RAW-RAG](https://github.com/Litmeb/RAW-RAG): adapted MIT-licensed token-window and dense/reranking retrieval; [full notice](agemem/LICENSE.raw-rag) and [adaptation details](agemem/RAW_RAG_ATTRIBUTION.md).
- [QSIV](https://huggingface.co/djinn-san/QSIV): optional local decision model and runtime, downloaded separately under Apache-2.0 with its original LICENSE and NOTICE.
- [Jev / TypeSafe AI](https://typesafe.ai): default hosted decision provider through its separately installed [Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python); Jev weights and service implementation are not bundled.

See [third-party attribution](THIRD_PARTY.md) for versions, source hashes, license boundaries and additional credits.

## Checks

```bash
.venv/bin/python -m unittest discover -s tests_live -q
```
