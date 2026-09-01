#!/bin/sh
# Finds a Python 3 and runs harness_hooks.py; if it cannot find one, emits
# the fail-closed decision itself instead of failing silently.
#
# Launcher, shell form, root-as-argument: docs/design-notes.md § run_hook.sh.

set -u

# Keeps the installed plugin comparable with `git ls-files` (no __pycache__).
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

PLUGIN_ROOT=${1:-}
SUBCOMMAND=${2:-}
SCRIPT="$PLUGIN_ROOT/hooks/harness_hooks.py"

# Probed, not trusted: `python` can be a Python 2 and Windows `python3` is
# often an alias stub. Stdin from /dev/null keeps the hook payload intact.
try_interpreter() {
    if "$@" -c 'import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)' \
            </dev/null >/dev/null 2>&1; then
        exec "$@" "$SCRIPT" "$SUBCOMMAND"
    fi
}

# Order is platform-dependent for a measured reason: on Windows the alias
# stub answers ~2040ms against ~1070ms for `python`, and this runs on every
# gated call. Measurements: docs/design-notes.md § run_hook.sh.
if [ "${OS:-}" = "Windows_NT" ]; then
    try_interpreter python
    try_interpreter py -3
    try_interpreter python3
else
    try_interpreter python3
    try_interpreter python
    try_interpreter py -3
fi

# --- No interpreter found ------------------------------------------------
#
# Everything below runs only when none of the three candidates works. It
# never allows a write through quietly and it never denies one: fail-closed
# in this plugin means "ask".

NOTE="appian-harness: no working Python 3 interpreter was found (tried python3, python and py -3), so the harness hooks did not run."

# Rule 3 still applies degraded: unconfigured -> answer as the Python path
# does for an unconfigured project; configured -> fail closed, loudly. The
# root comes from CLAUDE_PROJECT_DIR, not from the payload -- a shell should
# not parse JSON. Detail: docs/design-notes.md § run_hook.sh.
PROJECT_ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
CONFIGURED=0
if [ -f "$PROJECT_ROOT/.claude/appian-harness.json" ]; then
    CONFIGURED=1
fi

# Whether Claude Code marked this as the repeat Stop attempt.
#
# Builtins only: a PATH too starved for `python3` is too starved for `cat`
# and `grep`, and the pipeline this replaced failed silently into a permanent
# block. The whitespace collapse makes `"stop_hook_active":true` and
# `"stop_hook_active": true` compare equal. docs/design-notes.md § run_hook.sh.
is_repeat_stop() {
    _payload=''
    while IFS= read -r _line || [ -n "$_line" ]; do
        _payload="$_payload$_line"
    done
    set -f
    # shellcheck disable=SC2086
    set -- $_payload
    IFS=''
    _payload="$*"
    unset IFS
    set +f
    case "$_payload" in
        *'"stop_hook_active":true'*) return 0 ;;
    esac
    return 1
}

case "$SUBCOMMAND" in
    session-start)
        # Silence here would read as "all three requirements are present" --
        # the false reassurance this hook exists to prevent.
        if [ "$CONFIGURED" -eq 0 ]; then
            printf '%s\n' '{}'
        else
            printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"SessionStart\",\"additionalContext\":\"$NOTE Nothing has checked that the design MCP, the official Appian skill and the documentation MCP are present, and no gate will run in this session. Do not treat any Appian write as verified.\"}}"
        fi
        ;;
    scope-gate)
        if [ "$CONFIGURED" -eq 0 ]; then
            printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"appian-harness not configured for this project"}}'
        else
            printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"ask\",\"permissionDecisionReason\":\"$NOTE The scope gate could not be evaluated, so nothing has checked this write against an approved task.\"}}"
        fi
        ;;
    closure-gate)
        if [ "$CONFIGURED" -eq 0 ]; then
            printf '%s\n' '{"decision":"approve"}'
        else
            # Mirrors closure_gate(): a Stop hook has no "ask", so block
            # once and then approve loudly rather than deadlock the session.
            if is_repeat_stop; then
                printf '%s\n' "{\"decision\":\"approve\",\"systemMessage\":\"$NOTE This task is closing UNMEASURED: no verdict was checked. Install a Python 3 interpreter and re-run the audits before trusting this task as verified.\"}"
            else
                printf '%s\n' "{\"decision\":\"block\",\"reason\":\"$NOTE The closure gate could not check the practices-implementation, practices-review and practices-qa verdicts, so this task must not be treated as verified. Install a Python 3 interpreter on PATH as python3, python or py -3.\"}"
            fi
        fi
        ;;
    log-write)
        if [ "$CONFIGURED" -eq 0 ]; then
            printf '%s\n' '{}'
        else
            printf '%s\n' "{\"systemMessage\":\"$NOTE This write was NOT recorded in operations.jsonl: the write log is incomplete.\"}"
        fi
        ;;
    log-evidence-write)
        # Cannot tell whether the file was one the gates read, so it says so
        # and lets the write stand: this observes, it does not gate.
        if [ "$CONFIGURED" -eq 0 ]; then
            printf '%s\n' '{}'
        else
            printf '%s\n' "{\"systemMessage\":\"$NOTE If this edit touched the evidence directory, the harness config or the active task file, it was NOT recorded in evidence-writes.jsonl.\"}"
        fi
        ;;
    failure-notice)
        if [ "$CONFIGURED" -eq 0 ]; then
            printf '%s\n' '{}'
        else
            printf '%s\n' "{\"hookSpecificOutput\":{\"hookEventName\":\"PostToolUseFailure\",\"additionalContext\":\"$NOTE Do not retry the failed write blindly: check with a read whether it persisted, record what did and did not, and resume from the first unverified result.\"}}"
        fi
        ;;
    *)
        printf '%s\n' '{}'
        ;;
esac
exit 0
