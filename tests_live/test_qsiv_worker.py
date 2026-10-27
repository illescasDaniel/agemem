"""Isolated runtime transport contracts; no model weights or GPU needed."""
import os
import io
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agemem.deciders import _LegacyQSIVWorker as QSIVWorker
from agemem.notes.decider import DeciderUnavailable


@unittest.skipIf(os.name == "nt", "POSIX executable shim for the Linux-only QSIV runtime")
class WorkerTests(unittest.TestCase):
    def launcher(self, folder, body):
        path = Path(folder) / 'python'
        path.write_text(f'#!{sys.executable}\n'+body)
        path.chmod(0o700)
        return path

    def test_keeps_process_and_excludes_hosted_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = self.launcher(folder, '''import json,os,sys
print(json.dumps({'ready':True}),flush=True)
for line in sys.stdin:
    request=json.loads(line)
    print(json.dumps({'answers':[{'p_true':.9,'pid':os.getpid(),
        'secret_present':'JEV_API_KEY' in os.environ,
        'offline':os.environ.get('HF_HUB_OFFLINE') }]}),flush=True)
''')
            with patch.dict(os.environ, {'JEV_API_KEY':'test-secret'}):
                worker = QSIVWorker(executable, folder, 'fp8', timeout=5)
            try:
                first, second = worker.decide({})[0], worker.decide({})[0]
                self.assertEqual(first['pid'], second['pid'])
                self.assertFalse(first['secret_present'])
                self.assertEqual(first['offline'], '1')
            finally:
                worker.close()
            self.assertIsNotNone(worker.process.poll())

    def test_startup_failure_and_invalid_response_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            executable = self.launcher(folder, "print('{\"error\":\"failed\"}',flush=True)\n")
            with self.assertRaises(DeciderUnavailable):
                QSIVWorker(executable, folder, 'fp8', timeout=5)
            executable = self.launcher(folder, '''import sys
print('{"ready":true}',flush=True)
for line in sys.stdin:
    print('invalid-json',flush=True)
''')
            worker = QSIVWorker(executable, folder, 'fp8', timeout=5)
            with self.assertRaises(DeciderUnavailable):
                worker.decide({})
            self.assertIsNotNone(worker.process.poll())

    def test_worker_emits_inference_traceback_to_stderr(self):
        from agemem.qsiv_worker import main
        class Broken:
            def decide(self, request):
                raise RuntimeError('GPU diagnostic example')
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch('agemem.deciders.QSIVDecider.load', return_value=Broken()), patch.object(sys, 'argv', ['worker', 'model', 'fp8']), patch.object(sys, 'stdin', io.StringIO('{}\n')), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            main()
        lines = stdout.getvalue().splitlines()
        self.assertTrue(json.loads(lines[0])['ready'])
        self.assertIn('error', json.loads(lines[1]))
        self.assertIn('RuntimeError: GPU diagnostic example', stderr.getvalue())
