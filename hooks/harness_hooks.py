"""Six hooks that enforce the Appian harness's requirements, write and
closure gates. An agent must not be able to mark its own work as passing.

- session_start (SessionStart) -- reports whether the three links are there:
  design MCP, official Appian skill, documentation MCP. Informs, never blocks.
- scope_gate (PreToolUse on Appian write tools) -- approved active task,
  object in `allowedObjects`, atomic task, official skill recorded, a passing
  design audit, and the optional run and lease checks.
- closure_gate (Stop) -- blocks closing a task without the practices verdicts
  its risk tier requires; on a repeat attempt it approves and records debt.
- log_write (PostToolUse) -- appends every Appian write to operations.jsonl.
- log_evidence_write (PostToolUse on file writes) -- records edits to the
  files the gates themselves read.
- failure_notice (PostToolUseFailure) -- do not retry a failed write blindly.

Four rules, non-negotiable:

1. Never return "deny". Only "allow" or "ask".
2. Fail-closed means "ask": a hook that cannot inspect something asks.
3. No `.claude/appian-harness.json` in the project, every hook allows and
   exits 0. That absence is the activation switch.
4. scope_gate accumulates every reason it finds instead of stopping at the
   first.

Rationale, measurements and the traps behind the non-obvious lines:
docs/design-notes.md.
"""
import calendar
import json
import os
import re
import sys
import time

# validate_verdict.py lives in ../scripts/; inserted unconditionally so this
# module works both imported by the tests and run as the hook entry point.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from validate_verdict import isfile_exact, load_verdict, validate_verdict

# Second half of a two-stage filter: hooks.json routes, this decides. The
# invariant is that hooks.json must route everything this pattern gates --
# narrower here is safe, broader is unsafe and silent. `test_matcher_parity`
# holds it, and it is why there is no re.IGNORECASE.
# docs/design-notes.md § harness_hooks.py · the two-stage matcher.
WRITE_TOOL_RE = re.compile(
    r"^mcp__[a-zA-Z0-9_-]*[Aa]ppian[a-zA-Z0-9_-]*__"
    # The `appian` runtime server prefixes every tool with `appian_`.
    r"(?:appian_)?"
    r"(create|update|add|insert|configure|reorder|upload|replace|delete|remove"
    r"|invoke_process_model|invoke_agent|start_process|execute"
    r"|testProcessModel)",
)

# The runtime verbs are spelled out rather than matched as a bare
# `invoke|run|test`: `invoke_expression_rule`, `testRule` and
# `runAllInterfaceTestCases` have no side effects and stay ungated.
# Why each verb is in or out: docs/design-notes.md § harness_hooks.py · verbs.

# The irreversible half of an asymmetric pair, and a strict SUBSET of
# WRITE_TOOL_RE: `scope_gate` returns early for anything `_is_write_tool`
# rejects, so a name this matched and that did not would skip the
# confirmation on the one class of call that cannot be undone.
DESTRUCTIVE_TOOL_RE = re.compile(
    r"^mcp__[a-zA-Z0-9_-]*[Aa]ppian[a-zA-Z0-9_-]*__(?:appian_)?"
    r"(delete|remove"
    # A row has no version history, so overwriting one is as irreversible as
    # deleting it -- the "updates are recoverable" premise covers design
    # objects only.
    r"|updateRecordData)",
)

# Where a task records what it found before deleting. One file per task,
# keyed by object, because an object name is not safe to put in a filename.
DEPENDENTS_RECORD_NAME = "dependents.json"

# Candidate keys for the object a write tool targets: Appian MCP tools share
# no single argument name for it, so all of these are read as alternative
# spellings of the SAME target -- which is what makes "in scope if any
# matches" correct rather than a loosening.
# docs/design-notes.md § harness_hooks.py · object keys.
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

# Which phases a verdict may legitimately predate the writes for. An
# allow-list of exemptions, not a list of what to check, so a phase added
# later is checked by default.
STALENESS_EXEMPT_PHASES = ("design",)

# How much ceremony a task's risk tier buys. `risk` is declared in the plan
# and copied into the active task file: `trivial` is cosmetic and local and
# pays one verdict, `standard` is the default and what an unrecognised value
# means, `high` adds an adversarial pass. A `trivial` claim is not prevented,
# it is logged (see _log_risk_downgrade).
RISK_CLOSURE_PHASES = {
    "trivial": ("implementation",),
    "standard": CLOSURE_PHASES,
    "high": CLOSURE_PHASES + ("risk",),
}
DEFAULT_RISK = "standard"

# A hook cannot see whether a skill is in an agent's context, but it can open
# a file: the build records the official skill's load per task, and the gate
# reads the record. docs/design-notes.md § harness_hooks.py · official skill.
SKILL_RECORD_NAME = "appian-skill-loaded.json"
OFFICIAL_SKILL_URL = "github.com/appian/dev-mcp-skills"

# The three links, checked once at session start rather than discovered one
# failure at a time. Which servers a project actually calls them is its own
# business, so the names are defaults and not assumptions.
DEFAULT_DESIGN_MCP = "appian-dev"
DEFAULT_DOCS_MCP = "appian-docs"

# Where the official skill is normally installed. User scope first, because
# that is where `dev-mcp-skills` puts it and it is outside any project.
SKILL_SEARCH_RELPATHS = (
    os.path.join(".claude", "skills", "appian", "SKILL.md"),
)

# The one field of the load record that cannot be filled in without having
# opened the skill -- and, when the project points at the installed skill, the
# one that gets compared against the file instead of being trusted.
APPIAN_VERSION_RE = re.compile(r"^\s*\*\*Appian Version:\*\*\s*(\S+)", re.MULTILINE)


def _is_write_tool(tool_name):
    return bool(WRITE_TOOL_RE.match(tool_name or ""))


def _evidence_dir(config):
    """The evidence root, surviving a key that is present and null.

    `config.get(k, DEFAULT)` falls back only when the key is ABSENT, and a
    null there fails the logging hooks silently.
    docs/design-notes.md § harness_hooks.py · null config keys.
    """
    return config.get("evidenceDir") or DEFAULT_EVIDENCE_DIR


def _max_allowed_objects(config):
    """The atomicity budget, surviving a present-but-null or junk value."""
    value = config.get("maxAllowedObjects")
    return value if isinstance(value, int) and not isinstance(value, bool) \
        else DEFAULT_MAX_ALLOWED_OBJECTS


def _object_candidates(tool_input):
    """Every identifier in this call that could name the object it targets.

    A task can only be scoped by an identifier its plan could know, and at
    plan time a UUID does not exist yet -- it appears once the object does.
    So allowedObjects legitimately carries names, UUIDs, or both, and the
    gate compares the whole set rather than picking one and hoping.
    """
    if not isinstance(tool_input, dict):
        return []
    found = []
    for key in OBJECT_KEYS:
        val = tool_input.get(key)
        if isinstance(val, str) and val and val not in found:
            found.append(val)
    return found


def _object_name(tool_input):
    """The single identifier written to the operations log. The log records
    what was touched for a person reading afterwards, so one representative
    identifier is what it wants; the gate uses _object_candidates."""
    candidates = _object_candidates(tool_input)
    return candidates[0] if candidates else None


def _verdict_path(config, task_id, phase):
    return os.path.join(_evidence_dir(config), task_id,
                         "practices-%s.json" % phase)


# `None` is a real answer from _latest_write_epoch -- "this task has never
# written" -- so it cannot double as "nobody has looked yet".
_UNSET = object()


def _latest_write_epoch(config, task_id):
    """When this task last wrote to Appian, in epoch seconds, or None.

    Read from the write log, which the harness maintains rather than the
    agent -- so it is a record of what actually reached the environment,
    not of what anyone remembered to declare.
    """
    path = os.path.join(_evidence_dir(config), "operations.jsonl")
    if not os.path.isfile(path):
        return None
    latest = None
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if entry.get("task") != task_id:
                    continue
                stamp = entry.get("timestamp")
                if not isinstance(stamp, str):
                    continue
                try:
                    epoch = calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))
                except ValueError:
                    continue
                if latest is None or epoch > latest:
                    latest = epoch
    except OSError:
        return None
    return latest


def _verdict_recorded_epoch(verdict_path):
    """When a verdict says it was recorded, in epoch seconds, or None.

    Prefers the verdict's own `recordedAt` over the file's mtime. See
    `_staleness_error` for why the filesystem was the wrong witness. Returns
    None only when the file cannot be read at all -- an absent or malformed
    `recordedAt` falls back to mtime rather than skipping the check, so a bad
    value is never worth more than no value.
    """
    try:
        with open(verdict_path, encoding="utf-8") as f:
            recorded = json.load(f).get("recordedAt")
    except (OSError, ValueError, AttributeError):
        recorded = None
    if isinstance(recorded, str) and recorded.strip():
        try:
            return calendar.timegm(
                time.strptime(recorded.strip(), "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            pass
    try:
        return os.path.getmtime(verdict_path)
    except OSError:
        return None


def _staleness_error(config, task_id, phase, verdict_path, last_write=_UNSET):
    """Whether this verdict certifies an artifact that has since changed.

    Post-write phases only: `design` is supposed to predate every write.
    Equal timestamps count as fresh (the log has one-second resolution), the
    date comes from the verdict's own `recordedAt` rather than from mtime,
    and mtime is the fallback for verdicts written without that field.
    docs/design-notes.md § harness_hooks.py · verdict staleness.
    """
    if phase in STALENESS_EXEMPT_PHASES:
        return []
    # The write log grows one line per Appian write and lives as long as the
    # project does. Reading it once per phase meant three full scans per
    # Stop; the caller now reads it once and passes the answer down.
    if last_write is _UNSET:
        last_write = _latest_write_epoch(config, task_id)
    if last_write is None:
        return []
    written = _verdict_recorded_epoch(verdict_path)
    if written is None:
        return []
    if last_write <= written:
        return []
    return ["the practices-%s verdict is stale: task %r wrote to Appian at %s, after this "
            "verdict was recorded. It certifies an artifact that has since changed -- re-run "
            "this phase against the current one rather than closing on it"
            % (phase, task_id,
               time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(last_write)))]


def _phase_errors(config, task_id, phase, last_write=_UNSET):
    """Names what's wrong with a phase's verdict; empty means valid AND
    passing.

    validate_verdict answers the shape question, including whether the
    document is about THIS task and phase; this adds the outcome on top.
    Only PASS satisfies, or NOT_MEASURED/DEFERRED, which carries an owner
    and a closing condition. Missing, invalid and failing are three
    different messages on purpose.
    docs/design-notes.md § harness_hooks.py · what satisfies a gate.
    """
    path = _verdict_path(config, task_id, phase)
    # isfile_exact, not os.path.isfile: on Windows and macOS a verdict named
    # `practices-QA.json` would be found and would close the task.
    if not isfile_exact(path, _evidence_dir(config)):
        return ["no practices-%s verdict found at %s" % (phase, path)]
    plugin_root = config.get("pluginRoot")
    if not plugin_root:
        return ["cannot validate practices-%s: no pluginRoot configured" % phase]
    errors = validate_verdict(path, plugin_root, expected_task=task_id, expected_phase=phase)
    if errors:
        return ["practices-%s verdict is invalid: %s" % (phase, "; ".join(errors))]

    stale = _staleness_error(config, task_id, phase, path, last_write)
    if stale:
        return stale

    verdict = load_verdict(path)
    outcome = verdict.get("verdict")
    if outcome == "PASS":
        return []
    if outcome == "NOT_MEASURED" and verdict.get("notMeasuredClass") == "DEFERRED":
        # A deferral is a named debt, not a permission, and this is the
        # moment it is incurred. If the register cannot be written the
        # exception propagates and main() fails closed.
        _record_deferral(config, task_id, phase, verdict)
        return []
    if outcome == "FAIL":
        return ["the practices-%s audit exists and is well-formed, but says FAIL" % phase]
    return ["the practices-%s audit exists and is well-formed, but is NOT_MEASURED with "
            "notMeasuredClass=BLOCKING: it could have been measured and was not, which "
            "is a process failure, not a sanctioned limitation" % phase]


def _official_skill_path(config):
    """Where the official Appian skill is, or None.

    The configured path wins. Failing that, the standard user-scope
    location is checked, because that is where `dev-mcp-skills` installs
    and a project should not have to restate it.
    """
    configured = config.get("officialAppianSkillPath")
    if configured:
        path = configured
        if os.path.isdir(path):
            path = os.path.join(path, "SKILL.md")
        return path if os.path.isfile(path) else None
    for root in (os.path.expanduser("~"), config.get("projectRoot") or "."):
        for rel in SKILL_SEARCH_RELPATHS:
            candidate = os.path.join(root, rel)
            if os.path.isfile(candidate):
                return candidate
    return None


def _official_skill_present(config):
    return _official_skill_path(config) is not None


def _is_count(value):
    """A non-negative whole number, and `True` is not one.

    Python says `isinstance(True, int)`, so without the bool check a run
    written `"maxTasks": true` would authorize exactly one task and read,
    to anyone opening the file, like a switch that turned something on.
    """
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _run_authorization_errors(config, task_id):
    """Whether this task falls inside a run the user actually authorized.

    Authorization is per run, granted once and bounded, and checked here
    rather than trusted. Opt-in: with no `activeRunFile` this returns
    nothing. It never covers the irreversible -- `_destructive_errors`
    prompts regardless of any authorization.
    """
    path = config.get("activeRunFile")
    if not path:
        return []
    if not os.path.isfile(path):
        return ["no authorized run at %s: building without one means nobody granted this "
                "session permission to write. Start a run, or invoke the build by name" % path]
    try:
        with open(path, encoding="utf-8") as f:
            run = json.load(f)
    except (ValueError, OSError) as e:
        return ["the run authorization at %s could not be read: %s" % (path, e)]
    if not isinstance(run, dict):
        return ["the run authorization at %s is not a JSON object" % path]

    errors = []
    tasks = run.get("authorizedTasks")
    if run.get("authorizedAll") is True:
        pass
    elif isinstance(tasks, list):
        if not any(_norm_ident(t) == _norm_ident(task_id) for t in tasks):
            errors.append("task %r is not in this run's authorized tasks %r" % (task_id, tasks))
    else:
        errors.append("the run authorization names neither `authorizedAll` nor a list of "
                      "`authorizedTasks`, so it authorizes nothing in particular")

    # The budget is the difference between "the user authorized this run" and
    # "the user authorized everything from here on", so a missing or
    # unreadable one is an error rather than a check that quietly does not
    # run. A malformed field buys more ceremony, never less.
    budget = run.get("maxTasks")
    done = run.get("tasksCompleted", 0)
    if not _is_count(budget):
        errors.append("this run sets no usable `maxTasks` (found %r): a grant with no budget "
                      "is not a run, it is standing permission" % (budget,))
    elif not _is_count(done):
        errors.append("this run's `tasksCompleted` is %r, which is not a count, so the budget "
                      "of %d cannot be checked" % (done, budget))
    elif done >= budget:
        errors.append("this run's budget is spent (%d of %d tasks). A budget that renews itself "
                      "when it runs out is not a budget" % (done, budget))
    return errors


def _is_destructive_tool(tool_name):
    return bool(DESTRUCTIVE_TOOL_RE.match(tool_name or ""))


def _destructive_errors(config, task_id, tool_name, candidates):
    """The impact assessment a deletion needs before it is allowed to run.

    A deletion's blast radius is not bounded by `allowedObjects`, so two
    things are enforced and they differ in kind: the assessment must EXIST
    (the official skill makes `getObjectDependents` mandatory, and this
    checks its result was recorded for THIS object in this task), and the
    prompt is UNCONDITIONAL even when zero dependents were found.

    Returns reasons, never a refusal -- the gate still only ever asks.
    """
    if not _is_destructive_tool(tool_name):
        return []

    reasons = ["%s cannot be undone. A design object is versioned and recoverable; a deletion "
               "is not, and neither is a row -- record data has no version history, so "
               "overwriting it is as irreversible as removing it. Neither is bounded by "
               "allowedObjects" % tool_name]

    path = os.path.join(_evidence_dir(config), task_id,
                        DEPENDENTS_RECORD_NAME)
    record = {}
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                record = loaded
            else:
                reasons.append("the dependents record at %s is not a JSON object keyed by "
                               "object" % path)
        except (ValueError, OSError) as e:
            reasons.append("the dependents record at %s could not be read: %s" % (path, e))

    assessed = {_norm_ident(k) for k in record}
    unassessed = [c for c in candidates if _norm_ident(c) not in assessed]
    if not candidates:
        reasons.append("the target object could not be identified from this call, so no impact "
                       "assessment can be matched to it")
    elif unassessed:
        reasons.append("no recorded getObjectDependents result for %s at %s. Run the dependency "
                       "check and record what it found -- 'not checked' is not the same answer "
                       "as 'no dependents'" % (", ".join(unassessed), path))
    return reasons


def _lease_errors(config, task_id, candidates):
    """Whether another task holds a lease on the object being written.

    The half of concurrency a worktree cannot cover: two builders in two
    worktrees still write to the same Appian.

    The rule is one-sided on purpose -- a lease held by a DIFFERENT task
    blocks, no lease at all does not -- so single-builder projects, the
    common case, keep working. The register must be SHARED across
    worktrees or it only looks like coordination.
    """
    path = config.get("leaseFile")
    if not path or not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            leases = json.load(f)
    except (ValueError, OSError) as e:
        return ["the object lease register at %s could not be read: %s" % (path, e)]
    if not isinstance(leases, dict):
        return ["the object lease register at %s is not a JSON object mapping object to "
                "task" % path]

    held = {}
    for candidate in candidates:
        for obj, holder in leases.items():
            if _norm_ident(obj) == _norm_ident(candidate) and holder and holder != task_id:
                held[candidate] = holder
    if not held:
        return []
    return ["%s: leased to task %s, not to %s. Two builders on one Appian object is the "
            "collision a git worktree does not prevent -- worktrees isolate files, not the "
            "environment" % (obj, holder, task_id)
            for obj, holder in sorted(held.items())]


def _norm_ident(value):
    return str(value).strip().lower()


def _installed_skill_version(config):
    """The Appian version the installed official skill declares, or None.

    None means "the project did not point at the skill, or it could not be
    read" -- not "the skill is absent". The distinction matters: this is the
    strong half of the check and it is optional, so its absence weakens the
    check rather than failing it. A project that configures
    `officialAppianSkillPath` gets its record compared against the file on
    disk; one that does not gets the presence check only, and is told so
    nowhere because there is nothing actionable to say at write time.
    """
    path = _official_skill_path(config) if config.get("officialAppianSkillPath") else None
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            match = APPIAN_VERSION_RE.search(f.read())
    except (OSError, UnicodeDecodeError):
        return None
    return match.group(1) if match else None


def _skill_record_errors(config, task_id):
    """Names what's wrong with this task's official-skill load record.

    Empty list means the record is present, is about THIS task, and names
    all three links of the chain: the skill, the environment version it
    declares, and the documentation MCP the skill itself depends on.

    It does not prove the skill was loaded -- the agent writes this file.
    What it removes is the silent case. Where the project points at the
    installed skill, the version claim is checked against the file.
    """
    path = os.path.join(_evidence_dir(config), task_id,
                        SKILL_RECORD_NAME)
    if not os.path.isfile(path):
        return ["no load record for the official Appian skill (%s) at %s: load the skill "
                "before writing, then record it -- the tool schemas do not carry naming "
                "conventions, both sides of a relationship, creation order or UUID handling"
                % (OFFICIAL_SKILL_URL, path)]
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except (ValueError, OSError) as e:
        return ["the official-skill load record at %s could not be read: %s" % (path, e)]
    if not isinstance(record, dict):
        return ["the official-skill load record at %s is not a JSON object" % path]

    errors = []
    # Same discipline as a phase verdict: a record that names another task is
    # one record copied across tasks, which is indistinguishable from N real
    # ones unless somebody checks.
    if record.get("task") != task_id:
        errors.append("the official-skill load record names task %r, but this write belongs to "
                      "task %r" % (record.get("task"), task_id))
    if not record.get("skill"):
        errors.append("the official-skill load record names no `skill`")
    docs_claim = record.get("docsMcp")
    if not docs_claim:
        errors.append("the official-skill load record names no `docsMcp`: the official skill "
                      "depends on the documentation MCP for its function-availability checks, "
                      "and without it those checks come back empty, which reads as "
                      "'the function does not exist'")
    else:
        # Cross-check the claim against what is actually configured, when
        # that is knowable. Self-reporting is what the rest of this record
        # has to settle for; this one field does not, so it should not.
        servers = config.get("mcpServers")
        if servers is not None and docs_claim not in servers:
            errors.append("the official-skill load record names documentation MCP %r, which is "
                          "not among the servers configured for this session (%s)"
                          % (docs_claim, ", ".join(servers) or "none"))

    claimed = record.get("appianVersion")
    if not claimed:
        errors.append("the official-skill load record names no `appianVersion`: that field is "
                      "the one thing in it that cannot be filled in without opening the skill")
    else:
        installed = _installed_skill_version(config)
        if installed and str(claimed) != installed:
            errors.append("the official-skill load record claims Appian version %r, but the "
                          "installed skill declares %r" % (claimed, installed))
    return errors


def requirements_errors(config):
    """Which of the three links this session is missing. Empty means all present.

    The chain is design MCP -> official Appian skill -> documentation MCP,
    checked together at session start because each link fails in a way that
    looks like something else.
    docs/design-notes.md § harness_hooks.py · the three links.

    `mcpServers` is None when discovery did not run or could not read the
    configuration, and that is deliberately not an empty list: not knowing
    is not the same as knowing there are none.
    """
    missing = []
    servers = config.get("mcpServers")
    if servers is not None:
        design = config.get("designMcpServer") or DEFAULT_DESIGN_MCP
        docs = config.get("docsMcpServer") or DEFAULT_DOCS_MCP
        if design not in servers:
            missing.append(
                "the design MCP %r is not configured. The write and closure gates in this "
                "plugin hang off Appian `mcp__*` write tools, so without it the harness "
                "gates nothing at all while still looking healthy." % design)
        if docs not in servers:
            missing.append(
                "the documentation MCP %r is not configured. The official Appian skill "
                "relies on it for function-availability checks; without it those come back "
                "empty, and empty is indistinguishable from 'the function does not "
                "exist'." % docs)
    if not _official_skill_present(config):
        missing.append(
            "the official Appian skill is not installed where this plugin can see it. "
            "Install it from %s -- it carries the naming conventions, both sides of a "
            "relationship, the creation order and the UUID handling that the MCP tool "
            "schemas cannot express, and that no gate here measures." % OFFICIAL_SKILL_URL)
    return missing


def _loaded_version(config):
    """The version actually running, from the plugin root, or None.

    Not the installed version -- the *loaded* one. The component inventory
    is fixed when the process starts, so after an update the session keeps
    running the old copy until it restarts, and `CLAUDE_PLUGIN_ROOT` (one
    cache directory per version) is the only place that can say which.

    Returns None rather than raising: a session must never lose the
    requirements report to get the version.
    """
    root = config.get("pluginRoot")
    if not root:
        return None
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"),
                  encoding="utf-8") as f:
            version = json.load(f).get("version")
    except (OSError, ValueError, AttributeError):
        return None
    return version if isinstance(version, str) and version.strip() else None


def _banner(config):
    """`appian-harness` plus the running version when it can be read."""
    version = _loaded_version(config)
    return "appian-harness %s" % version if version else "appian-harness"


def session_start(payload, config):
    """SessionStart: report the three links up front, once.

    Informative, never blocking -- a session that cannot write yet is still
    a session worth having, for reading, planning or specifying. What it
    must not do is let someone reach their first write before finding out.

    It also asks for the one thing no hook can determine: whether the
    design MCP actually *answers*. Configured and alive are different
    states, and only a real call tells them apart.
    """
    missing = requirements_errors(config)
    if not missing:
        return {"additionalContext": (
            "%s: all three requirements are present (design MCP, official " % _banner(config) +
            "Appian skill, documentation MCP). Configured is not the same as answering: "
            "before the first write of this session, confirm the design MCP really "
            "responds with `validateExpression(\"1 + 1\")` -- listing tools proves "
            "nothing, it never reaches Appian. Then follow the phases: "
            "appian-specify -> appian-plan -> appian-build -> appian-verify -> "
            "appian-review, consulting `appian-best-practices` for the domains each "
            "change touches, and loading the official Appian skill before every build.")}
    return {"additionalContext": (
        "%s: WRITING TO APPIAN IS NOT SAFE IN THIS SESSION. %d of the three "
        "requirements %s missing:\n\n- %s\n\nReading, specifying and planning are fine. "
        "Do not issue create or update calls against Appian until this is resolved -- and "
        "say so plainly rather than working around it." % (
            _banner(config), len(missing), "is" if len(missing) == 1 else "are",
            "\n- ".join(missing)))}


def scope_gate(payload, config):
    """PreToolUse gate for Appian write tools. Never denies.

    Checks, in order, and accumulates every reason instead of stopping at
    the first:

      1. an active task exists
      2. the object is in its allowedObjects
      3. the task is inside an authorized run (only when the project
         configures `activeRunFile`; otherwise inert)
      4. no other task holds a lease on the object (only when the project
         configures `leaseFile`; otherwise inert)
      5. if the call is irreversible -- a delete, or a record-data
         overwrite -- an impact assessment exists, and it prompts either way
      6. the task is atomic (len(allowedObjects) <= maxAllowedObjects)
      7. the official Appian skill's load record exists for this task
      8. a present, valid and passing practices-design verdict

    The skill record is checked before the design verdict because that is
    the order the two happen in: a design audited without the domain
    knowledge was audited against the wrong thing.
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

        candidates = _object_candidates(payload.get("tool_input", {}))
        if not candidates:
            reasons.append("could not identify the target object from tool_input; "
                            "cannot check it against allowedObjects")
        elif not any(c in allowed_objects for c in candidates):
            reasons.append("no identifier in this call %r is in the task's allowedObjects %r" %
                            (candidates, allowed_objects))
        reasons.extend(_run_authorization_errors(config, task_id))
        reasons.extend(_lease_errors(config, task_id, candidates))
        reasons.extend(_destructive_errors(config, task_id, tool_name, candidates))

        max_allowed = _max_allowed_objects(config)
        if len(allowed_objects) > max_allowed:
            reasons.append(
                "task %r touches %d objects, more than maxAllowedObjects=%d: not atomic" %
                (task_id, len(allowed_objects), max_allowed))

        reasons.extend(_skill_record_errors(config, task_id))
        reasons.extend(_phase_errors(config, task_id, "design"))

    if reasons:
        return {"permissionDecision": "ask", "permissionDecisionReason": " · ".join(reasons)}
    return {"permissionDecision": "allow",
            "permissionDecisionReason": "scope and design audit check out"}


def _risk_tier(active_task):
    """This task's risk tier, normalised. Pure — it decides, it does not record.

    An unrecognised value is treated as `standard`: a typo should buy more
    ceremony than intended, never less.

    Deciding and recording are two calls on purpose. A query that writes a
    file puts an `evidence/` directory wherever the current directory
    happens to be — including inside the plugin's own checkout.
    """
    declared = (active_task or {}).get("risk")
    key = _norm_ident(declared) if isinstance(declared, str) else ""
    return key if key in RISK_CLOSURE_PHASES else DEFAULT_RISK


def _required_closure_phases(config, active_task):
    """Which verdicts this task must have, graduated by its declared risk."""
    return RISK_CLOSURE_PHASES[_risk_tier(active_task)]


def _log_risk_downgrade(config, task_id, declared):
    """Records a task closing on the reduced set, so the choice is auditable.

    Deduplicated per task, because the closure gate can fire more than once
    for the same task and a register that repeats itself is a register
    nobody reads.
    """
    path = os.path.join(_evidence_dir(config),
                        "risk-downgrades.jsonl")
    if os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        if json.loads(line).get("task") == task_id:
                            return
                    except ValueError:
                        continue
        except OSError:
            pass
    _append_jsonl(path, {
        "timestamp": _now(), "task": task_id, "declaredRisk": declared,
        "requiredPhases": list(RISK_CLOSURE_PHASES["trivial"]),
        "reason": "task %r closed as trivial: only %s was required. Recorded so that "
                  "'was it really trivial?' has an answer later."
                  % (task_id, ", ".join(RISK_CLOSURE_PHASES["trivial"])),
    })


def closure_gate(payload, config):
    """Stop gate: a task cannot close without its three post-write verdicts.

    scope_gate covers the write itself; review and QA happen after writing,
    so they can only be enforced here. Names which verdicts are missing,
    invalid or failing rather than making the agent guess.

    A task is in flight from appian-build until appian-review closes it, so
    the builder's own Stop lands here with the verdicts legitimately absent:
    that block names the next phase to run, it is not a failure report.

    A Stop hook has only approve and block, so on a repeat attempt
    (payload["stop_hook_active"]) this approves rather than deadlock the
    session -- never silently: the omission becomes named debt,
    NOT_MEASURED / BLOCKING, written where a human finds it.
    """
    active_task = config.get("activeTask")
    if not active_task or not active_task.get("id"):
        return {"decision": "approve"}

    task_id = active_task["id"]
    # Read once for all phases rather than once each: the write log grows
    # with the project and this is the only place they are all measured
    # against it.
    last_write = _latest_write_epoch(config, task_id)
    required = _required_closure_phases(config, active_task)
    if _risk_tier(active_task) == "trivial":
        _log_risk_downgrade(config, task_id, active_task.get("risk"))
    missing_phases = []
    missing_details = []
    for phase in required:
        errs = _phase_errors(config, task_id, phase, last_write)
        if errs:
            missing_phases.append(phase)
            missing_details.append("practices-%s (%s)" % (phase, "; ".join(errs)))

    if not missing_details:
        return {"decision": "approve"}

    if payload.get("stop_hook_active"):
        debt_path = _record_deferred_debt(config, task_id, missing_phases)
        return {"decision": "approve",
                "systemMessage": (
                    "Task %r is closing UNMEASURED: %s could not be produced. "
                    "This is recorded as NOT_MEASURED/BLOCKING debt in %s, not "
                    "waived." % (task_id,
                                 ", ".join("practices-%s" % p for p in missing_phases),
                                 debt_path))}

    return {"decision": "block",
            "reason": "task %r is still in flight, so this stop is a handoff, not a close. "
                      "Not yet produced or not yet passing: %s. Next step: run appian-verify "
                      "for this task -- it produces practices-implementation and practices-qa "
                      "-- and then appian-review, which produces practices-review and clears "
                      "the active task file once the task closes. Detail: %s" %
                      (task_id,
                       ", ".join("practices-%s" % p for p in missing_phases),
                       " | ".join(missing_details))}


def failure_notice(payload):
    """PostToolUseFailure: turns 'remember to be idempotent' into a reminder.

    A failed write leaves the agent guessing whether it landed. This tells
    it not to guess: read first, record the partial state, then resume from
    the first thing it never confirmed.

    A failed READ gets no notice, and that asymmetry is the point: nothing
    persisted, nothing partial to record, and "do not retry" is the opposite
    of the fix -- a read that failed on a misspelled field wants reissuing.
    """
    tool_name = payload.get("tool_name")
    if not _is_write_tool(tool_name):
        return {}
    message = (
        "The write via %s failed. Do not retry this write; check with a read "
        "whether it persisted, record what did and did not, and resume from "
        "the first unverified result." % tool_name
    )
    return {"additionalContext": message}


def _write_result(payload):
    # PostToolUse delivers the tool's return as `tool_response`; `tool_result`
    # is read as a fallback so a rename cannot silently log every write as
    # "ok". docs/design-notes.md § harness_hooks.py · tool_response.
    result = payload.get("tool_response")
    if result is None:
        result = payload.get("tool_result")
    if isinstance(result, dict) and (result.get("is_error") or result.get("error")):
        return "error"
    if isinstance(result, str) and result.lower().startswith("error"):
        return "error"
    return "ok"


def log_write(payload, config):
    """PostToolUse: the harness logs writes, not the agent -- an agent asked
    to log its own writes forgets exactly when it matters.

    It logs *writes*. The JSON matcher routes a bare
    `invoke|start|execute|run|test` on purpose -- the net that keeps a real
    write from escaping the scope gate -- so the line between a write and a
    read is drawn here, by `WRITE_TOOL_RE`. A read recorded as a write
    expires the in-flight task's verdicts and blocks its closure gate.
    """
    if not _is_write_tool(payload.get("tool_name")):
        return {}
    active_task = config.get("activeTask") or {}
    entry = {
        "timestamp": _now(),
        "task": active_task.get("id"),
        "tool": payload.get("tool_name"),
        "object": _object_name(payload.get("tool_input", {})),
        "result": _write_result(payload),
    }
    _append_jsonl(os.path.join(_evidence_dir(config),
                                "operations.jsonl"), entry)
    return {}


def _evidence_write_target(config, file_path):
    """Names which of the gates' inputs this path is, or None.

    The inputs are the evidence tree, the harness config, the active task
    file, the run authorization and the lease register: plain files in the
    project, all writable by the agent the gates constrain.

    THIS LIST MUST GROW whenever the gates learn to read something new, or
    an edit to the new input leaves no line.
    """
    if not isinstance(file_path, str) or not file_path:
        return None
    root = config.get("projectRoot") or "."
    target = os.path.normcase(os.path.abspath(os.path.join(root, file_path)))

    for key, label in (("configPath", "harness-config"),
                       ("activeTaskFile", "active-task"),
                       ("activeRunFile", "run-authorization"),
                       ("leaseFile", "lease-register")):
        known = config.get(key)
        if known and os.path.normcase(os.path.abspath(known)) == target:
            return label

    evidence = config.get("evidenceDir")
    if evidence:
        evidence = os.path.normcase(os.path.abspath(evidence))
        if target == evidence or target.startswith(evidence + os.sep):
            return "evidence"
    return None


def log_evidence_write(payload, config):
    """PostToolUse on file writes: records edits to what the gates read.

    Logged, not gated: the auditor legitimately writes verdicts here and a
    hook cannot tell which agent holds the pen, so gating would question the
    harness's own correct operation on every task.

    It does not prevent forgery -- an agent with write access can still
    author a verdict. What changes is that doing so is no longer invisible.
    """
    target = _evidence_write_target(config, (payload.get("tool_input") or {}).get("file_path"))
    if target is None:
        return {}
    active_task = config.get("activeTask") or {}
    _append_jsonl(os.path.join(_evidence_dir(config),
                                "evidence-writes.jsonl"),
                  {"timestamp": _now(),
                   "task": active_task.get("id"),
                   "tool": payload.get("tool_name"),
                   "target": target,
                   "path": (payload.get("tool_input") or {}).get("file_path"),
                   "result": _write_result(payload)})
    return {}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_jsonl(path):
    """Every well-formed object in a JSONL register, skipping the rest.

    A half-written line must not make a register unreadable.

    An unreadable register returns `[]`, so `_record_deferred_debt` finds no
    prior entry and appends: the failure costs noise, never a silently
    missing debt record.
    """
    if not os.path.isfile(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if isinstance(entry, dict):
                    out.append(entry)
    except OSError:
        return []
    return out


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
        "timestamp": _now(),
        "task": task_id,
        "tool": tool_name,
        "decision": "ask",
        "reason": reason,
    }
    _append_jsonl(os.path.join(_evidence_dir(config),
                                "gate-decisions.jsonl"), entry)


def _debt_register(config):
    return os.path.join(_evidence_dir(config), "deferred-debt.jsonl")


def _record_deferral(config, task_id, phase, verdict):
    """Appends one accepted deferral to the project's deferred-debt register.

    Deduplicated on (task, phase, criterion): the scope gate runs on every
    write, so without it one deferral becomes one line per write attempt.

    Shares the register with the closure gate's forced approvals, told apart
    by `notMeasuredClass`: DEFERRED here, an owned debt; BLOCKING there, a
    process failure.
    """
    path = _debt_register(config)
    criterion = verdict.get("deferredCriterion")
    key = (task_id, phase, criterion)
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if (e.get("task"), e.get("phase"), e.get("criterion")) == key:
                    return path
    _append_jsonl(path, {
        "timestamp": _now(),
        "task": task_id,
        "phase": phase,
        "criterion": criterion,
        "verdict": "NOT_MEASURED",
        "notMeasuredClass": "DEFERRED",
        "owner": verdict.get("owner"),
        "closingCondition": verdict.get("closingCondition"),
        "reason": "practices-%s for task %r deferred %r; it opened the gate on the owner and "
                  "closing condition recorded here" % (phase, task_id, criterion),
    })
    return path


def _record_deferred_debt(config, task_id, missing_phases):
    """Writes one entry to the project's deferred-debt register when the
    closure gate is forced to approve a task it cannot verify. Returns the
    register's path so the caller can point a human at it.

    Reaching here means the task is still in flight, not that it closed.
    Repeats of the same omission are skipped so a task waiting on a human
    across sessions does not bury the entry that carries an owner; a
    DIFFERENT set of missing phases is new information and is appended. The
    register is append-only -- nothing is ever rewritten in place.
    """
    debt_path = _debt_register(config)
    phases = list(missing_phases)
    for prior in _read_jsonl(debt_path):
        if (prior.get("task") == task_id
                and prior.get("missingPhases") == phases
                and prior.get("verdict") == "NOT_MEASURED"):
            return debt_path
    entry = {
        "timestamp": _now(),
        "task": task_id,
        "missingPhases": phases,
        "verdict": "NOT_MEASURED",
        "notMeasuredClass": "BLOCKING",
        "reason": "task %r remains in flight and unverified after a repeated Stop; the gate "
                  "approved so the session could hand off rather than deadlock. Still missing: "
                  "%s. This is a handoff, not a close: the task file is still there." %
                   (task_id, ", ".join(phases)),
    }
    _append_jsonl(debt_path, entry)
    return debt_path


# --- CLI wiring --------------------------------------------------------
# Above: pure functions, unit-tested directly. Below: stdin, config
# resolution, and the hook JSON contract Claude Code expects on stdout.

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


def _discover_mcp_servers(project_root):
    """Every MCP server name this session could see, or None if unknowable.

    Reports what the configuration files DECLARE: a hook cannot ask Claude
    Code which servers ended up live, which is why the session-start message
    asks for `validateExpression` instead of treating this as proof.

    None means no configuration file could be read at all -- reporting a
    missing server on that basis would be a false alarm.
    """
    names = set()
    seen_any = False
    candidates = [
        os.path.join(project_root, ".mcp.json"),
        os.path.join(os.path.expanduser("~"), ".claude.json"),
    ]
    for path in candidates:
        data, err = _load_json_file(path)
        if data is None or err or not isinstance(data, dict):
            continue
        seen_any = True
        servers = data.get("mcpServers")
        if isinstance(servers, dict):
            names.update(servers.keys())
        # ~/.claude.json also carries per-project blocks; the one for this
        # project counts, the others belong to somebody else's work.
        projects = data.get("projects")
        if isinstance(projects, dict):
            here = os.path.normcase(os.path.abspath(project_root))
            for key, cfg_block in projects.items():
                if os.path.normcase(os.path.abspath(key)) != here:
                    continue
                scoped = (cfg_block or {}).get("mcpServers")
                if isinstance(scoped, dict):
                    names.update(scoped.keys())
    return sorted(names) if seen_any else None


def _resolve_optional_path(project_root, value):
    """Expands `~` and makes a relative path project-relative. None stays None.

    The official skill is normally installed at user scope
    (`~/.claude/skills/appian/`), which is outside any project, so this has
    to accept an absolute path and a `~` prefix as first-class -- while
    still letting a project vendor its own copy and point at it relatively.
    """
    if not value:
        return None
    value = os.path.expanduser(value)
    return value if os.path.isabs(value) else os.path.join(project_root, value)


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
                                 project_config.get("evidenceDir") or DEFAULT_EVIDENCE_DIR)
    active_task_file = os.path.join(
        project_root, project_config.get("activeTaskFile") or DEFAULT_ACTIVE_TASK_FILE)
    active_task, task_err = _load_json_file(active_task_file)
    if task_err:
        return None, True, task_err

    config = {
        "pluginRoot": os.environ.get("CLAUDE_PLUGIN_ROOT"),
        "evidenceDir": evidence_dir,
        "activeTask": active_task,
        "maxAllowedObjects": _max_allowed_objects(project_config),
        # Optional: pointed at the installed skill, the load record's version
        # claim is compared against the file instead of trusted. Absolute
        # paths are taken as given -- the skill usually lives at user scope.
        "officialAppianSkillPath": _resolve_optional_path(
            project_root, project_config.get("officialAppianSkillPath")),
        # Opt-in, because sequential is the common case. When on, this path
        # must be SHARED across worktrees: a private copy per builder looks
        # like coordination and is worse than none.
        "leaseFile": _resolve_optional_path(project_root, project_config.get("leaseFile")),
        # Opt-in too: configured, writes must fall inside a run the user
        # granted; absent, every build is started by hand as before.
        "activeRunFile": _resolve_optional_path(project_root,
                                                project_config.get("activeRunFile")),
        # Server names are defaults, not assumptions: a project may call its
        # servers anything.
        "designMcpServer": project_config.get("designMcpServer") or DEFAULT_DESIGN_MCP,
        "docsMcpServer": project_config.get("docsMcpServer") or DEFAULT_DOCS_MCP,
        "mcpServers": _discover_mcp_servers(project_root),
        # The three paths the gates read, kept so log_evidence_write can
        # recognise a write aimed at one of them.
        "projectRoot": project_root,
        "configPath": config_path,
        "activeTaskFile": active_task_file,
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


def cmd_log_evidence_write():
    payload, parse_err = _read_stdin_json()
    config, active, err = _build_config(payload.get("cwd") or ".")
    if not active or err or parse_err:
        _emit({})
        return 0
    log_evidence_write(payload, config)
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


def cmd_session_start():
    payload, _parse_err = _read_stdin_json()
    config, active, err = _build_config(payload.get("cwd") or ".")
    if not active:
        _emit({})
        return 0
    if err:
        _emit({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "appian-harness: the harness config could not be read (%s), so "
                                 "the requirements check did not run. Nothing in this session has "
                                 "confirmed that the design MCP, the official Appian skill and the "
                                 "documentation MCP are present." % err,
        }})
        return 0
    _emit({"hookSpecificOutput": dict(session_start(payload, config),
                                      hookEventName="SessionStart")})
    return 0


COMMANDS = {
    "session-start": cmd_session_start,
    "scope-gate": cmd_scope_gate,
    "closure-gate": cmd_closure_gate,
    "log-write": cmd_log_write,
    "log-evidence-write": cmd_log_evidence_write,
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
