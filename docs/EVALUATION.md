# Evaluation protocol

## Questions and treatments

The initial corpus has 188 evidence records: selected committed srxy docs, instructions, memory files and source,
plus controlled history/state/notes. There are 18 author-written exploratory questions: 12 srxy and 6 controlled.
Two questions are intentionally unknown. All cases are marked exploratory; none are described as held out.
The exact srxy commit is `72bab1dbdc649fbd3d5f739ef73e39394e5db595`.

Tasks cover architecture location, conventions, decision rationale, bug causes, renamed entities, historical facts,
current release scope, session handoff, branch-local knowledge and absent information. They do **not** yet measure
whether an agent can implement a correct patch, recover from interruption, or resist prompt injection reliably.
The synthetic quoted injection is one diagnostic, not a safety benchmark.

`scripts/build_fixture.py` reads `git show <commit>:<allowlisted path>`, never the live working tree. Markdown
sections are source units; a subset of source files adds realistic distractors. No model creates benchmark gold.
Gold evidence specifies a source record and one or more acceptable verbatim substrings. Substrings are checked
against the **actual context after packing/truncation**, not just a retrieved document ID. This is a reproducible
passage-presence proxy, not semantic proof that the answer is supported.

## Equal access and budgets

All variants receive the same observable corpus, with shared project, branch and as-of filtering before ingestion.
The filter is infrastructure: it does not demonstrate native isolation or historical query support in a backend.
The bank baseline deliberately reads only current state; bank-search also searches its decision history. The local
layered treatment can read the explicitly hand-authored synthetic notes; the raw-only treatments omit those notes.
This representation difference is declared, not hidden as an algorithm improvement.

Context is capped at 1,800 **regex units** (words + punctuation), including citation headers. These are not BPE model
tokens. Native chunk sizes differ: local RAG uses 160 regex units with 24 overlap; upstream uses its tokenizer's
256-token windows with 32 overlap across a source-message stream. Model-token usage is recorded separately for
paid calls. Smaller/larger budgets should be a preregistered later sensitivity experiment, not tuned on these labels.

Raw text, event dates, source IDs, original gold and rejected-note records are retained. A rejected note stays in
the gold denominator. A query cannot become "unanswerable" because an ingestion policy dropped its evidence.
No backend is scored through a silent fallback; failure status is distinct from a completed run. Partial rows in
a failed run are diagnostic only. Warm-up/build times are included and labeled; do not compare them as p50 latency.

## Report interpretation

- **Evidence coverage:** fraction of annotated evidence units whose source ID and required phrase survived packing.
- **All evidence:** fraction of answerable questions with all annotated units present.
- **Context size:** common regex units delivered, not just number of notes.
- **Unknown cases:** context noise is reported; returning context is not itself a wrong answer. Only a backend's
  explicit sufficiency output can be evaluated as a sufficiency prediction.
- **False sufficient:** explicit `true` when at least one annotated unit is missing, or the question is unknown.
- **Calls/usage:** actual Jev call/input counters and OpenAI usage are retained. Estimated dollars use documented
  list prices, not an account billing receipt.

Jev's bounded pilot uses 2 write candidates, graph depth <=2, 6 calls per recall, 8 seconds per recall,
32 requests and 80,000 input tokens for the session. It is a latency/cost-limited profile, not stock jev-mem defaults.
The first pilot is five controlled queries, so its aggregate must **not** be ranked against the 18-question runs.

## Final reader

`amem packets` exports context without expected answers or gold labels. `scripts/paid_reader_pilot.py` uses the
same GPT-4.1 mini snapshot and prompt across methods, with <=220 output tokens, no automatic retries, and <=$0.03
reserved request cost by default. Synthetic cases are permitted by default; repository snippets require separate
egress permission. Evidence is explicitly untrusted data. Selection happens before the reader sees the question's gold.

Human/agent review rubric, applied per answer:

1. Correct substantive answer, including both alias and causal link for multi-hop tasks.
2. No unsupported facts, secrets, commands or actions inferred from missing context.
3. Citations point to supplied supporting evidence, not just a vaguely related source.
4. Correct temporal/current-state interpretation, and a clear unknown when evidence is absent.
5. Unfinished or output-truncated responses are flagged explicitly.

Store raw answers with usage and finish reason. Any initial review by this assistant is labeled **agent-reviewed,
not independent or blinded**. Do not convert three toy questions into a statistically meaningful ranking.

## Next evaluation

Before changing jev-mem's production behavior: freeze configuration, gather independently written questions across
at least 3 repos, include code-only/document-only/memory-only evidence controls, label uncertain gold, add negative
queries, and test cold-start and continuation tasks in isolated checkouts. Hold the reader and context budget fixed.
For actual coding tasks, grade tests/patches, repeated exploration, wrong/stale instructions, wall time, cost, and
memory maintenance. Keep task data split by repository/session to avoid near-duplicate leakage.
