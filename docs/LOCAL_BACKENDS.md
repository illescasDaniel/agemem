# Local decision backends

Edit `decision_backend` in `.agemem/config.json`: `jev` (default), `qsiv`, `ollaya`, or experimental `cascade`. These are typed decision engines; a separate answering/coding model still generates the final response.

## QSIV

QSIV is GPU-only in production; use Jev when a compatible NVIDIA GPU is unavailable. There is no automatic paid fallback. QSIV weights and runtime are not bundled. Download the upstream repository and real model/tokenizer files (a Git LFS pointer is not a model). Tested revision: `f1ee842daf758c0ab535cf7d281c85439d6e4b25` from https://huggingface.co/djinn-san/QSIV . Install its runtime dependencies in a separate GPU environment, then install this project there. Set `AGEMEM_QSIV_DIR` to the directory containing `qsiv_fp8.safetensors`, `calibration.json` and `tokenizer/`; ensure the upstream `qsiv` package is importable, for example through `PYTHONPATH=/path/to/QSIV`.

Configuration:

```json
{"decision_backend":"qsiv","qsiv_runtime":"fp8","qsiv_directory":"/absolute/path/to/QSIV"}
```

Merge these fields into the initialized config; preserve its project ID and other settings. `AGEMEM_QSIV_DIR` overrides the configured directory. Local loading refuses missing artifacts and does not silently download or call a hosted fallback. Native requests are batched at eight questions.

FP8 inference worked on this machine's RTX 4070 Laptop (8 GB), despite the runtime's Blackwell-optimization warning. A two-decision hardware probe allocated approximately 1.44 GiB of GPU memory. That establishes feasibility for these short inputs, not arbitrary context sizes or concurrency.

A clean standalone GPU environment is now validated in `.venv-qsiv/`, with durable
weights under `.cache/qsiv/model/` and embeddings under `.cache/embeddings/`.
It uses upstream Torch 2.11.0 / Triton 3.6.0 and an explicit packaging-only NumPy
2.5.4 patch to resolve jev-mem's incompatible minimum requirement. All 93 packages
pass compatibility checks; offline live write/recall and MCP pass. See
[standalone installation](QSIV_INSTALLATION.md) for pinned dependencies, setup,
checksums and limitations. No other project's environment is used. Reference
inference remains unvalidated.

## ollaya

With the user's existing ollaya server and installed model:

```json
{"decision_backend":"ollaya","ollaya_url":"http://127.0.0.1:11435","ollaya_model":"jevk5:4b"}
```

The endpoint must be loopback. Hosted keys are never forwarded to it. This uses the TypeSafe-compatible ollaya endpoint, not a generic Ollama chat endpoint. The existing service was left running; the model loaded for benchmarking was unloaded afterward. Initial synthetic result: 17/20, 7 requests, 3,810 input tokens.

## Confidence cascade

```json
{"decision_backend":"cascade","cascade_min_confidence":0.9,"qsiv_runtime":"fp8","qsiv_directory":"/absolute/path/to/QSIV"}
```

Every question goes to local QSIV. Only answers below the cutoff go to Jev, and only those answers are replaced. Binary native confidence is `abs(2*p_true - 1)`: 0.90 confidence means `p_true >= .95` or `<= .05`, not `p_true >= .90`. Choice confidence comes from the native runtime. This is not a calibrated probability of correctness. A confidently wrong answer can bypass Jev.

The cutoff was fixed using the original pilot before measuring 30 additional synthetic questions. We did not tune it against the new 30. At 0.90, the cascade matched Jev's 49/50 while routing 34/50 questions to Jev. It reduced hosted input tokens by 25%, but was slower overall in the measured run. Keep Jev as default until broader task-level evaluations support a change.

With `--offline`, a cascade cannot use its hosted fallback; uncertain decisions become unavailable and normal memory safeguards apply. Use `qsiv` for a fully local decision path. Prepare the local model caches first. Hybrid/BM25 and [prepared RAW-RAG](RAW_RAG.md) support offline source retrieval. Fully offline memory does not itself make a hosted coding agent offline.

## New controlled coding-memory fixtures

On ten final author-created executable-oracle selection tasks: Jev 9/10, QSIV
7/10, cascade 10/10. QSIV accepted 5/6 unsupported proposed memories; Jev and
cascade accepted none. Across calibration plus final, cascade required 29/32
hosted question fallbacks and saved only 3.22% of input tokens. These are small
controlled fixtures with supplied candidate code, not independently human-labeled
or end-to-end coding tasks.
