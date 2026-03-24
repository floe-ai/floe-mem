#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

INSTALL_META_FILENAME = ".memory_skill_install.json"


def normalize_global_flags(
    tool_args: list[str],
    repo_id: str,
    repo_root: str,
    db: str,
    enable_vector: bool,
) -> tuple[list[str], str, str, str, bool]:
    remaining: list[str] = []
    i = 0
    while i < len(tool_args):
        token = tool_args[i]
        if token == "--repo-id" and i + 1 < len(tool_args):
            repo_id = tool_args[i + 1]
            i += 2
            continue
        if token == "--repo-root" and i + 1 < len(tool_args):
            repo_root = tool_args[i + 1]
            i += 2
            continue
        if token == "--db" and i + 1 < len(tool_args):
            db = tool_args[i + 1]
            i += 2
            continue
        if token == "--enable-vector":
            enable_vector = True
            i += 1
            continue
        remaining.append(token)
        i += 1
    return remaining, repo_id, repo_root, db, enable_vector


def _resolve_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    skill_dir = script_path.parents[1]
    meta_path = skill_dir / INSTALL_META_FILENAME
    if meta_path.exists():
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            source = data.get("source_repo_root")
            if source:
                candidate = Path(str(source)).expanduser().resolve()
                if (candidate / "tools" / "memory_service").exists():
                    return candidate
        except Exception:
            pass

    for parent in script_path.parents:
        if (parent / "tools" / "memory_service").exists() and (parent / "pyproject.toml").exists():
            return parent

    raise RuntimeError("unable to locate source repo root for memory-skill-runner")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Skill-local entrypoint for repo memory tools",
    )
    ap.add_argument("tool", help="memory tool command, e.g. search, index, build_context_bundle")
    ap.add_argument("tool_args", nargs=argparse.REMAINDER, help="arguments forwarded to memory CLI")
    ap.add_argument("--repo-id", default="default")
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--db", default=".ai/memory/memory.db")
    ap.add_argument("--enable-vector", action="store_true")
    args = ap.parse_args()

    normalized_tool_args, repo_id, repo_root, db, enable_vector = normalize_global_flags(
        tool_args=args.tool_args,
        repo_id=args.repo_id,
        repo_root=args.repo_root,
        db=args.db,
        enable_vector=bool(args.enable_vector),
    )

    runner_argv = [
        "uv",
        "run",
        "--directory",
        str(_resolve_repo_root()),
        "memory-skill-runner",
        "--repo-id",
        repo_id,
        "--repo-root",
        repo_root,
        "--db",
        db,
        args.tool,
    ]
    if enable_vector:
        runner_argv.append("--enable-vector")
    if normalized_tool_args:
        runner_argv.extend(normalized_tool_args)

    proc = subprocess.run(runner_argv)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
