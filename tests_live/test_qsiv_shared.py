"""Exercise shared startup and inference without requiring a GPU."""
import concurrent.futures
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from agemem.notes.decider import DeciderUnavailable
from agemem.qsiv_shared import QSIVWorker


@unittest.skipUnless(sys.platform.startswith('linux'), 'QSIV shared service requires Linux')
class SharedServiceTests(unittest.TestCase):
    def test_concurrent_clients_share_service_and_it_exits_when_idle(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            root = Path(folder)
            launcher = root / 'python'
            launcher.write_text(f'''#!{sys.executable}
import os, sys, time
from pathlib import Path
import agemem.qsiv_shared as shared
shared._directory = lambda: Path({folder!r})
class Model:
    def decide(self, request):
        time.sleep(.03)
        return [{{'pid': os.getpid(), 'request': request}}]
shared.serve(sys.argv[3:6], loader=Model, idle_seconds=1)
''')
            launcher.chmod(0o700)
            with patch('agemem.qsiv_shared._directory', return_value=root):
                def connect(_):
                    return QSIVWorker(launcher, root, 'fp8', timeout=5)
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    workers = list(pool.map(connect, range(4)))
                    try:
                        results = list(pool.map(lambda pair: pair[1].decide({'id': pair[0]})[0], enumerate(workers)))
                        self.assertEqual(len({r['pid'] for r in results}), 1)
                        self.assertEqual([r['request']['id'] for r in results], list(range(4)))
                        with self.assertRaises(DeciderUnavailable) as error:
                            QSIVWorker(launcher, root, 'reference', timeout=5)
                        self.assertEqual(error.exception.diagnostic['cause'], 'model_in_use')
                    finally:
                        for worker in workers:
                            worker.close()
                deadline = time.monotonic() + 4
                while time.monotonic() < deadline:
                    try:
                        os.kill(results[0]['pid'], 0)
                    except ProcessLookupError:
                        break
                    # A child may remain a zombie until Popen's cleanup reaps it.
                    stat = Path(f"/proc/{results[0]['pid']}/stat")
                    if stat.exists() and stat.read_text().split()[2] == 'Z':
                        break
                    time.sleep(.05)
                else:
                    self.fail('Shared QSIV service did not exit after disconnect')

    def test_idle_service_exits_while_connected_and_restarts_on_next_request(self):
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            root = Path(folder)
            launcher = root / 'python'
            launcher.write_text(f'''#!{sys.executable}
import os, sys
from pathlib import Path
import agemem.qsiv_shared as shared
shared._directory = lambda: Path({folder!r})
class Model:
    def decide(self, request):
        return [{{'pid': os.getpid()}}]
shared.serve(sys.argv[3:6], loader=Model, idle_seconds=.5)
''')
            launcher.chmod(0o700)
            with patch('agemem.qsiv_shared._directory', return_value=root):
                worker = QSIVWorker(launcher, root, 'fp8', timeout=5)
                try:
                    first = worker.decide({})[0]['pid']
                    time.sleep(1.5)
                    second = worker.decide({})[0]['pid']
                    self.assertNotEqual(first, second)
                finally:
                    worker.close()
