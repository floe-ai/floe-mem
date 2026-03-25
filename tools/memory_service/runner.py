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

SIMPLE_COMMANDS = {"save", "recall", "status", "remember", "context"}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("error: expected memory tool command", file=sys.stderr)
        print(
            "usage: memory-skill-runner <command> [args...]",
            file=sys.stderr,
        )
        print(
            "commands: save, recall, status, remember, context (simplified)",
            file=sys.stderr,
        )
        print(
            "          register_document, upsert_memory_record, link_records, index, search, build_context_bundle (full API)",
            file=sys.stderr,
        )
        return 2

    first = argv[0]
    if first in TOOL_COMMANDS or first in SIMPLE_COMMANDS:
        return cli_run(argv)
    if any(token in TOOL_COMMANDS or token in SIMPLE_COMMANDS for token in argv):
        return cli_run(argv)

    print(f"error: unsupported runner command '{first}'", file=sys.stderr)
    print(
        "usage: memory-skill-runner <command> [args...]",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
