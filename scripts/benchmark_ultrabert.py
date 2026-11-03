"""Run the published UltraBERT System One API on the synthetic decision probe.

Set MODEL to the local model directory and include its jev_api.py on PYTHONPATH.
"""
import argparse
import importlib
import json
import time
from pathlib import Path

import torch

from scripts.decision_benchmark import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    torch.set_num_threads(min(8, torch.get_num_threads()))
    start = time.perf_counter()
    api = importlib.import_module('jev_api')
    result = {'model': 'davanstrien/ultrabert-380m-curation',
              'revision': 'c6a1fa055d36aeb3349b9a54537a5bc3f585d77d',
              'device': api.DEVICE, 'dtype': str(api.DTYPE), 'suite': 'expanded',
              'scope': 'Author-labeled synthetic typed decisions; not a coding effectiveness benchmark',
              'model_load_seconds': time.perf_counter() - start, 'rows': []}
    for name, state, questions, gold in cases(True):
        schema = {key: {'type': 'choice' if hasattr(q, 'criteria') else 'noul',
                        'instructions': q.instructions,
                        **({'criteria': q.criteria} if hasattr(q, 'criteria') else {})}
                  for key, q in questions.items()}
        t = time.perf_counter()
        response = api.system_one(state, schema)
        elapsed = time.perf_counter() - t
        for key, expected in gold.items():
            answer = response['answers'][key]
            p = None if isinstance(expected, str) else answer['noul']
            prediction = answer['choice'] if isinstance(expected, str) else p >= expected[1]
            confidence = answer.get('confidence', max(p, 1 - p) if p is not None else None)
            result['rows'].append({'case': name, 'question_key': key, 'prediction': prediction,
                                   'confidence': confidence, 'p': p, 'expected': expected,
                                   'correct': prediction == (expected if isinstance(expected, str) else expected[0]),
                                   'request_seconds': elapsed})
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
        print(name, flush=True)
    result.update(correct=sum(row['correct'] for row in result['rows']), total=len(result['rows']),
                  seconds_including_load=time.perf_counter() - start)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
