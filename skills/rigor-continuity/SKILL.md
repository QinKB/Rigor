---
name: rigor-continuity
description: Maintain durable project state across startup, resume, compaction, interruption, handoff, and completion. Use when HANDOFF.md, MEMORY.md, LOG.md, prior runs/checkpoints, or unfinished work affects the next action, and before closing a Rigor task whose memory gate is required.
---

# Rigor Continuity

Use repository files for durable human/agent state; use Plugin data for machine gate state.

- `HANDOFF.md`: active outcome, exact current state, unfinished integration, important artifacts/runs, and next action.
- `MEMORY.md`: verified, non-obvious, durable knowledge expensive to rediscover.
- `LOG.md`: chronology, failed attempts, commands, experiments, run evidence, and noisy operational history.

Before consequential resumed work, reconcile these files with the current repository and Git state. Do not trust stale prose over current code/artifacts.

Before task close, update only durable facts that matter, keep the files compact, then run the bundled `scripts/rigorctl.py continuity sync --memory-status updated|no-new-durable-memory --summary <what changed>`. HANDOFF.md and LOG.md must have been updated during the active task; declaring `updated` also requires MEMORY.md to have changed. The command marks the memory gate; it does not certify that invented prose is true, so the Lead must write only verified facts.
