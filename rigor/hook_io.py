import json, sys


def read_event():
    raw=sys.stdin.read()
    if not raw.strip(): return {}
    try: return json.loads(raw.lstrip("\ufeff"))
    except json.JSONDecodeError: return {}


def emit(value):
    sys.stdout.write(json.dumps(value, separators=(",",":")))


def deny(reason):
    return {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":reason}}


def allow(updated_input=None, context=None):
    body={"hookEventName":"PreToolUse","permissionDecision":"allow"}
    if updated_input is not None: body["updatedInput"]=updated_input
    if context: body["additionalContext"]=context
    return {"hookSpecificOutput":body}


def context(event, text, system_message=None):
    out={"hookSpecificOutput":{"hookEventName":event,"additionalContext":text}}
    if system_message: out["systemMessage"]=system_message
    return out
