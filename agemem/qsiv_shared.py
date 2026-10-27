"""One local QSIV model, shared by independent clients over a private socket."""
import atexit
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

from .notes.decider import DeciderUnavailable

try:
    import fcntl
except ImportError:  # Windows: callers fall back to a private worker.
    fcntl = None


def _directory():
    path = Path('/tmp') / f'agemem-qsiv-{os.getuid()}'
    path.mkdir(mode=0o700, exist_ok=True)
    if path.is_symlink() or path.stat().st_uid != os.getuid() or path.stat().st_mode & 0o077:
        raise DeciderUnavailable('Unsafe QSIV lock directory')
    return path


def _config(python, directory, runtime):
    # Do not resolve the Python symlink: its path selects the virtualenv.
    return [os.path.abspath(os.path.expanduser(str(python))), str(Path(directory).expanduser().resolve()), runtime]


def _exchange(stream, data):
    stream.write((json.dumps(data) + '\n').encode())
    stream.flush()
    line = stream.readline()
    if not line:
        raise OSError('QSIV service disconnected')
    return json.loads(line)


class QSIVWorker:
    """Attach to a shared model, starting it once if necessary."""
    def __init__(self, python, directory, runtime, timeout=120):
        self.timeout = timeout
        self.socket = self.stream = None
        self._mutex = threading.Lock()
        self._config = _config(python, directory, runtime)
        self._attach()

    def _attach(self):
        """Connect to the shared service, starting it under a lock if it is not running."""
        config, timeout = self._config, self.timeout
        root = _directory()
        path = root / 'service.sock'
        deadline = time.monotonic() + timeout
        fd = os.open(root / 'startup.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise DeciderUnavailable('Timed out waiting for QSIV startup') from None
                    time.sleep(.05)
            try:
                self._connect(path, config, max(.1, deadline - time.monotonic()))
            except (ConnectionRefusedError, FileNotFoundError):
                path.unlink(missing_ok=True)
                env = {k: v for k, v in os.environ.items()
                       if not any(word in k.upper() for word in ('API_KEY', 'TOKEN', 'SECRET'))}
                env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
                log_fd = os.open(root / 'service.log', os.O_CREAT | os.O_APPEND | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                try:
                    process = subprocess.Popen([config[0], '-m', 'agemem.qsiv_shared', *config],
                                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                               stderr=log_fd, env=env, start_new_session=True)
                finally:
                    os.close(log_fd)
                # Reap the detached service if this client remains alive after it exits.
                threading.Thread(target=process.wait, daemon=True).start()
                while True:
                    if process.poll() is not None:
                        raise DeciderUnavailable('QSIV service failed to start; see private service.log and run agemem doctor')
                    if time.monotonic() >= deadline:
                        process.terminate()
                        process.wait()
                        raise DeciderUnavailable('QSIV service startup timed out')
                    try:
                        self._connect(path, config, max(.1, deadline - time.monotonic()))
                        break
                    except (ConnectionRefusedError, FileNotFoundError):
                        time.sleep(.05)
        finally:
            os.close(fd)
        atexit.register(self.close)

    def _connect(self, path, config, timeout):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        try:
            sock.connect(str(path))
            stream = sock.makefile('rwb')
            response = _exchange(stream, {'config': config})
            if response.get('ready') is not True:
                stream.close()
                raise DeciderUnavailable(response.get('error', 'QSIV service unavailable'), response.get('diagnostic'))
            sock.settimeout(self.timeout)
            self.socket, self.stream = sock, stream
        except BaseException:
            sock.close()
            raise

    def decide(self, request):
        with self._mutex:
            try:
                try:
                    response = _exchange(self.stream, {'request': request})
                except (OSError, AttributeError):
                    # The service exited after being idle (or was never attached): start it again.
                    self.close()
                    self._attach()
                    response = _exchange(self.stream, {'request': request})
                if 'answers' not in response:
                    raise ValueError('QSIV inference failed')
                return response['answers']
            except DeciderUnavailable:
                self.close()
                raise
            except Exception:
                self.close()
                raise DeciderUnavailable('Local QSIV service failed; run agemem doctor') from None

    def close(self):
        atexit.unregister(self.close)
        if self.stream is not None:
            try:
                self.stream.close()
            except OSError:  # Flushing to a service that already exited.
                pass
            self.stream = None
        if self.socket is not None:
            self.socket.close()
            self.socket = None


def _idle_seconds():
    try:
        return float(os.environ['AGEMEM_QSIV_IDLE_SECONDS'])
    except (KeyError, ValueError):
        return 300.0


def serve(config, loader=None, idle_seconds=None):
    """Load once, serialize inference, and exit after `idle_seconds` without requests.

    Connected clients do not keep the model resident; they reattach on their next request."""
    if idle_seconds is None:
        idle_seconds = _idle_seconds()
    import contextlib
    import sys
    from .deciders import QSIVDecider
    root = _directory()
    with contextlib.redirect_stdout(sys.stderr):
        model = (loader or (lambda: QSIVDecider.load(config[1], config[2], _native=True)))()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(root / 'service.sock'))
    os.chmod(root / 'service.sock', 0o600)
    server.listen()
    server.settimeout(.2)
    inference = threading.Lock()
    state_lock = threading.Lock()
    clients = set()
    idle_since = time.monotonic()
    busy = 0

    def handle(conn):
        nonlocal idle_since, busy
        stream = None
        try:
            stream = conn.makefile('rwb')
            hello = json.loads(stream.readline())
            if hello.get('config') != config:
                stream.write((json.dumps({'error': 'A QSIV service with a different model or runtime is already running', 'diagnostic': {'stage': 'qsiv_startup', 'cause': 'model_in_use'}}) + '\n').encode())
                stream.flush()
                return
            stream.write(b'{"ready":true}\n')
            stream.flush()
            for line in stream:
                try:
                    request = json.loads(line)['request']
                    with state_lock:
                        busy += 1
                    try:
                        with inference, contextlib.redirect_stdout(sys.stderr):
                            result = model.decide(request)
                    finally:
                        with state_lock:
                            busy -= 1
                            idle_since = time.monotonic()
                    response = {'answers': result}
                except Exception:
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    response = {'error': 'Local QSIV inference failed'}
                stream.write((json.dumps(response) + '\n').encode())
                stream.flush()
        except (OSError, ValueError, KeyError):
            pass
        finally:
            if stream is not None:
                stream.close()
            conn.close()
            with state_lock:
                clients.discard(conn)

    try:
        while True:
            try:
                conn, _ = server.accept()
            except socket.timeout:
                with state_lock:
                    if not busy and time.monotonic() - idle_since >= idle_seconds:
                        break
                continue
            with state_lock:
                clients.add(conn)
                idle_since = time.monotonic()
            threading.Thread(target=handle, args=(conn,), daemon=True).start()
    finally:
        server.close()
        with state_lock:
            for conn in clients:
                with contextlib.suppress(OSError):
                    conn.shutdown(socket.SHUT_RDWR)


if __name__ == '__main__':
    import sys
    serve(sys.argv[1:4])
