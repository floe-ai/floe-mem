# Context Memory Skill

## Purpose

Provide bounded, trustworthy project continuity for fresh agents using the repo-local memory service.

## Quick start

For non-trivial tasks, run this loop:

1. Register/update relevant canonical docs with `memory.register_document`.
2. Run opportunistic `memory.index --scope delta`.
3. Retrieve relationship-first with `memory.search`.
4. Build a bounded bundle with `memory.build_context_bundle`.
5. Execute code work.
6. Write continuity via `memory.upsert_memory_record` class `summary`.
7. Re-run `memory.index`.

## Tool surface

Use only:

- `memory.register_document`
- `memory.upsert_memory_record`
- `memory.link_records`
- `memory.index`
- `memory.search`
- `memory.build_context_bundle`

Relationship edges must be created by `memory.link_records`, not `memory.upsert_memory_record`.

## Use scripts

Prefer skill-local scripts for deterministic execution and concise, parseable output:

- `scripts/memory_tool.py`: canonical direct entrypoint for memory tools.
- `scripts/memory_workflow.py`: opinionated non-interactive workflow helper.

Install/sync this skill with:
- `uvx --from <git-url-or-local-path> install-memory-skills`

## Progressive disclosure

Only load additional details as needed:

- `references/retrieval-order.md`: ranking tiers and precedence guardrails.
- `references/durability-and-records.md`: record classes, durability, promotion rules.
- `references/discovery-and-indexing.md`: generic discovery, freshness, invalidation.
- `references/bundle-policy.md`: quotas, token budgets, stop conditions.
- `references/script-usage.md`: script invocation patterns and troubleshooting.

## Stop and escalate

Escalate when:

- acceptance criteria conflict with architecture evidence
- intent remains contradictory after one deeper retrieval pass
- repeated failed attempts suggest decomposition is wrong

In those cases, write a structured blocked summary and request replanning.
