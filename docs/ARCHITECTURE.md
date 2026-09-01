# Architecture

## Control plane

`AGENTS.md` defines durable repository semantics. Codex Rigor turns selected semantics into stateful gates. Skills are progressive-disclosure workflows for satisfying those gates. Hooks enforce lifecycle transitions. Scripts perform deterministic state updates and validation.

## State machine

An active task declares a class, required gates, and required acceptance level. Research evidence is selected explicitly; current external searches can be corroborated by PostToolUse observations. A design gate freezes reference/target/method/integration/acceptance. Delegation uses immutable assignment contracts. Integration and acceptance are recorded separately. Continuity and Git gates complete the task.

A task may be `active`, `paused`, `aborted`, or `completed`. Stop blocks incomplete active tasks once per continuation cycle. Pausing requires an up-to-date continuity handoff; abort remains an explicit non-success terminal path. Any governed repository mutation invalidates prior integration, acceptance, memory, and Git gates so post-change evidence must be fresh.

## Why generic rather than algorithm-specific

The plugin forbids unsupported substitutions generically: do not replace a selected mechanism merely because a simpler substitute matches shapes/interfaces or passes an isolated test. Domain-specific mistakes belong in scenario regression tests, not permanent global instructions.


## Hard-enforcement boundaries

- `apply_patch`, common Bash repository-write forms, and write-like repository/Serena/MCP tools pass through the same research/design/verification gate. This prevents the ordinary `sed -i`/redirection/`tee` bypass while acknowledging that hooks are not a formal shell sandbox.
- Research evidence that satisfies a gate must be tied to successful observed tool activity for local code, literature/official sources, upstream code/issues, and external discovery. Observations are timestamp-bound to the active task; worker completion evidence is additionally bound to assignment creation time so stale prior checks cannot be replayed.
- Resource plans capture a live resource snapshot. Project-specific minimum GPU requirements live in project.compute.required_gpu_count. Global compute policy controls scheduling behavior such as whether all currently eligible GPUs should be used when the project does not specify a fixed requirement.

Rigor does not prescribe a launcher such as torchrun, accelerate, or a
particular Python entry command.
- A configurable sensitive-path classifier prevents the weak `mechanical` task class from being used to mutate common model/training/data/evaluation semantic paths. It is a misclassification guard, not an algorithm-specific policy.
