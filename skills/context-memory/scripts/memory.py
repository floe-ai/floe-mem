#!/usr/bin/env python3
"""Simplified memory interface for AI agents.

Usage (from project root):
    uv run scripts/memory.py save "We chose JWT for auth" --type decision --tags auth,api
    uv run scripts/memory.py recall "authentication approach"
    uv run scripts/memory.py status
    uv run scripts/memory.py remember docs/architecture.md
    uv run scripts/memory.py context "implement user login"
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _resolve_repo_root() -> Path:
    script_path = Path(__file__).resolve()
    for parent in script_path.parents:
        if (parent / "tools" / "memory_service").exists():
            return parent
    raise RuntimeError("unable to locate repo root containing tools/memory_service")


def main() -> int:
    repo_root = _resolve_repo_root()

    if len(sys.argv) < 2:
        print(json.dumps({
            "ok": False,
            "error": "no command provided",
            "usage": "uv run scripts/memory.py <save|recall|status|remember|context> [args]",
        }))
        return 2

    runner_argv = [
        "uv", "run",
        "--directory", str(repo_root),
        "python", "-m", "tools.memory_service.runner",
        "--repo-root", str(repo_root),
    ] + sys.argv[1:]

    try:
        proc = subprocess.run(runner_argv)
        return int(proc.returncode)
    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": "uv not found on PATH",
                          "hint": "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"}))
        return 1
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"unexpected error: {exc}"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
