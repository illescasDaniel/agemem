# Changelog

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
