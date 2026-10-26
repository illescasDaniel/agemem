"""Production QSIV is GPU-only; research CPU helpers never become a fallback."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from agemem.deciders import QSIVDecider
from agemem.notes.decider import DeciderUnavailable


class GpuGateTests(unittest.TestCase):
    def test_cpu_or_incompatible_gpu_fails_before_qsiv_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('config.json','calibration.json','tokenizer'):
                (root/name).touch()
            for available,capability in ((False,(0,0)),(True,(8,6))):
                cuda=SimpleNamespace(is_available=lambda:available,get_device_capability=lambda:capability)
                with patch.dict('sys.modules', {'torch':SimpleNamespace(cuda=cuda)}):
                    with self.assertRaisesRegex(DeciderUnavailable,'select Jev'):
                        QSIVDecider.load(root,'fp8')
