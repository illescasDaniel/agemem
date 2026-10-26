# Manual pre-release testing

**0.1.0 is on hold. Do not tag, run Release, or publish until Daniel approves
after manual MCP and hook testing.** Claude testing is planned for 2026-10-27.
CI does not substitute for these client checks.

## Install the unreleased source

From the Agemem checkout, create a persistent environment and install the source:

```bash
uv venv --python 3.12
uv pip install --python .venv/bin/python -e .
.venv/bin/agemem --help
```

Use an absolute path to that installed `agemem` when registering clients. Do not
use `uvx agemem@0.1.0` until the package is actually published. These examples are
POSIX shell commands; Windows uses the venv's `Scripts/agemem.exe` and Git Bash
for generated hook commands.

## Set up a disposable target project

Use a test repository, rather than important project memory, for the first pass.
From its root, replace the executable path below with the checkout's real path:

```bash
/absolute/path/to/agemem/.venv/bin/agemem project init --mcp claude --executable /absolute/path/to/agemem/.venv/bin/agemem --hooks
```

This still prompts for the provider when creating a new user configuration. With
existing valid YAML it reuses the settings. To keep the test configuration
separate, set `AGEMEM_CONFIG` to a private test YAML path before setup; the path
is forwarded to MCP/hook launchers. An explicit `--model jev` requires a key in
private YAML/environment; `--model qsiv` installs GPU dependencies/model. For
Codex too, use `--mcp claude codex`; Codex registration modifies its user-level
`agemem` entry and remains fixed to the selected project. Add Cursor if desired.
Review the generated settings and launcher paths, then reload the client.

For a no-download/offline contract check, first run `config init` with the same
executable and test config path, then:

```bash
/absolute/path/to/agemem/.venv/bin/agemem --offline project init --mcp claude --executable /absolute/path/to/agemem/.venv/bin/agemem --hooks --no-input --retrieval bm25 --embedder hash
```

Hash embeddings are a testing substitute only. Installed hooks always use local
BM25 regardless of the main retrieval provider.

## MCP checklist

- [ ] MCP connects from the registered local executable; inspect the command.
- [ ] All five `project_memory_*` tools are listed.
- [ ] Index a distinctive fact in tracked README/source; recall returns it with
      source IDs and the correct project and branch.
- [ ] Capture original test evidence; remember a durable fact linked to its source.
      With a working provider, verify a screened note. Offline, verify the write
      is pending/degraded and is not represented as screened success.
- [ ] Restart the client and recall again to confirm persistence.
- [ ] Switch branches and verify private branch facts do not leak; explicitly
      shared facts remain available.
- [ ] Re-run setup and verify config, memory and other MCP entries survive.

## Hook checklist (Claude and Codex)

- [ ] Inspect `/hooks`; trust project/definitions in Codex when prompted.
- [ ] Put a distinctive current task in `memory/activeContext.md`; a new session
      receives it as cited, untrusted background context.
- [ ] Submit a question about an indexed/captured fact; the prompt hook provides
      a relevant source citation, while MCP recall remains available.
- [ ] A successfully screened current/shared note can appear in hook context;
      pending/stale/other-branch notes do not.
- [ ] Confirm hooks do not capture prompts, modify the bank, or call the selected
      decision model. Do not confuse an agent-triggered MCP call with the hook.
- [ ] Resume and compact: context is loaded again when `SessionStart` fires.
- [ ] A malformed input or missing store does not block a session; inspect generic
      hook diagnostics. A client launch failure is visible in its own diagnostics.
- [ ] Repeat hook installation; unrelated settings and hooks remain and Agemem
      handlers are not duplicated. Try a project path containing spaces.

Record client versions, OS, provider, commands, observed context/citations and
failures in an ignored local report. Ask before running tests that incur hosted
provider charges. Send the results before approving publication.
