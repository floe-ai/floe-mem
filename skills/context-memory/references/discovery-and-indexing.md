# Discovery And Indexing

Generic-mode defaults:

- shallow deterministic scan
- register candidates with inferred kind, confidence, and reason
- exclude generated, vendored, binary, and oversized files

Indexing defaults:

- use `memory.index --scope delta`
- run opportunistically after registration, relinking, or durable writes
- invalidate only derived items whose provenance is stale
- reserve full rebuild for schema/index version changes, explicit rebuild, or integrity failures
