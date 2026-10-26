# Active context

2026-10-26: Jev remains default. QSIV standalone GPU environment `.venv-qsiv/`
validated with project-local durable weights `.cache/qsiv/model/` and BGE cache
`.cache/embeddings/`. Torch2.11.0/Triton3.6.0; QSIV metadata-only NumPy2.5.4
patch resolves jev-mem constraint conflict. 93-package compatibility check passes.
Offline live smoke, MCP host smoke, 20 live + eight inherited tests pass.

New frozen coding-memory selection fixtures: six calibration, ten final.
Final cited answer correctness Jev9/10, QSIV7/10, cascade10/10. Unsupported-memory
acceptance Jev0/6, QSIV5/6, cascade0/6. Cascade fallback29/32 overall; only3.22%
input-token savings. Total18391 new hosted input tokens; no OpenAI calls.
Author-created executable-oracle fixtures are not independent human labels or
end-to-end coding-task evidence. Keep Jev default; do not tune on final outcomes.

Read-only srxy/SpaceMaker source-grounded local QSIV probe4/4, no hosted egress.
Cross-branch/source citation gap fixed. See reports/CODING_MEMORY_FINDINGS.md,
docs/QSIV_INSTALLATION.md and HANDOFF.md for reproducibility and remaining work.
