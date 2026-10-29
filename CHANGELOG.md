# Changelog

## [0.2.0] - 2026-10-29

### Changed

- Client configuration no longer contains machine-specific paths. `project init`, `mcp-install` and
  `hooks-install` write `uvx --python 3.12 agemem@<version> mcp` without `--project`; Cursor passes
  `--project ${workspaceFolder}`, which it interpolates.
- Without `--project`, the project root is the nearest parent directory containing
  `.agemem/config.json` (falling back to the current directory so `init` works in a new project).
  Hooks derive the root from the `cwd` in the client payload.
- Git worktrees share the main checkout's untracked `.agemem/local/` store when it has the same
  project id. Bank files and branch identity still come from the worktree itself, and stores are keyed by branch.
- Claude Code hooks and `autoMemoryEnabled: false` go to the shareable `.claude/settings.json` by default.
  Use `--local-settings` with `project init` or `hooks-install` for `.claude/settings.local.json`.
  Codex hooks stay in `.codex/hooks.json`.
- `--project` still works unchanged.

### Migration

- Re-run `agemem project init` (same `--mcp` clients) in projects set up with 0.1.x. It replaces the
  old `agemem` MCP entries and `# agemem:` hooks with path-free ones and removes the old agemem hooks from
  the other Claude settings file; other entries are untouched. An existing `autoMemoryEnabled` value in
  `.claude/settings.local.json` is kept as is.

## [0.1.1] - 2026-10-29

### Changed

- `project init` for Claude Code now sets `autoMemoryEnabled: false` in
  `.claude/settings.local.json`, so Claude's built-in auto-memory does not duplicate agemem.
  An existing `autoMemoryEnabled` value in project settings is kept.

## [0.1.0] - 2026-10-26

### Added

- Initial 0.1.0 candidate: project-memory CLI and stdio MCP for recall, capture,
  screened notes, indexing and maintenance.
- Guided and unattended project setup, versioned private YAML configuration,
  and MCP registration for Codex, Cursor and Claude Code.
- Local read-only Claude Code/Codex hooks installed by default during project setup and explicit executable
  launchers for testing unpublished source builds.
- Local BM25/dense retrieval, optional adapted RAW-RAG retrieval, hosted Jev
  decisions and optional GPU QSIV, ollaya and cascade providers.
- Installation, agent guidance and PlantUML architecture/setup/recall diagrams.

Experimental first release. Python 3.12–3.14; QSIV installation requires Linux x86_64
and a compatible NVIDIA GPU. YAML schema version 1 accepts existing unversioned
configuration. Database and configuration migrations remain explicit.
