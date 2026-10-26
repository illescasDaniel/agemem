# Attribution and third-party material

Agemem builds on the following projects and services. Source-code licenses,
model licenses and hosted-service terms apply separately.

## jev-mem

Selected code in `agemem/notes/` is adapted from
[jev-mem](https://github.com/illescasDaniel/jev-mem) 0.4.0, copyright 2026
Daniel Illescas Romero, under the MIT License. The complete copyright and
permission notice is bundled in [LICENSE.jevmem](agemem/notes/LICENSE.jevmem).
[UPSTREAM.json](agemem/notes/UPSTREAM.json) records original file hashes and
adaptations.

The SQLite store, policy prompts, screening, retrieval, consolidation and
matrix index are retained. The upstream hosted client, global settings, hooks
and remote index backends are excluded. Agemem's live MCP uses this internal
adaptation; the external jev-mem package is optional for database compatibility tests only.

## RAW-RAG

[RAW-RAG](https://github.com/Litmeb/RAW-RAG), copyright 2026 RAW-RAG
contributors, supplies the overlapping token-window and dense candidate /
reranking pipeline adapted in [agemem/raw_rag.py](agemem/raw_rag.py). The full
MIT notice is bundled in [LICENSE.raw-rag](agemem/LICENSE.raw-rag).
[RAW_RAG_ATTRIBUTION.md](agemem/RAW_RAG_ATTRIBUTION.md) records the pinned
revision `95639191e9547219b426710e50fe1a36235e26fc`, reference-file hash and
changes.

The live implementation uses local BGE embeddings and MiniLM reranking, with
Agemem's source provenance and scope filtering. It omits upstream answer
generation and remote model clients. This is an adaptation, not a reproduction
of RAW-RAG's full method or published results. It does not require a RAW-RAG
checkout.

## QSIV

[QSIV](https://huggingface.co/djinn-san/QSIV), copyright 2026 the QSIV authors,
is an optional local decision runtime and model. Setup fetches revision
`f1ee842daf758c0ab535cf7d281c85439d6e4b25`; the full runtime and its weights are not bundled in the Agemem package. The downloaded model directory
retains its complete Apache-2.0
[LICENSE](https://huggingface.co/djinn-san/QSIV/blob/f1ee842daf758c0ab535cf7d281c85439d6e4b25/LICENSE)
and [NOTICE](https://huggingface.co/djinn-san/QSIV/blob/f1ee842daf758c0ab535cf7d281c85439d6e4b25/NOTICE).

QSIV's NOTICE credits the Qwen team / Alibaba Cloud for Qwen3.5-0.8B-Base and
its tokenizer, as well as the Gated DeltaNet and flash-linear-attention work.
Those notices and dependency licenses remain applicable. Our installer changes
only the downloaded runtime's NumPy dependency pin to match the tested
environment; it does not change QSIV inference code or weights.

## Jev and TypeSafe AI

[Jev / TypeSafe AI](https://typesafe.ai) provides the default hosted decision
service, accessed through the
[TypeSafe Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python).
Agemem includes its own provider adapter and depends on the SDK as a separately
installed package, which retains its own MIT license. It does not copy or
redistribute Jev model weights or the hosted service's implementation.
Hosted API terms and metering apply when that provider is explicitly used;
no credentials are included in this repository.

## Other material

The [memory-bank](https://github.com/illescasDaniel/memory-bank) project is a
design reference; this workspace does not install a copy of its skill.


Embedding and reranking weights download separately through FastEmbed and
retain their respective model licenses. Other installed dependencies retain
their own licenses; the notices above do not relicense those dependencies.
