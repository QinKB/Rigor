from __future__ import annotations
import copy, fnmatch, re, shlex
from pathlib import Path
from .contracts import render_assignment, validate_assignment
from .evidence import classify_observed_tool, infer_tool_success, response_summary
from .policy import command_matches, load_policy
from .state import RigorState
from .util import all_strings, now_iso, project_root

ASSIGNMENT_RE = re.compile(r"(?:RIGOR_ASSIGNMENT\s*=\s*|\[RIGOR_ASSIGNMENT:)(asg_[A-Za-z0-9]+)\]?", re.I)


def resolve(cwd):
    root=project_root(cwd); policy,path=load_policy(root); return root,policy,path,RigorState(root,policy)

def targets_are_project_profile(targets, root=None):
    targets = list(targets or [])

    if not targets:
        return False

    for target in targets:
        rel = relative_target(
            target,
            root,
        )

        if rel != ".codex/rigor.json":
            return False

    return True

def agent_action_from_input(tool_input):
    if not isinstance(tool_input, dict):
        return "spawn"
    for key in ("action", "operation", "method", "mode"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            low = value.strip().lower()
            if "follow" in low or low in {"send_input", "message", "continue", "resume"}:
                return "followup"
            if "spawn" in low or "create" in low or "start" in low:
                return "spawn"
    for text in all_strings(tool_input):
        low = str(text).lower()
        if "followup_task" in low or "follow-up" in low:
            return "followup"
    return "spawn"


def agent_id_from_input(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in ("agent_id", "target_agent_id", "id"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None

def assignment_id_from_input(tool_input):
    if isinstance(tool_input,dict):
        direct=tool_input.get("rigor_assignment_id")
        if isinstance(direct,str) and direct.startswith("asg_"): return direct
    for s in all_strings(tool_input):
        m=ASSIGNMENT_RE.search(s)
        if m: return m.group(1)
    return None


def agent_type_from_input(tool_input):
    if not isinstance(tool_input,dict): return None
    for key in ("agent_type","role","profile","name"):
        val=tool_input.get(key)
        if isinstance(val,str) and val: return val
    return None


def inject_assignment(tool_input, assignment):
    if not isinstance(tool_input,dict): return None
    out=copy.deepcopy(tool_input); text="\n\n"+render_assignment(assignment)
    for key in ("message","prompt","task","instructions"):
        if isinstance(out.get(key),str): out[key]=out[key]+text; return out
    return None


def is_destructive(command, policy):
    return command_matches(command,policy.get("safety",{}).get("deny_command_patterns",[]))


def is_git_checkpoint(command, policy):
    return command_matches(command,policy.get("safety",{}).get("git_checkpoint_patterns",[]))


def is_repository_write_command(command, policy, root=None):
    if re.search(
        r"\b("
        r"Set-Content|"
        r"Add-Content|"
        r"Out-File|"
        r"Copy-Item|"
        r"Move-Item|"
        r"Remove-Item|"
        r"New-Item"
        r")\b",
        text,
        re.I,
    ):
        return True

    if re.search(
        r"\[(?:System\.)?IO\.File\]::"
        r"(?:WriteAllText|WriteAllBytes|AppendAllText)",
        text,
        re.I,
    ):
        return True
    if not policy.get("safety", {}).get("govern_shell_repository_writes", True):
        return False
    text = str(command or "")
    low = text.lower()
    root_path = Path(root).resolve() if root else None

    # In-place editors and Git mutation target the working repository by nature.
    if re.search(r"\bsed\b[^\n;]*\s-i(?:\.[^\s]+)?(?:\s|$)", low) or re.search(r"\bperl\b[^\n;]*\s-pi(?:\s|$)", low):
        return True
    if re.search(r"\bgit\s+(?:apply|restore|mv|rm)\b|\bgit\s+checkout\s+--\b", low):
        return True
    if re.search(r"\b(?:write_text|write_bytes)\s*\(", low) or re.search(r"\bopen\s*\([^\n]*,[^\n]*['\"](?:w|a|x)[+b]?['\"]", low):
        return True

    def inside_repo(token):
        if not root_path:
            return True
        token = str(token or "").strip().strip("'\"")
        if not token or token in {"-", "/dev/null"} or token.startswith("/dev/"):
            return False
        # Shell variables/globs are ambiguous: fail closed only for relative forms,
        # which normally resolve in the repository cwd.
        if token.startswith("$") or any(x in token for x in ("*", "?", "[")):
            return not token.startswith("/")
        try:
            path = Path(token).expanduser()
            resolved = path.resolve() if path.is_absolute() else (root_path / path).resolve()
            return resolved == root_path or root_path in resolved.parents
        except Exception:
            return not token.startswith("/")

    # stdout redirection (but not stderr-only 2>/dev/null) can silently edit files.
    for m in re.finditer(r"(?:^|\s)(?:1)?>{1,2}\s*([^\s;&|]+)", text):
        if inside_repo(m.group(1)):
            return True

    try:
        tokens = shlex.split(text, posix=True)
    except Exception:
        tokens = []
    if not tokens:
        return False
    cmd = Path(tokens[0]).name.lower()
    args = [x for x in tokens[1:] if not x.startswith("-")]
    if cmd == "tee":
        return any(inside_repo(x) for x in args)
    if cmd in {"touch", "mkdir", "rmdir", "rm", "truncate"}:
        return any(inside_repo(x) for x in args)
    if cmd in {"cp", "mv", "install"} and args:
        return inside_repo(args[-1])
    if cmd == "dd":
        for token in tokens[1:]:
            if token.startswith("of=") and inside_repo(token[3:]):
                return True
    return False



def repository_write_targets(command, root=None):
    """Best-effort extraction of repository targets from common shell writes."""
    text = str(command or "")
    targets = []
    for m in re.finditer(r"(?:^|\s)(?:1)?>{1,2}\s*([^\s;&|]+)", text):
        targets.append(m.group(1))
    try:
        tokens = shlex.split(text, posix=True)
    except Exception:
        tokens = []
    if not tokens:
        return targets
    cmd = Path(tokens[0]).name.lower()
    plain = [x for x in tokens[1:] if not x.startswith("-")]
    if cmd in {"sed", "perl"} and plain:
        targets.append(plain[-1])
    elif cmd == "tee":
        targets.extend(plain)
    elif cmd in {"touch", "mkdir", "rmdir", "rm", "truncate"}:
        targets.extend(plain)
    elif cmd in {"cp", "mv", "install"} and plain:
        targets.append(plain[-1])
    elif cmd == "dd":
        targets.extend(x[3:] for x in tokens[1:] if x.startswith("of="))
    elif cmd == "git" and len(tokens) > 1 and tokens[1] in {"apply", "restore", "mv", "rm", "checkout"}:
        targets.extend(x for x in tokens[2:] if not x.startswith("-"))
    return targets


def tool_write_targets(tool_name, tool_input, root=None):
    inp = tool_input if isinstance(tool_input, dict) else {}
    targets = []
    for key in ("path", "file", "file_path", "relative_path", "filename", "target", "target_file"):
        if isinstance(inp.get(key), str):
            targets.append(inp[key])
    if str(tool_name) in {"apply_patch", "Edit", "Write"}:
        text = "\n".join(str(inp.get(k, "")) for k in ("patch", "command", "input", "content"))
        targets.extend(m.group(2).strip() for m in re.finditer(r"^\*\*\*\s+(Update|Add|Delete)\s+File:\s*(.+)$", text, re.M))
    elif str(tool_name) == "Bash":
        command = str(inp.get("command", ""))
        targets.extend(repository_write_targets(command, root))
        targets.extend(m.group(1) for m in re.finditer(r"(?:Path\s*\(\s*)?['\"]([^'\"]+)['\"]\s*\)?\s*\.write_(?:text|bytes)\s*\(", command))
        targets.extend(m.group(1) for m in re.finditer(r"open\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"](?:w|a|x)[+b]?['\"]", command))
    # Preserve order, remove empties and shell devices.
    out = []
    for target in targets:
        t = str(target or "").strip().strip("'\"")
        if t and t not in out and not t.startswith("/dev/"):
            out.append(t)
    return out



def targets_are_continuity_files(targets, policy, root=None):
    targets = list(targets or [])
    if not targets:
        return False
    allowed = {str(x).replace("\\", "/").lstrip("./") for x in policy.get("memory", {}).get("files", [])}
    if not allowed:
        return False
    normalized = []
    rp = Path(root).resolve() if root else None
    for target in targets:
        raw = str(target or "").strip().strip("'\"")
        try:
            p = Path(raw).expanduser()
            if rp:
                resolved = p.resolve() if p.is_absolute() else (rp / p).resolve()
                if resolved != rp and rp not in resolved.parents:
                    return False
                raw = resolved.relative_to(rp).as_posix()
            else:
                raw = p.as_posix().lstrip("./")
        except Exception:
            raw = raw.replace("\\", "/").lstrip("./")
        normalized.append(raw)
    return bool(normalized) and all(x in allowed for x in normalized)
def targets_are_project_profile(targets, root=None):
    targets = list(targets or [])
    if not targets:
        return False

    return all(
        relative_target(target, root) == ".codex/rigor.json"
        for target in targets
    )

def relative_target(target, root=None):
    raw = str(target or "").strip().strip("'\"")
    if not raw:
        return None
    try:
        p = Path(raw).expanduser()
        if root:
            rp = Path(root).resolve()
            resolved = p.resolve() if p.is_absolute() else (rp / p).resolve()
            if resolved != rp and rp not in resolved.parents:
                return None
            return resolved.relative_to(rp).as_posix()
        return p.as_posix().lstrip("./")
    except Exception:
        return raw.replace("\\", "/").lstrip("./")


def sensitive_target_rule(target, policy, root=None):
    cfg = policy.get("classification", {})
    if not cfg.get("guard_sensitive_paths", True):
        return None
    rel = relative_target(target, root)
    if not rel:
        return None
    for rule in cfg.get("protected_path_rules", []):
        if any(fnmatch.fnmatch(rel, pattern) for pattern in rule.get("patterns", [])):
            return rule
    project_patterns = (
        policy
        .get("project", {})
        .get("protected_surfaces", [])
    )

    if any(
        fnmatch.fnmatch(rel, pattern)
        for pattern in project_patterns
    ):
        return {
            "name": "project-protected",
            "patterns": project_patterns,
            "allowed_classes": [
                task_class
                for task_class in policy.get(
                    "task_classes",
                    {}
                )
                if task_class != "mechanical"
            ],
        }
    # Backward-compatible project override shape.
    patterns = cfg.get("sensitive_path_patterns", [])
    if any(fnmatch.fnmatch(rel, pattern) for pattern in patterns):
        return {"name": "sensitive", "patterns": patterns, "allowed_classes": cfg.get("classes_allowed_for_sensitive_write", [])}
    return None


def is_sensitive_repository_target(target, policy, root=None):
    return sensitive_target_rule(target, policy, root) is not None


def task_class_allows_sensitive_write(task, policy, targets=None, root=None):
    task_class = str((task or {}).get("class") or "")
    targets = list(targets or [])
    if not targets:
        allowed = set(policy.get("classification", {}).get("classes_allowed_for_sensitive_write", []))
        return task_class in allowed if allowed else False
    for target in targets:
        rule = sensitive_target_rule(target, policy, root)
        if rule and task_class not in set(rule.get("allowed_classes", [])):
            return False
    return True


def is_governed_mcp_write(tool_name, tool_input, policy, root=None):
    if not policy.get("safety", {}).get("govern_mcp_repository_writes", True):
        return False
    low = str(tool_name or "").lower()
    if not low.startswith("mcp__"):
        return False
    verbs = policy.get("safety", {}).get("mcp_write_verbs", [])
    segments = [x for x in re.split(r"[^a-z0-9]+", low) if x]
    if not any(v in segments or any(seg.startswith(v) for seg in segments) for v in verbs):
        return False
    # Repository/filesystem editors are governed even when their schema does not
    # expose a path. Remote source-control mutations are governed as consequential
    # writes as well; read/search/fetch tools do not match the write-verb test.
    if any(x in low for x in ("serena", "filesystem", "file", "repo", "github", "gitlab", "source")):
        return True
    targets = tool_write_targets(tool_name, tool_input, root)
    return bool(targets)

def is_long_run(command, policy):
    return command_matches(command,policy.get("safety",{}).get("long_run_patterns",[]))


def observed_tool_record(event):
    rec=classify_observed_tool(event.get("tool_name"),event.get("tool_input"))
    rec.update({
        "tool_use_id": event.get("tool_use_id"),
        "session_id": event.get("session_id"),
        "success": infer_tool_success(event.get("tool_name"), event.get("tool_response")),
        "response_summary": response_summary(event.get("tool_response")),
    })
    return rec


def session_context(root, policy, state, policy_path):
    task=state.active_task(); mem=policy.get("memory",{}); missing_files=[f for f in mem.get("files",[]) if not (Path(root)/f).exists()]
    lines=["CODEX RIGOR ACTIVE", "project: %s"%root, "policy: %s"%policy_path]
    if task:
        lines += [
            "active_task: %s (%s)"%(task["id"],task["class"]),
            "objective: %s"%task["objective"],
            "required_acceptance: %s"%task["required_acceptance"],
            "verification_profile: %s"%("selected" if task.get("verification_plan") else "missing"),
            "resource_plan: %s"%("frozen" if task.get("resources") else "not set"),
            "missing_gates: %s"%(", ".join(state.missing_gates(task)) or "none"),
        ]
    else:
        lines += ["active_task: none", "Before consequential writes, delegation, long runs, or checkpoints, invoke $rigor-task and create an active task."]
    if missing_files: lines.append("continuity_missing: "+", ".join(missing_files))
    lines += [
      "Rules: evidence before consequential design; select a repository acceptance profile before implementation; workers need a complete assignment contract; isolated/preflight checks are not repository completion.",
      "Subagents receive the same correctness/resource/acceptance policy through Rigor assignments.",
      "If Ponytail is active, use it only inside the frozen Rigor contract; it may not change reference semantics, integration, or acceptance.",
    ]
    return "\n".join(lines)
