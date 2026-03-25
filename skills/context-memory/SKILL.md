---
name: context-memory
description: >
  ALWAYS use this skill FIRST when starting work on a project. Search memory
  before reading files. Write memory after completing work. Provides repo-local
  memory retrieval and write-back tools for continuity across agent sessions.
  Keywords: context, history, onboarding, prior work, session memory, project
  knowledge, decisions, summaries.
license: MIT
compatibility: Requires uv and Python >=3.10. Works with Codex, Copilot, and Claude.
metadata:
  author: floe-ai
  version: "0.2.0"
---

# Context Memory Skill

## When to use this skill

**BEFORE you start working — always.** Search memory first, before exploring
files, reading code, or making plans. Prior agents may have already mapped the
codebase, recorded decisions, or left context that saves you significant work.
Starting without checking memory means you risk duplicating effort, contradicting
prior decisions, or missing critical context.

**AFTER you finish working — always.** Write back what you learned. Every
substantial piece of work produces knowledge that will help the next agent:
decisions made, approaches tried, gotchas discovered, architecture understood.
If you don't write it down, the next agent starts from zero.

**The only exception** is trivially obvious tasks — single-line typo fixes,
simple renames, or formatting changes where no prior context could matter.

## Required workflow

### Step 1: Search memory FIRST

Before reading any project files, search for context relevant to your task:

```bash
uv run scripts/memory.py recall "your task description"
```

Or build a full context bundle:

```bash
uv run scripts/memory.py context "your task description"
```

Use what you find to inform your approach. Only then proceed to explore files.

### Step 2: Do your work

Proceed with the task, informed by the memory context you retrieved.

If you discover important documents during your work, register them:

```bash
uv run scripts/memory.py remember docs/architecture.md src/config.py
```

### Step 3: Write back memories BEFORE finishing

This is not optional. Before you consider your work complete, write back:

**What to record — ask yourself these questions:**

- Did I make a decision? → `--type decision`
- Did I discover how something works? → `--type learning`
- Did I find a gotcha or edge case? → `--type issue`
- Did I establish a pattern or convention? → `--type pattern`
- Did I try something that didn't work? Record it so the next agent doesn't repeat it.

**How to record it:**

```bash
uv run scripts/memory.py save "Chose JWT with refresh tokens over session cookies. API is stateless across regions." --type decision --tags auth,api
```

Multiple memories? Save each one:

```bash
uv run scripts/memory.py save "FTS5 requires UNINDEXED for metadata columns to enable WHERE filtering" --type learning --tags sqlite,search
uv run scripts/memory.py save "text_cache was bloating the DB - content should be read from disk via locator" --type issue --tags performance,storage
```

### What good memory records look like

**Good:** *"Chose JWT with refresh token rotation over session cookies. The API is
stateless and deployed across multiple regions, so server-side sessions would
require a shared store. Refresh tokens rotate on each use with a 7-day expiry."*

**Bad:** *"Implemented authentication."*

Good records capture the **decision**, the **reasoning**, and the **constraints**.
Bad records state what happened without explaining why.

## Quick reference

| Command | What it does |
|---------|-------------|
| `uv run scripts/memory.py recall "<query>"` | Search memory for relevant context |
| `uv run scripts/memory.py context "<objective>"` | Build a context bundle for a task |
| `uv run scripts/memory.py save "<text>" --type <type> --tags <tags>` | Save a memory |
| `uv run scripts/memory.py remember <file> [file...]` | Register and index file(s) |
| `uv run scripts/memory.py status` | Show memory overview |

### Memory types

| Type | Use when |
|------|----------|
| `decision` | You chose between alternatives |
| `learning` | You discovered how something works |
| `pattern` | You established a convention or approach |
| `issue` | You found a bug, gotcha, or edge case |
| `preference` | You noted a project/team preference |
| `constraint` | You identified a technical limitation |

## Guidelines

- **Memory first, files second.** Always search before exploring the codebase.
- **Write before you finish.** Every task that produces knowledge should leave a memory record.
- Keep records concise but complete — capture decisions, reasoning, and constraints.
- Prefer targeted retrieval over broad context dumps.
- All file references in memory are relative paths from the project root.
- The memory database is stored at `.ai/memory/memory.db` and is gitignored.
