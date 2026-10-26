# CI and PyPI releases

Package: `agemem`. Repository: [illescasDaniel/agemem](https://github.com/illescasDaniel/agemem).
Author: Daniel Illescas Romero <illescas.daniel@protonmail.com>. License: MIT;
third-party notices remain bundled separately.

## Continuous integration

`ci.yml` runs the offline unit suite on Linux, macOS and Windows, with Python
3.12 and 3.14. Python 3.15 is excluded until ONNX Runtime supplies compatible
wheels. GPU-runtime executable-shim tests require POSIX; upstream note-database
compatibility tests require the optional compatibility extra.

A separate job builds the sdist and builds its wheel, validates distribution
metadata with Twine, installs the wheel into an empty environment, and exercises
CLI initialization, indexing, source capture, pending notes, persisted recall,
and an actual stdio MCP handshake and tool call away from the checkout. These
checks do not download embedding models or call hosted decision providers.
They do not validate GPU inference or hosted provider quality.

All actions are pinned to commit SHAs. Publishing is manual; pushes and tags do
not publish anything automatically.

## Trusted publishing setup

The trusted publisher for PyPI must use:

| Field | Value |
|---|---|
| PyPI project | `agemem` |
| GitHub owner | `illescasDaniel` |
| Repository | `agemem` |
| Workflow filename | `release.yml` |
| GitHub environment | `pypi` |

Register a pending publisher before the first upload at
[PyPI Publishing](https://pypi.org/manage/account/publishing/). In GitHub's
[environment settings](https://github.com/illescasDaniel/agemem/settings/environments),
create `pypi` and require the owner's review. No PyPI API token is needed.
See [PyPI trusted publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/).

## Release procedure

1. Update `pyproject.toml` and `agemem/__init__.py` to the same version. Add a
   nonempty, dated `## [X.Y.Z] - YYYY-MM-DD` entry to `CHANGELOG.md`.
2. Commit and push to `main`; wait for every CI job on that exact commit to pass.
3. After explicit authorization to publish that version, tag the tested commit
   and push the tag, for example `v0.1.0`.
4. Run Actions → Release → Run workflow with that existing tag, or
   `gh workflow run release.yml --ref main -f tag=v0.1.0`.
5. Approve the `pypi` environment deployment. The workflow validates the tag,
   package versions, license and release notes, requires the commit to be on
   `main`, reruns tests and the built-wheel smoke check, then publishes through
   OIDC and creates the GitHub release with changelog notes and artifacts.
6. From a clean directory, check `uvx --python 3.12 agemem@0.1.0 --help` and the
   [PyPI package](https://pypi.org/project/agemem/) and GitHub release pages.

A failure before upload can be corrected and rerun. After a successful PyPI
upload, that version cannot be reused; yank a bad release and publish a new patch.
If only GitHub release creation fails, create the release from the existing tag
and original artifacts; do not re-upload the package to PyPI.
