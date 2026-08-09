"""Four hooks that enforce the Appian harness's write and closure gates.

The plugin's premise is that an agent must not be able to mark its own work
as passing. These hooks are where that stops being advice:

- scope_gate (PreToolUse on Appian write tools): is there an approved active
  task? is the object in its allowedObjects? is the task atomic? is there a
  VALID design audit for it? "Valid" is decided by validate_verdict, so a
  fabricated citation fails the gate, not just a missing file.
- closure_gate (Stop): the write gate cannot cover review and QA, which
  happen after writing. This blocks closing a task without valid
  practices-implementation, practices-review and practices-qa verdicts, and
  names which are missing.
- log_write (PostToolUse): appends task, tool, object and result to
  operations.jsonl. The harness records it, not the agent -- an agent asked
  to log its own writes forgets exactly when it matters.
- failure_notice (PostToolUseFailure): tells the agent not to retry blindly.

Four rules, non-negotiable:

1. Never return "deny". Only "allow" or "ask". A guardrail that blocks gets
   switched off, and then it protects nothing.
2. Fail-closed means "ask", never refuse. If a hook cannot inspect something
   -- unreadable config, malformed JSON -- it asks. It never lets something
   through because it could not tell.
3. A plugin installed in a project that does not use it must not get in the
   way. If .claude/appian-harness.json is absent from the project, every
   hook returns allow (or approve / no-op) and exits 0. That is the
   activation mechanism.
4. scope_gate accumulates every reason it finds instead of stopping at the
   first. Telling someone one of four problems, three times in a row, is
   worse than telling them all four once.
"""
import json
import os
import re
import sys
import time

# harness_hooks.py lives in hooks/; validate_verdict.py lives in ../scripts/.
# Inserted unconditionally so this module is self-sufficient whether it's
# imported by the test suite or run directly as the hook's entry point.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from validate_verdict import validate_verdict

# Matches the same verbs as hooks.json's PreToolUse/PostToolUse matcher, so
# scope_gate/closure_gate agree with what the matcher already routed to them
# even when called directly (as the unit tests do, bypassing hooks.json).
WRITE_TOOL_RE = re.compile(
    r"^mcp__.*__(create|update|add|insert|configure|reorder|upload|replace|delete|remove)",
    re.IGNORECASE,
)

# Candidate keys for the object a write tool targets. Appian MCP tools don't
# share one argument name for "the object", so this tries the common ones in
# order and takes the first string it finds.
OBJECT_KEYS = (
    "name", "uuid", "id",
    "recordTypeUuid", "interfaceUuid", "processModelUuid", "expressionRuleUuid",
    "webApiUuid", "siteUuid", "documentUuid", "folderUuid", "constantUuid",
    "connectedSystemUuid", "groupUuid", "applicationUuid",
)

CONFIG_RELPATH = os.path.join(".claude", "appian-harness.json")
DEFAULT_EVIDENCE_DIR = "evidence"
DEFAULT_ACTIVE_TASK_FILE = os.path.join("tasks", "current.json")
DEFAULT_MAX_ALLOWED_OBJECTS = 3
CLOSURE_PHASES = ("implementation", "review", "qa")


def _is_write_tool(tool_name):
    return bool(WRITE_TOOL_RE.match(tool_name or ""))


def _object_name(tool_input):
    if not isinstance(tool_input, dict):
        return None
    for key in OBJECT_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            return val
    return None


def _verdict_path(config, task_id, phase):
    return os.path.join(config.get("evidenceDir", DEFAULT_EVIDENCE_DIR), task_id,
                         "practices-%s.json" % phase)


def _phase_errors(config, task_id, phase):
    """Names what's wrong with a phase's verdict; empty list means valid.

    A missing file and a structurally-invalid file (per validate_verdict,
    which resolves every cited reference against this plugin's own docs)
    both fail closed -- the caller decides what to do with the list, this
    only inspects.
    """
    path = _verdict_path(config, task_id, phase)
    if not os.path.isfile(path):
        return ["no practices-%s verdict found at %s" % (phase, path)]
    plugin_root = config.get("pluginRoot")
    if not plugin_root:
        return ["cannot validate practices-%s: no pluginRoot configured" % phase]
    errors = validate_verdict(path, plugin_root)
    if errors:
        return ["practices-%s verdict is invalid: %s" % (phase, "; ".join(errors))]
    return []


def scope_gate(payload, config):
    """PreToolUse gate for Appian write tools. Never denies.

    Checks, in order, and accumulates every reason instead of stopping at
    the first: active task -> object in allowedObjects -> atomicity
    (len(allowedObjects) > maxAllowedObjects) -> a present and valid
    practices-design verdict.
    """
    tool_name = payload.get("tool_name", "")
    if not _is_write_tool(tool_name):
        return {"permissionDecision": "allow", "permissionDecisionReason": "not a write tool"}

    reasons = []
    active_task = config.get("activeTask")
    if not active_task or not active_task.get("id"):
        reasons.append("no active task: nothing has been scoped and approved for this session")
    else:
        task_id = active_task["id"]
        allowed_objects = active_task.get("allowedObjects") or []

        obj_name = _object_name(payload.get("tool_input", {}))
        if obj_name is None:
            reasons.append("could not identify the target object from tool_input; "
                            "cannot check it against allowedObjects")
        elif obj_name not in allowed_objects:
            reasons.append("object %r is not in the task's allowedObjects %r" %
                            (obj_name, allowed_objects))

        max_allowed = config.get("maxAllowedObjects", DEFAULT_MAX_ALLOWED_OBJECTS)
        if len(allowed_objects) > max_allowed:
            reasons.append(
                "task %r touches %d objects, more than maxAllowedObjects=%d: not atomic" %
                (task_id, len(allowed_objects), max_allowed))

        reasons.extend(_phase_errors(config, task_id, "design"))

    if reasons:
        return {"permissionDecision": "ask", "permissionDecisionReason": " · ".join(reasons)}
    return {"permissionDecision": "allow",
            "permissionDecisionReason": "scope and design audit check out"}


def closure_gate(payload, config):
    """Stop gate: a task cannot close without its three post-write verdicts.

    scope_gate only covers the write itself; review and QA happen after
    writing, so they can only be enforced here. Names exactly which
    verdicts are missing or invalid so the agent doesn't have to guess.
    """
    active_task = config.get("activeTask")
    if not active_task or not active_task.get("id"):
        return {"decision": "approve"}

    task_id = active_task["id"]
    missing = []
    for phase in CLOSURE_PHASES:
        errs = _phase_errors(config, task_id, phase)
        if errs:
            missing.append("practices-%s (%s)" % (phase, "; ".join(errs)))

    if missing:
        return {"decision": "block",
                "reason": "task %r cannot close: missing or invalid verdicts -- %s" %
                          (task_id, " | ".join(missing))}
    return {"decision": "approve"}


def failure_notice(payload):
    """PostToolUseFailure: turns 'remember to be idempotent' into a reminder.

    A failed write leaves the agent guessing whether it landed. This tells
    it not to guess: read first, record the partial state, then resume from
    the first thing it never confirmed.
    """
    tool_name = payload.get("tool_name", "unknown tool")
    message = (
        "The write via %s failed. Do not retry this write; check with a read "
        "whether it persisted, record what did and did not, and resume from "
        "the first unverified result." % tool_name
    )
    return {"additionalContext": message}


def _write_result(payload):
    result = payload.get("tool_result")
    if isinstance(result, dict) and (result.get("is_error") or result.get("error")):
        return "error"
    if isinstance(result, str) and result.lower().startswith("error"):
        return "error"
    return "ok"


def log_write(payload, config):
    """PostToolUse: the harness logs writes, not the agent -- an agent asked
    to log its own writes forgets exactly when it matters."""
    active_task = config.get("activeTask") or {}
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": active_task.get("id"),
        "tool": payload.get("tool_name"),
        "object": _object_name(payload.get("tool_input", {})),
        "result": _write_result(payload),
    }
    _append_jsonl(os.path.join(config.get("evidenceDir", DEFAULT_EVIDENCE_DIR),
                                "operations.jsonl"), entry)
    return {}


def _append_jsonl(path, entry):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _log_ask(config, task_id, tool_name, reason):
    # Every ask decision is logged with its reason, so the ratio of "yes" to
    # a scope-gate prompt can be measured later without instrumenting the
    # agent itself.
    entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": task_id,
        "tool": tool_name,
        "decision": "ask",
        "reason": reason,
    }
    _append_jsonl(os.path.join(config.get("evidenceDir", DEFAULT_EVIDENCE_DIR),
                                "gate-decisions.jsonl"), entry)


# --- CLI wiring --------------------------------------------------------
#
# Everything above is pure and unit-tested directly. Everything below reads
# stdin, resolves the project's config, and adapts the pure functions'
# output to the hook JSON contract Claude Code expects on stdout.

def _read_stdin_json():
    raw = sys.stdin.read()
    if not raw.strip():
        return {}, None
    try:
        return json.loads(raw), None
    except ValueError as e:
        return {}, "cannot parse hook payload as JSON: %s" % e


def _load_json_file(path):
    """Returns (data, error).

    Absence is reported as (None, None); a file that exists but can't be
    read or parsed is (None, "..."). Callers must be able to tell "not
    there" (fine, means "not configured" or "no active task") from "there
    but broken" (fail closed).
    """
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except (ValueError, OSError) as e:
        return None, "cannot read %s: %s" % (path, e)


def _build_config(project_root):
    """Loads the project's harness config.

    Returns (config, active, error):
    - active=False: .claude/appian-harness.json is absent. The plugin is
      installed but this project doesn't use it -- every hook must allow.
    - active=True, error set: the config (or the active-task file) exists
      but could not be read. Fail closed, not silently-allow.
    - active=True, error=None: config is a usable dict.
    """
    config_path = os.path.join(project_root, CONFIG_RELPATH)
    project_config, err = _load_json_file(config_path)
    if project_config is None and err is None:
        return None, False, None
    if err:
        return None, True, err

    evidence_dir = os.path.join(project_root,
                                 project_config.get("evidenceDir", DEFAULT_EVIDENCE_DIR))
    active_task_file = os.path.join(
        project_root, project_config.get("activeTaskFile", DEFAULT_ACTIVE_TASK_FILE))
    active_task, task_err = _load_json_file(active_task_file)
    if task_err:
        return None, True, task_err

    config = {
        "pluginRoot": os.environ.get("CLAUDE_PLUGIN_ROOT"),
        "evidenceDir": evidence_dir,
        "activeTask": active_task,
        "maxAllowedObjects": project_config.get("maxAllowedObjects", DEFAULT_MAX_ALLOWED_OBJECTS),
    }
    return config, True, None


def _emit(obj):
    print(json.dumps(obj))


def cmd_scope_gate():
    payload, parse_err = _read_stdin_json()
    config, active, err = _build_config(payload.get("cwd") or ".")
    if not active:
        _emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "appian-harness not configured for this project",
        }})
        return 0
    if err or parse_err:
        _emit({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "harness config unreadable: %s" % (err or parse_err),
        }})
        return 0

    decision = scope_gate(payload, config)
    if decision["permissionDecision"] == "ask":
        active_task = config.get("activeTask") or {}
        _log_ask(config, active_task.get("id"), payload.get("tool_name"),
                  decision["permissionDecisionReason"])
    _emit({"hookSpecificOutput": dict(decision, hookEventName="PreToolUse")})
    return 0


def cmd_closure_gate():
    payload, parse_err = _read_stdin_json()
    config, active, err = _build_config(payload.get("cwd") or ".")
    if not active:
        _emit({"decision": "approve"})
        return 0
    if err or parse_err:
        _emit({"decision": "block",
               "reason": "harness config unreadable: %s" % (err or parse_err)})
        return 0

    _emit(closure_gate(payload, config))
    return 0


def cmd_log_write():
    payload, parse_err = _read_stdin_json()
    config, active, err = _build_config(payload.get("cwd") or ".")
    if not active or err or parse_err:
        _emit({})
        return 0
    log_write(payload, config)
    _emit({})
    return 0


def cmd_failure_notice():
    payload, _parse_err = _read_stdin_json()
    _config, active, _err = _build_config(payload.get("cwd") or ".")
    if not active:
        _emit({})
        return 0
    result = failure_notice(payload)
    _emit({"hookSpecificOutput": dict(result, hookEventName="PostToolUseFailure")})
    return 0


COMMANDS = {
    "scope-gate": cmd_scope_gate,
    "closure-gate": cmd_closure_gate,
    "log-write": cmd_log_write,
    "failure-notice": cmd_failure_notice,
}


def main(argv):
    if len(argv) < 2 or argv[1] not in COMMANDS:
        print("usage: harness_hooks.py {%s}" % "|".join(COMMANDS), file=sys.stderr)
        return 2
    try:
        return COMMANDS[argv[1]]()
    except Exception as e:  # fail closed, never crash out to a bare traceback
        subcommand = argv[1]
        if subcommand == "closure-gate":
            _emit({"decision": "block", "reason": "harness hook error: %s" % e})
        elif subcommand == "scope-gate":
            _emit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": "harness hook error: %s" % e,
            }})
        else:
            _emit({})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
