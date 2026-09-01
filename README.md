# Rigor

Rigor is an evidence-gated research-engineering plugin for Codex. It complements, rather than replaces, minimalism plugins such as Ponytail.

- **Rigor** freezes what must be built, why, from which reference, how it integrates, which employee owns it, which resources it may use, and what evidence proves completion.
- **Ponytail** may simplify the implementation only inside that frozen contract.

The core principle is: Skills teach how to satisfy a requirement; Hooks + scripts + state make required gates difficult to skip.

## Included

- Five progressive-disclosure skills: setup, task, evidence, verify, continuity.
- Lifecycle enforcement through SessionStart, PreCompact, SubagentStart/Stop, Pre/PostToolUse, Stop, and SessionEnd.
- Stable gates: `research`, `design`, `delegation`, `integration`, `acceptance`, `memory`, `git`.
- Stable assignment fields: `objective`, `reference`, `target`, `method`, `integration`, `resources`, `write_scope`, `acceptance`, `output`, `stop_conditions`.
- Project/user custom-agent templates: scout, researcher, runner, worker, reviewer.
- Deterministic `rigorctl` state machine and JSONL evidence ledger.
- Observed-source research gate: selected local code, literature/official sources, upstream code/issues, and external search must be tied to successful current-task tool observations when required; stale observations from earlier tasks cannot satisfy a new gate.
- Shell-write guard for common Bash edit paths (`sed -i`, `tee`, redirection, `cp`/`mv`/`rm`, Python file writes, etc.) plus write-like repository/Serena/MCP tools, so the Lead cannot trivially bypass write gates by switching edit surfaces.
- Generic sensitive-path classifier blocks a `mechanical` task from mutating model/training/data/evaluation semantic paths; projects can override the patterns in `.codex/rigor.json`.
- Frozen designs are bound to actual selected evidence IDs; new-design/reference-adaptation requires a primary definition plus upstream implementation by default, and Workers must use the same frozen reference/integration contract.
- Resource plans include a live hardware snapshot and, by default, must use all currently eligible GPUs for governed GPU work; CPU concurrency must be non-zero and within visible CPU capacity.
- Generic acceptance L0-L4. Any later governed repository mutation invalidates prior integration/acceptance/memory/Git evidence and requires fresh post-mutation validation. No domain-specific algorithm is hard-coded.

## Install and initialize

After extracting this package, the included installer can copy the plugin into your personal Codex plugin directory and register it in the personal marketplace without replacing unrelated marketplace entries:

```bash
cd /path/to/codex-rigor
python3 scripts/install_local_plugin.py
```

Use `--force` only when intentionally replacing an existing local Codex Rigor copy; the installer creates a timestamped backup first. Then restart Codex/ChatGPT Desktop, install/enable **Codex Rigor** from Personal Plugins, and open `/hooks` to review and trust the bundled hooks.

For each target repository:

1. Invoke `$rigor-setup`, or run the setup script from the installed plugin path:

```bash
python3 /path/to/codex-rigor/scripts/setup_project.py --root /path/to/repo --install-agents
```

2. Inspect `.codex/rigor.json`; set project-specific compute or sensitive-path overrides there when needed.
3. Start a new thread so SessionStart loads the project state.
4. Begin consequential work with `$rigor-task`.

The repository opt-in file is `.codex/rigor.json`. Without it, the plugin remains passive and only suggests setup on SessionStart.

## Normal workflow

```text
$rigor-task
    -> task start / resource plan / assignment contract
$rigor-evidence (when required)
    -> selected evidence -> frozen design
implementation
    -> PreToolUse refuses writes if research/design gates are missing
$rigor-verify
    -> integration + L0-L4 acceptance evidence bound to observed tool execution
$rigor-continuity
    -> HANDOFF/MEMORY/LOG sync
Git checkpoint
    -> git gate
rigorctl task close
```

Subagent dispatch requires an assignment token such as `[RIGOR_ASSIGNMENT:asg_ab12cd34]`. A `followup_task` may reuse the currently bound assignment; new related work can reuse the same agent by creating a new same-role assignment and including its token in the follow-up. The Agent PreToolUse hook validates the contract and injects it into the child. SubagentStop requires a structured result block, preventing a worker from silently treating an isolated module or low-level test as full completion.

## State and privacy

Machine state and the JSONL tool ledger live under the plugin writable data directory (`PLUGIN_DATA`) keyed by a hash of the repository path. The plugin does not upload this data. Durable human-readable state remains in repository `HANDOFF.md`, `MEMORY.md`, and `LOG.md`.

## Ponytail compatibility

No hook-order dependency exists. Rigor defines immutable semantic/acceptance boundaries. Ponytail can reduce implementation complexity only without changing those boundaries. Rigor's parent and subagent contexts repeat this rule.

## Limitations

- Hosted tools such as built-in WebSearch do not pass through local Pre/PostToolUse hooks in current Codex releases. Use observable MCP search tools (for example Exa) when auditable external-search evidence is required. Under the default policy, manually registered but unobserved search/source claims do not satisfy the research gate.
- Hooks are guardrails, not a formal security boundary; specialized tool paths can opt out of normal tool hooks, and shell-write detection intentionally covers common edit patterns rather than attempting to parse every possible program that could mutate files.
- Custom-agent TOML files are installed by `install_agents.py` because plugin manifests currently package skills/hooks/MCP/assets, while repository/user custom-agent files live in `.codex/agents/` or `~/.codex/agents/`.

## Test

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q rigor hooks scripts skills
```
# Rigor
