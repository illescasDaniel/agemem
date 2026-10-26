#!/usr/bin/env bash
# Explicit, pinned Linux GPU setup. Keep historical project-local destinations.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
python3 -c 'from agemem.providers import setup_qsiv; import json; print(json.dumps(setup_qsiv(".cache/qsiv/model", ".venv-qsiv"), indent=2))'
