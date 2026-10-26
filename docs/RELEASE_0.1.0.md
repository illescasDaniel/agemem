# Public release 0.1.0 plan

Status: preparation only; version metadata already says 0.1.0. No release is
published by this cleanup.

## Scope

Ship the explicit project-memory CLI and stdio MCP: initialize, index, capture,
remember, recall and maintain. Jev is the default decision provider; local QSIV,
ollaya and cascade remain experimental. Document first-run model downloads,
hosted context transmission and offline prerequisites. Preserve source citations,
project/branch scopes and existing note databases.

## Source hygiene

- Keep runtime code, tests, evaluation fixtures, installation
  scripts, provider lock files and third-party notices public.
- Keep this repository's own `memory/`, `HANDOFF.md`, experiment configurations,
  the entire `reports/` folder, caches and environments local.
  These ignore rules apply to this repository, not users' project memory banks.
- Removed the historical comparison harness, its scripts, upstream checkouts,
  experiment configurations and srxy snapshot. Runtime primitives live in
  `agemem.evidence`; only the `agemem` command is distributed.
- Ignoring/untracking files preserves local copies and does not erase Git history.
  Review history for credentials and private data before making the repo public.

## Release gates, in order

1. Choose the project's own license and add a root LICENSE. Third-party licenses
   do not license the original project code. Confirm required notices are bundled.
2. Review tracked source and history for private paths, credentials, captured
   project content and redistribution rights for evaluation data. Replace remaining
   machine-specific examples with portable paths.
3. Audit optional dependency groups and wheel/sdist contents; exclude maintainer artifacts from
   both distributions and confirm provider lock files and notices are included.
4. Run the `tests_live` suite from a fresh checkout without local reports.
   Build wheel and sdist, install the wheel into a fresh environment, and smoke-test
   CLI help plus offline init/index/capture/recall and an MCP tool roundtrip.
   Test hosted Jev and optional providers separately with explicit credentials
   and hardware; document unsupported combinations and known limitations.
5. Add a changelog for 0.1.0 and state Python/platform support, experimental
   guarantees, configuration/storage compatibility and upgrade expectations.
6. Review the final diff and artifacts, then create the release commit/tag and
   publish only after explicit publication authorization.

Completion criteria: a clean-checkout install works without maintainer files,
the MCP workflow is documented and tested, licensing is clear, and the published
artifacts contain the intended runtime and notices.

## Installation validation, 2026-10-26

Built wheel and sdist, then installed the wheel and 54 base packages into a
fresh temporary Python 3.12 environment, using the offline dependency cache.
Dependency compatibility passed. The package loaded from that environment's
site-packages, independently of the source checkout and removed research code.

Verified private YAML creation (0600) and preservation, provider setup dry-run,
project initialization and preservation, indexing, capture, pending/degraded
offline writes, persisted source recall, maintenance, and an MCP stdio handshake
with all five tools. Initialization did not edit agent instructions or install
skills. The MCP roundtrip passed outside the subprocess sandbox after the
sandboxed attempt timed out. All 52 runtime unit tests passed.

This is a BM25/hash offline contract check, not retrieval-quality validation,
a model-download test, or a fresh hosted Jev/GPU inference run. Those provider
checks and the remaining release gates above are still separate work.
