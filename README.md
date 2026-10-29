# agemem

[![PyPI](https://img.shields.io/pypi/v/agemem?logo=pypi&label=PyPI)](https://pypi.org/project/agemem/)

Experimental coding-project memory: a readable Markdown memory bank, screened SQLite notes, and cited original evidence. Jev is the default decision model. GPU-only QSIV, local ollaya `jevk5:4b`, and a QSIV → Jev confidence cascade are optional.

The answering agent receives current context, selected durable notes and source excerpts. Decision models screen, classify and select memories; your coding agent writes the final answer. No automatic conversation capture or automatic bank rewriting is installed.

![Agemem architecture](https://raw.githubusercontent.com/illescasDaniel/agemem/main/docs/diagrams/architecture.svg)

## Install and use

Requires Git and [uv](https://docs.astral.sh/uv/). From your project directory:

```bash
uvx --python 3.12 agemem@0.2.1 project init
```

Or paste this prompt into your coding agent:

> Integrate Agemem 0.2.1 into this project using the linked installation and
> agent-integration guides. Inspect the environment and existing setup first.
> Ask which clients to configure (Claude Code only, or also Cursor/Codex if
> detected), whether to use hosted Jev, local GPU QSIV, or the experimental
> QSIV → Jev cascade, and any installation constraints. Recommend considering
> the cascade if I have a compatible NVIDIA GPU. Explain QSIV's hardware and
> download requirements and that cascade fallback uses hosted Jev. Have me supply
> a Jev key privately through configuration or the environment, never in chat.
> Run `uvx --python 3.12 agemem@0.2.1 project init --model <jev|qsiv> --mcp <selected clients> --no-input`
> with the agreed choices; `claude` means Claude Code. For cascade, initialize
> with QSIV and then configure the cascade as described in the local backends
> guide; it is not a `--model` option. Preserve existing settings
> and guidance, resolve conflicts with me, and add the suggested memory workflow
> to the appropriate agent instructions. Agree on validation, run provider
> diagnostics and an MCP handshake/tool-list/recall smoke test, and ask before
> tests that incur hosted API charges. Report what passed, any skipped checks,
> and required client restart or approval steps.

Setup connects Codex, Cursor or Claude Code and configures hosted Jev or local
GPU QSIV. Restart your client and enable the server.

If you have a compatible NVIDIA GPU, consider the experimental [confidence
cascade](https://github.com/illescasDaniel/agemem/blob/main/docs/LOCAL_BACKENDS.md#confidence-cascade):
QSIV handles decisions locally and sends low-confidence decisions to hosted Jev.
It requires both QSIV setup and a Jev key; fallback can incur API charges. The
default cutoff is not a guarantee of correctness, and cascade may be slower.

### Give your agent memory instructions

Add the [suggested memory workflow](https://github.com/illescasDaniel/agemem/blob/main/docs/AGENT_INTEGRATION.md)
to your project’s agent instructions (for example, `AGENTS.md` for Codex or
`CLAUDE.md` for Claude Code). This tells the agent when to recall, verify,
capture and maintain memory; installation does not edit these files.

[Claude/Codex lifecycle hooks](https://github.com/illescasDaniel/agemem/blob/main/docs/HOOKS.md)
load local context automatically and are installed by default for those clients.
Use `--no-hooks` to skip installation. Hooks complement
the instructions: they supply context, while the instructions guide how the
agent uses and updates memory.

For Claude Code, `project init` also sets `autoMemoryEnabled: false` in
`.claude/settings.json`, so Claude's built-in auto-memory does not duplicate
agemem. An explicit `autoMemoryEnabled` value in either project settings file is kept.
See the [installation guide](https://github.com/illescasDaniel/agemem/blob/main/docs/INSTALLATION.md) for details. For development, [install from source](https://github.com/illescasDaniel/agemem/blob/main/docs/INSTALLATION.md#development-installation).

## How it works

The default is local BM25 + dense retrieval, combined with bank context and screened notes. An optional retrieval backend adapts RAW-RAG’s token chunking and dense/reranking pipeline. The default incorporates original evidence without depending on RAW-RAG's entire pipeline. [RAW-RAG setup](https://github.com/illescasDaniel/agemem/blob/main/docs/RAW_RAG.md) includes a validated offline MCP path with local embedding/reranking models and no paid retrieval API.

Project config and bank files are readable; SQLite notes, source snapshots and vectors live under ignored `.agemem/local/`. Notes are project- and branch-scoped, unless explicitly shared. Client configuration contains no machine-specific paths (the project is found from the working directory), so it can be committed; git worktrees share the main checkout's local store while keeping their own bank files and branch. Source excerpts include provenance; obsolete snapshots require `--history`. Recall always searches raw sources, even when the note-only sufficiency check succeeds. Its context budget uses regex units, not an exact model tokenizer count.

![Recall combines working context, durable notes and original evidence](https://raw.githubusercontent.com/illescasDaniel/agemem/main/docs/diagrams/recall.svg)

Indexing applies file selection, size and secret filters. Filters are best-effort: inspect material before calling hosted decisions. Retrieved text is untrusted data. Hosted Jev can receive selected memory/source context during screening and recall; indexing itself makes no hosted calls.

The MCP is the intended product interface; the note engine now incorporates selected MIT-licensed jev-mem code without requiring its package. See [implementation boundaries and release direction](https://github.com/illescasDaniel/agemem/blob/main/docs/ARCHITECTURE.md),
[configuration](https://github.com/illescasDaniel/agemem/blob/main/docs/CONFIGURATION.md), [local backends](https://github.com/illescasDaniel/agemem/blob/main/docs/LOCAL_BACKENDS.md),
and the [editable PlantUML diagrams](https://github.com/illescasDaniel/agemem/blob/main/docs/diagrams/README.md).

## Evaluation

On 50 author-labeled synthetic typed decisions: Jev 49/50, QSIV 42/50, cascade 49/50. At a fixed 0.90 native confidence cutoff the cascade kept 16 locally and sent 34 to Jev. This is an exploratory decision test, not proof of improved coding-task outcomes. The cascade is slower in this run and remains experimental.

A controlled coding-memory selection evaluation uses the fixtures in `evaluation/`. The ten final fixtures scored Jev 9/10, QSIV 7/10 and cascade 10/10; QSIV accepted 5/6 unsupported proposed memories. These author-created fixtures do not establish end-to-end coding improvement. See [standalone QSIV setup](https://github.com/illescasDaniel/agemem/blob/main/docs/QSIV_INSTALLATION.md).

Runtime utilities live in `agemem/evidence.py`. The historical comparison harness has been removed; current evaluation fixtures remain available. Reports and findings are local maintainer artifacts.

See the [release checklist](https://github.com/illescasDaniel/agemem/blob/main/docs/RELEASE_0.1.0.md) and [CI/publishing guide](https://github.com/illescasDaniel/agemem/blob/main/docs/PUBLISHING.md).

## Attribution

Agemem combines selected work from these projects and providers:

- [jev-mem](https://github.com/illescasDaniel/jev-mem): adapted MIT-licensed SQLite notes, screening, retrieval and maintenance code; [full notice](https://github.com/illescasDaniel/agemem/blob/main/agemem/notes/LICENSE.jevmem).
- [RAW-RAG](https://github.com/Litmeb/RAW-RAG): adapted MIT-licensed token-window and dense/reranking retrieval; [full notice](https://github.com/illescasDaniel/agemem/blob/main/agemem/LICENSE.raw-rag) and [adaptation details](https://github.com/illescasDaniel/agemem/blob/main/agemem/RAW_RAG_ATTRIBUTION.md).
- [QSIV](https://huggingface.co/djinn-san/QSIV): optional local decision model and runtime, downloaded separately under Apache-2.0 with its original LICENSE and NOTICE.
- [Jev / TypeSafe AI](https://typesafe.ai): default hosted decision provider through its separately installed [Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python); Jev weights and service implementation are not bundled.

See [third-party attribution](https://github.com/illescasDaniel/agemem/blob/main/THIRD_PARTY.md) for versions, source hashes, license boundaries and additional credits.

## Checks

```bash
.venv/bin/python -m unittest discover -s tests_live -q
```
