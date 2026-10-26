"""Explicit download/warmup for RAW-RAG local providers; no paid API calls."""
import argparse
import json
import os
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache', type=Path, default=Path('.cache/embeddings'))
    p.add_argument('--tokenizer-cache', type=Path, default=Path('.cache/tiktoken'))
    args = p.parse_args()
    args.cache.mkdir(parents=True, exist_ok=True)
    args.tokenizer_cache.mkdir(parents=True, exist_ok=True)
    os.environ['TIKTOKEN_CACHE_DIR'] = str(args.tokenizer_cache.resolve())
    import tiktoken
    from fastembed import TextEmbedding
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    assert tiktoken.encoding_for_model('gpt-4').encode('local tokenizer probe')
    embedding = TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir=str(args.cache), threads=2)
    assert len(list(embedding.embed(['local embedding probe']))) == 1
    reranker = TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2', cache_dir=str(args.cache), threads=2)
    assert len(list(reranker.rerank('deployment tool', ['Deploy using Ansible.']))) == 1
    print(json.dumps({'status':'prepared', 'model_cache':str(args.cache.resolve()),
                      'tokenizer_cache':str(args.tokenizer_cache.resolve()), 'paid_api_calls':0}))


if __name__ == '__main__':
    main()
