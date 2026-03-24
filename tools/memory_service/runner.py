from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import MemoryService, ServiceConfig
from .cli import run as cli_run

TOOL_COMMANDS = {
    "register_document",
    "upsert_memory_record",
    "link_records",
    "index",
    "search",
    "build_context_bundle",
}


def _workflow(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Deterministic memory workflow helper")
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--enable-vector", action="store_true")
    ap.add_argument("--objective", required=True)
    ap.add_argument("--profile", default="implementer")
    ap.add_argument("--token-budget", type=int)
    ap.add_argument("--register", action="append", default=[], help="paths to register before indexing")
    args = ap.parse_args(argv)

    svc = MemoryService(
        ServiceConfig(
            repo_id=args.repo_id,
            repo_root=Path(args.repo_root).resolve(),
            db_path=Path(args.db).resolve(),
            enable_vector=bool(args.enable_vector),
        )
    )

    try:
        for locator in args.register:
            svc.register_document(locator=locator, kind="doc")

        idx = svc.index(scope="delta", reason="workflow_refresh")
        search = svc.search(query=args.objective, limit=20)
        bundle = svc.build_context_bundle(
            objective=args.objective,
            profile=args.profile,
            token_budget=args.token_budget,
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "index": idx,
                    "search_top": search.get("results", [])[:5],
                    "bundle": bundle,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        svc.close()


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("error: expected memory tool command or 'workflow'", file=sys.stderr)
        return 2

    first = argv[0]
    if first in TOOL_COMMANDS:
        return cli_run(argv)
    if any(token in TOOL_COMMANDS for token in argv):
        return cli_run(argv)
    if first == "workflow":
        return _workflow(argv[1:])

    print(f"error: unsupported runner command '{first}'", file=sys.stderr)
    print(
        "usage: memory-skill-runner <tool-command|workflow> [args...]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
