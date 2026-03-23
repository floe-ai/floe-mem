# Bundle Policy

Bundles must be bounded and auditable.

Each item should include:

- inclusion reason
- retrieval tier
- source refs
- durability class
- token estimate/size class

Default policy:

- per-tier quotas
- global profile token budget
- optimize for minimum trustworthy context, not maximum recall

Stop retrieval when objective, constraints, likely files/symbols/tests, and verification path are clear.
