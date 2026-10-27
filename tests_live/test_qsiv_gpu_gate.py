"""Production QSIV is GPU-only; research CPU helpers never become a fallback."""
import tempfile
import os
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agemem.deciders import QSIVDecider, _lock_qsiv_model
from agemem.notes.decider import DeciderUnavailable


class GpuGateTests(unittest.TestCase):
    @unittest.skipIf(os.name != 'posix', 'QSIV GPU runtime is Linux-only')
    def test_model_slot_is_exclusive_across_processes_and_released_on_exit(self):
        child = subprocess.Popen([sys.executable, '-c',
            'import sys; from agemem.deciders import _lock_qsiv_model; _lock_qsiv_model(); print("ready", flush=True); sys.stdin.read()'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), 'ready')
            with self.assertRaises(DeciderUnavailable) as error:
                _lock_qsiv_model()
            self.assertEqual(error.exception.diagnostic['cause'], 'model_in_use')
        finally:
            child.stdin.close()
            child.wait(timeout=5)
            child.stdout.close()
        fd = _lock_qsiv_model()
        os.close(fd)

    def test_cpu_or_incompatible_gpu_fails_before_qsiv_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('config.json','calibration.json','tokenizer'):
                (root/name).touch()
            for available,capability in ((False,(0,0)),(True,(8,6))):
                cuda=SimpleNamespace(is_available=lambda:available,get_device_capability=lambda:capability)
                with patch.dict('sys.modules', {'torch':SimpleNamespace(cuda=cuda)}):
                    with self.assertRaisesRegex(DeciderUnavailable,'select Jev'):
                        QSIVDecider.load(root,'fp8', _native=True)
