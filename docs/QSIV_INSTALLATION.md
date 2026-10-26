# Standalone QSIV FP8 installation

The supported setup command installs an isolated GPU runtime and pinned model
weights. Jev remains the default provider until you explicitly select QSIV.
See [user configuration](CONFIGURATION.md) for paths and provider precedence.

Requires Linux x86_64, Python 3.12 for the isolated runtime, uv, a compatible
NVIDIA driver and compute capability 8.9 or newer. Setup needs network access
and several GB of disk; CPU inference is unsupported.

```bash
agemem provider setup qsiv --dry-run
agemem provider setup qsiv
agemem doctor
```

Inspect the dry run to see model/runtime paths and installation commands.
The installer uses the bundled `agemem/data/qsiv-linux-py312.lock`; there is no
separate repository-level requirements folder. This platform-specific lock pins
versions but is not a hash-locked dependency manifest.

Setup downloads QSIV revision `f1ee842daf758c0ab535cf7d281c85439d6e4b25`,
verifies the pinned FP8 weight hash and retains upstream LICENSE and NOTICE.
It adjusts only the runtime's NumPy packaging pin to the tested version;
QSIV inference code and weights are unchanged. It checks installed dependency
compatibility and rejects unsupported hardware before installation/downloads.

Set `default_provider: qsiv` in the private user `config.yaml` to select QSIV
for projects without an explicit provider override. Run `agemem doctor` to
check configuration and dependencies without inference or downloads.

Default model and runtime locations are under `~/.local/share/agemem/`, or
`$XDG_DATA_HOME/agemem/`. A persistent subprocess lets the main application use
the isolated GPU runtime. Setup does not change the selected provider.

Offline retrieval also needs previously cached embedding models and, for
RAW-RAG, tokenizer and reranker files. Downloading QSIV alone does not prepare
those caches. See [RAW-RAG setup](RAW_RAG.md).

Local validation used Linux, Python 3.12 and an RTX 4070 Laptop 8 GB. Screened
writes, cited recall and MCP passed for bounded inputs; this does not establish
arbitrary context sizes or concurrency. Reference BF16 inference remains
unvalidated. Maintainer run reports are local artifacts, excluded from Git.
