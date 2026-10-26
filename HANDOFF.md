# Prompt for the next agent

Work in `/home/daniel/Projects/Code/Python/agemem`. Read README.md,
docs/INSTALLATION.md, docs/LOCAL_BACKENDS.md, docs/QSIV_INSTALLATION.md,
reports/CODING_MEMORY_FINDINGS.md and memory/*.md first. Live implementation is
agemem/; inherited amem_lab experiments are historical. The environment exposes
a placeholder read-only .git rather than a usable checkout; no commit was made.

Preserve hosted Jev as default. Standalone GPU installation now exists at
.venv-qsiv/; durable model/runtime artifacts at .cache/qsiv/model/; embeddings at
.cache/embeddings/. No srxy dependencies/PYTHONPATH. Torch2.11.0/Triton3.6.0,
Transformers5.14.1, NumPy2.5.4. Upstream NumPy2.4.6 conflicts with jev-mem's
>=2.5.3; packaging-only patch requirements/qsiv-numpy.patch resolves it. Runtime
Python matches copied upstream; FP8 pinned SHA verified. All93 packages pass
uv pip check. See reports/qsiv-clean-install.json and exact requirements lock.
Manual clean installation and metadata rebuild passed; consolidated
scripts/install_qsiv.sh was syntax checked but not rerun from scratch. Do not
claim its full fresh-checkout download path was tested. No other project changed.

GPU and MCP subprocess access require sandbox escalation here. Host GPU offline
live write/recall passed (reports/live-qsiv-clean-offline.json), and MCP handshake,
all five tools and offline recall passed. 20 live + eight inherited tests pass.
Source review fixed notes citing other-branch sources or sharing citations to
private sources. Pending unscreened notes stay hidden. No automatic conversation
capture. RAW-RAG offline recall still rejected pending validated offline setup.

New evaluation: evaluation/PROTOCOL.md and immutable fixtures-v1.json were saved
before model runs. Six calibration/ten final author-created executable-oracle
coding-memory selection tasks; direct source state, supplied candidate code,
no retrieval or generated patches. This is separate from old50 but NOT independent
human labeling or proof of coding-agent gains. Final correctness: Jev9/10,
QSIV7/10, cascade10/10; unsupported-memory acceptance0/6,5/6,0/6. Cascade keeps
3/32 questions overall, fallbacks29/32;16 hosted calls each Jev/cascade;9346 and
9045 hosted input tokens respectively (18391 total new tokens), zero OpenAI calls.
Cascade difference on one conflict case could reflect request grouping/provider
variation; no quality advantage established. Existing .90 router unchanged.
Calibration-only threshold-aware binary margin cutoff.70 keeps1/10 final answers;
too little coverage for calibration claims. Do not tune against frozen final data.

User suggested real memory banks under /home/daniel/Projects/Code/Python/,
including srxy and SpaceMaker. Read-only inspection found stale “uncommitted”
notes versus later updates; use current code/tests/history for ground truth.
Four local-only source-grounded questions scored QSIV4/4; paths, lines and hashes
in reports/real-memory-local-probe.json; candidate cases in
evaluation/REAL_PROJECT_CASES.md. No real project excerpts sent to Jev/OpenAI.
User authorized inspecting those projects, not editing them. Existing OpenAI
permission from earlier work is still limited to selected srxy KDE URL-decoding
and release-next-step snippets; do not infer arbitrary repository OpenAI egress.

Next priority: a small genuinely independently reviewed coding-task evaluation,
with source-grounded gold patch outcomes, retrieval/persistence, stale/conflicting
notes, branch/project scope and injection. Keep calibration separate and retain
all failures, raw probabilities, harmful acceptance, citation quality, abstention,
fallback, cost and warm/fresh-process timing. Existing fixtures are a useful
controlled test, not a substitute. Keep API spend bounded and other projects and
global settings unchanged. Finish installation reproducibility by testing the
consolidated downloader in a new environment when appropriate. Document limits.
