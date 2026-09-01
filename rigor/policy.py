from __future__ import annotations
import fnmatch, json
from copy import deepcopy
from pathlib import Path

DEFAULT_POLICY = {
    "version": 1,
    "enabled": False,
    "mode": "enforce",
    "stop_policy": "active-task",
    "memory": {
        "required": True,
        "files": ["HANDOFF.md", "MEMORY.md", "LOG.md"],
    },
    "delegation": {
        "require_assignment": True,
        "roles": ["scout", "researcher", "runner", "worker", "reviewer"],
    },
    "research": {
        "prefer_external_provider": "exa",
        "require_observed_external_search": True,
        "require_observed_kinds": {
            "local-code": True,
            "local-paper": True,
            "primary-paper": True,
            "official-spec": True,
            "official-doc": True,
            "upstream-code": True,
            "external-search": True,
            "issue": True,
        },
        "requirements": {
            "mechanical": {},
            "root-cause-fix": {"local-code": 1, "external-search": 1},
            "reference-adaptation": {"local-code": 1, "primary": 1, "upstream-code": 1, "external-search": 1},
            "new-design": {"local-code": 1, "primary": 1, "upstream-code": 1, "external-search": 1},
            "experiment": {"local-code": 1},
            "evaluation": {"local-code": 1, "primary": 1},
            "data-change": {"local-code": 1},
        },
    },
    "task_classes": {
        "mechanical": ["integration", "acceptance", "memory", "git"],
        "root-cause-fix": ["research", "integration", "acceptance", "memory", "git"],
        "reference-adaptation": ["research", "design", "integration", "acceptance", "memory", "git"],
        "new-design": ["research", "design", "integration", "acceptance", "memory", "git"],
        "experiment": ["research", "integration", "acceptance", "memory", "git"],
        "evaluation": ["research", "integration", "acceptance", "memory", "git"],
        "data-change": ["research", "design", "integration", "acceptance", "memory", "git"],
    },
    "design": {
        "require_reference_evidence_ids": True,
        "required_reference_groups": {
            "reference-adaptation": [["primary-paper", "official-spec", "official-doc"], ["upstream-code"]],
            "new-design": [["primary-paper", "official-spec", "official-doc"], ["upstream-code"]],
            "data-change": [["local-code"]]
        },
    },
    "classification": {
        "guard_sensitive_paths": True,
        "block_unknown_write_target_for_mechanical": True,
        "protected_path_rules": [
            {
                "name": "model-semantics",
                "patterns": [
                    "model*.py", "**/model*.py", "models/**", "**/models/**",
                    "module*.py", "**/module*.py", "modules/**", "**/modules/**",
                    "encoder*.py", "**/encoder*.py", "decoder*.py", "**/decoder*.py",
                    "predict*.py", "**/predict*.py", "loss*.py", "**/loss*.py"
                ],
                "allowed_classes": ["reference-adaptation", "new-design"]
            },
            {
                "name": "data-semantics",
                "patterns": ["datasets/**", "**/datasets/**", "data/**", "**/data/**"],
                "allowed_classes": ["data-change", "reference-adaptation", "new-design"]
            },
            {
                "name": "training-execution",
                "patterns": ["train*.py", "**/train*.py", "trainer*.py", "**/trainer*.py"],
                "allowed_classes": ["experiment", "root-cause-fix", "reference-adaptation", "new-design"]
            },
            {
                "name": "evaluation-semantics",
                "patterns": ["eval*.py", "**/eval*.py", "evaluation/**", "**/evaluation/**", "metric*.py", "**/metric*.py"],
                "allowed_classes": ["evaluation", "root-cause-fix", "reference-adaptation", "new-design"]
            }
        ]
    },
    "acceptance": {
        "default_required_level": "L4",
        "levels": ["L0", "L1", "L2", "L3", "L4"],
        "require_observed_execution": True,
    },
    "integration": {
        "require_observed_execution": True,
    },
    "verification": {
        "require_frozen_plan": True,
    },
    "compute": {
        "cost_constraint": False,
        "priority": ["correctness", "reproducibility", "wall-clock"],
        "maximize_useful_headroom": True,
        "project_cuda_gpus": "auto",
        "resource_plan_required_for_long_runs": True,
        "require_observed_resource_inspection": True,
        "enforce_all_eligible_gpus": True,
        "eligible_gpu_free_ratio": 0.70,
        "eligible_gpu_max_utilization": 50,
    },
    "git": {
        "require_checkpoint": True,
        "require_clean_checkpoint": True,
    },
    "safety": {
        "deny_command_patterns": [
            "git reset --hard",
            "git clean -fd",
            "git clean -fx",
            "git push --force",
            "git push -f",
            "rm -rf /",
        ],
        "git_checkpoint_patterns": ["git commit"],
        "long_run_patterns": ["torchrun", "deepspeed", "accelerate launch", "python train", "python3 train"],
        "govern_shell_repository_writes": True,
        "govern_mcp_repository_writes": True,
        "mcp_write_verbs": ["write", "edit", "replace", "insert", "delete", "remove", "rename", "move", "create", "update", "patch", "apply", "upload", "commit", "push"],
    },
}


def _merge(base, override):
    out = deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def load_policy(root):
    path = Path(root) / ".codex" / "rigor.json"
    if not path.exists():
        return deepcopy(DEFAULT_POLICY), path
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {"enabled": False, "invalid": True}
    return _merge(DEFAULT_POLICY, raw), path


def required_gates(policy, task_class):
    return list(policy.get("task_classes", {}).get(task_class, ["integration", "acceptance", "memory", "git"]))


def research_requirements(policy, task_class):
    return dict(policy.get("research", {}).get("requirements", {}).get(task_class, {}))


def command_matches(command, patterns):
    low = (command or "").lower()
    return any(p.lower() in low for p in patterns)
