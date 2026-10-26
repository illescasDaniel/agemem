# Optional lifecycle hooks

Agemem supports command hooks for Claude Code and current Codex clients. These
complement the five MCP tools; they are opt-in and do not install the original
jev-mem hooks or skill. Cursor hook integration is not implemented.

| Event | Context added |
|---|---|
| `SessionStart` (including resume/compaction) | Current Markdown bank and recent screened notes in the current/shared scope |
| `UserPromptSubmit` | Local BM25 matches from screened notes and currently indexed/captured source evidence |

Handlers read local files and SQLite in read-only mode. They do not call Jev or
QSIV, download models, store prompts/transcripts, index changed files, or write
new memories. Pending and stale notes are excluded. Context is capped, cited and
marked as untrusted evidence. This fast path does not run dense retrieval,
RAW-RAG reranking or model sufficiency checks; use `project_memory_recall` for
full retrieval. Capture/remember and bank edits remain explicit agent actions.

On malformed input or unavailable configuration/stores, the handler returns
success without context and may print a generic diagnostic to stderr. It never
returns a blocking decision. Client-level launch errors and timeouts still appear
in the client's hook diagnostics. Each installed handler has a ten-second limit;
client shell/uvx launch overhead counts toward it.

## Install

With a published package:

```bash
uvx --python 3.12 agemem@0.1.0 project init --model jev --mcp claude codex --hooks --no-input
```

Supply the Jev key through private YAML or environment first. Or add hooks to an
already initialized project:

```bash
agemem --project . hooks-install --client claude codex
agemem --project . hooks-install --client claude --dry-run
```

The installer merges `.claude/settings.local.json` and `.codex/hooks.json`,
preserving unrelated settings and hooks. Re-running replaces only Agemem's
marked handlers. Claude uses a local settings file so machine-specific launcher
paths need not be committed. Codex hooks also contain an absolute project path;
review before sharing them. Explicit `AGEMEM_CONFIG` is forwarded as a non-secret
path; credentials are never copied into hook settings.

Shell commands quote project/executable paths, including spaces. They use POSIX
shell syntax; Windows manual testing currently requires Git Bash. The hook JSON
and local handlers have unit tests on Windows, but native Windows client/shell
execution has not been validated.

For source builds before PyPI publication, use an installed executable:

```bash
/absolute/path/to/agemem/.venv/bin/agemem --project . hooks-install --client claude codex --executable /absolute/path/to/agemem/.venv/bin/agemem
```

`mcp-install` and `project init` also accept `--executable`; the default `uvx`
launcher refers to the published version and cannot fetch unreleased code.
See the [manual testing checklist](MANUAL_TESTING.md) for a complete local setup.

## Enable and inspect

- Claude: review the generated settings, restart/start a new session and use
  `/hooks` to inspect the configured handlers.
- Codex: trust the project and use `/hooks` to review and trust the exact hook
  definitions. Changed definitions require review again. Start a new session to
  exercise `SessionStart`.

To disable, disable the handlers in the client's UI where supported, or remove
only the command handlers ending in `# agemem:SessionStart` and
`# agemem:UserPromptSubmit` from the generated file. Leave unrelated handlers intact.
Do not disable hook trust or other client safety settings to make the test pass.

The original jev-mem implementation also performs model-driven prompt selection
and optional automatic capture. Agemem's first integration deliberately keeps
these hooks local/read-only; MCP write operations provide source linkage and
explicit screened persistence.

References: [Claude hook specification](https://code.claude.com/docs/en/hooks),
[Codex hook specification](https://learn.chatgpt.com/docs/hooks).
