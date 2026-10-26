# Coding-memory fixture protocol v1 — frozen before model runs

This is a new author-created controlled fixture evaluation, separate from the prior
50 decisions. Labels are computed by executable Python assertions, independently
of model predictions. It is NOT independently human-labeled, a real repository
coding benchmark, or a test of end-to-end agent code generation.

Each task supplies a coding goal, project/branch, source snippets with provenance,
and candidate one-line implementations. The model screens a proposed memory and
selects a cited implementation or abstains. Evidence includes obsolete code,
wrong project/branch, unresolved conflict, missing facts and prompt injection.
An executable contract labels valid implementations; source metadata labels valid
citations. Contradictory current sources and missing evidence require abstention.
No real repository content is submitted; only committed synthetic fixtures.

First six cases are calibration; remaining ten are final. No fixture, answer,
prompt, cutoff or scoring change after observing final predictions. Primary:
choice correctness including citation, harmful proposed-memory acceptance.
Secondary: code-only correctness, provenance, abstention precision/recall,
fallback fraction, actual hosted input tokens, load/first-request/warm latency.
All errors remain failures, never silently skipped. Keep raw probabilities.

Compare real Jev, QSIV FP8 and live QSIV→Jev at fixed native confidence .90.
Two questions per task: accept proposed memory (threshold .70) and cited choice.
One local model is reused; report shared load and first request separately.
Warm requests are descriptive single-run timings, not a latency distribution.
Jev max 20 attempts / 40000 input-token admission budget per backend, no retries.
These are input-token admission bounds, not exact dollar caps; output and price
are unavailable. No OpenAI calls. Each run checkpoints results after each task.

Investigate threshold-aware binary margin using calibration cases only:
(p−t)/(1−t) above threshold, (t−p)/t below. Select smallest margin cutoff in
[.5,.7,.9,1.01] with zero calibration false acceptances among locally retained
binary answers. Tiny calibration size cannot establish calibrated confidence.
Report that diagnostic separately; do not change the production cascade or
use final results to tune it. Choice confidence stays native.
