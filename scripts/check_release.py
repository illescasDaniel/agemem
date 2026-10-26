"""Validate a release tag, metadata and dated changelog before uploading."""
import ast
from datetime import date
from pathlib import Path
import re
import sys
import tomllib

from release_notes import section


def check(tag):
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or tag != "v" + project["version"]:
        raise ValueError("Release tag must match v<project.version>")
    module = ast.parse(Path("agemem/__init__.py").read_text(encoding="utf-8"))
    version = next(ast.literal_eval(node.value) for node in module.body
                   if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets))
    if version != project["version"]:
        raise ValueError("Package __version__ must match pyproject.toml")
    if project.get("license") != "MIT" or not Path("LICENSE").is_file():
        raise ValueError("Expected MIT licensing and root LICENSE")
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    header = re.search(r"^## \[" + re.escape(project["version"]) + r"\] - (\d{4}-\d{2}-\d{2})$", changelog, re.MULTILINE)
    if not header or date.fromisoformat(header[1]) > date.today():
        raise ValueError("Release needs a dated, non-future CHANGELOG entry")
    section(changelog, project["version"])
    print("Release tag, version, license and changelog verified")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: check_release.py vX.Y.Z")
        check(sys.argv[1])
    except (ValueError, LookupError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
