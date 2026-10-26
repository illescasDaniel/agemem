import json
import subprocess
import tempfile
import unittest
import os
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from amem_lab.core import TOKEN
from agemem.deciders import Disabled, HostedJev, QSIVDecider, CascadingDecider
from agemem.engine import Engine
from agemem.project import initialize
from jevmem.decider import Answer, ChoiceQ, DeciderUnavailable, FakeDecider, NoulQ


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-b", "main", str(self.root)], check=True, capture_output=True)
        initialize(self.root, "bm25", "hash")
        self.root.joinpath("README.md").write_text("Atlas uses Ansible for deployment because Fabric could not resume failed runs.")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_live_index_bank_source_note_and_restart(self):
        self.root.joinpath("memory/activeContext.md").write_text("Current blocker: staging signature mismatch. Next: reproduce the staging payload.")
        # FakeDecider is a contract test only; no quality conclusions use it.
        fake = FakeDecider(lambda state, key, q: 0 if key in ("injection", "status", "multi_hop", "temporal", "missing_evidence") else 0.9)
        engine = Engine(self.root, decider=fake)
        indexed = engine.index()
        self.assertGreater(indexed["indexed_files"], 0)
        source = next(r for r in engine._records() if "README.md" in r.source)
        result = engine.remember("Atlas deploys using Ansible.", source.id)
        self.assertFalse(result["rejected"])
        packet = engine.recall("How does Atlas deploy and what is the current blocker?")
        self.assertTrue(packet["layers"]["bank"])
        self.assertTrue(packet["layers"]["notes"])
        self.assertTrue(packet["layers"]["sources"])
        self.assertIn("Ansible", packet["context"])
        self.assertIn("signature mismatch", packet["context"])
        self.assertIsNone(packet["combined_sufficient"])
        engine.close()
        engine = Engine(self.root, offline=True)
        self.assertIn("Ansible", engine.recall("Atlas deployment")["context"])
        engine.close()

    def test_bank_is_live_without_reindex(self):
        engine = Engine(self.root, offline=True)
        self.root.joinpath("memory/activeContext.md").write_text("New blocker: queue backpressure.")
        self.assertIn("queue backpressure", engine.recall("current blocker")["context"])
        engine.close()

    def test_removed_files_do_not_return_from_current_manifest(self):
        engine = Engine(self.root, offline=True)
        engine.index()
        self.root.joinpath("README.md").unlink()
        engine.index()
        self.assertNotIn("Ansible", engine.recall("Atlas deployment")["context"])
        self.assertIn("Ansible", engine.recall("Atlas deployment", history=True)["context"])
        engine.close()

    def test_default_jev_is_disabled_offline_and_pending_notes_are_hidden(self):
        engine = Engine(self.root, offline=True)
        with patch("agemem.deciders.HostedJev", side_effect=AssertionError("Network backend constructed")):
            result = engine.remember("Atlas deploys with Ansible.")
            self.assertTrue(result["pending"])
            self.assertEqual(engine.recall("Ansible deployment")["layers"]["notes"], [])
        self.assertIsInstance(engine.decider, Disabled)
        engine.close()

    def test_project_and_branch_isolation(self):
        engine = Engine(self.root, offline=True)
        engine.capture("Atlas deploys with Ansible", "history")
        engine.close()
        subprocess.run(["git", "-C", str(self.root), "symbolic-ref", "HEAD", "refs/heads/feature"], check=True)
        engine = Engine(self.root, offline=True)
        self.assertEqual(engine.branch, "feature")
        self.assertNotIn("Ansible", engine.recall("Atlas deployment")["context"])
        engine.close()

    def test_credentials_never_enter_raw_archive(self):
        engine = Engine(self.root, offline=True)
        with self.assertRaises(ValueError):
            engine.capture("api_key = abcdefghijklmnopqrstuvwxyz")
        self.assertEqual(len(engine._records()), 0)
        engine.close()

    def test_note_cannot_cite_another_branch_or_promote_private_source(self):
        engine = Engine(self.root, offline=True)
        source = engine.capture("Atlas uses PostgreSQL")['source_id']
        with self.assertRaises(ValueError):
            engine.remember("Atlas uses PostgreSQL", source, shared=True)
        engine.close()
        subprocess.run(["git", "-C", str(self.root), "symbolic-ref", "HEAD", "refs/heads/other"], check=True)
        engine = Engine(self.root, offline=True)
        with self.assertRaises(ValueError):
            engine.remember("Atlas uses PostgreSQL", source)
        engine.close()

    def test_reinitialization_preserves_existing_bank(self):
        path = self.root / "memory/activeContext.md"
        path.write_text("Existing project context")
        initialize(self.root)
        self.assertEqual(path.read_text(), "Existing project context")

    def test_symlink_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            path = self.root / "memory/activeContext.md"
            path.unlink()
            path.symlink_to(Path(outside) / "context.md")
            with self.assertRaises(ValueError):
                initialize(self.root)

    def test_entire_context_is_within_budget(self):
        engine = Engine(self.root, offline=True)
        engine.capture("Atlas deployment " * 1000)
        result = engine.recall("Atlas deployment", budget=128)
        self.assertLessEqual(len(TOKEN.findall(result["context"])), 128)
        engine.close()

    def test_offline_raw_setup_is_explicitly_rejected(self):
        path = self.root / ".agemem/config.json"
        config = json.loads(path.read_text())
        config["retrieval"] = "raw-rag"
        path.write_text(json.dumps(config))
        engine = Engine(self.root, offline=True)
        with self.assertRaises(ValueError):
            engine.recall("deployment")
        engine.close()


class QSIVContractTests(unittest.TestCase):
    def test_ollaya_never_receives_hosted_key(self):
        with patch.dict(os.environ, {"JEV_API_KEY": "hosted-key-must-stay-local"}):
            with patch("typesafe_sdk.TypeSafeClient") as client:
                client.return_value.system_one.return_value = SimpleNamespace(
                    usage=SimpleNamespace(input_tokens=3), answers={"ok": SimpleNamespace(type="noul", noul=0.9)})
                backend = HostedJev(local_url="http://127.0.0.1:11435", model="jevk5:4b")
                backend.ask({}, {"ok": NoulQ("Is it okay?")})
                self.assertEqual(client.call_args.kwargs["api_key"], "unused-local")
                self.assertEqual(client.call_args.kwargs["base_url"], "http://127.0.0.1:11435")

    def test_offline_endpoint_must_be_loopback(self):
        with self.assertRaises(ValueError):
            HostedJev(local_url="https://example.com")

    def test_physical_batch_limit_preserves_keys_and_complete_state(self):
        seen = []
        def decide(request):
            seen.append(request)
            return [{"type": "noul", "p_true": 0.8} for q in request["questions"]]
        adapter = QSIVDecider(decide)
        state = {"goal": "abc", "items": ["one", "two"]}
        result = adapter.ask(state, {f"q{i}": NoulQ(f"Question {i}") for i in range(24)})
        self.assertEqual(len(result), 24)
        self.assertEqual([len(r["questions"]) for r in seen], [8, 8, 8])
        self.assertTrue(all(r["state"] == state for r in seen))
        self.assertEqual(adapter.calls, 3)
        self.assertEqual(adapter.logical_calls, 1)

    def test_choice_maps_back_to_original_labels(self):
        adapter = QSIVDecider(lambda r: [{"choice": 1, "probs": [0.2, 0.8]}])
        result = adapter.ask({}, {"route": ChoiceQ("Who?", {"coder": "writes code", "reviewer": "reviews"})})
        self.assertEqual(result["route"].choice, "reviewer")
        self.assertEqual(result["route"].probs, {"coder": 0.2, "reviewer": 0.8})

    def test_incomplete_or_invalid_answers_fail_closed(self):
        for response in ([], [{"p_true": float("nan")}], [{"p_true": 2}]):
            adapter = QSIVDecider(lambda r: response)
            with self.assertRaises(DeciderUnavailable):
                adapter.ask({}, {"q": NoulQ("Is this safe?")})


if __name__ == "__main__":
    unittest.main()

class CascadeTests(unittest.TestCase):
    def test_only_uncertain_questions_fall_back(self):
        class Local:
            calls = 1
            def ask(self, state, questions):
                return {"sure": Answer(p=.99), "uncertain": Answer(p=.6)}
        class Remote:
            calls = input_tokens = 0
            def ask(self, state, questions):
                self.keys = set(questions)
                self.calls += 1
                return {"uncertain": Answer(p=.95)}
        remote = Remote()
        cascade = CascadingDecider(Local(), remote, .9)
        result = cascade.ask({}, {k: NoulQ("True?") for k in ("sure", "uncertain")})
        self.assertEqual(remote.keys, {"uncertain"})
        self.assertEqual(result["sure"].p, .99)
        self.assertEqual(result["uncertain"].p, .95)
        self.assertEqual((cascade.kept_questions, cascade.fallback_questions), (1, 1))

    def test_uncertain_offline_does_not_silently_accept(self):
        class Local:
            calls = 1
            def ask(self, state, questions):
                return {"a": Answer(p=.5)}
        with self.assertRaises(DeciderUnavailable):
            CascadingDecider(Local(), Disabled()).ask({}, {"a": NoulQ("True?")})
