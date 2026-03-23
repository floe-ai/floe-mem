#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from memory_service import MemoryService, ServiceConfig


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic memory workflow helper")
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--objective", required=True)
    ap.add_argument("--profile", default="implementer")
    ap.add_argument("--token-budget", type=int)
    ap.add_argument("--register", action="append", default=[], help="paths to register before indexing")
    args = ap.parse_args()

    svc = MemoryService(
        ServiceConfig(
            repo_id=args.repo_id,
            repo_root=Path(args.repo_root).resolve(),
            db_path=Path(args.db).resolve(),
        )
    )

    try:
        for locator in args.register:
            svc.register_document(
                locator=locator,
                kind="doc",
            )

        idx = svc.index(
            scope="delta",
            reason="workflow_refresh",
        )

        search = svc.search(
            query=args.objective,
            limit=20,
        )

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


if __name__ == "__main__":
    raise SystemExit(main())
