#!/usr/bin/env python3
from __future__ import annotations
import json, os, re, sys
from pathlib import Path

ROOT=Path(os.environ.get("PLUGIN_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0,str(ROOT))
from rigor.acceptance import at_least
from rigor.contracts import parse_result, render_assignment, validate_assignment
from rigor.hook_io import allow, context, deny, emit, read_event
from rigor.runtime import agent_action_from_input, agent_id_from_input, assignment_id_from_input, agent_type_from_input, inject_assignment, is_destructive, is_git_checkpoint, is_governed_mcp_write, is_long_run, is_repository_write_command, is_sensitive_repository_target, observed_tool_record, resolve, session_context, task_class_allows_sensitive_write, targets_are_continuity_files, tool_write_targets


def main():
    ev=read_event()
    try:
        return _main(ev)
    except Exception as exc:
        event = ev.get("hook_event_name")
        governed = _governed_hint(ev.get("cwd") or os.getcwd())
        if event == "PreToolUse" and governed:
            emit(deny("Codex Rigor hook error; governed action cannot be verified safely: %s" % exc))
        elif event in {"Stop", "SubagentStop"} and governed and not ev.get("stop_hook_active"):
            emit({"decision":"block","reason":"Codex Rigor hook error; completion cannot be verified safely: %s" % exc})
        elif event in {"Stop", "SubagentStop"}:
            emit({})
        return 0

def _governed_hint(cwd):
    try:
        root = Path(cwd).resolve()
        for candidate in [root, *root.parents]:
            policy = candidate / ".codex" / "rigor.json"
            if policy.exists():
                raw = json.loads(policy.read_text(encoding="utf-8"))
                return raw.get("enabled", False) is True
    except Exception:
        pass
    return False


def _main(ev):
    event=ev.get("hook_event_name",""); cwd=ev.get("cwd") or os.getcwd()
    root,policy,policy_path,state=resolve(cwd)
    enabled=bool(policy.get("enabled"))
    if not enabled:
        if event=="SessionStart":
            emit(context("SessionStart", "Codex Rigor is installed but this repository is not initialized. Use $rigor-setup to opt in."))
        elif event in {"Stop","SubagentStop"}: emit({})
        return 0

    if event=="SessionStart":
        state.log("session_start",session_id=ev.get("session_id"),source=ev.get("source"))
        emit(context("SessionStart",session_context(root,policy,state,policy_path),"RIGOR")); return 0
    if event=="PreCompact":
        state.log("pre_compact",session_id=ev.get("session_id"),trigger=ev.get("trigger")); return 0
    if event=="PostToolUse":
        rec=observed_tool_record(ev); state.record_observed_tool(rec); return 0
    if event=="PreToolUse":
        return pre_tool(ev,policy,state)
    if event=="SubagentStart":
        agent_id=ev.get("agent_id") or "unknown"; agent_type=ev.get("agent_type") or "unknown"; asg=state.bind_agent(agent_id,agent_type)
        text=[
            "CODEX RIGOR SUBAGENT POLICY",
            "You are a bounded employee, not the Lead.",
            "Follow the authoritative reference, frozen method, integration path, write scope, resource plan, and acceptance contract supplied by the Lead.",
            "Do not redefine architecture, replace a mechanism with a convenient approximation, or lower/reinterpret acceptance.",
            "If the reference or assumptions do not fit, stop and return evidence instead of inventing a substitute.",
            "Use assigned GPU/CPU resources efficiently; compute cost is not a constraint, but meaningless utilization and oversubscription are not goals.",
            "A standalone module, syntax/import/shape check, or isolated unit test is preflight evidence, not project completion.",
            "Only claim the acceptance level actually observed through the real integration path.",
            "If Ponytail is active, simplify only inside the frozen Rigor contract.",
        ]
        if asg: text += ["",render_assignment(asg)]
        else: text += ["", "No bound Rigor assignment was found. Do not perform consequential implementation; return to the Lead if your task requires one."]
        emit(context("SubagentStart","\n".join(text),"RIGOR:%s"%agent_type.upper())); return 0
    if event=="SubagentStop":
        if ev.get("stop_hook_active"): emit({}); return 0
        asg=state.agent_assignment(ev.get("agent_id") or "")
        if not asg: emit({}); return 0
        result=parse_result(ev.get("last_assistant_message") or "")
        if not result:
            emit({"decision":"block","reason":"Before stopping, emit the required RIGOR_ASSIGNMENT_RESULT block from your assignment contract. If blocked or partial, say so explicitly instead of claiming completion."}); return 0
        if result.get("assignment_id")!=asg.get("id"):
            emit({"decision":"block","reason":"RIGOR_ASSIGNMENT_RESULT has the wrong assignment_id. Report the result for %s."%asg.get("id")}); return 0
        status=result.get("status","").lower(); level=result.get("acceptance","").upper()
        if status=="complete":
            try: ok=at_least(level,asg.get("acceptance"))
            except Exception: ok=False
            if not ok:
                emit({"decision":"block","reason":"Assignment claims complete at %s but contract requires %s. Continue validation/integration or return status partial/blocked with exact remaining work."%(level or "unknown",asg.get("acceptance"))}); return 0
            for field in ("integration","validation","evidence"):
                if not result.get(field) or result.get(field,"none").lower()=="none":
                    emit({"decision":"block","reason":"Assignment claims complete but result field '%s' lacks evidence. Inspect the real path and report observed evidence."%field}); return 0
            try:
                state.validate_assignment_result_evidence(asg,result)
            except ValueError as exc:
                emit({"decision":"block","reason":"Assignment completion evidence rejected: %s. Run the planned real check, then report its exact command/tool/tool_use_id in validation."%exc}); return 0
        state.finish_assignment(asg["id"],result)
        emit({}); return 0
    if event=="Stop":
        if ev.get("stop_hook_active"): emit({}); return 0
        task=state.active_task()
        if not task or task.get("status") in {"paused","aborted","completed"}: emit({}); return 0
        missing=state.missing_gates(task)
        if policy.get("stop_policy")=="active-task":
            if missing:
                emit({"decision":"block","reason":"Codex Rigor: active task %s is not complete. Missing gates: %s. Continue through the required Skills/checks, or explicitly pause/abort the task with rigorctl if work genuinely cannot continue."%(task["id"],", ".join(missing))}); return 0
            emit({"decision":"block","reason":"Codex Rigor: all gates pass, but task %s is still active. Run rigorctl task close before ending so completion is explicit and persisted."%task["id"]}); return 0
        emit({}); return 0
    return 0


def pre_tool(ev,policy,state):
    tool=ev.get("tool_name",""); inp=ev.get("tool_input") or {}; task=state.active_task()
    continuity_missing = state.continuity_missing()
    write_targets = tool_write_targets(tool, inp, state.root)
    continuity_only_write = targets_are_continuity_files(write_targets, policy, state.root)
    sensitive_targets = [x for x in write_targets if is_sensitive_repository_target(x, policy, state.root)]
    if task and sensitive_targets and not task_class_allows_sensitive_write(task, policy, sensitive_targets, state.root):
        emit(deny("Repository write blocked: task class %s is too weak for research-sensitive target(s): %s. Reclassify the task honestly before changing technical semantics." % (task.get("class"), ", ".join(sensitive_targets[:5])))); return 0
    if tool=="Bash":
        command=str(inp.get("command","") if isinstance(inp,dict) else "")
        if re.search(r"(^|\s)git\s+push(?:\s|$)", command, re.I):
            if not policy.get("git", {}).get("allow_push", False):
                emit(deny(
                    "Codex Rigor blocked git push. "
                    "Pushing is an external write and requires explicit project/user authorization."
                ))
                return 0
        if is_destructive(command,policy): emit(deny("Codex Rigor blocked a destructive command. Use a reversible, task-scoped alternative.")); return 0
        if is_repository_write_command(command, policy, state.root) and not is_git_checkpoint(command, policy):
            if continuity_only_write:
                emit({}); return 0
            if task and task.get("class") == "mechanical" and not write_targets and policy.get("classification",{}).get("block_unknown_write_target_for_mechanical",True):
                emit(deny("Repository write through Bash blocked: mechanical task has an unclassifiable write target. Use an explicit path or reclassify the task so research-sensitive semantics cannot be bypassed.")); return 0
            if continuity_missing: emit(deny("Repository write blocked: required continuity files are missing/empty: "+", ".join(continuity_missing))); return 0
            if not task: emit(deny("Repository writes through Bash require an active Rigor task. Invoke $rigor-task first.")); return 0
            if task.get("status")!="active": emit(deny("The active Rigor task is not in active status.")); return 0
            for gate in ("research","design"):
                if gate in task.get("required_gates",[]) and not task["gates"][gate]["passed"]:
                    emit(deny("Repository write through Bash blocked: %s gate is incomplete. Freeze the supported design before implementation."%gate)); return 0
            if policy.get("verification",{}).get("require_frozen_plan",True) and not task.get("verification_plan"):
                emit(deny("Repository write through Bash blocked: freeze the verification plan before implementation.")); return 0
            state.mark_implementation_started(tool,ev.get("tool_use_id"))
        if is_long_run(command,policy):
            if continuity_missing: emit(deny("Long/resource-heavy execution blocked: required continuity files are missing/empty: "+", ".join(continuity_missing))); return 0
            if not task: emit(deny("Long/resource-heavy execution requires an active Rigor task. Invoke $rigor-task first.")); return 0
            if policy.get("verification",{}).get("require_frozen_plan",True) and not task.get("verification_plan"):
                emit(deny("Long/resource-heavy execution requires freeze the verification plan before implementation to be frozen before launch.")); return 0
            if policy.get("compute",{}).get("resource_plan_required_for_long_runs",True) and not task.get("resources"):
                emit(deny("Long/resource-heavy execution requires a frozen resource plan backed by an observed resource inspection.")); return 0
            state.mark_implementation_started(tool,ev.get("tool_use_id"),invalidate=False)
        if is_git_checkpoint(command,policy):
            if not task: emit(deny("A task checkpoint requires an active Rigor task.")); return 0
            missing=[g for g in ("integration","acceptance","memory") if g in task.get("required_gates",[]) and not task["gates"][g]["passed"]]
            if missing: emit(deny("Git checkpoint blocked until gates pass: "+", ".join(missing))); return 0
        emit({}); return 0
    if tool in {"apply_patch","Edit","Write"}:
        if continuity_only_write:
            emit({}); return 0
        if continuity_missing: emit(deny("Repository write blocked: required continuity files are missing/empty: "+", ".join(continuity_missing))); return 0
        if not task: emit(deny("Repository writes require an active Rigor task. Invoke $rigor-task and establish the task contract first.")); return 0
        if task.get("status")!="active": emit(deny("The active Rigor task is not in active status.")); return 0
        for gate in ("research","design"):
            if gate in task.get("required_gates",[]) and not task["gates"][gate]["passed"]:
                emit(deny("Repository write blocked: %s gate is incomplete. Use $rigor-evidence and freeze the supported design before implementation."%gate)); return 0
        if policy.get("verification",{}).get("require_frozen_plan",True) and not task.get("verification_plan"):
            emit(deny("Repository write blocked: freeze the verification plan before implementation before implementation so acceptance cannot be invented after seeing results.")); return 0
        state.mark_implementation_started(tool,ev.get("tool_use_id"))
        emit({}); return 0
    if is_governed_mcp_write(tool, inp, policy, state.root):
        if continuity_only_write:
            emit({}); return 0
        if task and task.get("class") == "mechanical" and not write_targets and policy.get("classification",{}).get("block_unknown_write_target_for_mechanical",True):
            emit(deny("MCP repository write blocked: mechanical task has an unclassifiable target. Use a tool/schema that exposes the target path or reclassify the task honestly.")); return 0
        if continuity_missing: emit(deny("MCP repository write blocked: required continuity files are missing/empty: "+", ".join(continuity_missing))); return 0
        if not task: emit(deny("MCP repository/external writes require an active Rigor task.")); return 0
        if task.get("status")!="active": emit(deny("The active Rigor task is not in active status.")); return 0
        for gate in ("research","design"):
            if gate in task.get("required_gates",[]) and not task["gates"][gate]["passed"]:
                emit(deny("MCP repository write blocked: %s gate is incomplete."%gate)); return 0
        if policy.get("verification",{}).get("require_frozen_plan",True) and not task.get("verification_plan"):
            emit(deny("MCP repository write blocked: freeze the verification plan before implementation.")); return 0
        state.mark_implementation_started(tool,ev.get("tool_use_id"))
        emit({}); return 0
    if tool=="Agent" or str(tool).lower()=="spawn_agent":
        action = agent_action_from_input(inp)
        if action == "followup":
            agent_id = agent_id_from_input(inp)
            if not agent_id:
                emit(deny("Subagent follow-up requires agent_id so Rigor can bind the correct employee contract.")); return 0
            aid = assignment_id_from_input(inp)
            try:
                asg = state.bind_followup_assignment(agent_id, aid)
            except ValueError as exc:
                emit(deny(str(exc))); return 0
            rewritten = inject_assignment(inp, asg)
            if rewritten is not None:
                emit(allow(updated_input=rewritten)); return 0
            emit(context("PreToolUse", "Rigor follow-up assignment %s validated." % asg["id"])); return 0
        if isinstance(inp, dict) and str(inp.get("fork_turns", "")).lower() == "all":
            emit(deny("Subagent dispatch with fork_turns=all is blocked because it can bypass intended role/model routing. Use fork_turns=none.")); return 0
        if not task: emit(deny("Subagent dispatch requires an active Rigor task.")); return 0
        if policy.get("delegation",{}).get("require_assignment",True):
            aid=assignment_id_from_input(inp)
            if not aid: emit(deny("Subagent dispatch blocked. Create a complete assignment with rigorctl assignment create and include [RIGOR_ASSIGNMENT:<id>] in the spawn prompt.")); return 0
            asg=state.assignment(aid)
            if not asg: emit(deny("Unknown Rigor assignment: %s"%aid)); return 0
            missing=validate_assignment(asg)
            if missing: emit(deny("Assignment is incomplete: "+", ".join(missing))); return 0
            atype=agent_type_from_input(inp)
            try: state.queue_assignment(aid,atype)
            except ValueError as exc: emit(deny(str(exc))); return 0
            rewritten=inject_assignment(inp,asg)
            if rewritten is not None: emit(allow(updated_input=rewritten)); return 0
            emit(context("PreToolUse","Rigor assignment %s validated; SubagentStart will inject its full contract."%aid)); return 0
        emit({}); return 0
    emit({}); return 0

if __name__=="__main__":
    sys.exit(main())
