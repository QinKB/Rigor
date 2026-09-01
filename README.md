# Rigor

Rigor is an evidence-gated research-engineering control plugin for Codex.

It is designed for repository work where correctness depends on more than producing code that compiles or passes isolated tests.

Rigor controls:

- why a technical design is justified;
- which reference implementation or primary source supports it;
- what design has been frozen;
- which subagent is allowed to perform which work;
- how the change enters the real system;
- which compute resources should be used;
- what real execution evidence is required;
- when Codex is allowed to claim completion.

Rigor complements minimalism plugins such as Ponytail.

**Rigor decides what must be built and what proves it correct.  
Ponytail may simplify the implementation only inside that frozen contract.**

The core principle is:

> Skills teach Codex how to satisfy a requirement. Hooks, scripts, and persistent state enforce whether the requirement has actually been satisfied.

## Architecture

Rigor separates workflow guidance from enforcement:

```text
Skills
  -> explain how to satisfy each gate

Hooks
  -> block governed actions when required gates are missing

Scripts
  -> perform deterministic checks and state transitions

State
  -> records what actually happened instead of relying on model memory

Project Profile
  -> defines the real repository entry points, protected surfaces,
     acceptance profiles, and compute requirements
```

The stable gates are:

```text
research
design
delegation
integration
acceptance
memory
git
```

## Included Skills

Rigor contains five focused Skills:

- `rigor-setup` — initialize Rigor and build the repository Project Profile.
- `rigor-task` — establish the governed task, select its acceptance profile, plan resources, and create delegation contracts.
- `rigor-evidence` — gather current evidence and freeze an evidence-backed design.
- `rigor-verify` — validate the real integration path and record acceptance evidence.
- `rigor-continuity` — maintain HANDOFF, MEMORY, and LOG state across sessions and compaction.

Skills are guidance. They are not the enforcement boundary.

## Lifecycle Hooks

Rigor currently uses:

```text
SessionStart
PreCompact
SubagentStart
SubagentStop
PreToolUse
PostToolUse
Stop
```

`PreToolUse` is the main enforcement boundary.

It can block consequential repository writes, long/resource-heavy execution, Git checkpoints, or subagent dispatch when the required Rigor contracts have not been established.

`PostToolUse` records actual successful or failed tool execution into the project evidence ledger.

`SubagentStart` injects the employee contract into the child agent.

`SubagentStop` rejects unsupported completion claims.

`Stop` prevents the Lead from ending an active task whose required gates have not passed.

## Installation

### Install from the GitHub marketplace

Add the Rigor marketplace:

```bash
codex plugin marketplace add QinKB/Rigor
```

Install the plugin:

```bash
codex plugin add rigor@rigor
```

Restart Codex after installation.

Then open:

```text
/hooks
```

Review and trust the Rigor hooks.

Open a new thread after installing or updating the plugin so the current Skills and Hook definitions are loaded.

### Optional local development install

The repository also contains a local installer for development or offline testing:

```bash
python scripts/install_local_plugin.py
```

The marketplace installation above is the normal installation path.

## Initialize a Repository

Rigor is opt-in per repository.

Invoke:

```text
$rigor-setup
```

or run:

```bash
python /path/to/rigor/scripts/setup_project.py \
  --root /path/to/repository \
  --install-agents
```

The setup script creates the initial repository state:

```text
.codex/rigor.json
HANDOFF.md
MEMORY.md
LOG.md
.codex/agents/
```

The initial `.codex/rigor.json` intentionally starts with:

```json
{
  "schema_version": 2,
  "enabled": true,
  "project": {
    "configured": false,
    "type": "unknown",
    "entrypoints": {},
    "protected_surfaces": [],
    "acceptance_profiles": {},
    "compute": {}
  },
  "overrides": {}
}
```

`configured=false` means the repository has not yet established its real execution and acceptance contract.

Rigor may still inspect code and gather setup evidence, but consequential implementation must not proceed until `$rigor-setup` has inspected the repository and populated the Project Profile.

## Project Profile

The Project Profile belongs to the repository, not to the global plugin.

It defines repository-specific facts such as:

```text
project.type
project.entrypoints
project.protected_surfaces
project.acceptance_profiles
project.compute
```

Rigor itself does not hard-code deep-learning, web, CLI, robotics, or other domain-specific execution rules.

For example, one machine-learning repository may define:

```json
{
  "project": {
    "configured": true,
    "type": "ml-research",
    "entrypoints": {
      "train": "tools/train.py",
      "inference": "tools/test.py",
      "evaluation": "tools/test.py"
    },
    "protected_surfaces": [
      "models/**",
      "datasets/**",
      "tools/train.py",
      "tools/test.py"
    ],
    "acceptance_profiles": {
      "model-change": {
        "required_level": "L4",
        "levels": {
          "L1": {
            "description": "real model integration",
            "observed_patterns": [
              "integration"
            ]
          },
          "L2": {
            "description": "real operational lifecycle",
            "observed_patterns": [
              "train"
            ]
          },
          "L3": {
            "description": "fresh state and reload/runtime path",
            "observed_patterns": [
              "checkpoint",
              "test"
            ]
          },
          "L4": {
            "description": "authoritative evaluation",
            "observed_patterns": [
              "tools/test.py"
            ],
            "authoritative": true
          }
        }
      }
    },
    "compute": {
      "required_gpu_count": 2
    }
  }
}
```

This is project configuration, not a global Rigor rule.

A different repository should define a different profile.

## Normal Workflow

A governed task follows this control flow:

```text
$rigor-task
    |
    +-> start task
    |
    +-> select repository acceptance profile
    |
    +-> inspect and freeze resource plan when required
    |
    v
$rigor-evidence
    |
    +-> inspect current repository
    +-> discover candidate references
    +-> open decisive primary/upstream sources
    +-> register verified evidence
    +-> freeze design
    |
    v
implementation
    |
    +-> PreToolUse checks required gates
    +-> repository mutation invalidates stale validation
    |
    v
$rigor-verify
    |
    +-> real integration execution
    +-> L0-L4 acceptance evidence
    |
    v
$rigor-continuity
    |
    +-> HANDOFF
    +-> MEMORY
    +-> LOG
    |
    v
Git checkpoint
    |
    v
rigorctl task close
```

## Verification Profiles

Tasks do not invent their own definition of L4.

The repository defines named acceptance profiles in:

```text
.codex/rigor.json
```

A task selects one with:

```bash
python scripts/rigorctl.py verification select \
  --profile <profile-name>
```

The selected profile is frozen before consequential implementation.

It cannot be replaced with a weaker task-local verification definition after implementation begins.

This prevents checks such as syntax validation, imports, shape checks, or isolated unit tests from being arbitrarily declared authoritative project acceptance.

## Acceptance Levels

Rigor uses the following generic levels:

- **L0 — Preflight:** syntax, imports, static checks, shapes/interfaces, mocks, isolated unit tests, narrow CPU checks.
- **L1 — Integrated:** the real entry point executes the change and the intended downstream consumer actually uses the result.
- **L2 — Operational:** the required real state-changing lifecycle succeeds.
- **L3 — Reproducible runtime:** current code/config produces required fresh state or artifacts and they survive the intended reload/runtime path.
- **L4 — Outcome accepted:** the authoritative evaluator, scientific protocol, or closest practical user/system outcome produces valid evidence.

A Git commit is not an acceptance level.

A standalone module is not L1 unless the real system actually consumes it.

## Evidence Model

Rigor distinguishes discovery from verified evidence.

For example:

```text
GitHub search
    -> discovered upstream candidate

fetch/read exact upstream file
    -> verified upstream implementation
```

Similarly:

```text
literature search
    -> candidate source

read decisive paper/specification content
    -> verified primary source
```

Search results, titles, snippets, abstracts, and remembered descriptions are not sufficient to freeze an authoritative design reference.

For research-sensitive changes, a frozen design is bound to actual evidence IDs recorded during the current task.

## Subagent Contracts

Subagents are bounded employees.

Before spawning a governed subagent, the Lead creates a complete assignment containing:

```text
objective
reference
target
method
integration
resources
write_scope
acceptance
output
stop_conditions
```

Rigor emits an assignment token:

```text
[RIGOR_ASSIGNMENT:asg_...]
```

The token is included in the spawn request.

The Agent `PreToolUse` hook validates the assignment and injects the contract into the child.

`SubagentStart` reinforces the contract:

- the child is not the Lead;
- it must follow the frozen reference and design;
- it may not choose a replacement architecture;
- it may not lower acceptance;
- reference incompatibility must be returned to the Lead;
- isolated module tests do not establish project completion;
- the task resource policy applies to the child;
- Ponytail may simplify code only inside the frozen Rigor contract.

A `followup_task` may reuse a bound agent when the work still belongs to its validated assignment.

New work requires a new assignment contract.

## Resource Policy

Rigor treats authorized compute cost as non-binding unless the repository says otherwise.

Priority is:

```text
correctness
reproducibility
wall-clock
```

Before resource-heavy execution, inspect the actual system:

```bash
python scripts/inspect_resources.py
```

Then record the task resource plan:

```bash
python scripts/rigorctl.py resources plan \
  --gpus <n> \
  --cpu-workers <n> \
  --strategy "<measured strategy>" \
  --observed <resource-inspection-tool-or-id>
```

`project.compute.required_gpu_count` expresses how many GPUs the project requires.

Rigor deliberately does **not** prescribe a specific launcher such as `torchrun`, `accelerate`, or `python train.py`.

A repository may implement its distributed execution however it chooses as long as the project resource contract is satisfied.

## Continuity

Durable human-readable state lives in:

```text
HANDOFF.md
MEMORY.md
LOG.md
```

- `HANDOFF.md` — exact continuation state and next action.
- `MEMORY.md` — verified, non-obvious, durable project knowledge.
- `LOG.md` — operational chronology, experiments, failures, and execution evidence.

Machine state and the JSONL evidence ledger live under the plugin writable data directory (`PLUGIN_DATA`), keyed by repository path.

Later repository mutations invalidate stale integration, acceptance, memory, and Git gate evidence.

## Git Policy

Rigor blocks destructive Git operations covered by the configured safety policy.

`git push` is denied by default because it is an external write.

A project checkpoint is not proof of correctness.

Git comes after the required integration, acceptance, and continuity gates.

## Ponytail Compatibility

Rigor has no Hook ordering dependency on Ponytail.

The contract is:

```text
Rigor
    -> freezes evidence, design, integration,
       resources, and acceptance

Ponytail
    -> may simplify implementation only inside
       those frozen semantic boundaries
```

Minimality never authorizes changing:

```text
reference semantics
design intent
integration path
acceptance criteria
required validation
```

## Limitations

- Hosted tools that do not emit normal local tool Hook events cannot automatically become audited `PostToolUse` evidence.
- Use observable MCP tools such as Exa or GitHub when external evidence must be automatically audited.
- Hooks are execution guardrails, not an operating-system security sandbox.
- Repository-specific behavior depends on the quality of the Project Profile established by `$rigor-setup`.
- Custom agent TOML files are installed separately because Codex plugins currently package Skills/Hooks/MCP/assets while custom agent profiles live under `.codex/agents/` or `~/.codex/agents/`.

## Development and Tests

Run the complete test suite:

```bash
python -m unittest discover \
  -s tests \
  -p "test_*.py" \
  -v
```

Compile all Python modules:

```bash
python -m compileall \
  -q rigor hooks scripts skills
```

Important regression scenarios should cover:

- search result cannot become a verified upstream implementation;
- design cannot freeze without required verified evidence;
- task-local verification plans cannot be invented;
- selected project acceptance profiles cannot be weakened after implementation begins;
- stale observations from an earlier task cannot satisfy a new task;
- later repository writes invalidate old acceptance evidence;
- a subagent cannot self-assert completion without observed validation;
- configured GPU requirements are enforced without prescribing a particular launcher;
- Stop cannot claim task completion before all required gates and explicit task close.