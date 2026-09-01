# Assignment Contract

Every delegated task uses these stable fields:

- `objective`: exact result and why it matters.
- `reference`: authoritative repo/commit/file/symbol, paper/spec section, existing local implementation, or explicit `none` only when the role genuinely does not need one.
- `target`: exact repository/file/symbol/data surface.
- `method`: frozen approach and adaptations; state what the employee must not redesign.
- `integration`: exact real entry point/downstream path, or `read-only evidence` for scout/researcher roles.
- `resources`: environment, GPU/CPU allocation, commands/run budget, or `read-only/no compute`.
- `write_scope`: exact permitted write boundary; use `read-only` for non-writers.
- `acceptance`: L0-L4 level the assignment itself must reach.
- `output`: concise evidence/diff/result format expected by the Lead.
- `stop_conditions`: conditions that require escalation instead of invention.

A worker contract must identify reference, target, adaptation, integration, and acceptance before dispatch. A standalone module cannot satisfy an integration contract unless the project outcome itself is that standalone module.
