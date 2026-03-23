# Script Usage

Use skill-local scripts for predictable, non-interactive execution.

## Scripts

- `scripts/memory_tool.py`
- `scripts/memory_workflow.py`

## Output conventions

- machine-readable data on stdout (JSON)
- diagnostics/progress on stderr
- concise outputs to avoid context-window bloat

## Error handling

- clear argument validation errors
- non-zero exit code on failures
- include expected input in error message
