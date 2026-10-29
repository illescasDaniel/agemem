"""Register an explicit project launcher without a Node.js dependency."""
import json
import os
from pathlib import Path
import sys
import tempfile
import tomlkit

from . import __version__
from .project import inside

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


def launcher(offline=False, executable=None, workspace_variable=None):
    """Client launcher without any machine-specific project path.

    The server finds its project from its working directory. workspace_variable (for example
    "${workspaceFolder}", which Cursor interpolates) is passed as --project when given.
    """
    if executable is not None:
        executable = Path(executable).expanduser().resolve()
        if not executable.is_file():
            raise ValueError("Launcher executable must be an existing installed agemem command")
        entry = {"command": str(executable), "args": []}
    else:
        entry = {"command": "uvx", "args": ["--python", "3.12", f"agemem@{__version__}"]}
    if workspace_variable:
        entry["args"] += ["--project", workspace_variable]
    if offline:
        entry["args"].append("--offline")
    entry["args"].append("mcp")
    if os.environ.get("AGEMEM_CONFIG"):
        entry["env"] = {"AGEMEM_CONFIG": str(Path(os.environ["AGEMEM_CONFIG"]).expanduser().resolve())}
    return entry


def install(project, client=None, dry_run=False, offline=False, executable=None):
    project = Path(project).expanduser().resolve()
    if not (project / ".agemem/config.json").is_file():
        raise ValueError("Run agemem init for this project before mcp-install")
    client = select_client(client)
    entry = launcher(offline=offline, executable=executable, workspace_variable="${workspaceFolder}" if client == "cursor" else None)
    result = {"client": client, "project": str(project), "server": "agemem", "launcher": entry, "dry_run": dry_run}
    if client == "codex":
        path = inside(project, project / ".codex/config.toml")
        result["path"] = str(path)
        result["scope"] = "project"
        try:
            data = tomlkit.parse(path.read_text() if path.exists() else "")
        except (ValueError, UnicodeError):
            raise ValueError("Invalid Codex TOML; repair the existing client configuration before installing") from None
        servers = data.get("mcp_servers", {})
        if not isinstance(servers, dict):
            raise ValueError("Codex MCP configuration must contain a mcp_servers mapping")
        current = servers.get("agemem", {})
        matches = current == entry
        result["changed"] = not matches
        if not dry_run and not matches:
            data.setdefault("mcp_servers", tomlkit.table())["agemem"] = entry
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".agemem-mcp-")
            try:
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(tomlkit.dumps(data))
                os.replace(temporary, path)
            finally:
                Path(temporary).unlink(missing_ok=True)
        result["next_step"] = "Trust the project, then restart or reload Codex to enable the agemem server"
    else:
        path = inside(project, project / (".cursor/mcp.json" if client == "cursor" else ".mcp.json"))
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
    result.setdefault("next_step", "Restart or reload the client and enable the agemem server")
    return result
