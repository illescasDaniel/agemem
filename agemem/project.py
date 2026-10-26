"""Project initialization and metadata; never store credentials in config."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

DEFAULTS = {"schema_version": 1, "decision_backend": "jev", "retrieval": "hybrid",
            "embedder": "BAAI/bge-small-en-v1.5", "context_budget": 1800,
            "qsiv_directory": None, "qsiv_runtime": "fp8", "raw_rag_directory": None,
            "ollaya_url": "http://127.0.0.1:11435", "ollaya_model": "jevk5:4b", "cascade_min_confidence": 0.9}
BANK = {
    "activeContext.md": "# Active context\n\n## Current focus\n\nDescribe the active task.\n\n## Blockers\n\nNone recorded.\n\n## Next steps\n\nRecord the exact next step when work stops.\n",
    "progress.md": "# Progress\n\n## Open\n\n- [ ] Record the current task.\n\n## Done\n",
    "decisions.md": "# Decisions\n\nAppend dated decisions with context, rationale and source references. Add a new entry when a decision is reversed.\n",
    "archive.md": "# Archive\n\nMove completed history here; keep current focus and progress short.\n",
}


def inside(root, path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Project path escapes through a symlink")
    return resolved


def git(root, *args, default=""):
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def identity(root):
    branch = git(root, "branch", "--show-current")
    commit = git(root, "rev-parse", "HEAD")
    return branch or (f"detached:{commit}" if commit else "working"), commit


def initialize(directory, retrieval="hybrid", embedder="BAAI/bge-small-en-v1.5"):
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project directory must already exist")
    folder = inside(root, root / ".agemem")
    folder.mkdir(exist_ok=True)
    created = []
    config = folder / "config.json"
    if not config.exists():
        config.write_text(json.dumps({**DEFAULTS, "project_id": uuid.uuid4().hex, "retrieval": retrieval,
                                      "embedder": embedder}, indent=2) + "\n")
        created.append(str(config.relative_to(root)))
    ignore = inside(root, folder / ".gitignore")
    existing = ignore.read_text() if ignore.exists() else ""
    if "/local/" not in existing.splitlines():
        ignore.write_text(existing.rstrip() + "\n/local/\n")
    memory = inside(root, root / "memory")
    memory.mkdir(exist_ok=True)
    for name, text in BANK.items():
        path = inside(root, memory / name)
        if not path.exists():
            path.write_text(text)
            created.append(str(path.relative_to(root)))
    return {"project": str(root), "created": created, "decision_backend": "jev"}


def configuration(root):
    path = inside(root, root / ".agemem/config.json")
    if not path.exists():
        raise ValueError("Run agemem init for this project first")
    config = {**DEFAULTS, **json.loads(path.read_text())}
    for key, variable in (("qsiv_directory", "AGEMEM_QSIV_DIR"), ("raw_rag_directory", "AGEMEM_RAW_RAG_DIR")):
        if os.environ.get(variable):
            config[key] = os.environ[variable]
    if config["decision_backend"] not in ("jev", "qsiv", "ollaya", "cascade") or config["retrieval"] not in ("bm25", "hybrid", "raw-rag"):
        raise ValueError("Unsupported decision backend or retrieval mode")
    if not 128 <= config["context_budget"] <= 16000:
        raise ValueError("context_budget must be between 128 and 16000 regex units")
    return config
