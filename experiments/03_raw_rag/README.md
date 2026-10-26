# Reuse actual RAW-RAG

Hypothesis: preserve original evidence and use the authors' tested chunk/search/selection code, rather than rebuild it.

```bash
python scripts/fetch_upstreams.py
python -m amem_lab.cli run --experiment experiments/03_raw_rag/experiment.json
```

`amem_lab.integrations.UpstreamRaw` subclasses the actual pinned `RAGAdapter`. Only embedding and reranking provider I/O
is overridden for local BGE + MiniLM. Tokenization, stream chunking, indexing, dense candidate retrieval, rerank-result
validation, selection and turn provenance execute upstream code. No copy of their retrieval algorithm is maintained here.
Native window settings: 256 tokenizer tokens, 32 overlap, 128 candidates, 15 selected. Source messages are records rather
than real conversational turns, a declared adaptation for coding artifacts. Display expansion is off; scoring inspects
selected window text. The common context packer caps what the final reader sees.

This is not a paper-score reproduction: model providers and corpus differ. The constructor creates unused API clients;
provider placeholders are explicitly unused and the answer method is never called. It fails if tokenizer setup silently
falls back to words. No live API key is needed for this local-provider variant.

Upstream: https://github.com/Litmeb/RAW-RAG
Pinned: 95639191e9547219b426710e50fe1a36235e26fc
