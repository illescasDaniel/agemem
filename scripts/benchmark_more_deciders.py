"""Benchmark Laya or Strands on the existing synthetic decision suite.

Provide locally downloaded model files and the model's published dependencies.
"""
import argparse
import json
import os
import platform
import statistics
import time
from pathlib import Path

import torch
from scripts.decision_benchmark import cases
from scripts.time_ultrabert import percentile


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--model', choices=['laya', 'strands', 'hobson', 'deberta', 'vega', 'openjev2b'], required=True)
    p.add_argument('--model-dir', required=True)
    p.add_argument('--device', choices=['cpu', 'cuda'], required=True)
    p.add_argument('--threads', type=int, default=8)
    p.add_argument('--repeats', type=int, default=5)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.threads < 1 or args.repeats < 1:
        p.error('threads and repeats must be positive')
    if args.device == 'cuda' and not torch.cuda.is_available():
        p.error('CUDA unavailable')
    if args.device == 'cpu':
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    torch.set_num_threads(args.threads)
    t = time.perf_counter()
    if args.model == 'laya':
        import laya
        model = laya.load(args.model_dir, device=args.device, backend='eager')
        def ask(state, schema):
            return model.predict(state, schema)
        revision = 'e929ae5cf69bc34259cd2f95c9e91145b818b1f0'
    elif args.model == 'deberta':
        from typed_decisions.open_jev import OpenJev
        model = OpenJev.from_pretrained(args.model_dir, device=args.device)
        def ask(state, schema):
            # DeBERTa's published interface requires a text state and a 512-token
            # total budget. Split whole questions only when necessary.
            text = json.dumps(state, ensure_ascii=False)
            names = list(schema)
            source = []
            for q in schema.values():
                item = {'type': q['type'], 'instructions': q['instructions']}
                if q['type'] == 'choice':
                    item['options'] = list(q['criteria'].values())
                source.append(item)
            batches, current = [], []
            for item in source:
                trial = current + [item]
                try:
                    model.collator.encode_one(text, [model._question(i, q) for i, q in enumerate(trial)])
                except ValueError:
                    if not current:
                        raise
                    batches.append(current)
                    current = [item]
                else:
                    current = trial
            if current:
                batches.append(current)
            raw = [a for batch in batches for a in model.decide(text, batch)]
            out = {}
            for name, item, answer in zip(names, source, raw):
                if item['type'] == 'choice':
                    keys = list(schema[name]['criteria'])
                    answer['choice'] = keys[item['options'].index(answer['choice'])]
                out[name] = answer
            return {'answers': out, 'usage': {'physical_calls': len(batches),
                    'state_truncated': len(model.collator._ids(text)) > model.collator.max_state}}
        revision = '188ee67a5c93122b916e5acd5bdb0cb3623e380a'
    elif args.model == 'vega':
        from vega_api import Vega
        model = Vega(args.model_dir, backbone=os.environ['BENCHMARK_BASE_MODEL'], device=args.device)
        def ask(state, schema):
            typed = {k: {**q, 'type': 'boolean' if q['type'] == 'noul' else q['type']}
                     for k, q in schema.items()}
            result = model.decide(state, typed)
            for answer in result['answers'].values():
                if 'boolean' in answer:
                    answer['noul'] = answer['boolean']
            return result
        revision = '42ac8d4fa9efb61f96e53d80962cf28f6dfe667e'
    elif args.model == 'openjev2b':
        from jev.serving import load_predictor
        model = load_predictor(checkpoint=args.model_dir, device='cuda:0' if args.device == 'cuda' else 'cpu',
                               batch_size=1, prefix_cache=False)
        def ask(state, schema):
            return model.predict({'state': state, 'questions': schema})
        revision = '0c7aa498b1627be8da4acf34c863ff0ee0a92785'
    else:
        from strands_decider.infer import load_engine
        model = load_engine(args.model_dir, device=args.device)
        def ask(state, schema):
            return model.ask(state, schema).model_dump()
        revision = ('bb282d786bc251fd4e3068de3ada9ddbb38127cd' if args.model == 'hobson'
                    else '216d1ccb46a9e9b036eb9187b248db98480f77d4')
    load_seconds = time.perf_counter() - t
    requests = []
    for name, state, questions, gold in cases(True):
        schema = {k: {'type': 'choice' if hasattr(q, 'criteria') else 'noul',
                      'instructions': q.instructions,
                      **({'criteria': q.criteria} if hasattr(q, 'criteria') else {})}
                  for k, q in questions.items()}
        requests.append((name, state, schema, gold))
    def sync():
        if args.device == 'cuda':
            torch.cuda.synchronize()
    for _, state, schema, _ in requests:
        ask(state, schema)
    sync()
    rows, predictions = [], []
    for run in range(args.repeats):
        for name, state, schema, gold in requests:
            sync()
            t = time.perf_counter()
            response = ask(state, schema)
            sync()
            elapsed = time.perf_counter() - t
            correct = 0
            for key, expected in gold.items():
                answer = response['answers'][key]
                prob = None if isinstance(expected, str) else answer['noul']
                prediction = answer['choice'] if isinstance(expected, str) else prob >= expected[1]
                good = prediction == (expected if isinstance(expected, str) else expected[0])
                correct += good
                if run == 0:
                    predictions.append({'case': name, 'question_key': key, 'prediction': prediction,
                                        'p': prob, 'expected': expected, 'correct': good, 'answer': answer})
            rows.append({'run': run + 1, 'case': name, 'seconds': elapsed,
                         'questions': len(gold), 'correct': correct, 'usage': response.get('usage')})
            print(f'{run + 1}/{args.repeats} {name} {elapsed:.3f}s', flush=True)
    times = [row['seconds'] for row in rows]
    result = {'model': args.model, 'revision': revision, 'device': args.device,
              'device_name': torch.cuda.get_device_name() if args.device == 'cuda' else platform.processor(),
              'threads': args.threads, 'torch': torch.__version__, 'repeats': args.repeats,
              'dtype_override': os.environ.get('JEV_TORCH_DTYPE') if args.model == 'openjev2b' else None,
              'load_seconds': load_seconds, 'warmup': 'one complete suite',
              'timing_scope': 'in-process request including rendering, tokenization, inference and response construction; excludes load and network',
              'request_count': len(times), 'question_count': sum(r['questions'] for r in rows),
              'median_request_seconds': statistics.median(times), 'mean_request_seconds': statistics.mean(times),
              'p95_request_seconds': percentile(times, .95),
              'seconds_per_suite': [sum(r['seconds'] for r in rows if r['run'] == n) for n in range(1,args.repeats+1)],
              'correct_per_suite': [sum(r['correct'] for r in rows if r['run'] == n) for n in range(1,args.repeats+1)],
              'predictions': predictions, 'rows': rows}
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','predictions')}))


if __name__ == '__main__':
    main()
