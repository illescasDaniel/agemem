"""Provider setup plans and failure paths never need model downloads."""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import os
import tempfile
import unittest

from agemem import providers


def test_setup_dry_run_does_not_create_files(tmp_path):
    os.environ["XDG_DATA_HOME"] = str(tmp_path)
    with patch.object(providers.platform, "system", return_value="Linux"), \
         patch.object(providers.platform, "machine", return_value="x86_64"), \
         patch.object(providers, "_run") as run:
        result = providers.setup_qsiv(dry_run=True)
    run.assert_not_called()
    assert not list(tmp_path.iterdir())
    assert result["runtime_python"] == str(tmp_path / "agemem/runtimes/qsiv/bin/python")
    assert result["directory"] == str(tmp_path / "agemem/models/qsiv")
    assert not any("jevmem" in word for command in result["commands"] for word in command)
    json.dumps(result)


def test_setup_failure_never_writes_success_manifest(tmp_path):
    model, runtime = tmp_path / "model", tmp_path / "runtime"
    with patch.object(providers.platform, "system", return_value="Linux"), \
         patch.object(providers.platform, "machine", return_value="x86_64"), \
         patch.object(providers.shutil, "which", return_value="/bin/uv"), \
         patch.object(providers, "_gpu_preflight", return_value=[{"compute_capability": [8, 9]}]), \
         patch.object(providers, "_run", side_effect=subprocess.CalledProcessError(1, "uv")):
        with unittest.TestCase().assertRaises(subprocess.CalledProcessError):
            providers.setup_qsiv(model, runtime)
    assert not (model / "agemem-install.json").exists()


def test_download_rejects_corrupt_weights_before_metadata_patch(tmp_path):
    (tmp_path / "qsiv_fp8.safetensors").write_bytes(b"corrupt")
    metadata = tmp_path / "pyproject.toml"
    metadata.write_text('dependencies=["numpy==2.4.6"]')
    with patch("huggingface_hub.snapshot_download"):
        with unittest.TestCase().assertRaisesRegex(ValueError, "checksum mismatch"):
            providers._download_qsiv(tmp_path)
    assert "numpy==2.4.6" in metadata.read_text()


def test_doctor_reports_missing_without_running_anything(tmp_path):
    with patch.object(providers.subprocess, "run") as run:
        result = providers.qsiv_doctor(tmp_path / "model", tmp_path / "runtime")
    run.assert_not_called()
    assert not result["ready"]
    assert "qsiv_fp8.safetensors" in result["missing"]


def test_doctor_uses_configured_python_and_does_not_load_model(tmp_path):
    python = tmp_path / "python"
    python.touch()
    for name in ("config.json", "calibration.json", "tokenizer", "qsiv_fp8.safetensors"):
        (tmp_path / name).touch()
    completed = subprocess.CompletedProcess([], 0, '{"cuda_available":true,"torch":"2","device":"test","compute_capability":[8,9]}')
    with patch.object(providers.subprocess, "run", return_value=completed) as run:
        result = providers.qsiv_doctor(tmp_path, runtime_python=python)
    assert result["ready"]
    command = run.call_args.args[0]
    assert command[0] == str(python)
    assert "QSIVService" not in command[2]
    assert "snapshot_download" not in command[2]


class ProviderSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_dry_run(self):
        test_setup_dry_run_does_not_create_files(Path(self.temp.name))

    def test_failed_install(self):
        test_setup_failure_never_writes_success_manifest(Path(self.temp.name))

    def test_corrupt_weights(self):
        test_download_rejects_corrupt_weights_before_metadata_patch(Path(self.temp.name))

    def test_missing_runtime(self):
        test_doctor_reports_missing_without_running_anything(Path(self.temp.name))

    def test_doctor(self):
        test_doctor_uses_configured_python_and_does_not_load_model(Path(self.temp.name))

    def test_setup_without_gpu_fails_before_installing_or_creating_directories(self):
        root = Path(self.temp.name)
        with patch.object(providers.platform, "system", return_value="Linux"), \
             patch.object(providers.platform, "machine", return_value="x86_64"), \
             patch.object(providers.subprocess, "run", side_effect=FileNotFoundError), \
             patch.object(providers, "_run") as install:
            with self.assertRaisesRegex(ValueError, "Select Jev"):
                providers.setup_qsiv(root / "new/model", root / "new/runtime")
        install.assert_not_called()
        self.assertFalse((root / "new").exists())

    def test_setup_rejects_older_gpu_and_accepts_ada(self):
        old = subprocess.CompletedProcess([], 0, "RTX 3090, 8.6\n")
        with patch.object(providers.subprocess, "run", return_value=old):
            with self.assertRaisesRegex(ValueError, "8.9"):
                providers._gpu_preflight()
        ada = subprocess.CompletedProcess([], 0, "RTX 4070, 8.9\n")
        with patch.object(providers.subprocess, "run", return_value=ada):
            self.assertEqual(providers._gpu_preflight()[0]["compute_capability"], [8, 9])

    def test_doctor_rejects_cpu_and_pre_ada_fp8_without_fallback(self):
        root = Path(self.temp.name)
        python = root / "python"
        python.touch()
        for available, capability in ((False, None), (True, [8, 6])):
            output = json.dumps({"cuda_available": available, "compute_capability": capability})
            with patch.object(providers.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output)):
                result = providers.qsiv_doctor(root, runtime_python=python)
            self.assertFalse(result["ready"])
            self.assertFalse(result["gpu_compatible"])
            self.assertIn("Select Jev", result["action"])

@unittest.skipUnless(os.name == "posix", "Local QSIV install sources use POSIX file URLs")
class ApplicationSetupSourceTests(unittest.TestCase):
    def test_installed_local_wheel_is_reused_instead_of_package_index(self):
        with tempfile.TemporaryDirectory() as folder:
            wheel = Path(folder) / 'agemem-0.1.0-py3-none-any.whl'
            wheel.touch()
            package = unittest.mock.Mock()
            package.read_text.return_value = json.dumps({'url': wheel.as_uri()})
            with patch.object(providers, '__file__', str(Path(folder) / 'site-packages/agemem/providers.py')), \
                 patch('importlib.metadata.distribution', return_value=package):
                self.assertEqual(providers._application_spec(), str(wheel))

    def test_installed_local_directory_is_reused_instead_of_package_index(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'source'
            source.mkdir()
            (source / 'pyproject.toml').touch()
            package = unittest.mock.Mock()
            package.read_text.return_value = json.dumps({'url': source.as_uri()})
            with patch.object(providers, '__file__', str(Path(folder) / 'site-packages/agemem/providers.py')), \
                 patch('importlib.metadata.distribution', return_value=package):
                self.assertEqual(providers._application_spec(), str(source))
