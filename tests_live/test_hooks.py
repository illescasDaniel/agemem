import contextlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agemem.engine import Engine
from agemem.hooks import context, install, run
from agemem.notes.store import Store, HashEmbedder
from agemem.project import initialize


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="agemem hooks ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.root)], check=True)
        initialize(self.root, "bm25", "hash")
        self.engine = Engine(self.root, offline=True)
        self.source = self.engine.capture("Atlas deploys using Ansible and verifies staging signatures.")["source_id"]
        self.scope = self.engine.scope()
        self.engine.close()
        self.payload = {"cwd": str(self.root), "prompt": "How does Atlas deploy using Ansible?"}

    def test_session_bank_and_prompt_source_context_use_no_models_and_write_nothing(self):
        database = self.root / ".agemem/local/sources.sqlite"
        before = database.read_bytes()
        with patch("agemem.engine.Engine", side_effect=AssertionError("No runtime provider in hooks")):
            session = context(self.root, "session-start", self.payload)
            prompt = context(self.root, "user-prompt", self.payload)
        self.assertIn("bank:activeContext.md", session)
        self.assertIn(self.source, prompt)
        self.assertIn("Ansible", prompt)
        self.assertIn("untrusted", prompt)
        self.assertEqual(database.read_bytes(), before)
        self.assertFalse((self.root / ".agemem/local/notes.sqlite").exists())

    def test_only_screened_current_and_shared_notes_are_injected(self):
        store = Store(str(self.root / ".agemem/local/notes.sqlite"), embedder=HashEmbedder(), index="matrix")
        for name, scope, state in (("Current Ansible rule", self.scope, "valid"),
                                   ("Shared Ansible rule", self.scope.rsplit(':', 1)[0] + ':shared', "valid"),
                                   ("Pending Ansible rule", self.scope, "pending"),
                                   ("Stale Ansible rule", self.scope, "stale"),
                                   ("Other Ansible rule", "project:other:main", "valid")):
            identifier = store.add_node(name, scope=scope, source=self.source)
            store.set_type_scores(identifier, {"convention": .95})
            if state == 'pending':
                store.queue_pending(identifier, "unscreened")
            if state == 'stale':
                store.add_flag(identifier, 'superseded_by', identifier, 1)
        store.db.close()
        text = context(self.root, "user-prompt", self.payload)
        self.assertIn("Current Ansible", text)
        self.assertIn("Shared Ansible", text)
        for hidden in ("Pending Ansible", "Stale Ansible", "Other Ansible"):
            self.assertNotIn(hidden, text)

    def test_other_cwd_or_event_is_ignored(self):
        self.assertIsNone(context(self.root, "session-start", {"cwd": str(self.root.parent)}))
        self.assertIsNone(context(self.root, "session-start", {**self.payload, "hook_event_name": "Stop"}))
        self.assertIsNone(context(self.root, "session-start", []))

    def test_malformed_and_oversize_input_fail_open_without_echo(self):
        for payload in ('{"prompt":"private-secret"', 'x' * 65537):
            output, error = io.StringIO(), io.StringIO()
            with patch('sys.stdin', io.StringIO(payload)), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
                run(self.root, "session-start")
            self.assertEqual(output.getvalue(), '')
            self.assertNotIn('private-secret', error.getvalue())

    def test_valid_hook_output_contract(self):
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(json.dumps(self.payload))), contextlib.redirect_stdout(output):
            run(self.root, 'session-start')
        result = json.loads(output.getvalue())
        self.assertEqual(result['hookSpecificOutput']['hookEventName'], 'SessionStart')
        self.assertNotIn('decision', result)
        self.assertNotIn('continue', result)

    def test_install_preserves_other_settings_and_is_idempotent(self):
        for client, relative in [('claude', '.claude/settings.json'), ('codex', '.codex/hooks.json')]:
            path = self.root / relative
            path.parent.mkdir(exist_ok=True)
            existing = {'permissions': {'allow': ['Read']}, 'hooks': {'SessionStart': [{'hooks': [{'type': 'command', 'command': 'echo unrelated'}]}]}}
            path.write_text(json.dumps(existing))
            result = install(self.root, [client], executable=Path(sys.executable))
            original = path.read_text()
            self.assertTrue(result[0]['changed'])
            self.assertFalse(install(self.root, [client], executable=Path(sys.executable))[0]['changed'])
            self.assertEqual(path.read_text(), original)
            data = json.loads(original)
            self.assertEqual(data['permissions'], existing['permissions'])
            self.assertEqual(data['hooks']['SessionStart'][0], existing['hooks']['SessionStart'][0])
            command = data['hooks']['SessionStart'][1]['hooks'][0]['command']
            tokens = shlex.split(command.split(' # agemem:')[0])
            self.assertNotIn('--project', tokens)
            self.assertNotIn(str(self.root), command)
            self.assertEqual(tokens[-2:], ['hook', 'session-start'])

    def test_dry_run_and_invalid_configuration_preserved(self):
        install(self.root, ['claude'], dry_run=True)
        self.assertFalse((self.root / '.claude').exists())
        path = self.root / '.codex/hooks.json'
        path.parent.mkdir()
        path.write_text('{bad')
        with self.assertRaises(ValueError):
            install(self.root, ['codex'])
        self.assertEqual(path.read_text(), '{bad')

    @unittest.skipIf(os.name == 'nt', 'POSIX symlink contract')
    def test_hook_directory_cannot_escape_project(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '.claude').symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'escapes'):
                install(self.root, ['claude'])
            self.assertFalse((Path(outside) / 'settings.json').exists())

    def test_installed_executable_mcp_launcher_does_not_need_pypi(self):
        from agemem.mcp_install import install as install_mcp
        result = install_mcp(self.root, 'cursor', executable=Path(sys.executable))
        self.assertEqual(result['launcher']['command'], str(Path(sys.executable).resolve()))
        self.assertNotIn('agemem@0.2.0', result['launcher']['args'])


    @unittest.skipIf(os.name == 'nt', 'POSIX hook shell execution; Windows requires Git Bash')
    def test_generated_hook_command_runs_the_installed_cli(self):
        executable = Path(sys.executable).parent / 'agemem'
        self.assertTrue(executable.is_file())
        result = install(self.root, ['claude'], executable=executable)
        settings = json.loads(Path(result[0]['path']).read_text())
        command = settings['hooks']['UserPromptSubmit'][0]['hooks'][0]['command']
        completed = subprocess.run(command, shell=True, input=json.dumps(self.payload), capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertIn(self.source, output['hookSpecificOutput']['additionalContext'])
