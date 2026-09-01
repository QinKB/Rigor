from __future__ import annotations
from .acceptance import normalize_level

ASSIGNMENT_FIELDS = [
    "objective", "reference", "target", "method", "integration", "resources",
    "write_scope", "acceptance", "output", "stop_conditions",
]


def validate_assignment(data):
    missing = []
    for key in ASSIGNMENT_FIELDS:
        val = data.get(key)
        if val is None or val == "" or val == [] or val == {}:
            missing.append(key)
    if not missing:
        try:
            normalize_level(data.get("acceptance"))
        except ValueError:
            missing.append("acceptance(valid L0-L4)")
    return missing


def render_assignment(data):
    lines = [
        "CODEX RIGOR ASSIGNMENT",
        "assignment_id: %s" % data.get("id", "unknown"),
        "role: %s" % data.get("role", "unknown"),
    ]
    for key in ASSIGNMENT_FIELDS:
        lines.append("%s: %s" % (key, _compact(data.get(key))))
    if data.get("task_resource_plan"):
        lines.append("task_resource_plan: %s" % _compact(data.get("task_resource_plan")))
    if data.get("verification_plan"):
        lines.append("verification_plan: %s" % _compact(data.get("verification_plan")))
    lines.extend([
        "",
        "Rules:",
        "- This assignment is bounded. Do not redefine architecture or acceptance.",
        "- Use the assigned custom role/profile with fork_turns=none; do not bypass role/model routing.",
        "- Follow the specified reference and preserve its meaningful semantics.",
        "- If assumptions do not fit, stop and return evidence instead of inventing a substitute.",
        "- A standalone module and preflight-only checks are not project completion.",
        "- Apply the same resource policy as the Lead: correctness, reproducibility, then wall-clock; use useful GPU/CPU headroom aggressively.",
        "- If Ponytail is active, simplify only inside this frozen contract.",
        "",
        "Before stopping, emit exactly one result block:",
        "RIGOR_ASSIGNMENT_RESULT",
        "assignment_id: <id>",
        "status: complete|partial|blocked",
        "acceptance: L0|L1|L2|L3|L4",
        "integration: <what real path consumes the result, or none>",
        "validation: <commands/checks and observed result>",
        "evidence: <files/symbols/artifacts/logs>",
        "remaining: <none or exact unresolved work>",
    ])
    return "\n".join(lines)


def _compact(value):
    if isinstance(value, list):
        return "; ".join(str(x) for x in value)
    if isinstance(value, dict):
        return "; ".join("%s=%s" % (k, v) for k, v in value.items())
    return str(value)


def parse_result(text):
    text = text or ""
    marker = "RIGOR_ASSIGNMENT_RESULT"
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    out = {}
    for raw in tail.splitlines():
        line = raw.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k = k.strip().lower()
        if k in {"assignment_id", "status", "acceptance", "integration", "validation", "evidence", "remaining"}:
            out[k] = v.strip()
    return out
