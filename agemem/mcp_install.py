"""Register an explicit project launcher without a Node.js dependency."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib

from . import __version__

CLIENTS = ("codex", "cursor", "claude-code")


def select_client(client=None):
    if client is None:
        if not sys.stdin.isatty():
            raise ValueError("Choose --client codex, cursor or claude-code in non-interactive sessions")
        print("Choose MCP client: codex, cursor, claude-code", file=sys.stderr)
        client = input("Client: ").strip().lower()
    if client not in CLIENTS:
        raise ValueError("Choose client codex, cursor or claude-code")
    return client


def install(project, client=None, dry_run=False, offline=False):
    project = Path(project).expanduser().resolve()
    if not (project / ".agemem/config.json").is_file():
        raise ValueError("Run agemem init for this project before mcp-install")
    client = select_client(client)
    args = ["--python", "3.12", f"agemem@{__version__}", "--project", str(project)]
    if offline:
        args.append("--offline")
    args.append("mcp")
    entry = {"command": "uvx", "args": args}
    if os.environ.get("AGEMEM_CONFIG"):
        entry["env"] = {"AGEMEM_CONFIG": str(Path(os.environ["AGEMEM_CONFIG"]).expanduser().resolve())}
    result = {"client": client, "project": str(project), "server": "agemem", "launcher": entry, "dry_run": dry_run}
    if client == "codex":
        command = ["codex", "mcp", "add", "agemem"]
        for key, value in entry.get("env", {}).items():
            command.extend(["--env", f"{key}={value}"])
        command.extend(["--", "uvx", *args])
        result["registration_command"] = command
        result["scope"] = "user"
        config = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser() / "config.toml"
        try:
            current = tomllib.loads(config.read_text()).get("mcp_servers", {}).get("agemem", {}) if config.exists() else {}
        except (ValueError, UnicodeError):
            raise ValueError("Invalid Codex TOML; repair the existing client configuration before installing") from None
        matches = all(current.get(key) == value for key, value in entry.items()) and current.get("env", {}) == entry.get("env", {}) and current.get("enabled", True)
        result["changed"] = not matches
        if not dry_run and not matches:
            executable = shutil.which("codex")
            if not executable:
                raise ValueError("Codex CLI is required for registration; install it or use the manual MCP configuration")
            completed = subprocess.run([executable, *command[1:]], cwd=project, capture_output=True, text=True)
            if completed.returncode:
                raise ValueError("Codex registration failed; check codex mcp configuration and permissions")
    else:
        path = project / (".cursor/mcp.json" if client == "cursor" else ".mcp.json")
        result["path"] = str(path)
        result["scope"] = "project"
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except (ValueError, UnicodeError):
                raise ValueError("Invalid MCP JSON; repair the existing client configuration before installing") from None
        else:
            data = {}
        if not isinstance(data, dict) or not isinstance(data.get("mcpServers", {}), dict):
            raise ValueError("MCP configuration must contain a mcpServers mapping")
        matches = data.get("mcpServers", {}).get("agemem") == entry
        result["changed"] = not matches
        data.setdefault("mcpServers", {})["agemem"] = entry
        if not dry_run and not matches:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".agemem-mcp-")
            try:
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(json.dumps(data, indent=2) + "\n")
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
    result["next_step"] = "Restart or reload the client and enable the agemem server"
    return result
