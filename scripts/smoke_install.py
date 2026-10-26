"""Exercise an installed wheel in a disposable project, without models or paid calls."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    import agemem
    if Path(agemem.__file__).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
        raise RuntimeError("Smoke test must import the installed wheel, not the checkout")
    with tempfile.TemporaryDirectory(prefix="agemem wheel smoke ") as folder:
        root = Path(folder)
        project = root / "project"
        project.mkdir()
        environment = {**os.environ, "AGEMEM_CONFIG": str(root / "private/config.yaml")}
        for name in ("AGEMEM_PROVIDER", "AGEMEM_QSIV_DIR", "AGEMEM_QSIV_PYTHON", "JEV_API_KEY", "TYPESAFE_API_KEY", "AGEMEM_JEV_API_KEY"):
            environment.pop(name, None)
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        (project / "README.md").write_text("The smoke project deploys with Ansible.\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(project), "add", "README.md"], check=True)

        def cli(*args):
            result = subprocess.run([sys.executable, "-m", "agemem.cli", "--project", str(project), *args],
                                    cwd=root, env=environment, capture_output=True, text=True, check=True)
            return json.loads(result.stdout)

        cli("config", "init")
        cli("--offline", "project", "init", "--mcp", "cursor", "claude", "--no-input", "--retrieval", "bm25", "--embedder", "hash")
        source = cli("--offline", "capture", "The smoke project deploys with Ansible.")["source_id"]
        cli("--offline", "remember", "The smoke project deploys with Ansible.", "--source-id", source)
        packet = cli("--offline", "recall", "How does the smoke project deploy?")
        assert "Ansible" in packet["context"]
        assert packet["layers"]["sources"]
        assert not (project / "AGENTS.md").exists()
        asyncio.run(mcp_roundtrip(project, environment))
    print("Installed-wheel CLI, offline evidence recall and five-tool MCP handshake passed")


async def mcp_roundtrip(project, environment):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    parameters = StdioServerParameters(command=sys.executable,
        args=["-m", "agemem.cli", "--project", str(project), "--offline", "mcp"], env=environment)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "project_memory_recall", "project_memory_remember", "project_memory_capture",
                "project_memory_index", "project_memory_maintain"}
            result = await session.call_tool("project_memory_recall", {"query": "How does the smoke project deploy?"})
            assert not result.is_error
            assert any("Ansible" in getattr(block, "text", "") for block in result.content)


if __name__ == "__main__":
    main()
