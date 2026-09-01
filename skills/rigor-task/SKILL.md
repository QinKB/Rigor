---
name: rigor-task
description: Establish and manage a governed repository task before consequential writes, implementation, architecture work, data/model changes, experiments, evaluation changes, long runs, Git checkpoints, or subagent implementation. Use whenever work needs a frozen objective, acceptance protocol, resource plan, or delegation contract.
---

# Rigor Task

Treat machine task state as the authoritative execution contract. Do not begin consequential implementation before the required contracts are frozen.

## Start

1. Inspect the real repository, Git state, applicable AGENTS, entry point, and durable state.
2. Choose the narrowest honest class from `mechanical`, `root-cause-fix`, `reference-adaptation`, `new-design`, `experiment`, `evaluation`, or `data-change`. Do not use `mechanical` to bypass evidence for research-sensitive model/training/data/evaluation changes; the Hook blocks configured sensitive paths.
3. Run `scripts/rigorctl.py task start --objective <...> --class <...> --acceptance <L0-L4>`.

4. Immediately select one acceptance profile already configured for this repository:

   `scripts/rigorctl.py verification select --profile <profile-name>`

   The project profile is authoritative and may raise the task's required acceptance level. Do not invent or weaken a verification protocol inside the task. If no suitable profile exists, return to `$rigor-setup`.

5. Complete `$rigor-evidence` when the class requires research/design. Freeze the design only after the project acceptance profile has established the real acceptance target.

The selected project acceptance profile cannot be changed after implementation/governed execution starts. Do not create task-local acceptance definitions or lower criteria after seeing results.

## Resource plan

Before resource-heavy execution, run `scripts/inspect_resources.py` through an observable tool/command. Record the plan against that successful observation:

```bash
scripts/rigorctl.py resources plan \
  --gpus <n> --cpu-workers <n> \
  --strategy <measured-plan> \
  --observed <inspect_resources.py-command-or-tool-id>
```

Compute cost is not a constraint. Optimize correctness, reproducibility, then wall-clock. Increase useful GPU workload and CPU/data parallelism toward stable measured headroom; do not create meaningless utilization or oversubscription.

## Delegation

Before each subagent spawn, create an assignment with every field in [references/task-contract.md](references/task-contract.md). Include the emitted `[RIGOR_ASSIGNMENT:asg_...]` token in the spawn prompt. Worker/runner assignments require a selected project acceptance profile. The Hook validates the contract and injects it into the child, including the task resource plan and selected acceptance profile.

The Lead selects references, architecture, integration, and final acceptance. Workers execute frozen designs; they do not choose replacements.

## Stop or completion

Close only with `rigorctl task close` after all required gates pass. If work genuinely cannot continue, update HANDOFF/LOG, run `$rigor-continuity`, then explicitly `task pause` with the exact reason. `task abort` remains an explicit terminal escape for abandoned work. Never manufacture evidence to satisfy a gate.
