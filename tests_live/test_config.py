import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agemem.config import config_path, doctor, initialize_user_config, provider_options, load_user_config
from agemem.project import configuration, initialize


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.environment = patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "config"),
                                                  "XDG_DATA_HOME": str(self.root / "data"), "PATH": os.environ.get("PATH", ""), "USERPROFILE": os.environ.get("USERPROFILE", str(Path.home())), "SYSTEMROOT": os.environ.get("SYSTEMROOT", "")}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.temp.cleanup)

    def write_user(self, text):
        config_path().parent.mkdir(parents=True, exist_ok=True)
        config_path().write_text(text)

    def test_private_template_preserves_existing_config(self):
        result = initialize_user_config()
        self.assertTrue(result["created"])
        self.assertEqual(load_user_config()["version"], 1)
        self.assertIn("Options: jev, qsiv, cascade", config_path().read_text())
        if os.name != "nt":
            self.assertEqual(stat.S_IMODE(config_path().stat().st_mode), 0o600)
        self.write_user("default_provider: qsiv\n")
        self.assertFalse(initialize_user_config()["created"])
        self.assertEqual(provider_options({})["decision_backend"], "qsiv")

    def test_schema_version_validation_and_legacy_compatibility(self):
        for version in ("2", "0", "true", "1.0", '"1"', "null"):
            self.write_user("version: " + version + "\n")
            with self.assertRaisesRegex(ValueError, "Unsupported config.yaml version"):
                load_user_config()
        for content in ("version: 1\n", "default_provider: jev\n"):
            self.write_user(content)
            self.assertEqual(provider_options({})["decision_backend"], "jev")

    def test_new_projects_follow_global_and_legacy_provider_remains(self):
        self.write_user("default_provider: qsiv\nproviders:\n  qsiv:\n    model_directory: /tmp/example-model\n    runtime: reference\n")
        initialize(self.root, "bm25", "hash")
        saved = json.loads((self.root / ".agemem/config.json").read_text())
        self.assertNotIn("decision_backend", saved)
        self.assertEqual(configuration(self.root)["decision_backend"], "qsiv")
        self.assertEqual(configuration(self.root)["qsiv_runtime"], "reference")
        saved["decision_backend"] = "jev"
        (self.root / ".agemem/config.json").write_text(json.dumps(saved))
        self.assertEqual(configuration(self.root)["decision_backend"], "jev")
        with patch.dict(os.environ, {"AGEMEM_PROVIDER": "qsiv"}):
            self.assertEqual(configuration(self.root)["decision_backend"], "qsiv")

    def test_credentials_never_saved_or_printed_and_env_overrides(self):
        self.write_user("providers:\n  jev:\n    api_key: private-yaml-token\n")
        initialize(self.root, "bm25", "hash")
        self.assertEqual(configuration(self.root)["jev_api_key"], "private-yaml-token")
        self.assertNotIn("private-yaml-token", (self.root / ".agemem/config.json").read_text())
        self.assertNotIn("private-yaml-token", json.dumps(doctor(self.root)))
        with patch.dict(os.environ, {"JEV_API_KEY": "environment-token"}):
            self.assertEqual(configuration(self.root)["jev_api_key"], "environment-token")

    def test_yaml_can_select_cascade_for_project(self):
        self.write_user("default_provider: cascade\n")
        initialize(self.root, "bm25", "hash")
        self.assertEqual(configuration(self.root)["decision_backend"], "cascade")
        self.assertEqual(configuration(self.root)["cascade_min_confidence"], 0.9)
        with patch.dict(os.environ, {"AGEMEM_PROVIDER": "jev"}):
            self.assertEqual(configuration(self.root)["decision_backend"], "jev")

    def test_runtime_python_is_discovered_from_xdg_install(self):
        runtime = self.root / "data/agemem/runtimes/qsiv/bin/python"
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        self.assertEqual(provider_options({})["qsiv_python"], str(runtime))
        with patch.dict(os.environ, {"AGEMEM_QSIV_PYTHON": "/other/python"}):
            self.assertEqual(provider_options({})["qsiv_python"], str(Path("/other/python")))

    def test_yaml_validation_and_errors_do_not_include_credentials(self):
        for content in ("[]", "default_provider: unknown", "providers: []", "providers:\n  jev: secret", "api_key: [private-secret"):
            self.write_user(content)
            with self.assertRaises(ValueError) as error:
                provider_options({})
            self.assertNotIn("private-secret", str(error.exception))

    def test_cli_doctor_reports_failure_without_credentials(self):
        from agemem.cli import main
        output = io.StringIO()
        with patch("sys.argv", ["agemem", "--project", str(self.root), "doctor"]), contextlib.redirect_stdout(output):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(json.loads(output.getvalue())["ok"])

    def test_cli_setup_respects_yaml_paths_and_does_not_select_provider(self):
        from agemem.cli import main
        self.write_user("providers:\n  qsiv:\n    model_directory: /custom/model\n    python: /custom/runtime/bin/python\n")
        output = io.StringIO()
        with patch("sys.argv", ["agemem", "provider", "setup", "qsiv", "--dry-run"]), contextlib.redirect_stdout(output), patch("agemem.providers.setup_qsiv", return_value={"dry_run": True}) as setup:
            main()
        setup.assert_called_once_with(directory=str(Path("/custom/model")), runtime_directory=Path("/custom/runtime"), dry_run=True)
        self.assertEqual(provider_options({})["decision_backend"], "jev")

    def test_doctor_passes_exact_selected_runtime_and_reports_ready(self):
        self.write_user("default_provider: qsiv\nproviders:\n  qsiv:\n    model_directory: " + str(self.root) + "\n    python: /custom/executable\n    runtime: reference\n")
        with patch("agemem.providers.qsiv_doctor", return_value={"ready": True}) as probe:
            self.assertTrue(doctor(self.root)["ok"])
        self.assertEqual(probe.call_args.kwargs["runtime_python"], str(Path("/custom/executable")))
        self.assertEqual(probe.call_args.kwargs["runtime"], "reference")

    def test_qsiv_default_paths_match_setup_and_doctor_uses_native_python(self):
        import sys
        self.write_user("default_provider: qsiv\n")
        options = provider_options({})
        expected = self.root / "data/agemem/models/qsiv"
        self.assertEqual(options["qsiv_directory"], str(expected))
        expected.mkdir(parents=True)
        with patch("agemem.providers.qsiv_doctor", return_value={"ready": True}) as probe:
            self.assertTrue(doctor(self.root)["ok"])
        self.assertEqual(probe.call_args.kwargs["runtime_python"], sys.executable)
        initialize(self.root, "bm25", "hash")
        with patch.dict(os.environ, {"AGEMEM_QSIV_DIR": "~/models/qsiv"}):
            self.assertEqual(configuration(self.root)["qsiv_directory"], str(Path.home() / "models/qsiv"))

    def test_jev_default_does_not_create_user_files(self):
        self.assertEqual(provider_options({})["decision_backend"], "jev")
        self.assertFalse(config_path().exists())
        self.assertFalse(doctor(self.root)["ok"])
        self.assertFalse(config_path().exists())


if __name__ == "__main__":
    unittest.main()
