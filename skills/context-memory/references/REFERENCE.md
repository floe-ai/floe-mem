# Context Memory — Operation Reference

Complete argument reference for all memory operations.
All commands are invoked via `python scripts/memory_tool.py <command> [args]`.

Global flags (apply to all commands):

| Flag | Default | Description |
|------|---------|-------------|
| `--repo-id` | `default` | Repository identifier for multi-repo setups |
| `--repo-root` | `.` | Path to the project root directory |
| `--db` | `.ai/memory/memory.db` | Path to the SQLite memory database |
| `--enable-vector` | off | Enable vector search tier (experimental) |

---

## register_document

Register a file so it can be indexed and searched. The file is referenced by its
relative path (locator) from the project root — content is read from disk on demand,
not stored in the database.

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `--locator` | yes | string | Relative path to the file from project root |
| `--kind` | yes | string | File type: `documentation`, `source`, `config`, `spec`, etc. |
| `--metadata` | no | JSON string | Arbitrary key-value metadata |
| `--anchors` | no | JSON array | Code anchors (symbol, section, line ranges) |
| `--discovery-reason` | no | string | Why this file was discovered |
| `--confidence` | no | float | Discovery confidence score (0.0–1.0) |
| `--commit-hash` | no | string | Git commit hash at time of registration |

### Example

```bash
python scripts/memory_tool.py register_document \
  --locator docs/architecture.md \
  --kind documentation \
  --metadata '{"tags": ["architecture", "overview"]}'
```

### Output

```json
{
  "ok": true,
  "result": {
    "document_id": "doc-a1b2c3d4-...",
    "version_id": "dver-e5f6a7b8-...",
    "freshness_state": "stale",
    "indexed_state": "pending_delta_index"
  }
}
```

After registering, run `index` to make the document searchable.

---

## upsert_memory_record

Create or update a memory record. Records store agent-produced knowledge like
decisions, summaries, and context that persists across sessions.

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `--record-class` | yes | string | One of: `summary`, `context_bundle`, `repo_map_entry`, `code_affinity_record`, `provenance_record`, `chunk_record`, `ephemeral_run_note` |
| `--payload` | yes | JSON string | Record content. Should include `title` and `body` fields |
| `--durability-class` | yes | string | One of: `canonical_reference`, `durable_derived`, `ephemeral_run` |
| `--provenance` | yes | JSON string | Origin metadata (agent, task, session, etc.) |
| `--record-id` | no | string | Existing record ID to update (creates new if omitted) |

### Durability Classes

- **canonical_reference** — Permanent, human-validated knowledge (e.g., architecture decisions)
- **durable_derived** — Agent-produced summaries intended to persist across sessions
- **ephemeral_run** — Temporary notes for the current work session only

### Example

```bash
python scripts/memory_tool.py upsert_memory_record \
  --record-class summary \
  --durability-class durable_derived \
  --payload '{"title": "Database migration strategy", "body": "Using Alembic for migrations. Schema changes require review."}' \
  --provenance '{"agent": "copilot", "task": "db-setup", "session": "2025-01-15"}'
```

### Output

```json
{
  "ok": true,
  "result": {
    "record_id": "rec-1a2b3c4d-...",
    "version_id": "rver-5e6f7a8b-...",
    "record_class": "summary",
    "durability_class": "durable_derived"
  }
}
```

---

## link_records

Create a typed, weighted edge between two records or documents.

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `--from-ref` | yes | JSON string | Source reference: `{"type": "record"\|"document", "id": "<id>"}` |
| `--to-ref` | yes | JSON string | Target reference: same format as from-ref |
| `--edge-type` | yes | string | Relationship type (e.g., `depends_on`, `supersedes`, `relates_to`, `derived_from`) |
| `--weight` | no | float | Edge weight, default 1.0 |
| `--evidence` | no | JSON string | Supporting evidence for the link |
| `--valid-from` | no | string | ISO 8601 start of validity window |
| `--valid-to` | no | string | ISO 8601 end of validity window |

### Example

```bash
python scripts/memory_tool.py link_records \
  --from-ref '{"type": "record", "id": "rec-abc123"}' \
  --to-ref '{"type": "document", "id": "doc-def456"}' \
  --edge-type derived_from \
  --weight 0.9
```

### Output

```json
{
  "ok": true,
  "result": {
    "edge_id": "edge-9a8b7c6d-...",
    "from_ref": {"type": "record", "id": "rec-abc123"},
    "to_ref": {"type": "document", "id": "doc-def456"},
    "edge_type": "derived_from"
  }
}
```

---

## index

Index registered documents and memory records for search. Builds full-text search
chunks from document content (read from disk) and record payloads.

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `--scope` | no | string | `delta` (default, only stale items), `targeted` (specific items), `full` (rebuild all) |
| `--targets` | no | JSON array | For targeted scope: `[{"type": "document"\|"record", "id": "<id>"}]` |
| `--reason` | no | string | Annotation for the indexing event |
| `--force-rebuild` | no | flag | Delete all existing chunks before re-indexing |

### Example

```bash
# Index only items changed since last index
python scripts/memory_tool.py index --scope delta

# Full rebuild
python scripts/memory_tool.py index --scope full --force-rebuild --reason "schema update"
```

### Output

```json
{
  "ok": true,
  "result": {
    "indexed": {"documents": 3, "records": 5, "chunks": 24, "repo_map": 0},
    "invalidated": {"chunks": 12, "freshness": 0}
  }
}
```

---

## search

Query memory across multiple retrieval tiers. Results are ranked by tier priority:
exact → lineage → explicit links → code affinity → validated recent history → lexical FTS → vector.

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `--query` | yes | string | Search query text or record/document ID |
| `--filters` | no | JSON string | Filter criteria (e.g., `{"record_class": "summary"}`) |
| `--profile` | no | string | Search profile: `generic`, `implementer`, `reviewer`, `planner`, `foreman` |
| `--limit` | no | int | Max results, default 20 |
| `--override-policy` | no | JSON string | Override tier quotas |

### Search Tiers (priority order)

1. **exact** — Direct ID or path matches (quota: 6)
2. **lineage** — Parent/child relationships (quota: 6)
3. **explicit_links** — Edges between records (quota: 6)
4. **code_affinity** — File/symbol relationships (quota: 5)
5. **validated_recent_history** — Summaries with specific statuses (quota: 4)
6. **lexical_fts** — Full-text search in indexed chunks (quota: 3)
7. **vector** — Embedding similarity, if enabled (quota: 2)

### Example

```bash
python scripts/memory_tool.py search \
  --query "authentication" \
  --profile implementer \
  --limit 5
```

### Output

```json
{
  "ok": true,
  "result": {
    "hits": [
      {
        "id": "rec-abc123",
        "tier": "lexical_fts",
        "record_class": "summary",
        "score": 0.85,
        "snippet": "JWT-based authentication with refresh tokens..."
      }
    ],
    "tiers_searched": ["exact", "lineage", "explicit_links", "code_affinity", "validated_recent_history", "lexical_fts"],
    "total_hits": 1
  }
}
```

---

## build_context_bundle

Assemble a token-budgeted context bundle for a specific objective. Combines search
results across tiers, respects profile budgets, and returns an auditable manifest.

| Argument | Required | Type | Description |
|----------|----------|------|-------------|
| `--objective` | yes | string | What you're trying to accomplish |
| `--focus-refs` | no | JSON array | Prioritized references: `[{"type": "record"\|"document", "id": "<id>"}]` |
| `--profile` | no | string | Budget profile: `generic` (1800), `implementer` (2200), `reviewer` (2200), `planner` (2600), `foreman` (2800) |
| `--token-budget` | no | int | Override the profile's default token budget |

### Example

```bash
python scripts/memory_tool.py build_context_bundle \
  --objective "implement user authentication" \
  --profile implementer \
  --token-budget 2200
```

### Output

```json
{
  "ok": true,
  "result": {
    "bundle_id": "bun-1a2b3c4d-...",
    "objective": "implement user authentication",
    "profile": "implementer",
    "token_budget": 2200,
    "tokens_used": 1850,
    "items": [
      {
        "source_type": "memory_record",
        "source_id": "rec-abc123",
        "tier": "exact",
        "heading": "Auth decision",
        "token_estimate": 150,
        "text_preview": "Chose JWT with refresh tokens..."
      }
    ],
    "tiers_included": ["exact", "lineage", "lexical_fts"],
    "overflow_dropped": 2
  }
}
```

---

## Workflow Script

`scripts/memory_workflow.py` provides a one-shot search-and-bundle flow:

```bash
python scripts/memory_workflow.py \
  --objective "understand caching layer" \
  --profile reviewer \
  --token-budget 2200 \
  --register docs/caching.md docs/redis.md
```

This registers the specified files (if not already registered), indexes them, then
builds a context bundle for the given objective — all in one command.

---

## Error Output

All commands return structured JSON on failure:

```json
{
  "ok": false,
  "error": "record_class must be one of: summary, context_bundle, ...",
  "command": "upsert_memory_record"
}
```

Common errors:
- Missing required arguments
- Invalid `record_class` or `durability_class` values
- File not found at locator path (for register_document)
- Database connection failure
