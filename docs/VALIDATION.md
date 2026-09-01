# Codex Rigor 1.1.0 Validation

Validated on 2026-09-01 before packaging.

## Functional tests

All 43 test methods passed when executed in stable isolated groups:

- 28 unit/structure/installer tests passed.
- 13 lifecycle Hook tests passed.
- 2 end-to-end scenarios passed.

The end-to-end `new-design` scenario covers current-task evidence, evidence-bound design freeze, Worker contract, subagent context injection, successful observed execution, L4 acceptance, continuity, Git gate, explicit task close, and Stop.

A single-process `unittest discover` run was also attempted. In this execution sandbox it hit the outer 180-second command timeout after its first 10 Hook tests had passed. This aggregate run is not counted as validation evidence; every test method was run successfully in smaller groups instead.

## Skill validation

The Skill Creator validator reported `Skill is valid!` for all five bundled skills:

- `rigor-setup`
- `rigor-task`
- `rigor-evidence`
- `rigor-verify`
- `rigor-continuity`

## Static/release checks

- `python3 -m compileall -q rigor hooks scripts skills`: passed.
- Plugin manifest and Hook JSON parse: passed.
- All five custom-agent TOML templates parse: passed.
- CLI `--help` smoke checks for `rigorctl.py`, `install_local_plugin.py`, `setup_project.py`, `inspect_resources.py`, and `install_agents.py`: passed.
- Non-test unfinished-marker scan: clean.

## Guardrails covered by regression tests

- no governed write before task/gate initialization;
- no research/design-sensitive write before required evidence and frozen design;
- common Bash write paths cannot bypass design gates;
- write-like Serena/MCP paths cannot bypass design gates;
- generic sensitive paths cannot be mislabeled as a mechanical task to bypass research/design;
- destructive Git operations are denied;
- Worker spawn requires a complete frozen assignment contract;
- `fork_turns: all` is rejected for routine governed dispatch;
- `followup_task` can reuse the bound employee contract without silently changing it;
- a child cannot self-assert success without fresh observed planned execution;
- failed or ambiguous execution cannot back L1-L4 evidence;
- stale observations from an earlier task cannot satisfy the current task;
- later governed repository mutations invalidate earlier integration/acceptance/memory/Git evidence;
- resource plans require observed hardware state and use all eligible GPUs in auto mode;
- continuity must be updated for the active task;
- Stop blocks incomplete tasks and also requires explicit task close after all gates pass.

## Known boundary

Hooks are deterministic workflow guardrails, not a formal OS security sandbox. Hosted built-in WebSearch is not locally observable through normal Pre/PostToolUse hooks, so auditable external-search requirements should use observable MCP tooling such as Exa. The plugin fails closed for its configured governed paths and common write surfaces, while documenting this platform boundary rather than claiming impossible enforcement.
