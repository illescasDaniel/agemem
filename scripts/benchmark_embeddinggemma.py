"""Compare a local typed-decision model with the existing synthetic decision probe."""
import argparse
import json
import time
from pathlib import Path

import torch
from transformers import AutoModel

from scripts.decision_benchmark import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    torch.set_num_threads(min(8, torch.get_num_threads()))
    started = time.perf_counter()
    model = AutoModel.from_pretrained(args.model_dir, trust_remote_code=True, local_files_only=True).eval()
    result = {'model': 'mrm8488/embeddinggemma-2-ft-typed-decision',
              'revision': '8403ff7fddc75b6994130e581a832f875fb5bd0e',
              'device': 'cpu', 'dtype': 'float32', 'suite': 'expanded',
              'scope': 'Author-labeled synthetic typed decisions; not a coding effectiveness benchmark',
              'model_load_seconds': time.perf_counter() - started, 'rows': []}
    for name, state, questions, gold in cases(True):
        schema = {k: {'type': 'choice' if hasattr(q, 'criteria') else 'noul',
                      'instructions': q.instructions, **({'criteria': q.criteria} if hasattr(q, 'criteria') else {})}
                  for k, q in questions.items()}
        t = time.perf_counter()
        with torch.inference_mode():
            answers = model.decide(state, schema)
        elapsed = time.perf_counter() - t
        for key, expected in gold.items():
            answer = answers[key]
            p = None if isinstance(expected, str) else answer.probabilities['true']
            prediction = answer.value if isinstance(expected, str) else p >= expected[1]
            result['rows'].append({'case': name, 'question_key': key, 'prediction': prediction,
                                   'confidence': answer.confidence, 'p': p, 'expected': expected,
                                   'correct': prediction == (expected if isinstance(expected, str) else expected[0]),
                                   'request_seconds': elapsed})
        print(name, flush=True)
        Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    result.update(correct=sum(row['correct'] for row in result['rows']), total=len(result['rows']),
                  seconds_including_load=time.perf_counter() - started)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'rows'}))


if __name__ == '__main__':
    main()
