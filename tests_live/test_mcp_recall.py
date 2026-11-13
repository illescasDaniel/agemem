import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agemem.project import initialize


class MCPRecallTests(unittest.IsolatedAsyncioTestCase):
    async def test_structured_recall_and_error_over_stdio(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            initialize(root, "bm25", "hash")
            (root / "memory/activeContext.md").write_text("Current blocker: staging deployment.")
            params = StdioServerParameters(command=sys.executable, args=[
                "-m", "agemem.cli", "--project", folder, "--offline", "mcp",
            ])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool("project_memory_recall", {"query": "blocker"})
                    self.assertFalse(result.is_error)
                    self.assertEqual(result.content, [])
                    packet = result.structured_content
                    self.assertEqual(packet["query"], "blocker")
                    self.assertIn("staging deployment", packet["context"])
                    self.assertEqual(packet["layers"]["bank"][0]["ids"], ["bank:activeContext.md"])
                    self.assertEqual(packet["decision_provider_usage"], {})
                    self.assertIn("summaries", packet)   # S1: the summaries tier rides along over MCP too
                    scoped = await session.call_tool("project_memory_recall", {"query": "blocker", "path": "memory"})
                    self.assertFalse(scoped.is_error)
                    self.assertEqual(scoped.structured_content["scoped"]["path"], "memory")   # S8: path reaches the engine
                    escape = await session.call_tool("project_memory_recall", {"query": "blocker", "path": "../secrets"})
                    self.assertTrue(escape.is_error)   # S3/F1 over MCP: rejected, nothing returned
                    self.assertEqual(escape.content, [])
                    self.assertEqual(escape.structured_content["error"]["type"], "ValueError")
                    error = await session.call_tool("project_memory_recall", {"query": ""})
                    self.assertTrue(error.is_error)
                    self.assertEqual(error.content, [])
                    self.assertEqual(error.structured_content["error"]["type"], "ValueError")
                    self.assertIn("CLI diagnostics", error.structured_content["error"]["message"])
                    (root / ".agemem/config.json").unlink()
                    startup_error = await session.call_tool("project_memory_recall", {"query": "blocker"})
                    self.assertTrue(startup_error.is_error)
                    self.assertEqual(startup_error.content, [])
                    self.assertEqual(startup_error.structured_content["error"]["type"], "ValueError")
