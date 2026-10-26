"""Explicit local provider installation and diagnostics; inference never downloads."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

QSIV_REVISION = "f1ee842daf758c0ab535cf7d281c85439d6e4b25"
QSIV_SHA256 = "c44a08dafe091b0ed565a8efe511600b81e8f427feee56fc14c1d30d9466b9fc"
GPU_REQUIRED = ("QSIV requires a compatible NVIDIA GPU; FP8 needs compute capability 8.9 or newer. "
                "Select Jev in configuration on unsupported hardware; no provider was switched.")


def _gpu_preflight():
    """Check the driver before creating environments or downloading GPU packages."""
    try:
        completed = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,compute_cap", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=10)
        devices = []
        for row in completed.stdout.splitlines():
            name, capability = row.rsplit(",", 1)
            major, minor = (int(part) for part in capability.strip().split("."))
            devices.append({"name": name.strip(), "compute_capability": [major, minor]})
        if not any(tuple(device["compute_capability"]) >= (8, 9) for device in devices):
            raise ValueError(GPU_REQUIRED)
        return devices
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ValueError(GPU_REQUIRED) from None


def qsiv_paths(directory=None, runtime_directory=None):
    """Resolve durable model and isolated environment locations without creating them."""
    data = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))) / "agemem"
    model = Path(directory).expanduser().resolve() if directory else data / "models/qsiv"
    runtime = Path(runtime_directory).expanduser().resolve() if runtime_directory else data / "runtimes/qsiv"
    return model, runtime


def _run(command):
    # Keep stdio clean for CLI JSON and never include API credentials in commands.
    subprocess.run(command, check=True, stdout=sys.stderr, stderr=sys.stderr)


def _download_qsiv(directory):
    """Runs in the isolated environment, where huggingface_hub is installed."""
    from huggingface_hub import snapshot_download

    root = Path(directory)
    snapshot_download("djinn-san/QSIV", revision=QSIV_REVISION, local_dir=str(root),
                      allow_patterns=["qsiv/*", "tokenizer/*", "pyproject.toml", "LICENSE", "NOTICE",
                                      "config.json", "calibration.json", "qsiv_fp8.safetensors",
                                      "qsiv_fp8.safetensors.sha256"])
    with (root / "qsiv_fp8.safetensors").open("rb") as weights:
        actual = hashlib.file_digest(weights, "sha256").hexdigest()
    if actual != QSIV_SHA256:
        raise ValueError("QSIV FP8 checksum mismatch; runtime was not installed")
    metadata = root / "pyproject.toml"
    text = metadata.read_text()
    if "numpy==2.4.6" not in text and "numpy==2.5.4" not in text:
        raise ValueError("Unexpected QSIV metadata; inspect before installing")
    metadata.write_text(text.replace("numpy==2.4.6", "numpy==2.5.4"))


def _application_spec():
    checkout = Path(__file__).resolve().parent.parent
    if (checkout / "pyproject.toml").is_file() and (checkout / "agemem").is_dir():
        return str(checkout)
    from importlib.metadata import distribution
    from urllib.parse import unquote, urlparse
    package = distribution("agemem")
    direct = package.read_text("direct_url.json")
    if direct:
        try:
            url = urlparse(json.loads(direct).get("url", ""))
            source = Path(unquote(url.path))
            if url.scheme == "file":
                if source.is_file() and source.suffix == ".whl":
                    return str(source)
                if source.is_dir() and (source / "pyproject.toml").is_file():
                    return str(source)
        except (ValueError, TypeError):
            pass
    return "agemem==" + package.version


def setup_qsiv(directory=None, runtime_directory=None, dry_run=False):
    """Install pinned Linux CUDA FP8 runtime, without changing provider selection.

    Downloads are explicit, potentially several GB, and require uv and Python 3.12.
    A successful install returns the Python path used by the subprocess provider.
    Re-running reuses existing environments/download caches; no environment is deleted.
    """
    if platform.system() != "Linux" or platform.machine().lower() not in ("x86_64", "amd64"):
        raise ValueError("QSIV FP8 setup currently supports Linux x86_64 with an NVIDIA GPU")
    model, runtime = qsiv_paths(directory, runtime_directory)
    python = runtime / "bin/python"
    lock = Path(__file__).with_name("data") / "qsiv-linux-py312.lock"
    uv = shutil.which("uv")
    commands = []
    if not python.exists():
        commands.append([uv or "uv", "venv", "--python", "3.12", str(runtime)])
    commands.extend([
        [uv or "uv", "pip", "install", "--python", str(python), "-r", str(lock)],
        [uv or "uv", "pip", "install", "--python", str(python), _application_spec()],
        [str(python), "-c", "from agemem.providers import _download_qsiv; import sys; _download_qsiv(sys.argv[1])", str(model)],
        [uv or "uv", "pip", "install", "--python", str(python), "--no-build-isolation", "--no-deps", str(model)],
        [uv or "uv", "pip", "check", "--python", str(python)],
    ])
    result = {"provider": "qsiv", "directory": str(model), "runtime_python": str(python),
              "executable": str(runtime / "bin/agemem"), "revision": QSIV_REVISION,
              "weights_sha256": QSIV_SHA256, "dry_run": dry_run, "commands": commands,
              "hardware_requirement": "NVIDIA GPU, compute capability >= 8.9 (FP8); CPU unsupported"}
    if dry_run:
        return result
    result["gpus"] = _gpu_preflight()
    if not uv:
        raise ValueError("QSIV setup requires uv; install uv and retry")
    runtime.parent.mkdir(parents=True, exist_ok=True)
    model.parent.mkdir(parents=True, exist_ok=True)
    for command in commands:
        _run(command)
    manifest = model / "agemem-install.json"
    manifest.write_text(json.dumps({key: value for key, value in result.items() if key != "commands"}, indent=2) + "\n")
    return result


def qsiv_doctor(directory=None, runtime_directory=None, verify=False, runtime_python=None, runtime="fp8"):
    """Check local files/runtime without downloading, loading weights, or paid calls."""
    if runtime not in ("fp8", "reference"):
        raise ValueError("QSIV runtime must be reference or fp8")
    model, environment = qsiv_paths(directory, runtime_directory)
    python = Path(runtime_python).expanduser() if runtime_python else environment / "bin/python"
    weights_name = "qsiv_fp8.safetensors" if runtime == "fp8" else "model.safetensors"
    required = ("config.json", "calibration.json", "tokenizer", weights_name)
    missing = [name for name in required if not (model / name).exists()]
    result = {"provider": "qsiv", "directory": str(model), "runtime_python": str(python),
              "missing": missing, "runtime_available": python.exists(), "ready": False}
    if verify and runtime == "fp8" and "qsiv_fp8.safetensors" not in missing:
        with (model / "qsiv_fp8.safetensors").open("rb") as weights:
            result["checksum_valid"] = hashlib.file_digest(weights, "sha256").hexdigest() == QSIV_SHA256
    if python.exists():
        probe = ("import json,torch,qsiv; "
                 "print(json.dumps({'cuda_available':torch.cuda.is_available(),"
                 "'torch':torch.__version__,'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,"
                 "'compute_capability':list(torch.cuda.get_device_capability(0)) if torch.cuda.is_available() else None}))")
        try:
            completed = subprocess.run([str(python), "-c", probe], check=True, capture_output=True, text=True, timeout=30)
            result["runtime"] = json.loads(completed.stdout)
            capability = result["runtime"].get("compute_capability") or []
            compatible = bool(result["runtime"]["cuda_available"] and
                              (runtime == "reference" or tuple(capability) >= (8, 9)))
            result["gpu_compatible"] = compatible
            if not compatible:
                result["action"] = GPU_REQUIRED
            result["ready"] = (not missing and compatible
                               and result.get("checksum_valid", True))
        except (subprocess.SubprocessError, OSError, ValueError) as exc:
            result["runtime_error"] = type(exc).__name__
    return result
