# Recall comparison: agemem 0.3.0 (released) vs the scoped-recall build

This page compares the released agemem 0.3.0 recall — the memory engine that
public agentic-loadout 0.6.0 installs and drives — against the scoped-recall
build, which adds two things to `project_memory_recall`:

1. **A summaries tier (L0):** every recall returns a one-line `> ` abstract per
   `memory/**/*.md`, so a session can see all topics before reading anything.
2. **A `path` argument:** recall scopes the bank and source layers to one
   memory subtree, instead of always paying for the whole index. Notes stay
   global.

Full design, spec and verification record: `sdd/scoped-recall.html`.

## How it was measured

Three evaluation runs (2026-11-13), all offline on the same machine:

- **Baseline side:** `git archive v0.3.0` (released code). **New side:** the
  scoped-recall working tree. Version loaded asserted per run.
- **Corpora:** the real agentic-loadout checkout (53 indexed files), the real
  agemem checkout (16), and a 94-file synthetic repo — identical content on
  both sides except the new abstract first lines.
- **Retrieval:** bm25 with the deterministic hash embedder throughout; hybrid
  re-run offline as a cross-check; retrieval backend unchanged by this feature.
- **Decision backends:** deterministic stub for the cost experiments; the real
  local QSIV FP8 backend (RTX 4070) end-to-end in the final run.
- **Relevance:** scored programmatically — a ground-truth passage located
  beforehand in the real content must appear in the returned context.
- **Cost metric:** the packet's own `context_units` (regex-token proxy), plus
  character counts and wall time (median of 3 runs).

## Headline: targeted (topic) queries

Scoped recall on the new build vs the released full recall, per corpus:

| Corpus | Baseline 0.3.0 (full recall) | New build (scoped) | Cost delta | Relevance |
|---|---|---|---|---|
| Real agentic-loadout (53 files) | ~1800 units (full recall) | 175–261 units | ~−90% | 3/3 both sides |
| Real agemem (16 files) | ~1800 units | 75–78 units | ~−96% | 3/3 both sides |
| Synthetic (94 files) | ~1800 units | 109–127 units | ~−93% | 3/3 both sides |

Aggregated over three queries per corpus: 583 vs 5400, 228 vs 5395 and 363 vs
3862 units (9–23×). Wall time: 1.1–2.7 ms scoped vs 6.5–21.5 ms full. Under
hybrid retrieval the same pattern held (scoped 109–127 vs full ~1800 units).

## Topic scan: what the summaries tier buys

Seeing every memory topic in one call:

| Corpus | Baseline: topics visible in a full recall | New: summaries tier |
|---|---|---|
| Real agentic-loadout | 2 of 3 (costs 1800 units) | 7/7 files, 104 tokens / 490 chars |
| Real agemem | 2 of 3 | 7/7 files, 103 tokens |
| Synthetic (94 files) | 3 of 8 | 12/12 files, 181 tokens |

The tier rides along with every recall at a fixed cost of roughly 100–180
regex tokens (477–853 chars) and ~1.5–3 ms, and is returned as its own JSON
key outside the context budget.

## With the real QSIV decision backend (end-to-end)

| Metric | Baseline 0.3.0 | New build |
|---|---|---|
| Screening (`remember`) with the real model | works; 4/4 accepted | works identically |
| Recall latency (median) | 0.107 s | 0.095 s full / 0.074 s scoped |
| `decision_calls` full vs scoped | n/a (no `path`) | byte-identical — scoping never reduces or duplicates decision work |
| Packet cost | 1790–1800 units | 1790–1800 full / 133–192 scoped (−89…−93%) |

QSIV cold start is one model load (~7 s once; later processes attach in
0.03–0.45 s). The decision layer is tens of milliseconds per steady-state
recall — scoping's saving is purely packet size.

## Fixed overhead of the new build

- The seeded `> ` abstract first lines shift full-recall cost by about ±25
  context units (~+4–6% on the smallest packets).
- The summaries tier adds ~100–181 regex tokens per recall (outside the
  context budget) plus ~1.5–3 ms.
- A scoped call trades away global source evidence by design: source hits
  drop (e.g. 12→1). A query whose answer lives outside the scope still
  receives it only if the global notes layer carries it.

## Failure behaviour (new build)

- A scope matching nothing returns a small, explicit empty packet
  (11–132 units) that is distinguishable from a failed recall.
- Escaping paths (`../`, absolute, outside `memory/`) are rejected before
  anything is read.
- 8 parallel recall calls (per-thread engines) produced packets identical to
  sequential runs, with and without scoping.

## What these numbers cannot show

- The Ollaya backend was not exercised (no Ollaya server was running during
  evaluation; the server tested was plain Ollama, a different backend).
  Hosted Jev needs credentials and was not run.
- One machine, one GPU, small note sets; relevance certified packet targeting,
  not deep-corpus retrieval; token counts are the packet's regex proxy, not
  model tokens; medians of 3 runs are noisy at the ~1–30 ms scale.
- QSIV screening accepted all four probe notes on both sides (including one
  that should have been rejected) — a decision-model quality observation,
  identical on 0.3.0, not a regression of this feature.
