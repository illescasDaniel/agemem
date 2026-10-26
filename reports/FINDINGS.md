# Initial findings — 2026-10-26

**The most promising direction is a small git memory bank plus source-preserving retrieval. Keep jev-mem as an
optional controller/concise-note layer, and test Tencent as a standalone alternative hub.** This is a direction for
the next experiment, not proof of a production winner.

The workspace contains six separate experiment designs, actual runnable adapters, saved source evidence and results,
and a shared evaluation harness. Original jev-mem and srxy files/settings were not modified. Temporary services were
stopped after tests. No hooks or global memory integrations were installed.

## Evidence retrieval on the same 18 questions

There are 16 answerable questions and 2 unknowns; 12 questions use a committed srxy snapshot and 6 use controlled Atlas
history. All configurations use an 1,800-regex-unit context cap. Scores check annotated passages in the actual packed
context, not final answers. Questions and annotations are author-written and exploratory.

| Read/retrieval policy | Annotated evidence coverage | All annotated evidence present |
|---|---:|---:|
| Current memory-bank files | 18.8% | 18.8% |
| Search memory-bank history | 43.8% | 43.8% |
| Ordinary BM25 retrieval | 81.3% | 81.3% |
| Ordinary dense retrieval (BGE) | 78.1% | 75.0% |
| Dense + MiniLM reranker | 87.5% | 87.5% |
| Lexical + dense RRF | 93.8% | 93.8% |
| Actual RAW-RAG adapter, local providers | 100% | 100% |
| Local state + synthetic notes + BM25 | 81.3% | 81.3% |
| Actual Tencent L0 keyword search | 93.8% | 93.8% |

Read these cautiously. Bank files are intended for state/handoffs, not to cover all code/document questions. Gold is
not exhaustive: for example, current state repeats the QUrl fix, so a reader can answer correctly without retrieving
the particular decision entry annotated as gold. Consequently these are **annotated-source coverage scores**, not
memory usefulness or answer accuracy. The generous context relative to this small corpus also helps all RAG variants.

The ordinary RAG and RAW-RAG variants use the same local BGE-small/MiniLM models where applicable. Their chunking and
stream representation differ; RAW-RAG's 100% cannot be attributed to an isolated algorithm change. Its actual upstream
code is reused, not a homegrown approximation; only model-provider calls are replaced. This is not a reproduction of
the paper's models or published benchmark scores.

Timings include first-use builds/model loading and shared caches. They are not valid steady-state latency rankings.
Local model warmup/indexing took tens of seconds, and CPU cross-encoder reranking was materially slower than BM25/RRF.

## Real jev-mem and the composition pilot

The separate paid Jev run used five controlled queries (four answerable and one unknown), 28 actual calls and 22,907
input tokens. No synthetic classifier or degraded fallback was scored. This is a bounded profile (small graph/call
limits), not an evaluation of stock defaults over the complete srxy corpus.

| Policy, same five-query subset | Annotated evidence coverage | Mean context units |
|---|---:|---:|
| Current bank | 25.0% | 30 |
| BM25 | 100% | 130 |
| Lexical + dense RRF | 100% | 173 |
| Actual RAW-RAG adapter | 100% | 228 |
| Real jev-mem, bounded pilot | 62.5% | 51 |
| Bank + cached Jev + cached RAW-RAG | 100% | 309 |

Observed behaviors:

- Jev rejected the current handoff/blocker note as work status, as its design intends. A bank or another state owner
  is needed for that information; it should not be "fixed" by weakening status rejection.
- It rejected the quoted synthetic injection. One example does not establish screen robustness.
- It found old and new deployment evidence and marked the unknown question insufficient.
- It returned only one of the two annotated rename/causal links while reporting sufficient. This is a concrete
  failure case for future sufficiency and alias-retrieval work.
- Adding current bank state and source evidence recovered the missing context without any new model calls. That
  result comes from **cached replay**, not an implemented live router or an established latency/cost advantage.

Do not rank the five-query Jev pilot against the full 18-question table. The case supports testing complementarity;
it does not establish whether Jev's context savings justify its control calls in actual coding sessions.

## Final-answer pilot

The same GPT-4.1 mini snapshot read three synthetic questions across six methods (18 answers). An initial context-only
run is preserved separately; it omitted Jev's sufficiency signal. The corrected run includes the actual signal using
the same prompt for every method. Both are exploratory, and review below is by this assistant, not a blinded grader.

The bank correctly supplied the handoff but could not explain the historical rename chain. BM25, hybrid retrieval,
RAW-RAG and the combined replay supplied enough evidence for the reader to answer the handoff and rename-chain cases.
All methods' readers recognized the unknown phone number as unknown. With the bounded Jev context, the reader gave
the right causal sentence for tally but omitted the missing alias justification and citations. On the handoff query
it invented a migration blocker from unrelated deployment/settlement facts, **even when told retrieval was insufficient**.
Therefore an insufficient signal should trigger source lookup or a caller-enforced response policy; merely including
the probability/boolean in a prompt does not guarantee the reader will honor it.

After explicit user egress approval, a second small pilot uses only the two approved srxy questions: KDE QUrl decoding
and the next 1.8.0 validation step, across bank/BM25/hybrid/RAW-RAG contexts. The reader identifies the main QUrl fix and
native Windows/macOS review. Several responses hit the 220-output-token cap, and some infer that follow-ups are
"after release" although the source does not establish that schedule. These are examples of reader behavior beyond
passage retrieval, not an accuracy leaderboard. Raw answers, finish reasons and usage are saved.

## Tencent: what actually works here

**MemoryCore is usable standalone.** Node 24.15 + SQLite/FTS5 ran locally; no Docker, Tencent Cloud account, remote vector
database, panel or proxy was needed for this test. Installation still pulled 621 npm packages. Runtime configuration,
storage directories, HTTP auth headers and asynchronous extraction timing require setup, so this is not simply an
agent skill copied into a repo.

The L0 adapter captured the same visible evidence and searched real v3 endpoints, with extraction disabled. FTS5 was
confirmed through health. No paid model was involved in that table's Tencent result. This evaluates the L0 keyword
API, not the full L1/L2/L3 memory stack or its proxy-driven recall behavior.

Separately, one synthetic three-message session triggered real L1 extraction through a bounded local gateway. One
OpenAI call (1,598 input, 339 output tokens) produced two memories: the original Fabric deployment and the Ansible
replacement with its reason. Search for "Atlas" found the first; search for "Ansible" found the second, which omitted
the project name. Thus retaining both facts did not guarantee a single project-name query would retrieve both.
No expensive extraction of the srxy corpus was run. L2/L3, skill generation, Wiki, CodeGraph, ACLs and proxy behavior
remain untested.

Tencent's checked-in configuration already supports `memory.persona.triggerMode: jev`, a native Jev control gate for
refreshing persona memory after L2 updates. It still needs a generative LLM for extraction/synthesis. Test that existing
gate before designing a second equivalent bridge. It does not embed this project's jev-mem implementation.

## Recommended next decision

1. Start an actual coding-session pilot with **memory-bank + hybrid source retrieval**: low complexity and strong
   coverage in this fixture. Keep facts traceable to committed docs/messages and current state in git.
2. Keep **the reused RAW-RAG adapter** as a reference and optional backend. Test whether its extra reranking cost and
   representation advantage persist on larger, independently authored multi-repo tasks.
3. Test **bank + Jev + source lookup** against that reference. Measure correct patches, repeated exploration, context
   tokens and actual spend. Use full jev-mem defaults in a separately budgeted run before changing its behavior.
4. Treat **Tencent as a parallel product choice**, particularly for shared/team asset management. First try it alongside
   the bank. Avoid syncing derived truth or running multiple injectors until ownership and deletion rules are explicit.

No production changes to jev-mem are justified by this pilot alone. The useful immediate artifacts are the runnable
comparisons, concrete failure cases, and evidence that direct upstream reuse and standalone Tencent are feasible.

## Files and reproducibility

- `lexical.json`, `semantic.json`, `normal-rag-rerank.json`, `raw-upstream.json`: local retrieval runs.
- `jev-pilot.json`, `composed-pilot.json`: bounded real Jev and cached composition.
- `tencent-l0.json`, `tencent-extraction-smoke.json`, `tencent-extraction-usage.json`: actual Tencent tests.
- `reader-pilot.json`: initial synthetic context-only ablation.
- `reader-with-signals.json`: corrected synthetic reader test.
- `srxy-reader-pilot.json` and `srxy-reader-final-packet.json`: scoped user-approved source-data reader test.
- `reader-review.json`: agent review with limitations; `usage-summary.json`: aggregate measured usage/cost estimates.
- `initial-tokenizer-failure.json`: original failed upstream attempt, preserved. Tokenizer caching fixed the environment;
  no word-chunk fallback was used in the successful run.
- `environment.json`: actual package versions. Dataset manifest pins upstream and source commits.

Sources: [RAW-RAG](https://github.com/Litmeb/RAW-RAG),
[Tencent MemoryCore](https://github.com/TencentCloud/TencentDB-Agent-Memory/tree/65730e979a5a590c54adc181ba8a375055410b84/MemoryCore),
[Tencent standalone configuration including Jev](https://github.com/TencentCloud/TencentDB-Agent-Memory/blob/65730e979a5a590c54adc181ba8a375055410b84/MemoryCore/tdai-gateway.standalone.yaml),
[OpenAI reader pricing](https://developers.openai.com/api/docs/models/gpt-4.1-mini).
