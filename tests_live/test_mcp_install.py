import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from agemem.mcp_install import install
from agemem.project import initialize


class MCPInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agemem project ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        initialize(self.root, "bm25", "hash")

    def test_json_clients_preserve_entries_repeat_and_paths_with_spaces(self):
        for client, name in (("cursor", ".cursor/mcp.json"), ("claude-code", ".mcp.json")):
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({"other": True, "mcpServers": {"existing": {"command": "kept"}}}))
            with patch.dict(os.environ, {"AGEMEM_CONFIG": str(self.root / "private config.yaml")}):
                install(self.root, client)
                original = path.read_text()
                install(self.root, client)
            self.assertEqual(path.read_text(), original)
            data = json.loads(original)
            self.assertTrue(data["other"])
            self.assertEqual(data["mcpServers"]["existing"], {"command": "kept"})
            entry = data["mcpServers"]["agemem"]
            self.assertIn(str(self.root.resolve()), entry["args"])
            self.assertEqual(entry["env"]["AGEMEM_CONFIG"], str(self.root / "private config.yaml"))

    def test_dry_run_no_writes_and_offline_forwarded(self):
        result = install(self.root, "cursor", dry_run=True, offline=True)
        self.assertFalse((self.root / ".cursor").exists())
        self.assertIn("--offline", result["launcher"]["args"])

    def test_invalid_json_preserved(self):
        path = self.root / ".mcp.json"
        for text in ("{bad", "[]", '{"mcpServers": []}'):
            path.write_text(text)
            with self.assertRaises(ValueError):
                install(self.root, "claude-code")
            self.assertEqual(path.read_text(), text)

    def test_codex_uses_argument_list_without_shell(self):
        with patch("agemem.mcp_install.shutil.which", return_value="/bin/codex"), patch("agemem.mcp_install.subprocess.run") as run:
            run.return_value.returncode = 0
            install(self.root, "codex")
        command = run.call_args.args[0]
        self.assertEqual(command[:5], ["/bin/codex", "mcp", "add", "agemem", "--"])
        self.assertIn(str(self.root.resolve()), command)
        self.assertEqual(run.call_args.kwargs["cwd"], self.root)

    def test_noninteractive_requires_client(self):
        with patch("sys.stdin.isatty", return_value=False), self.assertRaises(ValueError):
            install(self.root)

    def test_interactive_selection(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="cursor"):
            self.assertEqual(install(self.root, dry_run=True)["client"], "cursor")
