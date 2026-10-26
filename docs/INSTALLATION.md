# Installation and project setup

Requires Python 3.12+ and Git. Use an isolated virtual environment in this repository:

```bash
uv venv
uv pip install --python .venv/bin/python -e .
```

Alternatively use `python3 -m venv .venv` and `.venv/bin/python -m pip install -e .`.
Run `agemem config init` and set `providers.jev.api_key` in the private user
`config.yaml`; see [configuration](CONFIGURATION.md). Environment credentials
remain supported as overrides. The integration never reads or modifies your global jev-mem configuration. Never paste a literal key into tracked config.

```bash
AGEMEM=/absolute/path/to/agemem/.venv/bin/agemem
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
command = "/absolute/path/to/agemem/.venv/bin/agemem"
args = ["--project", "/absolute/path/to/project", "mcp"]
env_vars = ["TYPESAFE_API_KEY", "JEV_API_KEY"]
```

Alternatively `codex mcp add agemem-myproject -- /absolute/path/to/agemem/.venv/bin/agemem --project /absolute/path/to/project mcp`; ensure the launched server inherits its API key. See [official MCP configuration documentation](https://learn.chatgpt.com/docs/extend/mcp).

A generic MCP client configuration:

```json
{"mcpServers":{"agemem":{"command":"/absolute/path/to/agemem/.venv/bin/agemem","args":["--project","/absolute/path/to/project","mcp"]}}}
```

Ask the coding agent to recall context before work, update the readable bank at stopping points, capture useful original evidence, and remember durable decisions with provenance. Calling these tools is explicit; installing the server alone does not ingest conversations.

## Agent instructions

Installation does not install the original memory-bank skill or edit agent
instructions. Add the optional [Agemem AGENTS.md section](AGENT_INTEGRATION.md)
to teach the agent when to recall, capture, remember and update working state.

## Optional RAW-RAG retrieval

Install `.[raw]` for the bundled adapted retriever; no external checkout is needed.
Follow [RAW-RAG setup](RAW_RAG.md) to prepare local tokenizer, BGE and MiniLM caches,
then select `retrieval: raw-rag` in project config. This changes source retrieval;
Jev remains the default decision provider.

For user YAML settings and explicit provider setup commands, see
[configuration](CONFIGURATION.md).

For a validated independent GPU environment and durable local weights, follow [standalone QSIV installation](QSIV_INSTALLATION.md). Keep the default Jev environment unless explicitly selecting a local backend.
