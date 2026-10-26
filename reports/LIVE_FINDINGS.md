# Live integration findings — 2026-10-26

Follow-up: [clean QSIV installation and coding-memory fixture findings](CODING_MEMORY_FINDINGS.md) supersede the temporary-environment limitation below. The tables below preserve the earlier 50-decision results.

The live bank + jev-mem + original-evidence implementation is in `agemem/`. It is distinct from the earlier cached composition experiment. Real hosted Jev + actual upstream RAW-RAG passed a synthetic indexing → two screened writes → recall → persistence/reopen smoke test (`live-jev-raw.json`). Local FP8 QSIV also passed a live offline flow (`live-qsiv-offline.json`). MCP initialization, tool listing and offline recall passed (`mcp-smoke.json`).

## Confidence routing comparison

Same 50 author-labeled synthetic typed decisions using actual jev-mem question templates. The original 20 informed the fixed 0.90 confidence cutoff; 30 additional questions were defined before measuring them. No cutoff adjustment used those new outcomes. New questions cover typing, relevance, complete evidence, alias reasoning, causal direction, choice routing and conflict resolution. These are related synthetic examples, not an independent coding-project benchmark.

| Backend | Original 20 | Additional 30 | All 50 | Hosted requests | Hosted input tokens | End-to-end seconds |
|---|---:|---:|---:|---:|---:|---:|
| Jev | 20/20 | 29/30 | 49/50 | 19 | 9,204 | 2.83 |
| QSIV FP8 | 17/20 | 25/30 | 42/50 | 0 | 0 hosted | 7.40 |
| QSIV → Jev, confidence ≥ .90 kept | 20/20 | 29/30 | 49/50 | 15 | 6,898 | 7.78 |

Cascade kept 16 answers locally and sent 34 to Jev. Hosted input tokens fell 25.1%; requests fell 21.1%. QSIV native token usage is unavailable, not zero. Timings are single runs, include approximately 4–5 seconds of model loading and are affected by kernel caching, batching and network latency. They establish neither steady-state speed nor a production latency distribution. The larger original model-load probe included first-time compilation and was slower.

Both Jev and the cascade missed `complete-alias-cause/multi_hop`; the raw row outputs retain probabilities, labels and thresholds. The cascade reran real Jev on just uncertain question subsets; it did not substitute answers from the Jev baseline. Input-question grouping can change model predictions. QSIV's eight mistakes were all below the selected confidence cutoff on this set; future confidently wrong cases remain a risk.

QSIV confidence is not calibrated correctness. Binary confidence is `abs(2*p - 1)`; the existing predicate-specific thresholds (e.g. status .85, evidence sufficiency .3) remain unchanged. A more principled future router should assess distance from each predicate's decision threshold and calibrate against genuinely separate data. Do not optimize a cutoff and report its score on the same examples as held-out evidence.

Initial ollaya `jevk5:4b` comparison: 17/20, seven requests, 3,810 input tokens, 4.15 seconds including loading. It was not included in this expanded three-way run. Its preexisting service remains running; the test-loaded model was unloaded.

## Feasibility and limitations

QSIV's approximately 1 GB FP8 file did run on the RTX 4070 Laptop with 8 GB VRAM. The short hardware probe allocated approximately 1.44 GiB on the GPU. The runtime warns it is optimized for Blackwell; we verified this machine for bounded inputs only. GPU dependencies were reused read-only from an existing environment; a reproducible clean GPU installation is a remaining handoff task. Model weights are external temporary artifacts, not copied into this repository.

Jev remains default. The confidence cascade is an implemented optional backend, promising for reducing hosted traffic, with no measured quality advantage over Jev alone here. Local QSIV supports fully local memory decisions but scored lower. Offline memory also requires cached embeddings and hybrid/BM25 retrieval. The upstream RAW-RAG integration explicitly rejects offline recall until its setup path is validated offline.

Current tests: 17 live contract tests plus eight inherited research tests passed. These cover scope, persistence, source/bank behavior, budget bounds, secret screens, SDK key separation, QSIV batching, cascade routing and offline uncertain-answer behavior. No real coding-task improvement has yet been established. Historical reports describe earlier research and should not be read as results of this live implementation.

No OpenAI calls were needed for this expansion. The two 50-question hosted paths used 16,102 Jev input tokens total; preceding live/20-question checks are recorded separately. No source-code or private project snippets were sent in these synthetic comparisons.

Reproduce with `python -m scripts.decision_benchmark --backend jev --output reports/jev-decisions-50.json`; use `--backend qsiv` or `--backend cascade --confidence .9` plus `--model-dir /path/to/QSIV` in a working local GPU environment. Results are per-question raw JSON in matching report files.
