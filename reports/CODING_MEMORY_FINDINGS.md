# Coding-memory evaluation and clean QSIV installation — 2026-10-26

Jev stays default. A standalone QSIV GPU installation now passes live offline
write/recall, package compatibility, MCP and contract checks without borrowing
srxy's environment. New controlled fixtures expose unsupported-memory acceptance
that the earlier synthetic decision set did not. They do not establish actual
coding-agent improvement or independently human-reviewed quality.

## Preregistered controlled comparison

Protocol: `evaluation/PROTOCOL.md`; immutable fixture snapshot:
`evaluation/fixtures-v1.json`, SHA256
`f500187c57c30854ed73a02831ab701ac8c64a88eeba88d10af97a032bd20e73`.
Six calibration tasks and ten final tasks were defined before predictions.
Executable assertions determine implementation behavior independently of model
outputs; author-created metadata/rubric determine which evidence is current and
in scope. This is independent of the prior 50-decision set, but NOT independent
human labeling. Two typed questions per task screen a proposed memory at .70
and select an implementation with citation or abstention. All evidence is supplied
directly: retrieval, jev-mem persistence and final agent code generation are not
measured by this benchmark. Errors remain failures; none occurred.

Final split only:

| Metric | Jev | QSIV FP8 | QSIV → Jev (.90) |
|---|---:|---:|---:|
| Correct cited answer / 10 | 9 | 7 | 10 |
| Correct implementation among answered | 8/9 | 6/9 | 8/8 |
| Correct provenance among answered | 8/9 | 6/9 | 8/8 |
| Unsupported proposed memory accepted | 0/6 | 5/6 | 0/6 |
| Correct abstentions / required | 1/2 | 1/2 | 2/2 |
| Total abstentions | 1 | 1 | 2 |
| Warm median request seconds | .125 | .010 | .147 |

Calibration cited answers: Jev 5/6, QSIV 3/6, cascade 5/6. The final difference
between Jev and cascade was the conflict task; only one run was measured.
Cascade invokes Jev on question subsets, changing request grouping, and provider
outputs may vary. Do not infer a reliable cascade quality advantage from one item.

Cost/latency over ALL 16 tasks (32 questions per backend):

| Metric | Jev | QSIV | Cascade |
|---|---:|---:|---:|
| Hosted calls | 16 | 0 | 16 |
| Hosted input tokens | 9,346 | 0 | 9,045 |
| Physical local calls | 0 | 16 | 16 |
| Model/adapter setup seconds | .001 | 3.944 | 4.178 |
| First request seconds | .341 | .569 | .856 |
| Total seconds including setup | 2.309 | 4.918 | 7.543 |

Cascade kept 3/32 questions locally and sent 29/32 to Jev (90.6% fallback).
Hosted input-token reduction was 3.22%; hosted request count did not fall.
These runtimes follow an earlier installation smoke test, so kernel/disk caches
were already populated. “Setup” is fresh-process model loading, not a pristine
machine cold start. Warm medians exclude the process's first request. No repeated
runs or percentile claims. QSIV native token counts remain unavailable.

Total new hosted usage: 32 calls, 18,391 input tokens, zero OpenAI calls. Each
backend had a 20-attempt / 40,000 input-token admission limit, no SDK retries.
The admission estimate is conservative but is not an exact currency cap; provider
output billing/pricing was not measured. All hosted inputs were synthetic.

## Threshold-aware calibration diagnostic

At binary decision threshold .70, distance from .50 is not the relevant safety
margin. The preregistered normalized distance-to-.70 cutoff grid on six QSIV
calibration answers retained 3 answers at .50 (one mistake), 1 at .70 (zero
mistakes), and zero at .90. Thus .70 was selected from calibration only.
It retains just 1/10 final binary answers, correctly rejecting the missing-evidence
memory. This is too little coverage/data to claim calibrated correctness or a
useful router. Choice questions need separate calibration. Production cascade
routing and defaults were left unchanged.

## Real project follow-up, local only

The user suggested existing `/memory` banks. Read-only inspection found banks in
srxy, SpaceMaker, SpaceMaker-worktrees/dev1, aiscript, amem and agemem.
`evaluation/REAL_PROJECT_CASES.md` records source-grounded candidate questions.
Four narrow srxy/SpaceMaker facts were verified against current source/tests
before QSIV predictions. QSIV selected 4/4 correct answers; source paths, line
numbers and full-file hashes are in `real-memory-local-probe.json`.
This is a narrow local selection smoke test, not a three-way real-project study.
No real project excerpts were sent to Jev/OpenAI; no other project was modified.

Stale “uncommitted” entries in srxy coexist with later saved/pushed updates.
SpaceMaker's older HEAD subject does not describe its later working-tree tooling
changes. These support testing current evidence against stale notes rather than
using memory text itself as ground truth. A real independent coding-task study
still needs reviewed task/patch outcomes and an evaluator separate from the
fixture author; the supplied-code multiple-choice test does not replace that.

## Installation and safeguards

See `docs/QSIV_INSTALLATION.md` and `qsiv-clean-install.json`. Durable weights and
BGE cache are under this project's ignored `.cache/`; environment `.venv-qsiv/`
uses Torch 2.11.0, Triton 3.6.0, Transformers 5.14.1 and NumPy 2.5.4.
Upstream's NumPy 2.4.6 metadata conflicts with jev-mem >=2.5.3; the explicit
packaging-only patch is recorded. Rebuilt QSIV metadata passes `uv pip check`.
The consolidated installer script is syntax checked; the actual clean install
and subsequent metadata rebuild were executed separately. FP8 worked on the
RTX 4070 Laptop GPU despite the upstream Blackwell warning. No BF16 claim.

Source review found and fixed cross-branch citation acceptance: notes now require
an existing source in their branch or shared scope. A shared note must cite a
shared source, preventing promotion of private-branch evidence through citation.
Pending unscreened notes remain hidden; MCP refreshes project/branch connections.
20 live tests and eight inherited tests pass in the standalone environment;
MCP initialize/list/five tools/offline recall passed with host subprocess access.
