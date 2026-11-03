# Decision model evaluation and local provider choice

agemem uses hosted Jev by default. QSIV is an optional local GPU provider, not
the default or a claim that it is the most accurate model. We retained QSIV as
the supported local option because it gave a useful combination of decision
quality, low request latency and an existing isolated, reproducible local
runtime on the test machine. The comparisons below are exploratory evidence for
that tradeoff, not proof that QSIV is the best model in general. In particular,
UltraBERT scored one question higher and runs on CPU; we have not integrated or
evaluated it in a complete agemem workflow.

## Decision probe

The expanded probe contains 19 synthetic states and 50 author-labeled questions,
including memory typing, relevance, evidence sufficiency, replacement, causal
relations, conflict and routing. The questions use agemem's jev-mem templates.
The original 20 decisions informed earlier cascade experiments; the remaining
30 were added before that comparison. This is a small, related, author-created
set, not an independent held-out dataset or an end-to-end coding benchmark.

Each model received the same state and question instructions via its own typed
interface. Binary answers use the existing per-question probability thresholds
(0.3, 0.5, 0.7 or 0.85), while choices use the selected option; thresholds were
not tuned separately for each model. We count each question once. This measures
the model *and its interface and rendering*, and the threshold sensitivity
limits cross-model conclusions. In particular, Vega's CPU probability for one
answer was 0.706 and GPU probability was 0.699, on opposite sides of the 0.7
threshold. It signaled abstention on 9 of the 50 GPU answers; the table scores
its top predictions anyway, to use the same rule as the other models.

| Model | CPU correct | GPU correct | CPU median / p95 request | GPU median / p95 request |
| --- | ---: | ---: | ---: | ---: |
| UltraBERT 380M Curation | 43/50 | 43/50 | 652 / 1,730 ms | 26 / 78 ms |
| QSIV FP8 | — | 42/50 | — | 10 / 32 ms |
| Strands Decider 2B Qwen3.5 v1 | 42/50 | 42/50 | 3,844 / 7,150 ms | 144 / 257 ms |
| Strands Hobson v19 | 40/50 | 40/50 | 3,609 / 7,057 ms | 153 / 269 ms |
| Open-Jev 2B | 39/50 | 39/50 | 3,458 / 7,502 ms | 109 / 279 ms |
| Laya typed-decisions | 35/50 | 35/50 | 883 / 1,805 ms | 34 / 49 ms |
| Vega 0.8B public intents | 30/50 | 31/50 | 2,060 / 4,559 ms | 82 / 162 ms |
| Open-Jev DeBERTa v3 large | 30/50 | 30/50 | 631 / 1,271 ms | 40 / 76 ms |
| EmbeddingGemma typed-decision | 26/50 | — | — | — |

EmbeddingGemma was measured once on CPU, without the repeated timing procedure,
so its timings are omitted. A separate earlier run scored hosted Jev 49/50 and
a QSIV → Jev cascade 49/50 on this probe; the cascade used a fixed 0.90 native
confidence cutoff. Those are not comparable local-only latency measurements.
QSIV and UltraBERT both made mistakes: in the paired comparison QSIV alone got
four questions right, UltraBERT alone got five right, both got 38 right and
both missed three. A difference of one on 50 questions does not establish a
winner.

## Timing method

The repeated measurements used an Intel i9-13900HX CPU with eight PyTorch
threads and an NVIDIA RTX 4070 Laptop GPU with 8 GiB VRAM. After one full suite
of warm-up, each model ran the 19 requests five times, sequentially: 95 request
samples covering 250 question answers. Median and linearly interpolated p95 are
calculated across those requests. Each sample runs from the local call to its
returned response, including rendering, tokenization and inference. GPU calls
are synchronized. Model loading, warm-up, network and concurrent workload are
not included; QSIV's local worker transport is included. Inputs have different
numbers of questions, and timings are not a production latency guarantee.

The providers keep their native interfaces: QSIV batches at most eight questions
per physical call; UltraBERT scores questions independently; the others use
their respective published paths. DeBERTa accepts a text state, so the
structured state was serialized as JSON. Its 512-token limit required the
replacement request to be split at question boundaries into two model calls;
no state was truncated. Laya and the other structured interfaces received the
original state. Vega used its default automatic adapter routing; none of these
questions selected a specialized adapter.

CPU runs used float32 and GPU runs generally used bfloat16, except QSIV FP8 and
DeBERTa float32. Open-Jev 2B used its conservative uncached, batch-size-one
path; the CPU run explicitly selected float32 because its default bfloat16 path
was very slow. Strands, Hobson, Vega and Open-Jev used reference GPU kernels
when optional accelerated kernels were unavailable. Different precision,
batching, implementations and hardware utilization affect timing and may change
predictions. These measurements do not establish each model's optimal speed.

The benchmark scripts and per-question results are in the source repository's
`scripts/` and `evaluation/decision-results/` directories, with developer notes
in `evaluation/DECISION_BENCHMARK.md`. They are excluded from installed wheel
and source distributions. Model weights and third-party inference code are not
bundled. Open-Jev 9B and 27B were not run because their base models exceeded the
available GPU capacity.

## What this does not show

The separate coding-memory fixture evaluation reported in the README found
QSIV 7/10, hosted Jev 9/10 and the cascade 10/10 on ten author-created final
fixtures; QSIV accepted 5 of 6 unsupported proposed memories. It does not prove
coding-task improvement either. The local-provider decision should be revisited
with larger independently labeled examples, real memory workflows, stronger
negative cases and measurements on the target hardware. Confidence is not a
guarantee of correctness; the cascade and its cutoff remain experimental.
