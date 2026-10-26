# Installation and project setup

Requires Python 3.12+ and Git. Use an isolated virtual environment in this repository:

```bash
uv venv
uv pip install --python .venv/bin/python -e .
```

Alternatively use `python3 -m venv .venv` and `.venv/bin/python -m pip install -e .`.
Export `JEV_API_KEY` or `TYPESAFE_API_KEY` in the launching environment. The integration never reads or modifies your global jev-mem configuration. Never paste a literal key into tracked config.

```bash
AGEMEM=/home/daniel/Projects/Code/Python/agemem/.venv/bin/agemem
PROJECT=/absolute/path/to/your/project
"$AGEMEM" --project "$PROJECT" init
"$AGEMEM" --project "$PROJECT" index
"$AGEMEM" --project "$PROJECT" capture 'Original task event or diagnostic text' --label task-event
"$AGEMEM" --project "$PROJECT" remember 'A durable decision with its rationale'
"$AGEMEM" --project "$PROJECT" recall 'What should I know before resuming?'
"$AGEMEM" --project "$PROJECT" maintain
```

Review the created `.agemem/config.json`, `.agemem/.gitignore` and `memory/` bank. Commit config/bank when appropriate. Generated local databases and model caches stay ignored. Capture returns a source ID; pass it as `remember --source-id ID` to link a note. Avoid sensitive content in shell arguments/history.

The default embedder downloads on first use and then runs locally. Set `AGEMEM_MODEL_CACHE` to reuse a machine-local cache. Offline mode requires cached weights and `decision_backend` set to `qsiv` or `ollaya`; hosted decisions are disabled. `--offline` precedes the subcommand. `init --retrieval bm25 --embedder hash` provides a lightweight smoke-test configuration; hash embeddings are not a quality substitute for BGE.

## MCP

Tools: `project_memory_recall`, `project_memory_remember`, `project_memory_capture`, `project_memory_index`, `project_memory_maintain`. The server uses stdio and is scoped to the supplied project. No agent configuration is changed automatically.

For Codex, add this to the applicable MCP configuration (replace the project path):

```toml
[mcp_servers.agemem-myproject]
command = "/home/daniel/Projects/Code/Python/agemem/.venv/bin/agemem"
args = ["--project", "/absolute/path/to/project", "mcp"]
env_vars = ["TYPESAFE_API_KEY", "JEV_API_KEY"]
```

Alternatively `codex mcp add agemem-myproject -- /absolute/path/to/agemem/.venv/bin/agemem --project /absolute/path/to/project mcp`; ensure the launched server inherits its API key. See [official MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp).

A generic MCP client configuration:

```json
{"mcpServers":{"agemem":{"command":"/absolute/path/to/agemem/.venv/bin/agemem","args":["--project","/absolute/path/to/project","mcp"]}}}
```

Ask the coding agent to recall context before work, update the readable bank at stopping points, capture useful original evidence, and remember durable decisions with provenance. Calling these tools is explicit; installing the server alone does not ingest conversations.

## Actual upstream RAW-RAG

Install `.[upstream]` and clone the upstream source separately:

```bash
uv pip install --python .venv/bin/python -e '.[upstream]'
git clone https://github.com/Litmeb/RAW-RAG /path/to/RAW-RAG
git -C /path/to/RAW-RAG checkout 95639191e9547219b426710e50fe1a36235e26fc
export AGEMEM_RAW_RAG_DIR=/path/to/RAW-RAG
```

Set `retrieval` to `raw-rag` in project config. This invokes the upstream retriever with local embeddings; Jev remains the decision backend. First-use tokenizer/embedding setup can download weights. This integration explicitly rejects `raw-rag` recall with `--offline`; use tested `hybrid` or `bm25` retrieval for offline operation.

For a validated independent GPU environment and durable local weights, follow [standalone QSIV installation](QSIV_INSTALLATION.md). Keep the default Jev environment unless explicitly selecting a local backend.
