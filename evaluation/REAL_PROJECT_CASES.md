# Read-only project-grounded follow-up — 2026-10-26

Discovered memory banks in srxy, SpaceMaker, SpaceMaker-worktrees/dev1, aiscript,
amem and agemem. Read srxy and SpaceMaker activeContext only; changed neither
project nor their environments. No real project excerpts sent to Jev or OpenAI.

Candidate questions with evidence established before local predictions:

1. srxy: Should the native Browse handler unquote the selected path a second time?
   Gold: no; accept a typed QUrl and call toLocalFile once. Independent current
   code check: src/srxy/adapters/inbound/gui/controller.py setBrowsedPath and
   qml/Main.qml controller.setBrowsedPath(selectedFolder). Memory agrees.
2. srxy: What does CLI cancellation return and where is its message printed?
   Gold: 130, stderr. Current cli.py code independently confirms activeContext.
3. SpaceMaker: Where should Claude load shared project instructions?
   Gold: AGENTS.md; current CLAUDE.md contains only @AGENTS.md. Memory agrees.
4. SpaceMaker: What is the shared instruction-file line budget?
   Gold: 130. tests/unit/test_agent_context.py defines and asserts it.
5. srxy: Are all items described as “uncommitted” in activeContext actually
   uncommitted now? Gold: cannot use that sentence alone; later entries say saved
   and pushed. Check current git history/status per task. Avoid labeling from an
   isolated stale note. HEAD observed 72bab1d.
6. SpaceMaker: Does the old “agent-guild 1.2.0” HEAD subject establish current
   installed configuration? Gold: no. activeContext describes subsequent 1.3.0
   tooling maintenance as uncommitted; inspect working files, not HEAD subject.
   HEAD observed cfcc18f.

These are source-grounded questions, not an independent human review. Four narrow
facts can be verified from current code/tests; release-policy questions require
human intent and date-sensitive notes. Local probe uses only the four narrow
facts and records source hashes. Keep separate from frozen synthetic final data.
