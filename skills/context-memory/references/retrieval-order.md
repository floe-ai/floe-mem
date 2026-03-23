# Retrieval Order

Use deterministic tier order:

1. `exact`
2. `lineage`
3. `explicit_links`
4. `code_affinity`
5. `validated_recent_history`
6. `lexical_fts`
7. `vector`

Rules:

- Relationship-first is mandatory.
- Lower tiers do not outrank higher tiers without explicit override.
- Every selected item should carry inclusion reason, tier, and source refs.
