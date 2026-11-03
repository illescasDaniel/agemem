"""Time QSIV request-response calls over the synthetic decision probe."""
import argparse
import json
import statistics
import time
from pathlib import Path

from agemem.deciders import QSIVDecider
from agemem.notes.decider import ChoiceQ, NoulQ
from scripts.decision_benchmark import cases
from scripts.time_ultrabert import percentile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir', required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('repeats must be positive')
    t = time.perf_counter()
    model = QSIVDecider.load(args.model_dir, python=args.python)
    load = time.perf_counter() - t
    requests = [(name, state, {k: ChoiceQ(q.instructions, q.criteria) if hasattr(q, 'criteria')
                               else NoulQ(q.instructions) for k, q in questions.items()}, gold)
                for name, state, questions, gold in cases(True)]
    for _, state, questions, _ in requests:
        model.ask(state, questions)
    rows = []
    for run in range(args.repeats):
        for name, state, questions, gold in requests:
            t = time.perf_counter()
            answers = model.ask(state, questions)
            elapsed = time.perf_counter() - t
            correct = sum((answers[key].choice if isinstance(expected, str) else answers[key].p >= expected[1])
                          == (expected if isinstance(expected, str) else expected[0]) for key, expected in gold.items())
            rows.append({'run': run + 1, 'case': name, 'questions': len(gold), 'seconds': elapsed, 'correct': correct})
    times = [row['seconds'] for row in rows]
    result = {'model': 'djinn-san/QSIV', 'runtime': 'fp8', 'repeats': args.repeats,
              'warmup': 'one complete suite, including lazy worker startup', 'client_init_seconds': load,
              'timing_scope': 'QSIVDecider.ask in-process caller, including worker transport and inference; excludes load and network',
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
