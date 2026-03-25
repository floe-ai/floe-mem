# Context Memory — Operation Reference

This document covers the full API and the simplified commands.

## Simplified Commands

These are the recommended commands for everyday use. They wrap the full API
with sensible defaults so you don't need to construct JSON payloads.

All commands use `uv run scripts/memory.py` from the project root.

### save

Save a memory record with flat arguments.

```bash
uv run scripts/memory.py save "<content>" [--type <type>] [--tags <comma-separated>] [--title <title>] [--agent <name>] [--task <description>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `content` | yes | — | The memory content (positional) |
| `--type` | no | `learning` | One of: `decision`, `pattern`, `issue`, `learning`, `preference`, `constraint` |
| `--tags` | no | — | Comma-separated tags, e.g. `auth,api,jwt` |
| `--title` | no | auto-derived | Short title (first 80 chars of content if omitted) |
| `--agent` | no | `unknown` | Agent identifier |
| `--task` | no | — | Current task description |
| `--record-id` | no | auto-generated | Update an existing record by ID |

**Example:**

```bash
uv run scripts/memory.py save "Chose JWT with refresh tokens over session cookies" --type decision --tags auth,api
```

**Output:**

```json
{"ok": true, "result": {"saved": "rec_abc123", "type": "decision", "title": "Chose JWT with refresh tokens over session cookies"}}
```

### recall

Search memory for relevant context.

```bash
uv run scripts/memory.py recall "<query>" [--limit <n>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `query` | yes | — | What to search for (positional) |
| `--limit` | no | `5` | Maximum results |

**Example:**

```bash
uv run scripts/memory.py recall "authentication approach"
```

**Output:**

```json
{"ok": true, "result": {"query": "authentication approach", "count": 2, "memories": [{"id": "rec_abc123", "type": "memory_record", "tier": "validated_recent_history", "snippet": "Chose JWT with...", "score": 54.0}]}}
```

### status

Show an overview of what's in memory.

```bash
uv run scripts/memory.py status
```

**Output:**

```json
{"ok": true, "result": {"documents": 15, "memories": 4, "chunks": 120, "recent": [{"id": "rec_abc123", "class": "summary", "title": "Chose JWT...", "type": "decision", "updated": "2025-01-15T10:30:00+00:00"}]}}
```

### remember

Register and index one or more files in a single step.

```bash
uv run scripts/memory.py remember <file> [file...] [--kind <type>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `files` | yes | — | One or more file paths (positional) |
| `--kind` | no | `doc` | Document kind |

**Example:**

```bash
uv run scripts/memory.py remember docs/architecture.md src/auth/config.py
```

### context

Build a context bundle for a task objective.

```bash
uv run scripts/memory.py context "<objective>" [--profile <profile>] [--token-budget <n>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `objective` | yes | — | What you are trying to accomplish (positional) |
| `--profile` | no | `implementer` | One of: `generic`, `implementer`, `reviewer`, `planner`, `foreman` |
| `--token-budget` | no | profile default | Override token budget |

**Example:**

```bash
uv run scripts/memory.py context "implement user login flow"
```

---

## Full API Reference

Complete argument reference for all memory operations.
All commands are invoked via `uv run scripts/memory_tool.py <command> [args]`
or `uv run scripts/memory.py` (which delegates to the same backend).

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
uv run scripts/memory_tool.py register_document \
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
| `--provenance` | yes | JSON string | Origin metadata. Must include `source_refs` (list of related IDs) plus any agent/task context |
| `--record-id` | no | string | Existing record ID to update (creates new if omitted) |

### Record Class Payload Schemas

| `record-class` | Required payload keys |
|----------------|-----------------------|
| `summary` | `title` (string), `summary` (string), `status` (string, e.g. `accepted`, `superseded`, `draft`) |
| `ephemeral_run_note` | `note` (string) |
| `context_bundle` | `objective` (string), `items` (array) |
| `repo_map_entry` | `locator` (string), `inferred_kind` (string), `confidence` (float) |
| `code_affinity_record` | `subject` (string), `affinities` (array) |
| `provenance_record` | `target` (string), `source_ref` (string), `derivation_method` (string) |
| `chunk_record` | `source` (string), `text` (string) — indexer-owned, not agent-authored |

- **canonical_reference** — Permanent, human-validated knowledge (e.g., architecture decisions)
- **durable_derived** — Agent-produced summaries intended to persist across sessions
- **ephemeral_run** — Temporary notes for the current work session only

### Example

```bash
uv run scripts/memory_tool.py upsert_memory_record \
  --record-class summary \
  --durability-class durable_derived \
  --payload '{"title": "Database migration strategy", "summary": "Using Alembic for migrations. Schema changes require review.", "status": "accepted"}' \
  --provenance '{"source_refs": ["doc-abc123"], "agent": "copilot", "task": "db-setup", "session": "2025-01-15"}'
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
uv run scripts/memory_tool.py link_records \
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
uv run scripts/memory_tool.py index --scope delta

# Full rebuild
uv run scripts/memory_tool.py index --scope full --force-rebuild --reason "schema update"
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
uv run scripts/memory_tool.py search \
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
uv run scripts/memory_tool.py build_context_bundle \
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
