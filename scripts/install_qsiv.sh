#!/usr/bin/env bash
# Standalone Linux/Python 3.12 GPU environment; never borrows another project.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
model_dir="$PWD/.cache/qsiv/model"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/.cache/uv}"
uv venv --python 3.12 .venv-qsiv
uv pip install --python .venv-qsiv/bin/python -r requirements/qsiv-linux-py312.lock
.venv-qsiv/bin/python - "$model_dir" <<'PY'
import hashlib
import sys
from pathlib import Path
from huggingface_hub import snapshot_download
root = Path(sys.argv[1])
snapshot_download('djinn-san/QSIV', revision='f1ee842daf758c0ab535cf7d281c85439d6e4b25',
                  local_dir=str(root), allow_patterns=['qsiv/*','tokenizer/*','pyproject.toml',
                  'LICENSE','NOTICE','config.json','calibration.json','qsiv_fp8.safetensors',
                  'qsiv_fp8.safetensors.sha256'])
expected = 'c44a08dafe091b0ed565a8efe511600b81e8f427feee56fc14c1d30d9466b9fc'
with (root/'qsiv_fp8.safetensors').open('rb') as weights:
    actual = hashlib.file_digest(weights, 'sha256').hexdigest()
if actual != expected:
    raise SystemExit('QSIV FP8 checksum mismatch')
# Explicit compatibility patch: upstream NumPy 2.4.6 conflicts with jevmem>=2.5.3.
p = root/'pyproject.toml'
text = p.read_text()
if 'numpy==2.4.6' not in text and 'numpy==2.5.4' not in text:
    raise SystemExit('Unexpected QSIV metadata; inspect before installing')
p.write_text(text.replace('numpy==2.4.6', 'numpy==2.5.4'))
PY
uv pip install --python .venv-qsiv/bin/python --no-build-isolation --no-deps "$model_dir"
uv pip install --python .venv-qsiv/bin/python --no-deps -e .
uv pip check --python .venv-qsiv/bin/python
