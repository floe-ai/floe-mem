---
name: context-memory
description: Use when prior project decisions, summaries, relationships, or document context would help solve a task without rereading large parts of the repo. Provides repo-local memory retrieval and write-back tools for continuity across agent sessions.
---

# Context Memory Skill

Use project memory when it is useful, not by default for every task.

Prefer it when:

- the task depends on prior decisions or summaries
- you need a compact view of relevant docs or linked work
- you want to write back a durable summary for future agents

Skip it when the task is simple enough that direct repo inspection is faster.

Use the skill-local scripts for deterministic operations:

- `scripts/memory_tool.py` for direct memory commands
- `scripts/memory_workflow.py` when you want a compact search-and-bundle flow

Available memory operations:

- `memory.register_document`
- `memory.upsert_memory_record`
- `memory.link_records`
- `memory.index`
- `memory.search`
- `memory.build_context_bundle`

Keep outputs small and relevant. Prefer targeted retrieval and concise summaries over broad context dumps.

Before finishing substantial work, consider writing a concise memory record when the outcome, decision, or discovered context is likely to help a future agent.
