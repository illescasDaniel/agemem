"""Time published UltraBERT System One requests over the decision probe.

Set MODEL to a local model directory, add its jev_api.py to PYTHONPATH, and
install its documented dependencies. Run once per device on an idle machine.
"""
import argparse
import importlib
import json
import os
import platform
import statistics
import time
from pathlib import Path

import torch
from scripts.decision_benchmark import cases


def percentile(values, p):
    values = sorted(values)
    pos = (len(values) - 1) * p
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', choices=['cpu', 'cuda'], required=True)
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.threads < 1 or args.repeats < 1:
        parser.error('threads and repeats must be positive')
    if args.device == 'cuda' and not torch.cuda.is_available():
        parser.error('CUDA is unavailable; refusing to silently benchmark CPU')
    if args.device == 'cpu':
        os.environ['CUDA_VISIBLE_DEVICES'] = ''
    torch.set_num_threads(args.threads)
    t = time.perf_counter()
    api = importlib.import_module('jev_api')
    if (api.DEVICE.startswith('cuda')) != (args.device == 'cuda'):
        raise RuntimeError(f'Unexpected model device: {api.DEVICE}')
    load = time.perf_counter() - t
    requests = []
    for name, state, questions, gold in cases(True):
        schema = {key: {'type': 'choice' if hasattr(q, 'criteria') else 'noul',
                        'instructions': q.instructions,
                        **({'criteria': q.criteria} if hasattr(q, 'criteria') else {})}
                  for key, q in questions.items()}
        requests.append((name, state, schema, gold))
    def sync():
        if args.device == 'cuda':
            torch.cuda.synchronize()
    # One complete untimed pass warms up tokenization and model kernels.
    for _, state, schema, _ in requests:
        api.system_one(state, schema)
    sync()
    rows = []
    for run in range(args.repeats):
        for name, state, schema, gold in requests:
            sync()
            start = time.perf_counter()
            response = api.system_one(state, schema)
            sync()
            elapsed = time.perf_counter() - start
            correct = 0
            for key, expected in gold.items():
                a = response['answers'][key]
                prediction = a['choice'] if isinstance(expected, str) else a['noul'] >= expected[1]
                correct += prediction == (expected if isinstance(expected, str) else expected[0])
            rows.append({'run': run + 1, 'case': name, 'questions': len(gold),
                         'seconds': elapsed, 'correct': correct,
                         'input_tokens': response['usage']['input_tokens']})
            print(f'{run + 1}/{args.repeats} {name} {elapsed:.3f}s', flush=True)
    times = [row['seconds'] for row in rows]
    result = {'model': 'davanstrien/ultrabert-380m-curation',
              'revision': 'c6a1fa055d36aeb3349b9a54537a5bc3f585d77d',
              'device': api.DEVICE, 'device_name': torch.cuda.get_device_name() if args.device == 'cuda' else platform.processor(),
              'dtype': str(api.DTYPE), 'threads': args.threads, 'torch': torch.__version__,
              'python': platform.python_version(), 'repeats': args.repeats,
              'warmup': 'one complete suite', 'load_seconds': load,
              'timing_scope': 'system_one in-process call, includes rendering, tokenization, inference and response construction; excludes load and network',
              'request_count': len(times), 'question_count': sum(row['questions'] for row in rows),
              'median_request_seconds': statistics.median(times), 'mean_request_seconds': statistics.mean(times),
              'p95_request_seconds': percentile(times, .95),
              'seconds_per_suite': [sum(row['seconds'] for row in rows if row['run'] == n) for n in range(1, args.repeats + 1)],
              'correct_per_suite': [sum(row['correct'] for row in rows if row['run'] == n) for n in range(1, args.repeats + 1)],
              'rows': rows}
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
