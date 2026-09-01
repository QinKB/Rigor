from __future__ import annotations
import json
import re


def classify_observed_tool(tool_name, tool_input):
    name = str(tool_name or "")
    low = name.lower()
    provider = None
    kind = "tool"
    if "exa" in low:
        provider = "exa"
        kind = "web-source-read" if any(x in low for x in ("fetch", "contents", "get_page", "read")) else "external-search"
    elif "github" in low:
        provider, kind = "github", "upstream-tool"
    elif "papermeld" in low or "papermason" in low or "zotero" in low:
        provider, kind = "local-literature", "literature-tool"
    elif "firecrawl" in low:
        provider = "firecrawl"
        kind = "external-search" if "search" in low else "web-source-read"
    elif "context7" in low or "docs" in low and low.startswith("mcp__"):
        provider, kind = "context7", "official-doc-tool"
    elif "serena" in low:
        provider, kind = "serena", "local-code-search"
    elif name == "Bash":
        command = str((tool_input or {}).get("command", "")) if isinstance(tool_input, dict) else ""
        if "inspect_resources.py" in command or "nvidia-smi" in command or re.search(r"(^|\s)lscpu(\s|$)", command):
            provider, kind = "shell", "resource-inspection"
        elif re.search(r"(^|\s)rg(\s|$)", command) or "git grep" in command:
            provider, kind = "rg", "local-code-search"
        elif "git " in command or command.startswith("git"):
            provider, kind = "git", "repository-tool"
        elif any(x in command for x in ["pytest", "unittest", "torchrun", "train", "evaluate", "eval.py", "python ", "python3 "]):
            provider, kind = "shell", "execution"
    query = _extract_query(tool_input)
    return {"provider": provider, "kind": kind, "query": query, "tool_name": name}


def infer_tool_success(tool_name, tool_response):
    """Return True/False only when PostToolUse gives enough evidence, else None.

    Acceptance/integration gates require True. This intentionally rejects an
    ambiguous observation instead of treating "tool was called" as "tool passed".
    """
    name = str(tool_name or "")
    result = _infer_success_value(tool_response, name)
    if result is not None:
        return result
    # A non-Bash tool returning a non-empty structured result without an error
    # marker is a successful call in the common MCP/function-tool shape.
    if name != "Bash" and isinstance(tool_response, dict) and tool_response:
        if any(k in tool_response for k in ("content", "result", "structuredContent", "data")):
            return True
    return None


def response_summary(value, limit=500):
    if value is None:
        return None
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True) if not isinstance(value, str) else value
    except Exception:
        text = repr(value)
    return text[:limit]


def _infer_success_value(value, tool_name):
    if isinstance(value, dict):
        # Explicit error flags are strongest.
        for key in ("is_error", "isError", "error"):
            if key in value:
                v = value[key]
                if isinstance(v, bool):
                    return not v
                if key == "error" and v not in (None, "", False, 0, [], {}):
                    return False

        for key in ("exit_code", "exitCode", "returncode", "return_code", "returnCode"):
            if key in value:
                try:
                    return int(value[key]) == 0
                except (TypeError, ValueError):
                    pass

        for key in ("status", "state", "outcome"):
            if key in value and isinstance(value[key], str):
                s = value[key].strip().lower()
                if s in {"failed", "failure", "error", "errored", "cancelled", "canceled", "timed_out", "timeout"}:
                    return False
                if s in {"ok", "success", "succeeded", "completed", "complete", "passed"}:
                    return True

        found_true = False
        for child in value.values():
            result = _infer_success_value(child, tool_name)
            if result is False:
                return False
            if result is True:
                found_true = True
        if found_true:
            return True
        return None

    if isinstance(value, (list, tuple)):
        found_true = False
        for child in value:
            result = _infer_success_value(child, tool_name)
            if result is False:
                return False
            if result is True:
                found_true = True
        return True if found_true else None

    if isinstance(value, str):
        text = value.strip()
        low = text.lower()
        exit_patterns = [
            r"(?:process\s+)?exit(?:ed)?(?:\s+with)?\s+(?:status|code)\s*[:=]?\s*(-?\d+)",
            r"(?:exit[_\s-]*code|return[_\s-]*code)\s*[:=]\s*(-?\d+)",
        ]
        for pattern in exit_patterns:
            m = re.search(pattern, low)
            if m:
                try:
                    return int(m.group(1)) == 0
                except ValueError:
                    pass
        if re.search(r"\b(command|process|tool)\s+(failed|errored)\b", low):
            return False
        if re.search(r"\b(completed successfully|succeeded|passed)\b", low):
            return True
    return None


def _extract_query(value):
    if isinstance(value, dict):
        for key in ["query", "q", "search_query", "pattern", "command"]:
            if key in value and isinstance(value[key], str):
                return value[key][:500]
        for v in value.values():
            q = _extract_query(v)
            if q:
                return q
    if isinstance(value, list):
        for v in value:
            q = _extract_query(v)
            if q:
                return q
    return None
