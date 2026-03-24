# Script Usage

Use skill-local scripts for predictable, non-interactive execution.
Run through `uv` only.

## Scripts

- `scripts/memory_tool.py`
- `scripts/memory_workflow.py`

These are the canonical executable interfaces for this skill.
They delegate to `uv run python -m tools.memory_service.runner ...` so snapshot-copied installs remain stable.

## Install flow

1. Install/sync the skill with:
`uvx --from <git-url-or-local-path> install-memory-skills`
2. Pick clients, scope, and mode in the guided prompts.
3. Execute scripts from the installed skill location.

## Output conventions

- machine-readable data on stdout (JSON)
- diagnostics/progress on stderr
- concise outputs to avoid context-window bloat

## Error handling

- clear argument validation errors
- non-zero exit code on failures
- include expected input in error message
