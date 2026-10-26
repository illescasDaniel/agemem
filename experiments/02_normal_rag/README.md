# Ordinary RAG

Hypothesis: good retrieval over original sources is competitive without a memory mutation engine.

- `bm25`: local lexical ranking of source-preserving windows.
- `dense`: BAAI/bge-small-en-v1.5 cosine search.
- `hybrid`: reciprocal-rank fusion of lexical and dense search.
- `dense-rerank`: 128 dense candidates, local Xenova/ms-marco-MiniLM-L-6-v2 cross-encoder, top 15.

```bash
python -m amem_lab.cli run --experiment experiments/02_normal_rag/experiment.json
```

No API key. Dense/rerank models download on first use. Windows are document-local, 160 regex units with 24 overlap;
these are not tokenizer tokens. Use the same final host agent to read evidence. The code implements ordinary RAG;
it is intentionally separate from the upstream RAW-RAG adapter so we can compare both representations.
