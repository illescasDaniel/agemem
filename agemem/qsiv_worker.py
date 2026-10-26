"""Private JSON-lines transport for the isolated native QSIV environment."""
import contextlib
import json
import sys


def main():
    # Native libraries may print diagnostics; stdout belongs to this protocol.
    from .deciders import QSIVDecider
    try:
        with contextlib.redirect_stdout(sys.stderr):
            decider = QSIVDecider.load(sys.argv[1], sys.argv[2])
        print(json.dumps({'ready': True}), flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with contextlib.redirect_stdout(sys.stderr):
                    result = decider.decide(request)
                print(json.dumps({'answers': result}), flush=True)
            except Exception:
                print(json.dumps({'error': 'Local QSIV inference failed'}), flush=True)
    except Exception:
        print(json.dumps({'error': 'Local QSIV startup failed; run agemem doctor'}), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
