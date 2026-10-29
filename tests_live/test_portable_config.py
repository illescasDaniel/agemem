"""Path-free client configuration, root discovery and git worktree store sharing."""
import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from agemem.engine import Engine
from agemem.hooks import context, install as install_hooks
from agemem.mcp_install import install as install_mcp, launcher
from agemem.project import discover_root, find_root, initialize, local_store
from agemem.setup import initialize_project

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]


def git(root, *args):
    subprocess.run([*GIT, "-C", str(root), *args], check=True, capture_output=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agemem portable ")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "main"
        self.root.mkdir()
        environment = patch.dict(os.environ, {"AGEMEM_CONFIG": str(self.base / "config.yaml"), "PATH": os.environ.get("PATH", ""),
                                              "HOME": os.environ.get("HOME", str(Path.home()))}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        git(self.root, "init", "-q", "-b", "main")


class DiscoveryTests(Base):
    def test_walk_up_from_subdirectory_and_fallback(self):
        nested = self.root / "a/b"
        nested.mkdir(parents=True)
        self.assertIsNone(find_root(nested))
        self.assertEqual(discover_root(nested), nested)
        initialize(self.root, "bm25", "hash")
        self.assertEqual(find_root(nested), self.root)
        self.assertEqual(discover_root(nested), self.root)
        self.assertEqual(discover_root(self.root), self.root)

    def test_cli_defaults_to_discovered_root_and_explicit_project_wins(self):
        initialize(self.root, "bm25", "hash")
        nested = self.root / "src/pkg"
        nested.mkdir(parents=True)
        other = self.base / "other"
        other.mkdir()
        initialize(other, "bm25", "hash")
        from agemem import cli
        for cwd, extra, expected in ((nested, [], self.root), (nested, ["--project", str(other)], other)):
            out = io.StringIO()
            with patch("sys.argv", ["agemem", *extra, "doctor"]), patch("pathlib.Path.cwd", return_value=cwd), \
                    patch("agemem.cli.doctor") as doctor, contextlib.redirect_stdout(out):
                doctor.return_value = {"ok": True}
                cli.main()
            self.assertEqual(Path(doctor.call_args.args[0]), expected)

    def test_hook_root_comes_from_payload_cwd(self):
        initialize(self.root, "bm25", "hash")
        engine = Engine(self.root, offline=True)
        source = engine.capture("Atlas deploys using Ansible.")["source_id"]
        engine.close()
        nested = self.root / "deep/dir"
        nested.mkdir(parents=True)
        payload = {"cwd": str(nested), "prompt": "How does Atlas deploy using Ansible?"}
        with patch("pathlib.Path.cwd", return_value=self.base):
            self.assertIn(source, context(None, "user-prompt", payload))
            self.assertIn("bank:activeContext.md", context(None, "session-start", payload))
            # Outside any project the hook fails (run() turns that into a silent skip); no cwd injects nothing.
            with self.assertRaises(ValueError):
                context(None, "user-prompt", {**payload, "cwd": str(self.base)})
            self.assertIsNone(context(None, "user-prompt", {"prompt": payload["prompt"]}))
        # An explicit root still rejects a payload cwd outside it.
        self.assertIsNone(context(self.root, "user-prompt", {**payload, "cwd": str(self.base)}))


class WorktreeTests(Base):
    def setUp(self):
        super().setUp()
        initialize(self.root, "bm25", "hash")
        git(self.root, "add", ".agemem/config.json", ".agemem/.gitignore", "memory")
        git(self.root, "commit", "-q", "-m", "init")
        self.tree = self.base / "tree"
        git(self.root, "worktree", "add", "-q", "-b", "feature", str(self.tree))

    def test_worktree_uses_main_store_but_own_bank_and_branch(self):
        self.assertEqual(local_store(self.root), self.root / ".agemem/local")
        self.assertEqual(local_store(self.tree), self.root / ".agemem/local")
        (self.tree / "memory/activeContext.md").write_text("# Worktree context\n")
        main_engine = Engine(self.root, offline=True)
        tree_engine = Engine(self.tree, offline=True)
        try:
            self.assertEqual(tree_engine.local, self.root / ".agemem/local")
            self.assertEqual((main_engine.branch, tree_engine.branch), ("main", "feature"))
            tree_engine.index()
            main_engine.index()
            recall = tree_engine.recall("context")
            self.assertIn("Worktree context", recall["context"])
            self.assertEqual(recall["branch"], "feature")
            manifests = {row[0] for row in tree_engine.db.execute("SELECT branch FROM manifests")}
            self.assertEqual(manifests, {"main", "feature"})
            self.assertFalse((self.tree / ".agemem/local").exists())
        finally:
            main_engine.close()
            tree_engine.close()
        payload = {"cwd": str(self.tree), "prompt": "worktree context"}
        self.assertIn("Worktree context", context(None, "session-start", payload))

    def test_different_project_id_or_missing_config_uses_own_store(self):
        config = self.tree / ".agemem/config.json"
        data = json.loads(config.read_text())
        config.write_text(json.dumps({**data, "project_id": "other"}))
        self.assertEqual(local_store(self.tree), self.tree / ".agemem/local")
        config.write_text(json.dumps(data))
        (self.root / ".agemem/config.json").unlink()
        self.assertEqual(local_store(self.tree), self.tree / ".agemem/local")

    def test_not_a_repository_or_git_missing(self):
        plain = self.base / "plain"
        plain.mkdir()
        initialize(plain, "bm25", "hash")
        self.assertEqual(local_store(plain), plain / ".agemem/local")
        with patch("agemem.project.subprocess.check_output", side_effect=FileNotFoundError):
            self.assertEqual(local_store(self.tree), self.tree / ".agemem/local")


class LauncherTests(Base):
    def setUp(self):
        super().setUp()
        initialize(self.root, "bm25", "hash")

    def test_launchers_are_path_free_per_client(self):
        import tomllib
        install_mcp(self.root, "claude-code")
        install_mcp(self.root, "cursor")
        install_mcp(self.root, "codex")
        claude = json.loads((self.root / ".mcp.json").read_text())["mcpServers"]["agemem"]
        cursor = json.loads((self.root / ".cursor/mcp.json").read_text())["mcpServers"]["agemem"]
        codex = tomllib.loads((self.root / ".codex/config.toml").read_text())["mcp_servers"]["agemem"]
        for entry in (claude, codex):
            self.assertEqual(len(entry["args"]), 4)
            self.assertEqual(entry["args"][-1], "mcp")
            self.assertNotIn("--project", entry["args"])
        self.assertEqual(claude["args"][:2], ["--python", "3.12"])
        self.assertTrue(claude["args"][2].startswith("agemem@"))
        self.assertEqual(cursor["args"][3:], ["--project", "${workspaceFolder}", "mcp"])
        for name in (".mcp.json", ".cursor/mcp.json", ".codex/config.toml"):
            self.assertNotIn(str(self.root), (self.root / name).read_text())

    def test_executable_launcher_has_no_project_path(self):
        import sys
        entry = launcher(executable=Path(sys.executable))
        self.assertEqual(entry["args"], ["mcp"])
        self.assertEqual(launcher(executable=Path(sys.executable), workspace_variable="${workspaceFolder}")["args"],
                         ["--project", "${workspaceFolder}", "mcp"])


class SettingsTests(Base):
    def setUp(self):
        super().setUp()
        initialize(self.root, "bm25", "hash")

    def commands(self, path):
        data = json.loads(path.read_text())
        return [h["command"] for groups in data["hooks"].values() for g in groups for h in g["hooks"]]

    def test_shared_settings_by_default_and_local_with_flag(self):
        shared, local = self.root / ".claude/settings.json", self.root / ".claude/settings.local.json"
        result = install_hooks(self.root, ["claude"])
        self.assertEqual(result[0]["path"], str(shared))
        self.assertFalse(local.exists())
        commands = self.commands(shared)
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertNotIn(str(self.root), command)
            self.assertNotIn("--project", command)
            self.assertIn(" hook ", command)
        self.assertTrue(commands[0].endswith("hook session-start # agemem:SessionStart"))
        # Switching to local moves the hooks and strips the shared file clean.
        result = install_hooks(self.root, ["claude"], local_settings=True)
        self.assertEqual(result[0]["path"], str(local))
        self.assertEqual(result[0]["removed_from"], str(shared))
        self.assertEqual(len(self.commands(local)), 2)
        self.assertNotIn("hooks", json.loads(shared.read_text()))
        self.assertFalse(install_hooks(self.root, ["claude"], local_settings=True)[0]["changed"])

    def test_dry_run_changes_nothing(self):
        install_hooks(self.root, ["claude"])
        before = (self.root / ".claude/settings.json").read_text()
        install_hooks(self.root, ["claude"], local_settings=True, dry_run=True)
        self.assertEqual((self.root / ".claude/settings.json").read_text(), before)
        self.assertFalse((self.root / ".claude/settings.local.json").exists())

    def test_project_init_auto_memory_follows_local_flag(self):
        for flag, name in ((False, "settings.json"), (True, "settings.local.json")):
            root = self.base / f"proj{flag}"
            root.mkdir()
            git(root, "init", "-q")
            result = initialize_project(root, "claude-code", "bm25", "hash", True, local_settings=flag)
            path = root / ".claude" / name
            self.assertEqual(result["claude_settings"]["path"], str(path))
            self.assertIs(json.loads(path.read_text())["autoMemoryEnabled"], False)
            self.assertEqual(len(self.commands(path)), 2)
            self.assertFalse((root / ".claude" / ("settings.local.json" if name == "settings.json" else "settings.json")).exists())


class MigrationTests(Base):
    def test_0_1_x_install_is_replaced_without_duplicates(self):
        import tomllib
        initialize(self.root, "bm25", "hash")
        absolute = ["--python", "3.12", "agemem@0.1.1", "--project", str(self.root), "mcp"]
        old_entry = {"command": "uvx", "args": absolute}
        (self.root / ".cursor").mkdir()
        (self.root / ".cursor/mcp.json").write_text(json.dumps({"mcpServers": {"agemem": old_entry, "keep": {"command": "x"}}}))
        (self.root / ".mcp.json").write_text(json.dumps({"mcpServers": {"agemem": old_entry}}))
        (self.root / ".codex").mkdir()
        (self.root / ".codex/config.toml").write_text(f'[mcp_servers.agemem]\ncommand = "uvx"\nargs = {json.dumps(absolute)}\n[mcp_servers.keep]\ncommand = "x"\n')

        def old_hook(event, action):
            command = shlex.join(["uvx", "--python", "3.12", "agemem@0.1.1", "--project", str(self.root), "hook", action])
            return {"hooks": [{"type": "command", "command": f"{command} # agemem:{event}", "timeout": 10}]}
        unrelated = {"hooks": [{"type": "command", "command": "echo mine"}]}
        legacy = {"autoMemoryEnabled": False, "permissions": {"allow": ["Read"]},
                  "hooks": {"SessionStart": [unrelated, old_hook("SessionStart", "session-start")],
                            "UserPromptSubmit": [old_hook("UserPromptSubmit", "user-prompt")]}}
        (self.root / ".claude").mkdir()
        (self.root / ".claude/settings.local.json").write_text(json.dumps(legacy))
        (self.root / ".codex/hooks.json").write_text(json.dumps({"hooks": {"SessionStart": [old_hook("SessionStart", "session-start")]}}))

        initialize_project(self.root, None, "bm25", "hash", True, clients=["cursor", "claude", "codex"])
        initialize_project(self.root, None, "bm25", "hash", True, clients=["cursor", "claude", "codex"])

        for name in (".mcp.json", ".cursor/mcp.json"):
            text = (self.root / name).read_text()
            self.assertNotIn(str(self.root), text.replace(str(self.root / "x"), ""))
            self.assertEqual(text.count("agemem@"), 1)
        self.assertEqual(json.loads((self.root / ".cursor/mcp.json").read_text())["mcpServers"]["keep"], {"command": "x"})
        codex = tomllib.loads((self.root / ".codex/config.toml").read_text())
        self.assertEqual(codex["mcp_servers"]["keep"], {"command": "x"})
        self.assertNotIn("--project", codex["mcp_servers"]["agemem"]["args"])
        # Hooks: one pair, in the shared file; the old local file keeps only non-agemem content.
        local = json.loads((self.root / ".claude/settings.local.json").read_text())
        self.assertEqual(local, {"autoMemoryEnabled": False, "permissions": {"allow": ["Read"]},
                                 "hooks": {"SessionStart": [unrelated]}})
        shared = json.loads((self.root / ".claude/settings.json").read_text())
        self.assertEqual(sorted(shared["hooks"]), ["SessionStart", "UserPromptSubmit"])
        self.assertEqual([len(g) for g in shared["hooks"].values()], [1, 1])
        self.assertNotIn("autoMemoryEnabled", shared)  # existing value in the local file is kept
        codex_hooks = json.loads((self.root / ".codex/hooks.json").read_text())["hooks"]
        self.assertEqual(len(codex_hooks["SessionStart"]), 1)
        self.assertEqual(len(codex_hooks["UserPromptSubmit"]), 1)
        self.assertNotIn(str(self.root), json.dumps(codex_hooks))

    def test_explicit_executable_install_keeps_working(self):
        import sys
        initialize(self.root, "bm25", "hash")
        result = install_mcp(self.root, "claude-code", executable=Path(sys.executable))
        self.assertEqual(result["launcher"]["args"], ["mcp"])


if __name__ == "__main__":
    unittest.main()
