"""Project initialization and metadata; never store credentials in config."""
from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path

from .config import provider_options

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
    root = Path(root).resolve()
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("Project path escapes through a symlink")
    return resolved


def git(root, *args, default=""):
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.DEVNULL).decode().strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return default


def find_root(start):
    """Nearest directory at or above start that holds .agemem/config.json, else None."""
    start = Path(start).expanduser().resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".agemem/config.json").is_file():
            return candidate
    return None


def discover_root(start=None):
    """Project root for start (default cwd); start itself when no project is found yet."""
    start = Path(start).expanduser().resolve() if start is not None else Path.cwd().resolve()
    return find_root(start) or start


def _project_id(root):
    try:
        data = json.loads((root / ".agemem/config.json").read_text(encoding="utf-8"))
        return data.get("project_id") if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def local_store(root):
    """Directory for the untracked local stores.

    A linked git worktree shares the main checkout's .agemem/local when that checkout
    has the same project id (stores are keyed by branch); otherwise the root's own.
    """
    root = Path(root).resolve()
    own = root / ".agemem/local"
    out = git(root, "rev-parse", "--git-dir", "--git-common-dir", "--show-toplevel").splitlines()
    if len(out) != 3:
        return own
    gitdir, common, top = ((root / line).resolve() for line in out)
    if gitdir == common or common.name != ".git":
        return own
    try:
        relative = root.relative_to(top)
    except ValueError:
        return own
    main = common.parent / relative
    wanted = _project_id(root)
    if wanted is None or main == root or _project_id(main) != wanted:
        return own
    shared = main / ".agemem/local"
    if shared.is_symlink() or not shared.resolve().is_relative_to(main.resolve()):
        return own
    return shared


def identity(root):
    branch = git(root, "branch", "--show-current")
    commit = git(root, "rev-parse", "HEAD")
    return branch or (f"detached:{commit}" if commit else "working"), commit


# The local store is never committed. The SQLite sidecar files are listed too, in case a store is ever moved.
LOCAL_IGNORE = ("/local/", "*.sqlite-wal", "*.sqlite-shm", "*.sqlite-journal")


def initialize(directory, retrieval="hybrid", embedder="BAAI/bge-small-en-v1.5"):
    root = Path(directory).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("Project directory must already exist")
    folder = inside(root, root / ".agemem")
    folder.mkdir(exist_ok=True)
    created = []
    config = inside(root, folder / "config.json")
    if not config.exists():
        project_defaults = {key: value for key, value in DEFAULTS.items() if key not in ("decision_backend", "qsiv_directory", "qsiv_runtime")}
        config.write_text(json.dumps({**project_defaults, "project_id": uuid.uuid4().hex, "retrieval": retrieval,
                                      "embedder": embedder}, indent=2) + "\n")
        created.append(str(config.relative_to(root)))
    ignore = inside(root, folder / ".gitignore")
    existing = ignore.read_text() if ignore.exists() else ""
    lines = existing.splitlines()
    missing = [rule for rule in LOCAL_IGNORE if rule not in lines]
    if missing:
        ignore.write_text((existing.rstrip() + "\n" if existing.strip() else "") + "\n".join(missing) + "\n")
    memory = inside(root, root / "memory")
    memory.mkdir(exist_ok=True)
    for name, text in BANK.items():
        path = inside(root, memory / name)
        if not path.exists():
            path.write_text(text)
            created.append(str(path.relative_to(root)))
    return {"project": str(root), "created": created, "decision_backend": configuration(root)["decision_backend"]}


def configuration(root):
    path = inside(root, root / ".agemem/config.json")
    if not path.exists():
        raise ValueError("Run agemem init for this project first")
    project = json.loads(path.read_text())
    if not isinstance(project, dict):
        raise ValueError("Project configuration must be a JSON mapping")
    config = {**DEFAULTS, **project, **provider_options(project)}
    for key, variable in (("raw_rag_directory", "AGEMEM_RAW_RAG_DIR"),):
        if os.environ.get(variable):
            config[key] = os.environ[variable]
    if config["decision_backend"] not in ("jev", "qsiv", "ollaya", "cascade") or config["retrieval"] not in ("bm25", "hybrid", "raw-rag"):
        raise ValueError("Unsupported decision backend or retrieval mode")
    if not 128 <= config["context_budget"] <= 16000:
        raise ValueError("context_budget must be between 128 and 16000 regex units")
    return config
