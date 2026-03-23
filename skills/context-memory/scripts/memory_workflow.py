#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_memory(entry: Path, args: list[str]) -> dict:
    cmd = [sys.executable, str(entry), *args]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "memory command failed")
    return json.loads(proc.stdout)


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

    skill_dir = Path(__file__).resolve().parents[1]
    repo_base = (skill_dir / ".." / "..").resolve()
    entry = repo_base / "scripts" / "memory.py"
    if not entry.exists():
        print("error: scripts/memory.py not found", file=sys.stderr)
        return 2

    try:
        for locator in args.register:
            run_memory(
                entry,
                [
                    "--repo-id",
                    args.repo_id,
                    "--repo-root",
                    args.repo_root,
                    "--db",
                    args.db,
                    "register_document",
                    "--locator",
                    locator,
                    "--kind",
                    "doc",
                ],
            )

        idx = run_memory(
            entry,
            [
                "--repo-id",
                args.repo_id,
                "--repo-root",
                args.repo_root,
                "--db",
                args.db,
                "index",
                "--scope",
                "delta",
                "--reason",
                "workflow_refresh",
            ],
        )

        search = run_memory(
            entry,
            [
                "--repo-id",
                args.repo_id,
                "--repo-root",
                args.repo_root,
                "--db",
                args.db,
                "search",
                "--query",
                args.objective,
                "--limit",
                "20",
            ],
        )

        bundle_args = [
            "--repo-id",
            args.repo_id,
            "--repo-root",
            args.repo_root,
            "--db",
            args.db,
            "build_context_bundle",
            "--objective",
            args.objective,
            "--profile",
            args.profile,
        ]
        if args.token_budget is not None:
            bundle_args.extend(["--token-budget", str(args.token_budget)])
        bundle = run_memory(entry, bundle_args)

        print(
            json.dumps(
                {
                    "ok": True,
                    "index": idx.get("result"),
                    "search_top": search.get("result", {}).get("results", [])[:5],
                    "bundle": bundle.get("result"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
