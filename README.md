# Repo-Local Memory Service

Standalone, database-backed memory continuity for coding agents.
Canonical project docs stay in-place; memory stores derived retrieval state.

## Prerequisites

Install [Bun](https://bun.sh):
```bash
curl -fsSL https://bun.sh/install | bash
```

```iex
powershell -c "irm bun.sh/install.ps1 | iex"
```

## One-command install

```bash
bunx github:floe-ai/floe-mem
```

The guided installer prompts for:
- target clients (`Codex`, `Copilot`, `Claude`)
- scope (`project` or `global`)
- confirmation of resolved install paths

It copies `SKILL.md` + `scripts/memory.ts` into the selected targets. That's it — no other dependencies.

**CLI flags (skip prompts):**
```bash
bunx github:floe-ai/floe-mem --target codex,copilot --scope project --yes
```

**Local install (from cloned repo):**
```bash
bun run scripts/install.ts --target codex --scope project --yes
```

## Memory commands

All commands run from the project root:

| Command | What it does |
|---------|-------------|
| `bun run scripts/memory.ts recall "<query>"` | Search memory for relevant context |
| `bun run scripts/memory.ts context "<objective>"` | Build a context bundle for a task |
| `bun run scripts/memory.ts save "<text>" --type <type> --tags <tags>` | Save a memory |
| `bun run scripts/memory.ts remember <file> [file...]` | Register and index file(s) |
| `bun run scripts/memory.ts status` | Show memory overview |

Memory types: `decision`, `pattern`, `issue`, `learning`, `preference`, `constraint`.

## Runtime model

- `scripts/memory.ts` is a self-contained script using `bun:sqlite` (zero external deps).
- The memory database lives at `.ai/memory/memory.db` (gitignored).
- The installer (`scripts/install.ts`) is also a self-contained Bun script.

## Tests

```bash
bun test
```
