# Durability And Record Classes

Allowed `upsert_memory_record` classes:

- `summary`
- `context_bundle`
- `repo_map_entry`
- `code_affinity_record`
- `provenance_record`
- `chunk_record`
- `ephemeral_run_note`

Guardrails:

- Relationship edges are created only through `memory.link_records`.
- `ephemeral_run_note` stays `ephemeral_run` by default.
- `chunk_record` is indexer-owned/internal derived state.
- Unknown classes are rejected.

Promotion guidance:

Promote to durable only when repeatedly useful, explicitly marked important, or validated against canonical sources and stable relationships.
