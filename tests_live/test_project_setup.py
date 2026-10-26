import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agemem.config import config_path, load_user_config
from agemem.setup import initialize_project, configure_provider


class ProjectSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agemem setup ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "project"
        self.root.mkdir()
        environment = patch.dict(os.environ, {"AGEMEM_CONFIG": str(Path(self.temp.name).resolve() / "config.yaml"), "PATH": os.environ.get("PATH", ""), "USERPROFILE": os.environ.get("USERPROFILE", str(Path.home())), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}, clear=True)
        environment.start()
        self.addCleanup(environment.stop)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / "example.py").write_text('print("example")\n')
        subprocess.run(["git", "-C", str(self.root), "add", "example.py"], check=True)

    def test_fresh_and_repeated_setup_preserve_settings_bank_and_registration(self):
        first = initialize_project(self.root, "cursor", "bm25", "hash", True)
        self.assertTrue(first["user_config"]["created"])
        self.assertTrue(first["mcp"]["changed"])
        config = self.root / ".agemem/config.json"
        original = config.read_text()
        bank = self.root / "memory/activeContext.md"
        bank.write_text("# Our actual context\n")
        user = config_path().read_text().replace("default_provider: jev", "default_provider: qsiv")
        config_path().write_text(user)
        mcp = self.root / ".cursor/mcp.json"
        modified = mcp.stat().st_mtime_ns
        second = initialize_project(self.root, "cursor", "hybrid", "not-downloaded", True)
        self.assertFalse(second["user_config"]["created"])
        self.assertFalse(second["mcp"]["changed"])
        self.assertEqual(second["initialization"]["created"], [])
        self.assertEqual(config.read_text(), original)
        self.assertEqual(bank.read_text(), "# Our actual context\n")
        self.assertEqual(config_path().read_text(), user)
        self.assertEqual(mcp.stat().st_mtime_ns, modified)

    def test_invalid_schema_stops_before_project_creation(self):
        config_path().write_text("version: 2\n")
        with self.assertRaisesRegex(ValueError, "Unsupported config.yaml version"):
            initialize_project(self.root, "cursor", "bm25", "hash", True)
        self.assertFalse((self.root / ".agemem").exists())

    def test_cli_single_command(self):
        command = [sys.executable, "-m", "agemem.cli"]
        completed = subprocess.run([*command, "--offline", "project", "init", "--client", "claude-code", "--retrieval", "bm25", "--embedder", "hash"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["project"], str(self.root))
        self.assertTrue((self.root / ".mcp.json").exists())
        hook_file = self.root / ".claude/settings.local.json"
        self.assertTrue(hook_file.exists())
        first = hook_file.read_text()
        repeated = subprocess.run([*command, "--offline", "project", "init", "--client", "claude-code", "--retrieval", "bm25", "--embedder", "hash"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(hook_file.read_text(), first)

    def test_cli_no_hooks_skips_installation(self):
        completed = subprocess.run([sys.executable, "-m", "agemem.cli", "--offline", "project", "init", "--client", "claude-code", "--no-hooks", "--retrieval", "bm25", "--embedder", "hash"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["hooks"], [])
        self.assertFalse((self.root / ".claude/settings.local.json").exists())
        self.assertTrue((self.root / ".mcp.json").exists())

    def test_jev_key_is_private_and_absent_from_output(self):
        import stat
        with patch("sys.stdin.isatty", return_value=True), patch("agemem.setup.platform.system", return_value="Darwin"), patch("agemem.setup.getpass.getpass", return_value='secret: "quoted"'):
            result = initialize_project(self.root, "cursor", "bm25", "hash")
        self.assertEqual(load_user_config()["providers"]["jev"]["api_key"], 'secret: "quoted"')
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(config_path().stat().st_mode), 0o600)
        self.assertNotIn("secret", json.dumps(result))
        self.assertFalse(any("Configure the selected" in step for step in result["next_steps"]))

    def test_gpu_selection_installs_and_selects_qsiv(self):
        with patch("sys.stdin.isatty", return_value=True), patch("agemem.setup.platform.system", return_value="Linux"), patch("agemem.setup.platform.machine", return_value="x86_64"), patch("agemem.providers._gpu_preflight", return_value=[{}]), patch("builtins.input", return_value="qsiv"), patch("agemem.providers.setup_qsiv") as setup, patch("agemem.setup.getpass.getpass") as password:
            configure_provider()
        setup.assert_called_once_with()
        password.assert_not_called()
        self.assertEqual(load_user_config()["default_provider"], "qsiv")

    def test_failed_gpu_setup_does_not_save_selection(self):
        with patch("sys.stdin.isatty", return_value=True), patch("agemem.setup.platform.system", return_value="Linux"), patch("agemem.setup.platform.machine", return_value="x86_64"), patch("agemem.providers._gpu_preflight", return_value=[{}]), patch("builtins.input", return_value="qsiv"), patch("agemem.providers.setup_qsiv", side_effect=ValueError("install failed")):
            with self.assertRaises(ValueError):
                configure_provider()
        self.assertFalse(config_path().exists())

    def test_no_compatible_gpu_skips_choice_and_uses_environment_key(self):
        with patch.dict(os.environ, {"JEV_API_KEY": "env-secret"}), patch("sys.stdin.isatty", return_value=True), patch("agemem.setup.platform.system", return_value="Linux"), patch("agemem.setup.platform.machine", return_value="x86_64"), patch("agemem.providers._gpu_preflight", side_effect=ValueError("no gpu")), patch("builtins.input") as choice, patch("agemem.setup.getpass.getpass") as password:
            configure_provider()
        choice.assert_not_called()
        password.assert_not_called()
        self.assertIsNone(load_user_config()["providers"]["jev"]["api_key"])
        self.assertNotIn("env-secret", config_path().read_text())

    def test_existing_config_preserved_without_prompts_or_probe(self):
        config_path().write_text("version: 1\ndefault_provider: qsiv\n")
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input") as choice, patch("agemem.providers._gpu_preflight") as gpu, patch("agemem.setup.getpass.getpass") as password:
            self.assertFalse(configure_provider()["created"])
        choice.assert_not_called()
        gpu.assert_not_called()
        password.assert_not_called()

    def test_offline_does_not_prompt_or_install(self):
        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input") as choice, patch("agemem.providers.setup_qsiv") as setup, patch("agemem.setup.getpass.getpass") as password:
            configure_provider(offline=True)
        choice.assert_not_called()
        setup.assert_not_called()
        password.assert_not_called()


    def test_explicit_multiple_clients_never_prompt(self):
        with patch.dict(os.environ, {"JEV_API_KEY": "env-secret"}), patch("sys.stdin.isatty", return_value=True), patch("builtins.input") as choice, patch("agemem.setup.getpass.getpass") as password:
            result = initialize_project(self.root, retrieval="bm25", embedder="hash", model="jev", clients=["cursor", "claude", "cursor"], no_input=True)
        choice.assert_not_called()
        password.assert_not_called()
        self.assertEqual([item["client"] for item in result["mcp"]], ["cursor", "claude-code"])
        self.assertTrue((self.root / ".cursor/mcp.json").exists())
        self.assertTrue((self.root / ".mcp.json").exists())
        self.assertNotIn("env-secret", json.dumps(result))
        self.assertNotIn("env-secret", config_path().read_text())

    def test_explicit_jev_missing_key_fails_before_writes(self):
        with patch("builtins.input") as choice, self.assertRaisesRegex(ValueError, "requires an API key"):
            initialize_project(self.root, model="jev", clients=["cursor"], no_input=True)
        choice.assert_not_called()
        self.assertFalse(config_path().exists())
        self.assertFalse((self.root / ".agemem").exists())

    def test_explicit_qsiv_runs_setup_without_prompt(self):
        with patch("builtins.input") as choice, patch("agemem.providers.setup_qsiv") as setup:
            result = initialize_project(self.root, retrieval="bm25", embedder="hash", model="qsiv", clients=["cursor"], no_input=True)
        choice.assert_not_called()
        setup.assert_called_once()
        self.assertEqual(load_user_config()["default_provider"], "qsiv")
        self.assertEqual(result["initialization"]["decision_backend"], "qsiv")

    def test_explicit_model_preserves_conflicting_existing_config(self):
        config_path().write_text("version: 1\ndefault_provider: qsiv\n")
        original = config_path().read_text()
        with self.assertRaisesRegex(ValueError, "differs from existing"):
            initialize_project(self.root, model="jev", clients=["cursor"], no_input=True)
        self.assertEqual(config_path().read_text(), original)

    def test_no_input_missing_choices_fails_without_prompt(self):
        with patch("builtins.input") as choice:
            with self.assertRaisesRegex(ValueError, "requires --mcp"):
                initialize_project(self.root, no_input=True)
            with self.assertRaisesRegex(ValueError, "requires --model"):
                initialize_project(self.root, clients=["cursor"], no_input=True)
        choice.assert_not_called()
        self.assertFalse(config_path().exists())

    def test_explicit_cli_multiple_clients(self):
        command = [sys.executable, "-m", "agemem.cli"]
        with patch.dict(os.environ, {"JEV_API_KEY": "env-secret"}):
            completed = subprocess.run([*command, "project", "init", "--model", "jev", "--mcp", "cursor", "claude", "--no-input", "--retrieval", "bm25", "--embedder", "hash"], cwd=self.root, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(len(json.loads(completed.stdout)["mcp"]), 2)
        self.assertNotIn("env-secret", completed.stdout + completed.stderr)


    @unittest.skipIf(os.name == "nt", "POSIX symlink contract")
    def test_dangling_config_symlink_cannot_write_outside_project(self):
        from agemem.project import initialize
        with tempfile.TemporaryDirectory() as outside:
            folder = self.root / ".agemem"
            folder.mkdir()
            target = Path(outside) / "config.json"
            (folder / "config.json").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "escapes"):
                initialize(self.root, "bm25", "hash")
            self.assertFalse(target.exists())

    def test_explicit_qsiv_rejects_reference_runtime_before_downloads(self):
        config_path().write_text("version: 1\ndefault_provider: qsiv\nproviders:\n  qsiv:\n    runtime: reference\n")
        with patch("agemem.providers.setup_qsiv") as setup, self.assertRaisesRegex(ValueError, "fp8 only"):
            configure_provider(model="qsiv", no_input=True)
        setup.assert_not_called()
