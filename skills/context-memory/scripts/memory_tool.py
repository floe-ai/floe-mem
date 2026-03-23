#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Skill-local wrapper for repo memory CLI",
    )
    ap.add_argument("tool", help="memory tool command, e.g. search, index, build_context_bundle")
    ap.add_argument("tool_args", nargs=argparse.REMAINDER, help="arguments forwarded to scripts/memory.py")
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--enable-vector", action="store_true")
    args = ap.parse_args()

    skill_dir = Path(__file__).resolve().parents[1]
    repo_root = (skill_dir / ".." / "..").resolve()
    entry = repo_root / "scripts" / "memory.py"
    if not entry.exists():
        print(
            "error: scripts/memory.py not found; ensure memory service is installed in repo",
            file=sys.stderr,
        )
        return 2

    cmd = [
        sys.executable,
        str(entry),
        "--repo-id",
        args.repo_id,
        "--repo-root",
        args.repo_root,
        "--db",
        args.db,
    ]
    if args.enable_vector:
        cmd.append("--enable-vector")
    cmd.append(args.tool)
    if args.tool_args:
        cmd.extend(args.tool_args)

    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.stderr:
        print(proc.stderr.strip(), file=sys.stderr)
    if proc.stdout:
        print(proc.stdout.strip())
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
