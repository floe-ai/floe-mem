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
  version: "0.1.0"
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
python scripts/memory_tool.py search --query "<your task description>" --limit 5
```

Or build a full context bundle:

```bash
python scripts/memory_tool.py build_context_bundle \
  --objective "<your task description>" \
  --profile implementer
```

Use what you find to inform your approach. Only then proceed to explore files.

### Step 2: Do your work

Proceed with the task, informed by the memory context you retrieved.

If you discover important documents during your work, register them:

```bash
python scripts/memory_tool.py register_document \
  --locator <relative-path> \
  --kind <documentation|source|config|spec>

python scripts/memory_tool.py index --scope delta
```

### Step 3: Write back memories BEFORE finishing

This is not optional. Before you consider your work complete, write back:

**What to record — ask yourself these questions:**

- Did I make a decision? Record it as a summary.
- Did I discover how something works? Record it as a summary.
- Did I find a gotcha or edge case? Record it as a summary.
- Did I establish a pattern or convention? Record it as a summary.
- Did I try something that didn't work? Record it so the next agent doesn't repeat it.

**How to record it:**

```bash
python scripts/memory_tool.py upsert_memory_record \
  --record-class summary \
  --durability-class durable_derived \
  --payload '{"title": "<concise title>", "summary": "<what happened, what was decided, and why>", "status": "accepted"}' \
  --provenance '{"source_refs": [], "agent": "<agent-name>", "task": "<task-description>"}'
```

**Link related records when relevant:**

```bash
python scripts/memory_tool.py link_records \
  --from-ref '{"type": "record", "id": "<new-record-id>"}' \
  --to-ref '{"type": "document", "id": "<related-doc-id>"}' \
  --edge-type derived_from
```

### What good memory records look like

**Good:** *"Chose JWT with refresh token rotation over session cookies. The API is
stateless and deployed across multiple regions, so server-side sessions would
require a shared store. Refresh tokens rotate on each use with a 7-day expiry."*

**Bad:** *"Implemented authentication."*

Good records capture the **decision**, the **reasoning**, and the **constraints**.
Bad records state what happened without explaining why.

## Scripts

- `scripts/memory_tool.py` — direct memory commands (register, upsert, link, index, search, bundle)
- `scripts/memory_workflow.py` — compact search-and-bundle flow for a given objective

## Available Operations

| Operation | Script invocation |
|-----------|-------------------|
| Search memory | `python scripts/memory_tool.py search --query <text>` |
| Build a context bundle | `python scripts/memory_tool.py build_context_bundle --objective <text>` |
| Create/update a memory record | `python scripts/memory_tool.py upsert_memory_record --record-class <class> --payload <json> --durability-class <durability> --provenance <json>` |
| Register a document | `python scripts/memory_tool.py register_document --locator <path> --kind <type>` |
| Index documents and records | `python scripts/memory_tool.py index --scope delta` |
| Link two records | `python scripts/memory_tool.py link_records --from-ref <json> --to-ref <json> --edge-type <type>` |

See [references/REFERENCE.md](references/REFERENCE.md) for full argument details, types, and output formats.

## Guidelines

- **Memory first, files second.** Always search before exploring the codebase.
- **Write before you finish.** Every task that produces knowledge should leave a memory record.
- Keep records concise but complete — capture decisions, reasoning, and constraints.
- Prefer targeted retrieval over broad context dumps.
- All file references in memory are relative paths from the project root.
- The memory database is stored at `.ai/memory/memory.db` and is gitignored.
