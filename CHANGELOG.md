# Changelog

## [0.4.0] - 2026-11-13

### Added

- A summaries tier in every `project_memory_recall` packet: one line per `memory/**/*.md` file
  (the file's first `>` blockquote, seeded by `agemem init`), so a session can scan all memory
  topics in one cheap call. Files without an abstract are returned as `(no summary)` with
  `missing_abstract: true` instead of failing recall.
- An optional `path` argument on `project_memory_recall` and the recall engine: a project-relative
  path under `memory/` that scopes the bank and source layers to that subtree while notes stay
  global. A scope matching nothing returns an explicit empty result with a `scoped` block; a scope
  escaping the project is rejected before anything is read. Measured against released 0.3.0,
  scoped recall cuts packet cost 90–96% at equal relevance; see `docs/RECALL_COMPARISON.md`.
- `docs/RECALL_COMPARISON.md`: the measured recall comparison (real repos, hybrid retrieval, the
  QSIV decision backend, concurrency), produced during the feature's review.
- The wrap-up skill moved from `docs/memory-wrapup/` to `skills/memory-wrapup/` so the Skills CLI
  finds it (`npx skills add illescasDaniel/agemem`), and it now suggests running at a finished task
  or before a push.

## [0.3.0] - 2026-11-10

### Added

- `project_memory_pending`, `project_memory_resolve` and `project_memory_dismiss` MCP tools. Consolidation
  already queued conflicts and repeated patterns for the agent, but nothing could read or answer the
  queue. Resolving writes one dated note through the same screens as `project_memory_remember`, links it to
  the originals and flags conflicting originals as merged; dismissing closes the item. No existing note is deleted.
- `agemem maintain --pending` prints the queue without starting a decision provider.
- An end-of-session wrap-up routine in `docs/AGENT_INTEGRATION.md` and a copyable
  `docs/memory-wrapup/SKILL.md` (not installed by agemem).

### Fixed

- The consolidation instructions no longer name `memory_forget`, `memory_resolve` and `memory_dismiss`,
  which did not exist; they name the real `project_memory_*` tools.
- Resolving while the decision provider is unavailable no longer leaves a hidden, unscreened note behind:
  it fails, rolls back that one note and leaves the item pending.

## [0.2.3] - 2026-11-10

### Changed

- The suggested project instructions in `docs/AGENT_INTEGRATION.md` were revised: what memory is
  for, keeping `activeContext.md` to intent, blockers and the exact next step, marking confidence
  and what was verified, correcting stale notes on read, keeping conflicting claims under a
  `CONFLICT:` line, plain write style without secrets, and one topic file per agent when several
  work in parallel. Existing projects need to re-copy the block to benefit.
- New projects get a reworded `memory/activeContext.md` template that asks for intent and the next
  step, not state that can be read from git or code. Existing bank files are never changed.

## [0.2.2] - 2026-11-04

### Changed

- New projects share downloaded embedding model files through the user data directory,
  reducing duplicate downloads. Existing project-local model caches keep precedence,
  and `AGEMEM_MODEL_CACHE` still overrides either location.
- The user configuration template now includes Ollaya's local URL and `jevk5:4b`
  model. Jev remains the default provider; explicit project Ollaya settings take
  precedence over user-wide settings.
- Document the expanded decision-model comparison, including Ollaya; benchmark
  inputs and scripts remain in the repository and are excluded from distributions.

## [0.2.1] - 2026-10-29

### Fixed

- Concurrent access from several processes (for example one agent session per git worktree, all sharing
  one `.agemem/local`). Both SQLite stores now open in WAL mode with `synchronous=NORMAL` and a 30 s
  busy timeout, so readers never block the writer and short lock contention waits instead of failing
  with `database is locked`. WAL is optional: where it cannot be enabled the default journal is kept.
- Every write now runs in a short `BEGIN IMMEDIATE` transaction taken through one helper
  (`agemem.sqlite_util`). Note ids are allocated under the write lock (two processes could previously
  pick the same id and fail with a UNIQUE error), schema migrations check and apply inside the lock,
  and no transaction is held across embedding, model or network calls.
- A new note and its type scores are stored in one transaction, so other sessions never see a typed note
  half written. The consolidation write counter is updated atomically (a concurrent consolidation no longer
  resets writes made meanwhile) and the consolidation watermark only moves forward.
- `project init` also ignores SQLite `-wal`, `-shm` and `-journal` files in `.agemem/.gitignore`.

### Notes

- `.agemem/local` must be on a local file system; WAL does not work reliably on network file systems.
  See `docs/ARCHITECTURE.md` for the remaining multi-process limitations.

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
