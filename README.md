# Repo-Local Memory Service

Standalone, database-backed memory continuity for coding agents.
Canonical project docs stay in-place; memory stores derived retrieval state.

## Prerequisites

1. Install `uv`.
On macOS/Linux:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
On Windows (PowerShell):
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```
2. Restart your shell or ensure `uv` is on `PATH`.
3. Verify:
```bash
uv --version
```
4. For `uvx --from <git-url> ...`, ensure `git` is installed.

## One-command install

Use `uvx` from a Git URL or local path:

```bash
uvx --from <git-url-or-local-path> install-memory-skills
```

The guided installer prompts for:
- target clients (`Codex`, `Copilot`, `Claude`)
- scope (`project` or `global`)
- confirmation of resolved install paths

Install behavior is snapshot-copy only.
It copies skill files and `tools/memory_service` into the selected target root.

## Local development install

From this repository:

```bash
uv run install-memory-skills
```

Exact script path form from this repo:
```bash
uv run tools/memory_service/install_skills.py
```

Non-interactive example:

```bash
uv run install-memory-skills \
  --target codex,copilot,claude \
  --scope project \
  --force \
  --yes \
  --non-interactive
```

## Installed locations

- Codex: `.agents/skills/context-memory` (project), `~/.agents/skills/context-memory` (global)
- Copilot: `.github/skills/context-memory` (project), `~/.copilot/skills/context-memory` (global)
- Claude: `.claude/skills/context-memory` (project), `~/.claude/skills/context-memory` (global)

## Memory commands

Installed skill scripts call `uv run memory-skill-runner ...`:

- `scripts/memory_tool.py`
- `scripts/memory_workflow.py`

Tool surface:
- `register_document`
- `upsert_memory_record`
- `link_records`
- `index`
- `search`
- `build_context_bundle`

## Runtime model

- `tools/memory_service` is internal tooling, not app runtime.
- `skills/context-memory` is the authored skill source.
- Installed client skill directories are generated/synced artifacts.
- Runtime DB is local state under `.ai/` and is intentionally gitignored.

## Tests

```bash
uv run python -m unittest -v tests/test_memory_service.py tests/test_skill_scripts.py tests/test_installer.py
```
