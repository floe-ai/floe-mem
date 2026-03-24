#!/usr/bin/env python3
from __future__ import annotations

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
    # This wrapper keeps skill execution stable for snapshot-copied installs.
    runner_argv = [
        "uv",
        "run",
        "--directory",
        str(_resolve_repo_root()),
        "python",
        "-m",
        "tools.memory_service.runner",
        "workflow",
    ]
    runner_argv.extend(sys.argv[1:])
    proc = subprocess.run(runner_argv)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
