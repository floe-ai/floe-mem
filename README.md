# Floe Memory

Repo-local memory continuity for coding agents, installed through the shared
`floe-boot` bootstrap flow.

## Prerequisites

Install [Bun](https://bun.sh):

```bash
curl -fsSL https://bun.sh/install | bash
```

```powershell
powershell -c "irm bun.sh/install.ps1 | iex"
```

## Install

Primary install command:

```bash
bunx github:floe-ai/floe-mem
```

Package-manager install:

```bash
npm install git+github:floe-ai/floe-mem
```

This installs:

- the canonical runtime into `.floe/memory/`
- duplicated agent skill markdown into the selected targets under `.agents/`, `.github/`, and `.claude/`

When you install from an interactive terminal, the installer prompts for target
selection. If you omit `--target` in non-interactive mode, all supported
targets for the selected mode are installed.

Useful flags:

```bash
bunx github:floe-ai/floe-mem --mode project --target codex --yes
bunx github:floe-ai/floe-mem --mode global --target codex --target claude --yes
```

Local repo usage:

```bash
bun run install:bootstrap
```

## Memory Commands

From a project root, run:

```bash
bun run .floe/memory/scripts/memory.ts <command> [args]
```

Common commands:

| Command | What it does |
|---------|-------------|
| `bun run .floe/memory/scripts/memory.ts recall "<query>"` | Search memory for relevant context |
| `bun run .floe/memory/scripts/memory.ts context "<objective>"` | Build a context bundle for a task |
| `bun run .floe/memory/scripts/memory.ts save "<text>" --type <type> --tags <tags>` | Save a memory |
| `bun run .floe/memory/scripts/memory.ts deprecate <memory-id> [--replacement <memory-id>]` | Mark a memory deprecated, optionally linked to its replacement |
| `bun run .floe/memory/scripts/memory.ts duplicate-audit` | Surface likely duplicate/merge candidates (non-mutating) |
| `bun run .floe/memory/scripts/memory.ts remember <file> [file...]` | Register and index file(s) |
| `bun run .floe/memory/scripts/memory.ts status` | Show memory overview |

By default, `recall` and `context` hide retired memories (deprecated or superseded).
Use `--include-retired` when you need historical results.

Memory types: `decision`, `pattern`, `issue`, `learning`, `preference`, `constraint`.

For a global install, use:

```bash
bun run ~/.floe/memory/scripts/memory.ts <command> [args]
```

## Runtime Model

- Canonical shipped files live under `floe/`.
- The installed runtime lives under `.floe/memory/`.
- Agent-facing `SKILL.md` files are duplicated into the selected dotfolders.
- The memory database lives at `.floe/memory/memory.db` in the active project root.

## Tests

```bash
bun test
```
