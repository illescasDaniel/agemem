"""Pending-queue MCP tools, CLI flag and docs (Track B, scenarios S12-S15 in sdd/pending-queue.html)."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agemem.engine import Engine
from agemem.notes import consolidate
from agemem.notes.decider import FakeDecider
from agemem.project import initialize

ROOT = Path(__file__).resolve().parents[1]
NEW_TOOLS = {"project_memory_pending", "project_memory_resolve", "project_memory_dismiss"}
OLD_TOOLS = {"project_memory_recall", "project_memory_remember", "project_memory_capture",
             "project_memory_index", "project_memory_maintain"}


def project_with_items(folder, count=2):
    root = Path(folder)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    initialize(root, "bm25", "hash")
    engine = Engine(root, offline=True, decider=FakeDecider())
    store = engine._notes()[0]
    ids = []
    for i in range(count):
        a, b = store.add_node(f"fact {i} a", "global"), store.add_node(f"fact {i} b", "global")
        ids.append(store.add_synth("conflict", [a, b], 0.9))
    engine.close()
    return root, ids


class CliTests(unittest.TestCase):
    def test_s12_maintain_pending_is_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ids = project_with_items(folder)
            run = subprocess.run([sys.executable, "-m", "agemem.cli", "--project", folder, "--offline",
                                  "maintain", "--pending"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            page = json.loads(run.stdout)
            self.assertEqual(page["total"], 2)
            self.assertEqual([item["id"] for item in page["items"]], ids)
            engine = Engine(root, offline=True, decider=FakeDecider())
            store = engine._notes()[0]
            try:
                self.assertEqual(len(store.synth_items()), 2)
                self.assertEqual(store.meta_get("last_consolidated_id"), 0)
            finally:
                engine.close()


def payload(result):
    """The tool's JSON result, as the other dict-returning tools (remember, capture) deliver it: in content text."""
    return json.loads(result.content[0].text)


class McpTests(unittest.IsolatedAsyncioTestCase):
    async def test_s13_tools_listed_and_called_over_stdio(self):
        with tempfile.TemporaryDirectory() as folder:
            root, ids = project_with_items(folder)
            params = StdioServerParameters(command=sys.executable, args=[
                "-m", "agemem.cli", "--project", folder, "--offline", "mcp"])
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = {t.name: t for t in (await session.list_tools()).tools}
                    self.assertEqual(set(tools), NEW_TOOLS | OLD_TOOLS)
                    self.assertEqual(tools["project_memory_resolve"].input_schema["properties"]["id"]["type"], "integer")
                    self.assertEqual(tools["project_memory_resolve"].input_schema["properties"]["text"]["type"], "string")
                    self.assertEqual(tools["project_memory_pending"].input_schema["properties"]["limit"]["type"], "integer")
                    listed = await session.call_tool("project_memory_pending", {})
                    self.assertFalse(listed.is_error)
                    self.assertEqual(payload(listed)["total"], 2)
                    dismissed = await session.call_tool("project_memory_dismiss", {"id": ids[0]})
                    self.assertFalse(dismissed.is_error)
                    self.assertTrue(payload(dismissed)["ok"])
                    refused = await session.call_tool("project_memory_resolve", {"id": 999, "text": "x"})
                    self.assertFalse(refused.is_error)
                    self.assertFalse(payload(refused)["ok"])
                    bad = await session.call_tool("project_memory_pending", {"limit": 0})
                    self.assertTrue(bad.is_error)

    def test_s11_instruction_tools_are_registered(self):
        text = " ".join(consolidate._INSTRUCTION.values())
        self.assertTrue(set(re.findall(r"project_memory_\w+", text)) <= NEW_TOOLS | OLD_TOOLS)


class DocsTests(unittest.TestCase):
    def test_s14_wrapup_routine_documented(self):
        guide = (ROOT / "docs/AGENT_INTEGRATION.md").read_text(encoding="utf-8")
        skill = (ROOT / "docs/memory-wrapup/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("End-of-session routine", guide)
        for text in (guide.split("End-of-session routine", 1)[1], skill):
            flat = " ".join(text.split())
            positions = [flat.find(t) for t in ("project_memory_capture", "project_memory_remember",
                                                  "project_memory_maintain", "project_memory_pending")]
            self.assertTrue(all(p >= 0 for p in positions), positions)
            self.assertEqual(positions, sorted(positions))
            self.assertIn("project_memory_resolve", flat)
            self.assertIn("project_memory_dismiss", flat)
            self.assertRegex(flat, r"(?i)each item once")
            self.assertRegex(flat, r"(?i)data,? (and )?(never|not) instructions")
        front = re.match(r"---\nname: memory-wrapup\ndescription: .+\n---\n", skill)
        self.assertIsNotNone(front)

    def test_s15_counts_and_changelog(self):
        for name in ("ARCHITECTURE.md", "HOOKS.md"):
            text = " ".join((ROOT / "docs" / name).read_text(encoding="utf-8").split())
            self.assertNotRegex(text, r"(?i)\bfive (public |MCP )?tools\b")
        architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
        for name in NEW_TOOLS:
            self.assertIn(name, architecture)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = changelog.split("## [0.3.0]", 1)[1].split("\n## [", 1)[0]
        for needle in ("project_memory_pending", "maintain --pending", "memory_forget", "wrap-up"):
            self.assertIn(needle, unreleased)


if __name__ == "__main__":
    unittest.main()
