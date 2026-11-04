# Decision benchmark: developer notes

The public interpretation and limitations are in
[Decision model evaluation](../docs/DECISION_MODEL_EVALUATION.md). The archived
raw outputs are in [decision-results](decision-results/). These are exploratory,
synthetic, author-labeled cases, not ground truth for end-to-end performance.

`scripts/decision_benchmark.py` defines the inputs, labels and thresholds.
The other `benchmark_*.py` and `time_*.py` scripts used the models' separate
published interfaces. The runners need optional, model-specific packages and
weights that are deliberately not agemem dependencies. They should be run from
the repository root in an isolated environment with `PYTHONPATH` containing the
repository and, where needed, the downloaded model's inference code. Inspect
third-party inference code before executing it. The checked-in scripts accept
local model directories and output paths; `--help` shows their arguments. The
GPU runs require a working CUDA environment and an available GPU. Run CPU and GPU
measurements separately, with the machine otherwise as idle as practical.

The expanded suite and fixed thresholds were identical across runs. The
benchmark originally imported the matching jev-mem 0.4.0 templates; the script
now imports agemem's bundled copies, whose instructions and keys were checked
against those templates. `time_qsiv.py` handles the current local question
classes and requires `--model-dir` and `--python` for the isolated QSIV runtime.
The QSIV run starts its worker lazily, so `client_init_seconds` is not model
load time. The EmbeddingGemma script records a single run rather than the
five-run timing protocol.

The Ollaya result was collected separately with Ollaya 0.10.0 and its local
`jevk5:4b` Q8_0 model (weights SHA-256
`aea433883bc7ed399f2fbd539e53d2eac7caf71a946fe6650995a413979d4a30`).
The full suite ran on CPU, followed by one warmed timing pass, not five. The
server fell back to CPU because the GPU was already in use. Its local HTTP
request timing includes transport; the Ollaya thread count was not fixed.
Both passes returned the same 41/50 predictions. The raw full-suite and warmed
timing outputs are in `decision-results/ollaya-jevk5-*-cpu.json`. The main
runner supports `--backend ollaya --suite expanded` with a running local service.

For repeatability, the model revisions used were:

| Model | Revision |
| --- | --- |
| QSIV | `f1ee842daf758c0ab535cf7d281c85439d6e4b25` |
| mrm8488/embeddinggemma-2-ft-typed-decision | `8403ff7fddc75b6994130e581a832f875fb5bd0e` |
| davanstrien/ultrabert-380m-curation | `c6a1fa055d36aeb3349b9a54537a5bc3f585d77d` |
| convaiinnovations/laya-typed-decisions | `e929ae5cf69bc34259cd2f95c9e91145b818b1f0` |
| StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 | `216d1ccb46a9e9b036eb9187b248db98480f77d4` |
| StrandsAgents/strands-decider-2B-hobson-v19 | `bb282d786bc251fd4e3068de3ada9ddbb38127cd` |
| com-kotobalabs/open-jev-deberta-v3-large | `188ee67a5c93122b916e5acd5bdb0cb3623e380a` |
| nandakishorm/vega-08b-public-intents | `42ac8d4fa9efb61f96e53d80962cf28f6dfe667e` |
| ZefanCai/Open-Jev-2B | `0c7aa498b1627be8da4acf34c863ff0ee0a92785` |

The two Strands checkpoints used `Qwen/Qwen3.5-2B-Base` revision
`b1485b2fa6dfa1287294f269f5fb618e03d52d7c`; Vega used
`Qwen/Qwen3.5-0.8B` revision `2fc06364715b967f1860aea9cf38778875588b17`;
Open-Jev used `Qwen/Qwen3.5-2B` revision
`15852e8c16360a2fea060d615a32b45270f8a8fc`. The Open-Jev loader checkout was
commit `bd4118882f733574a3250a4b65fe4d884130c08b`. Its CPU run set
`JEV_TORCH_DTYPE=float32`; the GPU run used the loader's bfloat16 default.
Both used `batch_size=1` and no prefix cache.

Laya used `laya` 0.4.21; Strands used `strands-decider` 0.2.0 and PEFT 0.21.2;
UltraBERT used `gliclass` 0.1.21 and its published `jev_api.py`. The recent
model runs used PyTorch 2.11.0+cu130 and Transformers 5.22.1. Local checkpoint
configuration files for Strands and Open-Jev were adjusted to refer to the
already-downloaded pinned base directories; model weights were unchanged.
Vega's runner takes that directory in `BENCHMARK_BASE_MODEL`. Model names and
revisions recorded by these scripts identify the intended checkpoints; the
scripts do not verify the contents of an arbitrary supplied directory. Verify
revisions and dependencies before interpreting a rerun.

DeBERTa accepts text, so the runner serializes structured state as JSON and
passes choice descriptions as options, mapping the selected description back to
its original key. When a group exceeds 512 tokens, it splits whole questions
into separate calls; duplicate option descriptions would make this mapping
ambiguous. Vega's `boolean` answers are converted to noul probabilities; its
abstention and routing metadata is retained. The detailed answer rows use each
model's unmodified returned probability and the existing fixed threshold.
