from __future__ import annotations

import time
import uuid
from datetime import datetime
from pathlib import Path

from .acceptance import LEVELS, at_least, normalize_level
from .contracts import validate_assignment
from .policy import required_gates, research_requirements
from .resources import inspect_resources
from .util import atomic_write_json, append_jsonl, now_iso, plugin_data_dir, project_key, read_json, run_capture


ROLE_ALIASES = {"explorer": "scout"}


def _canonical_role(value):
    value = str(value or "").strip().lower()
    return ROLE_ALIASES.get(value, value)


class RigorState:
    def __init__(self, root, policy):
        self.root = Path(root).resolve()
        self.policy = policy
        self.base = plugin_data_dir() / "projects" / project_key(self.root)
        self.path = self.base / "state.json"
        self.ledger_path = self.base / "ledger.jsonl"
        self.data = read_json(self.path, None) or self._fresh()
        if self.data.get("project_root") != str(self.root):
            self.data = self._fresh()
        self._upgrade()
        self.save()

    def _fresh(self):
        return {
            "schema_version": 2,
            "project_root": str(self.root),
            "created_at": now_iso(),
            "active_task_id": None,
            "tasks": {},
            "assignments": {},
            "pending_assignments": [],
            "active_agents": {},
            "observed_tools": [],
        }

    def _upgrade(self):
        self.data["schema_version"] = 2
        for key, default in (("tasks", {}), ("assignments", {}), ("pending_assignments", []), ("active_agents", {}), ("observed_tools", [])):
            self.data.setdefault(key, default)
        for task in self.data.get("tasks", {}).values():
            task.setdefault("verification_plan", None)
            task.setdefault("implementation_started", None)
            task.setdefault("start_head", None)
            task.setdefault("last_mutation_epoch", None)
            task.setdefault("mutation_count", 0)

    def save(self):
        atomic_write_json(self.path, self.data)

    def log(self, event, **fields):
        append_jsonl(self.ledger_path, {"ts": now_iso(), "event": event, **fields})

    def active_task(self):
        tid = self.data.get("active_task_id")
        return self.data.get("tasks", {}).get(tid) if tid else None

    def start_task(self, objective, task_class, acceptance=None):
        active = self.active_task()
        if active and active.get("status") == "active":
            raise ValueError("an active task already exists: %s" % active["id"])
        if task_class not in self.policy.get("task_classes", {}):
            raise ValueError("unknown task class: %s" % task_class)
        tid = "task_" + uuid.uuid4().hex[:10]
        req = required_gates(self.policy, task_class)
        required_level = normalize_level(acceptance or self.policy["acceptance"]["default_required_level"])
        gates = {name: {"passed": False, "at": None, "evidence": []} for name in ["research", "design", "delegation", "integration", "acceptance", "memory", "git"]}
        for name, reason in (("research", "not required for task class"), ("design", "not required for task class"), ("delegation", "delegation gate is per assignment"), ("memory", "not required"), ("git", "not required")):
            if name not in req:
                self._pass_gate_obj(gates[name], reason)
        rc, head, _ = run_capture(["git", "rev-parse", "HEAD"], cwd=self.root)
        task = {
            "id": tid,
            "objective": objective,
            "class": task_class,
            "status": "active",
            "started_at": now_iso(),
            "started_epoch": time.time(),
            "start_head": head if rc == 0 else None,
            "required_gates": req,
            "required_acceptance": required_level,
            "gates": gates,
            "evidence": [],
            "design": None,
            "verification_plan": None,
            "implementation_started": None,
            "last_mutation_epoch": None,
            "mutation_count": 0,
            "integration": [],
            "acceptance": {"highest": None, "records": []},
            "resources": None,
            "pause_reason": None,
        }
        self.data["tasks"][tid] = task
        self.data["active_task_id"] = tid
        self.save()
        self.log("task_started", task_id=tid, task_class=task_class, objective=objective, required_acceptance=required_level)
        return task

    def pause_task(self, reason):
        task = self._require_task()
        if "memory" in task.get("required_gates", []) and not task["gates"]["memory"]["passed"]:
            raise ValueError("sync HANDOFF/MEMORY/LOG with rigorctl continuity sync before pausing so the next session has an explicit handoff")
        task["status"] = "paused"
        task["pause_reason"] = reason
        task["paused_at"] = now_iso()
        self.save(); self.log("task_paused", task_id=task["id"], reason=reason)
        return task

    def resume_task(self):
        task = self._require_task()
        task["status"] = "active"; task["pause_reason"] = None
        self.save(); self.log("task_resumed", task_id=task["id"])
        return task

    def abort_task(self, reason):
        task = self._require_task()
        task["status"] = "aborted"; task["abort_reason"] = reason; task["ended_at"] = now_iso()
        self.data["active_task_id"] = None
        self.save(); self.log("task_aborted", task_id=task["id"], reason=reason)
        return task

    def add_evidence(self, kind, source, locator, summary, observed=""):
        task = self._require_task()
        observed_record = None
        require_map = self.policy.get("research", {}).get("require_observed_kinds", {})
        if not str(source or "").strip() or not str(locator or "").strip() or not str(summary or "").strip():
            raise ValueError("evidence source, locator, and summary must be non-empty")
        if require_map.get(kind):
            observed_record = self._require_observed(observed, after_epoch=task.get("started_epoch"))
            observed_kind = observed_record.get("kind")
            provider = str(observed_record.get("provider") or "").lower()
            if kind == "local-code" and observed_kind not in {"local-code-search", "repository-tool"} and provider not in {"serena", "rg", "git"}:
                raise ValueError("local-code evidence must be backed by an observed local repository/code search")
            if kind == "local-paper" and observed_kind != "literature-tool":
                raise ValueError("local-paper evidence must be backed by an observed literature-library read/search")
            if kind == "primary-paper" and observed_kind not in {"literature-tool", "web-source-read"}:
                raise ValueError("primary-paper evidence must be backed by an observed paper/source read, not an unobserved citation")
            if kind in {"official-spec", "official-doc"} and observed_kind not in {"official-doc-tool", "web-source-read", "upstream-tool"}:
                raise ValueError("official evidence must be backed by an observed authoritative source read")
            if kind == "upstream-code" and observed_kind not in {"upstream-tool", "repository-tool"} and provider not in {"github", "git"}:
                raise ValueError("upstream-code evidence must be backed by an observed upstream/repository inspection")
            if kind == "issue" and observed_kind not in {"upstream-tool", "web-source-read", "external-search"}:
                raise ValueError("issue evidence must be backed by an observed upstream/web source")
            if kind == "external-search":
                if observed_kind != "external-search":
                    raise ValueError("external-search evidence must be backed by an observed external search tool")
                if source.lower() != provider:
                    raise ValueError("external-search source %r does not match observed provider %r" % (source, provider))
        elif kind == "external-search" and self.policy.get("research", {}).get("require_observed_external_search", True):
            providers = {x.get("provider") for x in self.data.get("observed_tools", []) if x.get("success") is True and float(x.get("epoch") or 0) >= float(task.get("started_epoch") or 0)}
            if source.lower() not in {str(x).lower() for x in providers if x}:
                raise ValueError("external-search evidence provider '%s' has not been observed by PostToolUse" % source)
        ev = {
            "id": "ev_" + uuid.uuid4().hex[:10],
            "kind": kind,
            "source": source,
            "locator": locator,
            "summary": summary,
            "observed": observed or None,
            "observed_tool": observed_record,
            "at": now_iso(),
        }
        task["evidence"].append(ev)
        self._refresh_research_gate(task)
        self.save(); self.log("evidence_selected", task_id=task["id"], evidence=ev)
        return ev

    def freeze_design(self, reference, target, method, integration, acceptance, reference_evidence_ids=None):
        task = self._require_task()
        if task.get("implementation_started"):
            raise ValueError("design cannot be changed after implementation/execution has started; pause/abort and create a new task if the design must change")
        self._refresh_research_gate(task)
        if "research" in task["required_gates"] and not task["gates"]["research"]["passed"]:
            raise ValueError("research gate is incomplete")
        for name, value in (("reference", reference), ("target", target), ("method", method), ("integration", integration)):
            if not str(value).strip():
                raise ValueError("design field is required: %s" % name)
        ids = [str(x).strip() for x in (reference_evidence_ids or []) if str(x).strip()]
        design_policy = self.policy.get("design", {})
        selected = []
        if design_policy.get("require_reference_evidence_ids", True):
            if not ids:
                raise ValueError("design must bind to selected evidence IDs; pass --reference-evidence ev_... for the authoritative sources")
            by_id = {ev.get("id"): ev for ev in task.get("evidence", [])}
            missing_ids = [x for x in ids if x not in by_id]
            if missing_ids:
                raise ValueError("design references unknown evidence IDs: %s" % ", ".join(missing_ids))
            selected = [by_id[x] for x in ids]
            selected_kinds = {ev.get("kind") for ev in selected}
            for group in design_policy.get("required_reference_groups", {}).get(task.get("class"), []):
                if not selected_kinds.intersection(set(group)):
                    raise ValueError("design reference evidence for %s must include one of: %s" % (task.get("class"), ", ".join(group)))
        level = normalize_level(acceptance)
        if LEVELS.index(level) < LEVELS.index(task["required_acceptance"]):
            raise ValueError("design acceptance cannot be lower than task required acceptance %s" % task["required_acceptance"])
        task["design"] = {"reference": reference, "reference_evidence_ids": ids, "reference_evidence": selected, "target": target, "method": method, "integration": integration, "acceptance": level, "frozen_at": now_iso()}
        self._pass_gate(task, "design", "frozen design contract")
        self.save(); self.log("design_frozen", task_id=task["id"], design=task["design"])
        return task["design"]

    def freeze_verification_plan(self, entrypoint, protocol, integration_patterns, acceptance_patterns, artifact_policy, notes=""):
        task = self._require_task()
        if task.get("implementation_started"):
            raise ValueError("verification plan must be frozen before implementation or governed execution starts")
        integration_patterns = [str(x).strip() for x in integration_patterns if str(x).strip()]
        acceptance_patterns = [str(x).strip() for x in acceptance_patterns if str(x).strip()]
        if not str(entrypoint).strip() or not str(protocol).strip() or not integration_patterns or not acceptance_patterns or not str(artifact_policy).strip():
            raise ValueError("verification plan requires entrypoint, protocol, integration patterns, acceptance patterns, and artifact policy")
        plan = {
            "required_level": task["required_acceptance"],
            "entrypoint": entrypoint,
            "protocol": protocol,
            "integration_patterns": integration_patterns,
            "acceptance_patterns": acceptance_patterns,
            "artifact_policy": artifact_policy,
            "notes": notes,
            "frozen_at": now_iso(),
        }
        task["verification_plan"] = plan
        self.save(); self.log("verification_plan_frozen", task_id=task["id"], plan=plan)
        return plan

    def mark_implementation_started(self, tool_name, tool_use_id=None, invalidate=True):
        task = self._require_task()
        first = not task.get("implementation_started")
        if first:
            task["implementation_started"] = {"at": now_iso(), "tool_name": tool_name, "tool_use_id": tool_use_id}
            self.log("implementation_started", task_id=task["id"], **task["implementation_started"])
        if invalidate:
            task["last_mutation_epoch"] = time.time()
            task["mutation_count"] = int(task.get("mutation_count") or 0) + 1
            reason = "invalidated by repository mutation via %s" % tool_name
            for gate_name in ("integration", "acceptance", "memory", "git"):
                if gate_name in task.get("required_gates", []):
                    gate = task["gates"][gate_name]
                    gate["passed"] = False
                    gate["at"] = None
                    gate.setdefault("evidence", []).append(reason)
            task["integration"] = []
            task["acceptance"] = {"highest": None, "records": []}
            self.log("validation_invalidated", task_id=task["id"], tool_name=tool_name, tool_use_id=tool_use_id, mutation_count=task["mutation_count"])
        self.save()
        return task["implementation_started"]

    def _current_validation_epoch(self, task):
        return max(float(task.get("started_epoch") or 0), float(task.get("last_mutation_epoch") or 0))

    def plan_resources(self, gpus, cpu_workers, strategy, notes="", observed=""):
        task = self._require_task()
        gpus = int(gpus); cpu_workers = int(cpu_workers)
        if gpus < 0 or cpu_workers < 0:
            raise ValueError("resource counts must be non-negative")
        compute = self.policy.get("compute", {})
        required_gpus = compute.get("project_cuda_gpus", "auto")
        if isinstance(required_gpus, int) and gpus < required_gpus:
            raise ValueError("project policy requires at least %d CUDA GPUs for governed execution" % required_gpus)
        if not str(strategy or "").strip():
            raise ValueError("resource strategy is required")
        obs = None
        if compute.get("require_observed_resource_inspection", True):
            obs = self._require_observed(observed, after_epoch=task.get("started_epoch"))
            if obs.get("kind") != "resource-inspection":
                raise ValueError("resource plan must be backed by an observed resource inspection")
        live = inspect_resources(self.root, compute)
        visible = int(live.get("visible_gpu_count") or 0)
        eligible = int(live.get("eligible_gpu_count") or 0)
        if gpus > visible:
            raise ValueError("resource plan requests %d GPUs but only %d are currently visible in the observed execution environment" % (gpus, visible))
        if required_gpus == "auto" and compute.get("enforce_all_eligible_gpus", True) and eligible and gpus < eligible:
            raise ValueError("resource plan must use all %d currently eligible GPUs (requested %d); change project policy only when the workload genuinely cannot use them" % (eligible, gpus))
        cpu_count = int((live.get("cpu") or {}).get("count") or 0)
        if cpu_count and cpu_workers > cpu_count:
            raise ValueError("resource plan requests %d CPU workers but only %d logical CPUs are visible" % (cpu_workers, cpu_count))
        if compute.get("maximize_useful_headroom", True) and cpu_count > 1 and cpu_workers == 0:
            raise ValueError("resource plan cannot set zero CPU workers while CPU resources are available; choose measured useful concurrency")
        task["resources"] = {"gpus": gpus, "cpu_workers": cpu_workers, "strategy": strategy, "notes": notes, "observed": observed, "observed_tool": obs, "live_snapshot": live, "at": now_iso()}
        self.save(); self.log("resources_planned", task_id=task["id"], resources=task["resources"])
        return task["resources"]

    def create_assignment(self, role, fields):
        task = self._require_task()
        if role == "worker" and "design" in task["required_gates"] and not task["gates"]["design"]["passed"]:
            raise ValueError("worker cannot be dispatched before design gate passes")
        if role == "worker" and task.get("design"):
            design = task["design"]
            if str(fields.get("reference", "")).strip() != str(design.get("reference", "")).strip():
                raise ValueError("worker reference must match the frozen design reference exactly")
            if str(fields.get("integration", "")).strip() != str(design.get("integration", "")).strip():
                raise ValueError("worker integration must match the frozen full-path design integration exactly")
        if role in {"worker", "runner"} and self.policy.get("verification", {}).get("require_frozen_plan", True) and not task.get("verification_plan"):
            raise ValueError("worker/runner dispatch requires the frozen verification plan")
        if role == "runner" and self.policy.get("compute", {}).get("resource_plan_required_for_long_runs", True) and not task.get("resources"):
            raise ValueError("runner dispatch requires a frozen task resource plan")
        data = {
            "id": "asg_" + uuid.uuid4().hex[:10],
            "task_id": task["id"],
            "role": role,
            "created_at": now_iso(),
            "created_epoch": time.time(),
            "status": "ready",
            "task_resource_plan": task.get("resources"),
            "verification_plan": task.get("verification_plan"),
            **fields,
        }
        missing = validate_assignment(data)
        if missing:
            raise ValueError("assignment missing: " + ", ".join(missing))
        self.data["assignments"][data["id"]] = data
        self._pass_gate(task, "delegation", "validated assignment %s" % data["id"])
        self.save(); self.log("assignment_created", task_id=task["id"], assignment_id=data["id"], role=role)
        return data

    def assignment(self, aid):
        return self.data.get("assignments", {}).get(aid)

    def queue_assignment(self, aid, agent_type=None):
        asg = self.assignment(aid)
        if not asg:
            raise ValueError("unknown assignment: %s" % aid)
        if asg.get("status") not in {"ready"}:
            raise ValueError("assignment %s is already %s; do not duplicate-dispatch it" % (aid, asg.get("status")))
        expected = _canonical_role(asg.get("role"))
        actual = _canonical_role(agent_type)
        if not actual:
            raise ValueError("agent_type/profile is required so the assignment role can be enforced")
        if expected != actual:
            raise ValueError("assignment role %s does not match agent type %s" % (asg.get("role"), agent_type))
        self.data["pending_assignments"].append({"assignment_id": aid, "agent_type": actual, "queued_at": now_iso()})
        asg["status"] = "queued"
        self.save(); self.log("assignment_queued", assignment_id=aid, agent_type=actual)

    def bind_agent(self, agent_id, agent_type):
        actual = _canonical_role(agent_type)
        idx = None
        for i, item in enumerate(self.data.get("pending_assignments", [])):
            aid = item.get("assignment_id"); asg = self.assignment(aid)
            if asg and _canonical_role(asg.get("role")) == actual and item.get("agent_type") == actual:
                idx = i; break
        if idx is None:
            return None
        item = self.data["pending_assignments"].pop(idx)
        aid = item["assignment_id"]; asg = self.assignment(aid)
        self.data["active_agents"][agent_id] = aid
        if asg:
            asg["status"] = "running"; asg["agent_id"] = agent_id; asg["agent_type"] = agent_type
        self.save(); self.log("agent_bound", assignment_id=aid, agent_id=agent_id, agent_type=agent_type)
        return asg

    def agent_assignment(self, agent_id):
        aid = self.data.get("active_agents", {}).get(agent_id)
        return self.assignment(aid) if aid else None

    def bind_followup_assignment(self, agent_id, aid=None):
        current = self.agent_assignment(agent_id)
        target = self.assignment(aid) if aid else current
        if not target:
            raise ValueError("follow-up target has no bound/known Rigor assignment")
        task = self.active_task()
        if not task or target.get("task_id") != task.get("id"):
            raise ValueError("follow-up assignment must belong to the current active Rigor task")
        if aid and current and _canonical_role(target.get("role")) != _canonical_role(current.get("role")):
            raise ValueError("follow-up assignment role must match the existing agent role")
        if aid and target is not current:
            if target.get("status") != "ready":
                raise ValueError("new follow-up assignment must be in ready state")
            self.data["active_agents"][agent_id] = aid
        elif target.get("status") == "complete":
            raise ValueError("completed assignment cannot be silently reused; create a new assignment contract for the follow-up")
        target["status"] = "running"
        target["agent_id"] = agent_id
        self.save(); self.log("followup_assignment_bound", assignment_id=target["id"], agent_id=agent_id)
        return target

    def finish_assignment(self, aid, result):
        asg = self.assignment(aid)
        if not asg:
            return
        asg["last_result"] = result; asg["status"] = result.get("status", "unknown"); asg["ended_at"] = now_iso()
        self.save(); self.log("assignment_result", assignment_id=aid, result=result)

    def _require_observed(self, needle, after_epoch=None):
        needle = str(needle or "").strip().lower()
        if not needle:
            raise ValueError("an observed command/tool/tool_use_id is required")
        matched_unsuccessful = False
        for item in self.data.get("observed_tools", []):
            if after_epoch is not None and float(item.get("epoch") or 0) < float(after_epoch):
                continue
            hay = " ".join(str(item.get(k, "")) for k in ("query", "tool_name", "tool_use_id")).lower()
            if needle in hay or (hay and hay in needle):
                if item.get("success") is True:
                    return item
                matched_unsuccessful = True
        if matched_unsuccessful:
            raise ValueError("matching PostToolUse observation did not prove successful execution: %s" % needle)
        raise ValueError("no successful PostToolUse observation matches: %s" % needle)

    def _require_plan_observation(self, task, lane, observed_record):
        if not self.policy.get("verification", {}).get("require_frozen_plan", True):
            return
        plan = task.get("verification_plan")
        if not plan:
            raise ValueError("verification plan is not frozen")
        patterns = plan.get("%s_patterns" % lane, [])
        hay = " ".join(str(observed_record.get(k, "")) for k in ("query", "tool_name", "tool_use_id")).lower()
        if not any(str(p).lower() in hay or (hay and hay in str(p).lower()) for p in patterns):
            raise ValueError("successful observation is not part of the frozen %s plan" % lane)

    def validate_assignment_result_evidence(self, assignment, result):
        level = normalize_level(result.get("acceptance"))
        if level == "L0":
            return None
        task = self.data.get("tasks", {}).get(assignment.get("task_id"))
        if not task:
            raise ValueError("assignment task state is missing")
        observed = self._require_observed(
            result.get("validation", ""),
            after_epoch=max(float(assignment.get("created_epoch") or 0), self._current_validation_epoch(task)),
        )
        lane = "integration" if level == "L1" else "acceptance"
        self._require_plan_observation(task, lane, observed)
        return observed

    def record_integration(self, entrypoint, evidence, observed=""):
        task = self._require_task()
        obs = self._require_observed(observed, after_epoch=self._current_validation_epoch(task)) if self.policy.get("integration", {}).get("require_observed_execution", True) else None
        if obs is not None:
            self._require_plan_observation(task, "integration", obs)
        rec = {"entrypoint": entrypoint, "evidence": evidence, "observed": observed, "observed_tool": obs, "at": now_iso()}
        task["integration"].append(rec)
        self._pass_gate(task, "integration", evidence)
        self.save(); self.log("integration_recorded", task_id=task["id"], record=rec)
        return rec

    def record_acceptance(self, level, evidence, observed=""):
        task = self._require_task(); level = normalize_level(level)
        obs = None
        if level != "L0":
            if self.policy.get("acceptance", {}).get("require_observed_execution", True):
                obs = self._require_observed(observed, after_epoch=self._current_validation_epoch(task))
            if obs is not None:
                self._require_plan_observation(task, "acceptance", obs)
        rec = {"level": level, "evidence": evidence, "observed": observed, "observed_tool": obs, "at": now_iso()}
        task["acceptance"]["records"].append(rec)
        highest = task["acceptance"].get("highest")
        if highest is None or LEVELS.index(level) > LEVELS.index(highest):
            task["acceptance"]["highest"] = level
        if at_least(task["acceptance"]["highest"], task["required_acceptance"]):
            self._pass_gate(task, "acceptance", evidence)
        self.save(); self.log("acceptance_recorded", task_id=task["id"], record=rec)
        return rec

    def continuity_missing(self):
        missing = []
        if not self.policy.get("memory", {}).get("required", True):
            return missing
        for rel in self.policy.get("memory", {}).get("files", []):
            p = self.root / rel
            if not p.exists() or not p.read_text(encoding="utf-8", errors="ignore").strip():
                missing.append(rel)
        return missing

    def sync_memory(self, memory_status, summary):
        task = self._require_task(); files = self.policy.get("memory", {}).get("files", []); missing = []; empty = []
        if memory_status not in {"updated", "no-new-durable-memory"}:
            raise ValueError("memory_status must be updated or no-new-durable-memory")
        if not str(summary or "").strip():
            raise ValueError("continuity summary is required")
        started_ts = task.get("started_epoch")
        if started_ts is None:
            try: started_ts = datetime.fromisoformat(task.get("started_at", "")).timestamp()
            except Exception: started_ts = 0
        stale = []
        for rel in files:
            p = self.root / rel
            if not p.exists(): missing.append(rel)
            elif not p.read_text(encoding="utf-8", errors="ignore").strip(): empty.append(rel)
            elif rel in {"HANDOFF.md", "LOG.md"} and p.stat().st_mtime < started_ts - 0.001: stale.append(rel)
        if missing or empty or stale:
            raise ValueError("continuity files invalid; missing=%s empty=%s not_updated_this_task=%s" % (missing, empty, stale))
        if memory_status == "updated":
            mp = self.root / "MEMORY.md"
            if mp.exists() and mp.stat().st_mtime < started_ts - 0.001:
                raise ValueError("MEMORY.md was declared updated but was not modified during this task")
        ev = "continuity synced; memory_status=%s; %s" % (memory_status, summary)
        self._pass_gate(task, "memory", ev)
        self.save(); self.log("memory_synced", task_id=task["id"], files=files, memory_status=memory_status, summary=summary)
        return {"files": files, "memory_status": memory_status, "summary": summary}

    def record_git(self):
        task = self._require_task()
        rc, head, err = run_capture(["git", "rev-parse", "HEAD"], cwd=self.root)
        if rc:
            raise ValueError("not a Git repository or cannot read HEAD: %s" % err)
        rc, status, err = run_capture(["git", "status", "--porcelain"], cwd=self.root)
        if rc:
            raise ValueError("cannot read Git status: %s" % err)
        if self.policy.get("git", {}).get("require_clean_checkpoint", True) and status.strip():
            raise ValueError("working tree is not clean; create the isolated task checkpoint before recording git gate")
        if self.policy.get("git", {}).get("require_checkpoint", True) and task.get("implementation_started") and task.get("start_head") == head:
            raise ValueError("git gate requires a task-scoped checkpoint newer than the task start HEAD")
        rec = {"head": head, "clean": not bool(status.strip()), "at": now_iso()}
        self._pass_gate(task, "git", "checkpoint %s" % head)
        self.save(); self.log("git_recorded", task_id=task["id"], record=rec)
        return rec

    def record_observed_tool(self, record):
        item = {**record, "at": now_iso(), "epoch": time.time()}
        self.data.setdefault("observed_tools", []).append(item)
        self.data["observed_tools"] = self.data["observed_tools"][-500:]
        self.save(); self.log("tool_observed", **item)
        return item

    def missing_gates(self, task=None):
        task = task or self.active_task()
        if not task:
            return []
        return [g for g in task.get("required_gates", []) if not task["gates"].get(g, {}).get("passed")]

    def close_task(self):
        task = self._require_task(); missing = self.missing_gates(task)
        if missing:
            raise ValueError("cannot close task; incomplete gates: " + ", ".join(missing))
        task["status"] = "completed"; task["ended_at"] = now_iso(); self.data["active_task_id"] = None
        self.save(); self.log("task_completed", task_id=task["id"])
        return task

    def _refresh_research_gate(self, task):
        req = research_requirements(self.policy, task["class"]); counts = {}
        for ev in task.get("evidence", []):
            kind = ev.get("kind"); counts[kind] = counts.get(kind, 0) + 1
            if kind in {"primary-paper", "official-spec", "official-doc"}:
                counts["primary"] = counts.get("primary", 0) + 1
        missing = {k: n - counts.get(k, 0) for k, n in req.items() if counts.get(k, 0) < n}
        if not missing:
            self._pass_gate(task, "research", "selected evidence meets policy")
        return missing

    def research_missing(self):
        task = self._require_task(); req = research_requirements(self.policy, task["class"]); counts = {}
        for ev in task.get("evidence", []):
            kind = ev.get("kind"); counts[kind] = counts.get(kind, 0) + 1
            if kind in {"primary-paper", "official-spec", "official-doc"}:
                counts["primary"] = counts.get("primary", 0) + 1
        return {k: max(0, n - counts.get(k, 0)) for k, n in req.items() if counts.get(k, 0) < n}

    def _pass_gate(self, task, name, evidence):
        self._pass_gate_obj(task["gates"][name], evidence)

    def _pass_gate_obj(self, gate, evidence):
        gate["passed"] = True; gate["at"] = now_iso(); gate.setdefault("evidence", []).append(evidence)

    def _require_task(self):
        task = self.active_task()
        if not task:
            raise ValueError("no active Rigor task")
        return task
