#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

INSTALL_META_FILENAME = ".memory_skill_install.json"


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
    # This wrapper keeps skill execution stable across copied and symlinked installs.
    runner_argv = [
        "uv",
        "run",
        "--directory",
        str(_resolve_repo_root()),
        "memory-skill-runner",
        "workflow",
    ]
    runner_argv.extend(sys.argv[1:])
    proc = subprocess.run(runner_argv)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
