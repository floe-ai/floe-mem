# Context Memory — Command Reference

All commands run from the project root:

```bash
uv run scripts/memory.py <command> [args]
```

Global flags (apply to all commands):

| Flag | Default | Description |
|------|---------|-------------|
| `--repo-id` | `default` | Repository identifier for multi-repo setups |
| `--repo-root` | `.` | Path to the project root (auto-detected from script location) |
| `--db` | `.ai/memory/memory.db` | SQLite memory database path |

---

## save

Save a memory record.

```bash
uv run scripts/memory.py save "<content>" [--type <type>] [--tags <tags>] [--title <title>] [--agent <name>] [--task <description>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `content` | yes | — | The memory content |
| `--type` | no | `learning` | `decision`, `pattern`, `issue`, `learning`, `preference`, `constraint` |
| `--tags` | no | — | Comma-separated tags |
| `--title` | no | auto-derived | Short title (first 80 chars of content if omitted) |
| `--agent` | no | `unknown` | Agent identifier for provenance |
| `--task` | no | — | Task description for provenance |
| `--record-id` | no | auto-generated | Update an existing record by ID |

**Examples:**

```bash
uv run scripts/memory.py save "Chose JWT with refresh tokens over session cookies" --type decision --tags auth,api
uv run scripts/memory.py save "FTS5 requires UNINDEXED for metadata columns" --type learning --tags sqlite
uv run scripts/memory.py save "text_cache was bloating DB - read content from disk" --type issue --tags performance
```

**Output:**

```json
{"ok": true, "result": {"saved": "rec_abc123", "type": "decision", "title": "Chose JWT with refresh tokens over session cookies"}}
```

---

## recall

Search memory for relevant context.

```bash
uv run scripts/memory.py recall "<query>" [--limit <n>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `query` | yes | — | What to search for |
| `--limit` | no | `5` | Maximum results |

**Example:**

```bash
uv run scripts/memory.py recall "authentication approach" --limit 3
```

**Output:**

```json
{
  "ok": true,
  "result": {
    "query": "authentication approach",
    "count": 1,
    "memories": [
      {"id": "rec_abc123", "type": "memory_record", "tier": "validated_recent_history", "snippet": "Chose JWT with...", "score": 54.0}
    ]
  }
}
```

---

## status

Show an overview of what's in memory.

```bash
uv run scripts/memory.py status
```

**Output:**

```json
{
  "ok": true,
  "result": {
    "documents": 15,
    "memories": 4,
    "chunks": 120,
    "recent": [
      {"id": "rec_abc123", "class": "summary", "title": "Chose JWT...", "type": "decision", "updated": "2025-01-15T10:30:00+00:00"}
    ]
  }
}
```

---

## remember

Register and index one or more files in one step.

```bash
uv run scripts/memory.py remember <file> [file...] [--kind <type>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `files` | yes | — | One or more relative file paths |
| `--kind` | no | `doc` | Document kind |

**Example:**

```bash
uv run scripts/memory.py remember docs/architecture.md src/auth/config.py
```

**Output:**

```json
{
  "ok": true,
  "result": {
    "registered": [{"file": "docs/architecture.md", "doc_id": "doc_abc123"}],
    "indexed": {"documents": 1, "records": 0, "chunks": 12, "repo_map": 1}
  }
}
```

---

## context

Build a context bundle for a task objective.

```bash
uv run scripts/memory.py context "<objective>" [--profile <profile>] [--token-budget <n>]
```

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `objective` | yes | — | What you are trying to accomplish |
| `--profile` | no | `implementer` | `generic`, `implementer`, `reviewer`, `planner`, `foreman` |
| `--token-budget` | no | profile default | Token budget: generic=1800, implementer/reviewer=2200, planner=2600, foreman=2800 |

**Example:**

```bash
uv run scripts/memory.py context "implement user login flow" --profile implementer
```

---

## Error Output

All commands return structured JSON on failure:

```json
{"ok": false, "error": "description of what went wrong", "command": "save"}
```

Common errors:
- `no command provided` — no subcommand given
- `uv not found on PATH` — install uv first
- `unable to locate repo root` — run from within the project directory
