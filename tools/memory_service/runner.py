from __future__ import annotations

import sys

from .cli import COMMANDS, run as cli_run

VALID_COMMANDS = set(COMMANDS)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: memory-skill-runner <command> [args...]", file=sys.stderr)
        print(f"commands: {', '.join(sorted(VALID_COMMANDS))}", file=sys.stderr)
        return 2

    if argv[0] in VALID_COMMANDS or any(t in VALID_COMMANDS for t in argv):
        return cli_run(argv)

    print(f"error: unknown command '{argv[0]}'", file=sys.stderr)
    print(f"commands: {', '.join(sorted(VALID_COMMANDS))}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
