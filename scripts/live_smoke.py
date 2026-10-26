"""Exercise the real persistent layered path on a disposable synthetic git project."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from agemem.engine import Engine
from agemem.project import initialize


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", choices=["jev", "qsiv"], default="jev")
    p.add_argument("--model-dir")
    p.add_argument("--runtime", default="fp8")
    p.add_argument("--raw-checkout")
    p.add_argument("--output", required=True)
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix="agemem-live-") as folder:
        root = Path(folder)
        subprocess.run(["git", "init", "-b", "main", folder], check=True, capture_output=True)
        initialize(root)
        config = json.loads((root / ".agemem/config.json").read_text())
        config.update(decision_backend=args.backend, qsiv_directory=args.model_dir, qsiv_runtime=args.runtime)
        if args.raw_checkout:
            config.update(retrieval="raw-rag", raw_rag_directory=args.raw_checkout)
        (root / ".agemem/config.json").write_text(json.dumps(config))
        (root / "memory/activeContext.md").write_text("Current blocker: staging webhook signature mismatch. Next: reproduce the recorded staging payload.")
        (root / "README.md").write_text("Atlas deploys with Ansible because Fabric could not resume failed runs.")
        subprocess.run(["git", "-C", folder, "add", "README.md"], check=True)
        engine = Engine(root, offline=args.backend == "qsiv")
        indexed = engine.index()
        source = engine.capture("On October 12 Atlas's ledger worker was renamed to tally. Its responsibility did not change. The ledger worker serializes settlement jobs because the upstream API rejects concurrent writes.", "incident-history")
        writes = [engine.remember("On October 12 Atlas renamed its ledger worker to tally.", source["source_id"]),
                  engine.remember("The ledger worker serializes settlement jobs because the upstream API rejects concurrent writes.", source["source_id"])]
        result = engine.recall("Why must tally serialize settlement jobs, and what is the current blocker?")
        assert result["layers"]["bank"] and result["layers"]["notes"] and result["layers"]["sources"]
        assert "signature mismatch" in result["context"] and "rejects concurrent writes" in result["context"]
        assert not any(w["rejected"] or w["degraded"] for w in writes)
        output = {"backend": args.backend, "status": "passed", "indexed": indexed, "writes": writes,
                  "recall": result, "project_kind": "disposable synthetic fixture", "calls": getattr(engine.decider, "calls", 0),
                  "input_tokens": getattr(engine.decider, "input_tokens", 0)}
        engine.close()
        # Reopen from disk with hosted calls disabled: originals and bank still work.
        # For QSIV this also exercises persistence without changing provider semantics.
        if args.backend == "jev":
            # Offline provider guarantee currently covers hybrid/BM25, not upstream setup.
            config["retrieval"] = "hybrid"
            (root / ".agemem/config.json").write_text(json.dumps(config))
            reopened = Engine(root, offline=True)
            output["offline_reopen"] = reopened.recall("tally settlement blocker")
            reopened.close()
        Path(args.output).write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"status": "passed", "backend": args.backend, "calls": output["calls"],
                          "input_tokens": output["input_tokens"], "context_units": result["context_units"]}))


if __name__ == "__main__":
    main()
