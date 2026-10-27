"""Private JSON-lines transport for the isolated native QSIV environment."""
import contextlib
import json
import sys
import traceback


def main():
    # Native libraries may print diagnostics; stdout belongs to this protocol.
    from .deciders import QSIVDecider
    try:
        with contextlib.redirect_stdout(sys.stderr):
            decider = QSIVDecider.load(sys.argv[1], sys.argv[2], _native=True)
        print(json.dumps({'ready': True}), flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line)
                with contextlib.redirect_stdout(sys.stderr):
                    result = decider.decide(request)
                print(json.dumps({'answers': result}), flush=True)
            except Exception:
                traceback.print_exc(file=sys.stderr)
                print(json.dumps({'error': 'Local QSIV inference failed'}), flush=True)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        diagnostic = getattr(exc, 'diagnostic', None)
        message = str(exc) if diagnostic and diagnostic.get('cause') == 'model_in_use' else 'Local QSIV startup failed; run agemem doctor'
        print(json.dumps({'error': message, 'diagnostic': diagnostic}), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
