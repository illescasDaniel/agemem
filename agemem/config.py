"""User configuration, kept outside project checkouts and never written implicitly."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

PROVIDERS = ("jev", "qsiv", "ollaya", "cascade")


def config_path():
    explicit = os.environ.get("AGEMEM_CONFIG")
    return Path(explicit).expanduser() if explicit else Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "agemem/config.yaml"


def load_user_config():
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text())
        if data is None:
            data = {}
    except yaml.YAMLError:
        raise ValueError("Invalid YAML in agemem user configuration") from None
    if not isinstance(data, dict):
        raise ValueError("Agemem user configuration must be a YAML mapping")
    if data.get("default_provider", "jev") not in PROVIDERS:
        raise ValueError("Unsupported default_provider in agemem user configuration")
    providers = data.get("providers", {})
    if not isinstance(providers, dict) or any(not isinstance(value, dict) for value in providers.values()):
        raise ValueError("providers must map provider names to option mappings")
    return data


def provider_options(project):
    user = load_user_config()
    providers = user.get("providers", {})
    qsiv = providers.get("qsiv", {})
    jev = providers.get("jev", {})
    backend = os.environ.get("AGEMEM_PROVIDER") or project.get("decision_backend") or user.get("default_provider", "jev")
    if backend not in PROVIDERS:
        raise ValueError("Unsupported decision backend")
    runtime = project.get("qsiv_runtime", qsiv.get("runtime", "fp8"))
    if runtime not in ("fp8", "reference"):
        raise ValueError("qsiv runtime must be fp8 or reference")
    directory = os.environ.get("AGEMEM_QSIV_DIR") or project.get("qsiv_directory") or qsiv.get("model_directory")
    if directory is not None and not isinstance(directory, str):
        raise ValueError("QSIV model_directory must be a path string")
    key = os.environ.get("AGEMEM_JEV_API_KEY") or os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY") or jev.get("api_key")
    if key is not None and not isinstance(key, str):
        raise ValueError("Jev api_key must be a string")
    data_root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    directory = directory or str(data_root / "agemem/models/qsiv")
    default_python = data_root / "agemem/runtimes/qsiv/bin/python"
    runtime_python = os.environ.get("AGEMEM_QSIV_PYTHON") or qsiv.get("python")
    if runtime_python is not None and not isinstance(runtime_python, str):
        raise ValueError("QSIV python must be a path string")
    if runtime_python is None and default_python.is_file():
        runtime_python = str(default_python)
    return {"decision_backend": backend, "qsiv_python": str(Path(runtime_python).expanduser()) if runtime_python else None, "qsiv_runtime": runtime,
            "qsiv_directory": str(Path(directory).expanduser()) if directory else None,
            "jev_api_key": key}


def initialize_user_config():
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data_root = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    template = """# Provider selection is global; projects can explicitly override it.
default_provider: jev
providers:
  jev:
    # Prefer AGEMEM_JEV_API_KEY, TYPESAFE_API_KEY or JEV_API_KEY.
    api_key: null
  qsiv:
    runtime: fp8
    model_directory: MODEL_DIRECTORY
    # python: ~/.local/share/agemem/runtimes/qsiv/bin/python
"""
    template = template.replace("MODEL_DIRECTORY", yaml.safe_dump(str(data_root / "agemem/models/qsiv"), default_style='"').strip())
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return {"path": str(path), "created": False}
    with os.fdopen(descriptor, "w") as stream:
        stream.write(template)
    return {"path": str(path), "created": True}


def doctor(project):
    """Inspect configuration without opening stores, downloading or calling providers."""
    from .project import configuration
    path = Path(project).expanduser().resolve()
    options = configuration(path) if (path / ".agemem/config.json").exists() else provider_options({})
    backend = options["decision_backend"]
    checks = {"user_config": str(config_path()), "user_config_exists": config_path().exists(),
              "provider": backend, "project_initialized": (path / ".agemem/config.json").exists()}
    issues = []
    if backend in ("jev", "cascade"):
        checks["jev_credentials_present"] = bool(options.get("jev_api_key"))
        if not checks["jev_credentials_present"]:
            issues.append("Set a Jev API key in the user configuration or environment")
    if backend in ("qsiv", "cascade"):
        directory = options.get("qsiv_directory")
        checks["qsiv_model_directory"] = directory
        checks["qsiv_model_directory_exists"] = bool(directory and Path(directory).is_dir())
        if not checks["qsiv_model_directory_exists"]:
            issues.append("Configure and install the QSIV model directory")
        from .providers import qsiv_doctor
        import sys
        runtime_python = options.get("qsiv_python") or sys.executable
        runtime_directory = Path(runtime_python).parent.parent if runtime_python else None
        diagnostic = qsiv_doctor(directory=directory, runtime_directory=runtime_directory, runtime_python=runtime_python, runtime=options["qsiv_runtime"])
        checks["qsiv"] = diagnostic
        if not diagnostic.get("ready", False):
            issues.append("QSIV runtime diagnostics require attention; see checks.qsiv")
    return {"ok": not issues, "checks": checks, "issues": issues,
            "note": "Read-only diagnostics; no model inference or API calls performed"}
