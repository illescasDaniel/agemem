"""Repeatable setup of user configuration, project memory and client registration."""
from pathlib import Path
import getpass
import os
import json
import platform
import sys
import warnings

from .config import initialize_user_config, load_user_config, config_path, provider_options
from .engine import Engine
from .mcp_install import install, select_client
from .project import initialize


def configure_provider(offline=False, model=None, no_input=False):
    """Prompt only for a new interactive user configuration; never return a secret."""
    if model is not None:
        if model not in ("jev", "qsiv"):
            raise ValueError("Choose model jev or qsiv")
        existing = load_user_config()
        if config_path().exists() and existing.get("default_provider", "jev") != model:
            raise ValueError("Requested model differs from existing user config; update default_provider explicitly before rerunning")
        options = provider_options({})
        if os.environ.get("AGEMEM_PROVIDER") and options["decision_backend"] != model:
            raise ValueError("AGEMEM_PROVIDER conflicts with the requested model")
        if model == "jev":
            if not options.get("jev_api_key"):
                raise ValueError("Non-interactive Jev setup requires an API key in private config or AGEMEM_JEV_API_KEY, TYPESAFE_API_KEY or JEV_API_KEY")
        else:
            if offline:
                raise ValueError("QSIV setup needs downloads; omit --offline and rerun")
            from .providers import setup_qsiv
            runtime_python = options.get("qsiv_python")
            setup_qsiv(directory=options.get("qsiv_directory"),
                       runtime_directory=Path(runtime_python).parent.parent if runtime_python else None)
        return initialize_user_config(default_provider=model)
    if config_path().exists() or no_input or not sys.stdin.isatty() or offline:
        return initialize_user_config()
    from .providers import _gpu_preflight, setup_qsiv
    compatible = False
    if platform.system() == "Linux" and platform.machine().lower() in ("x86_64", "amd64"):
        try:
            _gpu_preflight()
            compatible = True
        except ValueError:
            pass
    provider = "jev"
    if compatible:
        print("QSIV runs locally on your compatible NVIDIA GPU. Selecting it installs an isolated runtime and downloads several GB.", file=sys.stderr)
        while True:
            provider = input("Main provider [jev/qsiv] (jev): ").strip().lower() or "jev"
            if provider in ("jev", "qsiv"):
                break
            print("Choose jev or qsiv.", file=sys.stderr)
    else:
        print("Compatible QSIV GPU setup unavailable; using hosted Jev.", file=sys.stderr)
    if provider == "qsiv":
        # Save the selection only after installation succeeds.
        setup_qsiv()
        return initialize_user_config(default_provider="qsiv")
    key = None
    if not provider_options({}).get("jev_api_key"):
        # Refuse getpass's echoing fallback when a secure terminal is unavailable.
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            try:
                key = getpass.getpass("Jev API key (hidden; Enter to configure later): ").strip() or None
            except getpass.GetPassWarning:
                raise ValueError("Secure key input unavailable; configure the key in the private YAML file or environment") from None
    return initialize_user_config(api_key=key)


def initialize_project(project, client=None, retrieval="hybrid", embedder="BAAI/bge-small-en-v1.5", offline=False, *, model=None, clients=None, no_input=False):
    root = Path(project).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project directory must already exist")
    if no_input and not (client or clients):
        raise ValueError("--no-input requires --mcp or --client")
    selected_clients = list(dict.fromkeys("claude-code" if value == "claude" else value for value in clients)) if clients else [select_client(client)]
    from .mcp_install import CLIENTS
    if any(value not in CLIENTS for value in selected_clients):
        raise ValueError("Choose MCP clients codex, cursor or claude")
    if no_input and model is None and not config_path().exists():
        raise ValueError("--no-input requires --model when creating user configuration")
    # Validate existing user settings before creating any project files.
    load_user_config()
    project_config = root / ".agemem/config.json"
    if model and project_config.exists():
        saved = json.loads(project_config.read_text())
        if saved.get("decision_backend", model) != model:
            raise ValueError("Requested model conflicts with project decision_backend; update project config explicitly before rerunning")
    user = configure_provider(offline, model=model, no_input=no_input)
    project_result = initialize(root, retrieval, embedder)
    engine = Engine(root, offline)
    try:
        index = engine.index()
    finally:
        engine.close()
    registrations = [install(root, selected, offline=offline) for selected in selected_clients]
    next_steps = ["Restart or reload the client and enable the agemem server",
                  "Add the project-memory instructions from docs/AGENT_INTEGRATION.md to your agent guidance"]
    options = provider_options({})
    if options["decision_backend"] in ("jev", "cascade") and not options.get("jev_api_key"):
        next_steps.insert(0, "Configure the selected provider in " + user["path"])
    return {"project": str(root), "user_config": user, "initialization": project_result,
            "index": index, "mcp": registrations[0] if len(registrations) == 1 else registrations,
            "next_steps": next_steps}
