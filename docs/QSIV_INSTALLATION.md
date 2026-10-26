# Standalone QSIV FP8 installation

Validated on 2026-10-26, Linux x86_64, Python 3.12.13, RTX 4070 Laptop 8 GB.
Jev remains the default. No global configuration or other project environment is
modified. GPU access inside this Codex sandbox is restricted; validation succeeded
with host GPU access. Normal local terminal execution can access the driver.

Current durable installation:

- `.venv-qsiv/`: independent environment, no srxy imports/PYTHONPATH.
- `.cache/qsiv/model/`: model, tokenizer and installed upstream source.
- `.cache/embeddings/`: copied BGE cache for offline hybrid retrieval.
- `requirements/qsiv-linux-py312.lock`: exact resolved GPU/application dependencies.
- `reports/qsiv-clean-install.json`: package versions, GPU, artifact/runtime hashes.

The upstream runtime pins Torch 2.11.0 / Triton 3.6.0 and NumPy 2.4.6.
jev-mem 0.4.0 requires NumPy >=2.5.3, making an unmodified combined install
unsatisfiable. We explicitly changed ONLY QSIV's packaging metadata to NumPy
2.5.4 (`requirements/qsiv-numpy.patch`), then installed it normally. Runtime code
is unchanged. `uv pip check` passes all 93 packages. An initial resolver override
proved inference compatibility; rebuilding with patched metadata removed the
metadata inconsistency. This is a locally patched upstream installation.

From a fresh checkout with Python 3.12 and uv installed:

```bash
bash scripts/install_qsiv.sh
```

This downloads pinned upstream revision f1ee842daf758c0ab535cf7d281c85439d6e4b25,
verifies the pinned FP8 weight SHA256, applies the metadata patch, installs the
locked dependencies and checks compatibility. Requires network, a compatible
NVIDIA driver, a C compiler for Triton, and several GB of disk. The original
manual clean install and metadata rebuild were tested; the consolidated download
script was syntax checked, not rerun as a second full network installation.
The lock is platform-specific and version-pinned, not a hash-locked supply-chain
attestation. The existing Python interpreter is uv-managed outside the project;
no other project's packages are required. Do not delete that base interpreter.

Configure a target project with `decision_backend: qsiv`, `qsiv_runtime: fp8`
and an absolute `qsiv_directory` pointing to this model directory. Launch with
this environment's `agemem` executable. No PYTHONPATH adjustment is needed.

Reproduce the offline smoke test from the repository root:

```bash
export AGEMEM_MODEL_CACHE="$PWD/.cache/embeddings"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
.venv-qsiv/bin/python -m scripts.live_smoke --backend qsiv \
  --model-dir "$PWD/.cache/qsiv/model" \
  --output reports/live-qsiv-clean-offline.json
```

The BGE cache must already exist for this test. On a fresh installation first
index a non-sensitive project online to populate the embedding cache; a QSIV-only
weight download does not supply BGE. BM25/hash is an explicitly lower-quality
alternative for contract tests.

Measured: offline indexing, two screened writes and cited recall passed in six
local calls; MCP handshake, all five tools and offline recall passed. The clean
environment passes 20 live tests (including new scope/evaluator checks) and eight
inherited tests. FP8 still emits the upstream Blackwell warning on this Ada GPU;
these bounded inputs worked. Reference BF16 inference remains unvalidated.
