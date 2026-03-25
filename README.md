# Repo-Local Memory Service

Standalone, database-backed memory continuity for coding agents.
Canonical project docs stay in-place; memory stores derived retrieval state.

## Prerequisites

1. Install [Bun](https://bun.sh):
```bash
curl -fsSL https://bun.sh/install | bash
```
2. For the installer, install [uv](https://docs.astral.sh/uv/):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## One-command install

Use `uvx` from GitHub:

```bash
uvx --from https://github.com/floe-ai/floe-mem.git install-memory-skills
```

Local-path equivalent:
```bash
uvx --from . install-memory-skills
```

The guided installer prompts for:
- target clients (`Codex`, `Copilot`, `Claude`)
- scope (`project` or `global`)
- confirmation of resolved install paths

Install behavior is snapshot-copy only.
It copies the skill directory (`SKILL.md` + `scripts/memory.ts`) into the selected targets.

## Memory commands

All commands run from the project root using `bun`:

| Command | What it does |
|---------|-------------|
| `bun run scripts/memory.ts recall "<query>"` | Search memory for relevant context |
| `bun run scripts/memory.ts context "<objective>"` | Build a context bundle for a task |
| `bun run scripts/memory.ts save "<text>" --type <type> --tags <tags>` | Save a memory |
| `bun run scripts/memory.ts remember <file> [file...]` | Register and index file(s) |
| `bun run scripts/memory.ts status` | Show memory overview |

Memory types: `decision`, `pattern`, `issue`, `learning`, `preference`, `constraint`.

## Runtime model

- `scripts/memory.ts` is a self-contained script using `bun:sqlite` (zero deps).
- The memory database is stored at `.ai/memory/memory.db` and is gitignored.
- The installer (`tools/memory_service/`) is Python-based, invoked via `uvx`.

## Tests

```bash
bun test tests/memory.test.ts
```
