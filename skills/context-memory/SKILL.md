---
name: context-memory
description: >
  Use when prior project decisions, summaries, relationships, or document
  context would help solve a task without rereading large parts of the repo.
  Provides repo-local memory retrieval and write-back tools for continuity
  across agent sessions. Keywords: context, history, onboarding, prior work,
  session memory, project knowledge.
license: MIT
compatibility: Requires uv and Python >=3.10. Works with Codex, Copilot, and Claude.
metadata:
  author: floe-ai
  version: "0.1.0"
---

# Context Memory Skill

Use project memory when it is useful, not by default for every task.

Prefer it when:

- the task depends on prior decisions or summaries
- you need a compact view of relevant docs or linked work
- you want to write back a durable summary for future agents

Skip it when the task is simple enough that direct repo inspection is faster.

## Scripts

Use the skill-local scripts for deterministic operations:

- `scripts/memory_tool.py` — direct memory commands (register, upsert, link, index, search, bundle)
- `scripts/memory_workflow.py` — compact search-and-bundle flow for a given objective

## Available Operations

| Operation | Script invocation |
|-----------|-------------------|
| Register a document | `python scripts/memory_tool.py register_document --locator <path> --kind <type>` |
| Create/update a memory record | `python scripts/memory_tool.py upsert_memory_record --record-class <class> --payload <json> --durability-class <durability> --provenance <json>` |
| Link two records | `python scripts/memory_tool.py link_records --from-ref <json> --to-ref <json> --edge-type <type>` |
| Index documents and records | `python scripts/memory_tool.py index --scope delta` |
| Search memory | `python scripts/memory_tool.py search --query <text>` |
| Build a context bundle | `python scripts/memory_tool.py build_context_bundle --objective <text>` |

See [references/REFERENCE.md](references/REFERENCE.md) for full argument details, types, and output formats.

## Quick Examples

### Search for prior decisions

```bash
python scripts/memory_tool.py search --query "authentication approach" --limit 3
```

Returns:

```json
{
  "ok": true,
  "result": {
    "hits": [
      {
        "id": "rec-abc123",
        "tier": "exact",
        "record_class": "summary",
        "score": 1.0,
        "snippet": "Chose JWT with refresh tokens..."
      }
    ],
    "tiers_searched": ["exact", "lineage", "explicit_links", "lexical_fts"],
    "total_hits": 1
  }
}
```

### Write back a decision for future agents

```bash
python scripts/memory_tool.py upsert_memory_record \
  --record-class summary \
  --durability-class durable_derived \
  --payload '{"title": "Auth decision", "summary": "Chose JWT with refresh tokens over session cookies for stateless API.", "status": "accepted"}' \
  --provenance '{"source_refs": [], "agent": "copilot", "task": "auth-implementation"}'
```

### Register a document and index it

```bash
python scripts/memory_tool.py register_document \
  --locator docs/architecture.md \
  --kind documentation

python scripts/memory_tool.py index --scope delta
```

### Build a context bundle for a task

```bash
python scripts/memory_tool.py build_context_bundle \
  --objective "implement user authentication" \
  --profile implementer \
  --token-budget 2200
```

Returns a token-budgeted bundle with the most relevant records, ranked by tier priority.

## Guidelines

- Keep outputs small and relevant. Prefer targeted retrieval and concise summaries over broad context dumps.
- Before finishing substantial work, consider writing a concise memory record when the outcome, decision, or discovered context is likely to help a future agent.
- All file references in memory are relative paths from the project root.
- The memory database is stored at `.ai/memory/memory.db` and is gitignored.
