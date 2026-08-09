#!/bin/sh
# Finds a Python 3 and runs harness_hooks.py; if it cannot find one, emits
# the fail-closed decision itself instead of failing silently.
#
# Why a launcher exists at all. hooks.json used to invoke `python`, which
# does not exist on macOS or on most Linux distributions -- only `python3`
# does. A hook whose command cannot be found does not ask and does not
# block: it does not run. So the plugin installed, looked healthy, and
# enforced nothing, which is the same silent absence the plugin exists to
# prevent. harness_hooks.py is carefully fail-closed, but that safety net is
# inside the program; this script's job is to make sure the program starts,
# and to answer in its place when it cannot.
#
# Why shell form. hooks.json invokes this as
#   sh "${CLAUDE_PLUGIN_ROOT}/hooks/run_hook.sh" "${CLAUDE_PLUGIN_ROOT}" <sub>
# rather than the exec form (`args`) the hooks reference generally prefers
# for commands carrying a path placeholder. That preference is about
# quoting, and here it would break the platform it is meant to help: exec
# form spawns the executable from the process PATH, while Git for Windows
# puts git.exe on PATH via Git\cmd and leaves sh.exe in Git\bin, which is
# usually not on PATH at all. Shell form on Windows runs the command string
# *through* Git Bash, where sh is guaranteed by definition -- and on macOS
# and Linux shell form is `sh -c`, where sh is guaranteed too.
#
# Why the plugin root arrives as an argument instead of being derived from
# $0: on Windows ${CLAUDE_PLUGIN_ROOT} expands to a backslash path, and
# `dirname "C:\...\hooks\run_hook.sh"` returns ".". The placeholder is
# substituted by Claude Code, so passing it explicitly is the only form
# that holds on every platform.

set -u

# The interpreter is about to import harness_hooks.py -- and, through the
# closure gate, validate_verdict.py -- from inside the installed plugin.
# Python caches bytecode next to the source, so a plugin that starts out
# identical to its repository grows __pycache__ directories the first time a
# hook fires. Nothing breaks, but the copy stops being comparable with
# `git ls-files`, which is how anyone checks what they are actually running.
PYTHONDONTWRITEBYTECODE=1
export PYTHONDONTWRITEBYTECODE

PLUGIN_ROOT=${1:-}
SUBCOMMAND=${2:-}
SCRIPT="$PLUGIN_ROOT/hooks/harness_hooks.py"

# Each candidate is probed rather than trusted. `python` can still be a
# Python 2 (harness_hooks.py requires 3), and on Windows `python3` is often
# an App Execution Alias stub that resolves on PATH and then fails to run
# anything. The probe takes its stdin from /dev/null: the hook payload on
# our stdin has to survive untouched as far as the exec below.
try_interpreter() {
    if "$@" -c 'import sys; sys.exit(0 if sys.version_info[0] >= 3 else 1)' \
            </dev/null >/dev/null 2>&1; then
        exec "$@" "$SCRIPT" "$SUBCOMMAND"
    fi
}

try_interpreter python3
try_interpreter python
try_interpreter py -3

# --- No interpreter found ------------------------------------------------
#
# Everything below runs only when none of the three candidates works. It
# never allows a write through quietly and it never denies one: fail-closed
# in this plugin means "ask".

NOTE="appian-harness: no working Python 3 interpreter was found (tried python3, python and py -3), so the harness hooks did not run."

# Rule 3 of harness_hooks.py still applies here: a plugin installed in a
# project that does not use it must not get in the way. Without an
# interpreter the config cannot be parsed, but its presence can still be
# tested, and presence is the activation switch. Absent -> answer exactly
# as the Python path answers for an unconfigured project. Present -> fail
# closed and say so loudly.
#
# This resolves the project root from CLAUDE_PROJECT_DIR, which Claude Code
# exports on every hook process, rather than from the payload's `cwd`, which
# is what the Python path reads: parsing JSON out of a shell is not worth
# the fragility for a degraded path.
PROJECT_ROOT=${CLAUDE_PROJECT_DIR:-$PWD}
CONFIGURED=0
if [ -f "$PROJECT_ROOT/.claude/appian-harness.json" ]; then
    CONFIGURED=1
fi

case "$SUBCOMMAND" in
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
            # A Stop hook has only approve and block -- there is no "ask"
            # here. Blocking on every attempt would deadlock the session,
            # and the first thing anyone does with a deadlocked guardrail
            # is switch it off. Claude Code marks the repeat attempt with
            # stop_hook_active, so this mirrors closure_gate(): block once,
            # then approve loudly. The systemMessage is the whole record in
            # this mode -- writing the deferred-debt entry would need the
            # config parsed, which is precisely what is unavailable.
            payload=$(cat)
            if printf '%s' "$payload" | tr -d '[:space:]' | grep -q '"stop_hook_active":true'; then
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
        # Without an interpreter this cannot tell whether the file written
        # was one the gates read, so it cannot stay quiet either: an
        # unrecorded edit to a verdict is exactly what this hook exists to
        # make visible. It says so and lets the write stand -- this observes
        # rather than gates, degraded or not.
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
