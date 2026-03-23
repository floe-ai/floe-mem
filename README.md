# Repo-Local Memory Service

A standalone, database-backed memory capability for coding agents.

It provides continuity and targeted retrieval without requiring a runtime harness.
Canonical project docs stay where they already live in the repo.

## What this implements

- Relationship-first retrieval with deterministic tier order
- SQLite-backed memory store (FTS5 lexical search baseline)
- Optional vector tier flag (off by default)
- Generic mode document discovery + registration
- Structured mode via file-backed foreign artefacts and explicit links
- Bounded context bundle construction with token budgets and tier quotas
- Provenance/freshness/invalidation tracking for derived memory

## Tool contracts (CLI subcommands)

- `register_document`
- `upsert_memory_record`
- `link_records`
- `index`
- `search`
- `build_context_bundle`

Single entrypoint:

```bash
python3 scripts/memory.py --help
```

## Quick start

1. Register a canonical document.

```bash
python3 scripts/memory.py register_document \
  --repo-id demo \
  --repo-root . \
  --locator docs/architecture.md \
  --kind architecture \
  --metadata '{"owner":"platform"}'
```

2. Write a memory-owned summary record.

```bash
python3 scripts/memory.py upsert_memory_record \
  --repo-id demo \
  --repo-root . \
  --record-class summary \
  --durability-class durable_derived \
  --payload '{"title":"Run summary","summary":"Completed targeted fix","status":"completed"}' \
  --provenance '{"source_refs":["doc_123"]}'
```

3. Link records/documents explicitly.

```bash
python3 scripts/memory.py link_records \
  --repo-id demo \
  --repo-root . \
  --from-ref '{"type":"memory_record","id":"rec_a"}' \
  --to-ref '{"type":"document","id":"doc_b"}' \
  --edge-type relates_to
```

4. Refresh derived state incrementally.

```bash
python3 scripts/memory.py index --repo-id demo --repo-root . --scope delta
```

5. Run deterministic search.

```bash
python3 scripts/memory.py search \
  --repo-id demo \
  --repo-root . \
  --query "profile settings layout"
```

6. Build bounded context bundle.

```bash
python3 scripts/memory.py build_context_bundle \
  --repo-id demo \
  --repo-root . \
  --objective "implement profile settings grouping" \
  --profile implementer
```

## Retrieval order

1. exact match
2. lineage traversal
3. explicit links
4. code-affinity
5. recent validated summaries/history
6. lexical FTS
7. vector (optional)

Lower tiers do not outrank higher tiers unless explicitly overridden.

## Record class constraints

`upsert_memory_record` allows only:

- `summary`
- `context_bundle`
- `repo_map_entry`
- `code_affinity_record`
- `provenance_record`
- `chunk_record` (internal/indexer-owned)
- `ephemeral_run_note` (ephemeral only by default)

Relationship edges must be created via `link_records`.

## Tests

Run:

```bash
python3 -m unittest -v tests/test_memory_service.py
```

The test suite verifies:

- deterministic retrieval precedence
- invalidation/freshness transition after source changes
- bounded and auditable context bundles
