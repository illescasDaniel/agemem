# User configuration and provider setup

Agemem reads `~/.config/agemem/config.yaml`, or
`$XDG_CONFIG_HOME/agemem/config.yaml`. `AGEMEM_CONFIG` selects an explicit file.
It does not read or change aiscript's configuration.

```sh
agemem config init
```

This creates a private file (mode `0600`) and preserves an existing file:

```yaml
version: 1
default_provider: jev
providers:
  jev:
    api_key: null
  qsiv:
    runtime: fp8
    model_directory: ~/.local/share/agemem/models/qsiv
    # python: ~/.local/share/agemem/runtimes/qsiv/bin/python
```

`version` is the configuration schema version, independent of the package version.
This release accepts integer `1`; unversioned configurations are treated as schema 1
for compatibility. Unsupported versions fail before provider settings are used.
Future releases must migrate older schemas explicitly or reject them rather than
silently reinterpret settings. `config init` never rewrites an existing file;
add `version: 1` to an existing configuration when convenient.

Set `providers.jev.api_key` in this private YAML file for hosted Jev.
Environment overrides remain supported: `AGEMEM_JEV_API_KEY`, then
`TYPESAFE_API_KEY`, then `JEV_API_KEY` override the YAML `api_key`.
User credentials are resolved in memory and never copied into project config
or diagnostic output. Keep the user config out of version control.

Provider precedence is `AGEMEM_PROVIDER`, an explicit project
`.agemem/config.json` `decision_backend`, user `default_provider`, then `jev`.
Existing projects preserve their explicit provider. New `agemem init` projects
omit provider fields and follow the global provider. Remove an old project's
`decision_backend` field to follow the global setting.

QSIV model path precedence is `AGEMEM_QSIV_DIR`, project `qsiv_directory`,
then user `providers.qsiv.model_directory`. The runtime is project
`qsiv_runtime`, then user `providers.qsiv.runtime`, then `fp8`.
`AGEMEM_QSIV_PYTHON` overrides `providers.qsiv.python`; otherwise an installed
`$XDG_DATA_HOME/agemem/runtimes/qsiv/bin/python` is detected automatically
(`XDG_DATA_HOME` defaults to `~/.local/share`). Without a configured or detected
isolated Python, the existing in-process runtime remains available.

## Optional QSIV installation

```sh
agemem provider setup qsiv --dry-run
agemem provider setup qsiv
agemem doctor
```

Setup explicitly installs an isolated Python runtime and downloads pinned,
verified model weights. It does not change the selected provider or require a
paid API. Inspect the dry run before downloading. Custom locations are available
through `--model-directory` and `--runtime-directory`; set the matching YAML
`model_directory` and `python` fields when using those locations.

After setup, set `default_provider: qsiv` to select it in projects without an
explicit provider override. QSIV is GPU-only and runs natively using Python/PyTorch/CUDA;
Ollama and Ollaya are not involved. A persistent subprocess lets the normal
Agemem environment use the isolated runtime. There is no silent hosted fallback
when QSIV fails. The separate `cascade` provider intentionally permits Jev
fallback and therefore is not local-only.

To use QSIV first and fall back to Jev for low-confidence answers, set
`default_provider: cascade` in the private YAML, alongside the QSIV paths and Jev
credentials. A project `decision_backend` or `AGEMEM_PROVIDER` can override the
YAML provider selection. Offline mode disables the hosted fallback.

`agemem doctor` checks the selected provider and reports missing credentials,
model files or runtime dependencies. It does not run inference, download
weights or call hosted APIs. `--offline` prevents hosted decisions; selecting
Jev while offline does not automatically select QSIV.

The memory service can run locally while the coding agent using it still uses
a hosted model. Local source retrieval also requires cached embedding and
reranker models; see [RAW-RAG setup](RAW_RAG.md).

Production QSIV requires a compatible NVIDIA GPU. FP8 setup supports Linux x86_64
and compute capability8.9 or newer; setup rejects missing/older hardware before
installing or downloading. Doctor checks CUDA and device capability, and inference
also rejects unsupported hardware. Use `default_provider: jev` on machines without
a compatible GPU. This is an explicit user choice; no automatic paid call occurs.
There is no production CPU fallback.
