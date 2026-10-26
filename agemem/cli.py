"""User-facing project setup and live memory commands."""
import argparse
import json
import sys
from pathlib import Path

from .engine import Engine
from .project import initialize
from .config import initialize_user_config, doctor, provider_options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="Project checkout to use")
    parser.add_argument("--offline", action="store_true", help="Never use hosted decisions or download embedding weights")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("config", help="Manage user configuration")
    p.add_subparsers(dest="config_command", required=True).add_parser("init", help="Create a private YAML template without overwriting existing settings")
    p = sub.add_parser("provider", help="Set up optional local providers")
    provider_sub = p.add_subparsers(dest="provider_command", required=True)
    setup = provider_sub.add_parser("setup", help="Explicitly download models and install an isolated runtime")
    setup.add_argument("provider_name", choices=["qsiv"])
    setup.add_argument("--model-directory", type=Path)
    setup.add_argument("--runtime-directory", type=Path)
    setup.add_argument("--dry-run", action="store_true", help="Show actions without downloads or filesystem changes")
    sub.add_parser("doctor", help="Check provider setup without inference or API calls")
    p = sub.add_parser("init", help="Create missing bank/config files; preserve existing memory")
    p.add_argument("--retrieval", choices=["hybrid", "bm25", "raw-rag"], default="hybrid")
    p.add_argument("--embedder", default="BAAI/bge-small-en-v1.5")
    sub.add_parser("index", help="Snapshot selected tracked project files; no hosted calls")
    p = sub.add_parser("capture", help="Archive original text as untrusted source evidence")
    p.add_argument("text")
    p.add_argument("--label", default="event")
    p.add_argument("--shared", action="store_true")
    p = sub.add_parser("remember", help="Write a durable note through jev-mem's actual screens")
    p.add_argument("text")
    p.add_argument("--source-id")
    p.add_argument("--shared", action="store_true")
    p = sub.add_parser("recall", help="Read current bank, recall notes, and retrieve source evidence live")
    p.add_argument("query")
    p.add_argument("--budget", type=int)
    p.add_argument("--history", action="store_true", help="Also search older file snapshots on this branch")
    sub.add_parser("maintain", help="Screen pending notes and run jev-mem consolidation")
    sub.add_parser("mcp", help="Run the project's MCP server over stdio")
    args = parser.parse_args()
    try:
        if args.command == "config":
            result = initialize_user_config()
        elif args.command == "provider":
            from .providers import setup_qsiv
            options = provider_options({})
            if options["qsiv_runtime"] != "fp8":
                raise ValueError("Automatic QSIV setup currently supports runtime fp8 only")
            runtime_python = options.get("qsiv_python")
            runtime_directory = args.runtime_directory or (Path(runtime_python).parent.parent if runtime_python else None)
            result = setup_qsiv(directory=args.model_directory or options.get("qsiv_directory"),
                                runtime_directory=runtime_directory, dry_run=args.dry_run)
        elif args.command == "doctor":
            result = doctor(args.project)
        elif args.command == "init":
            result = initialize(args.project, args.retrieval, args.embedder)
        elif args.command == "mcp":
            from .mcp import serve
            serve(args.project, args.offline)
            return
        else:
            engine = Engine(args.project, args.offline)
            try:
                if args.command == "index":
                    result = engine.index()
                elif args.command == "capture":
                    result = engine.capture(args.text, args.label, args.shared)
                elif args.command == "remember":
                    result = engine.remember(args.text, args.source_id, args.shared)
                elif args.command == "recall":
                    result = engine.recall(args.query, args.budget, args.history)
                else:
                    result = engine.maintain()
            finally:
                engine.close()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if args.command == "doctor" and not result["ok"]:
            raise SystemExit(1)
    except Exception as exc:
        # Do not echo SDK exception bodies, key-bearing URLs or supplied source text.
        message = str(exc) if isinstance(exc, ValueError) else "See installation/runtime diagnostics; provider details omitted"
        print(json.dumps({"error": type(exc).__name__, "message": message}), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
