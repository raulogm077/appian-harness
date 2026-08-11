"""Six hooks that enforce the Appian harness's requirements, write and
closure gates.

The plugin's premise is that an agent must not be able to mark its own work
as passing. These hooks are where that stops being advice:

- session_start (SessionStart): are the three links present -- a design MCP,
  the official Appian skill, a documentation MCP? Each one fails in a way
  that looks like something else, so they are reported together at the
  start rather than discovered one confusing afternoon at a time. Informs,
  never blocks: a session missing a link is still good for reading and
  planning. It cannot tell "configured" from "answering", so it asks the
  agent to prove the design MCP alive with validateExpression.
- scope_gate (PreToolUse on Appian write tools): is there an approved active
  task? is the object in its allowedObjects? is the task inside an
  authorized run, and is the object free of another task's lease (both only
  when the project configures them)? is this call irreversible, and if so
  has its impact been assessed? is the task atomic? was the official Appian
  skill loaded and recorded for this task? is there a
  PASSING design audit for it? "Passing" is two checks stacked: structurally
  valid per validate_verdict (so a fabricated citation fails the gate, not
  just a missing file), AND an outcome of PASS or a sanctioned, owned
  NOT_MEASURED/DEFERRED -- a FAIL or an unowned NOT_MEASURED/BLOCKING audit
  does not unlock the write, because a gate that accepts a FAIL is not a
  gate.
- closure_gate (Stop): the write gate cannot cover review and QA, which
  happen after writing. This blocks closing a task without passing
  practices-implementation, practices-review and practices-qa verdicts, and
  names which are missing or failing -- except on a repeat Stop attempt,
  where blocking forever would just get the gate disabled, so it approves
  and records the omission as recorded debt instead (see closure_gate's
  own docstring).
- log_write (PostToolUse): appends task, tool, object and result to
  operations.jsonl. The harness records it, not the agent -- an agent asked
  to log its own writes forgets exactly when it matters.
- log_evidence_write (PostToolUse on file writes): records edits aimed at
  the three files the gates themselves read -- the evidence tree, the
  harness config, the active task file. Every one of them is writable by
  the agent the gates constrain, so this exists to make that visible. It
  logs rather than gates, for the reason argued in its own docstring.
- failure_notice (PostToolUseFailure): tells the agent not to retry a failed
  write blindly. Says nothing about a failed read, which wants retrying.

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
import calendar
import json
import os
import re
import sys
import time

# harness_hooks.py lives in hooks/; validate_verdict.py lives in ../scripts/.
# Inserted unconditionally so this module is self-sufficient whether it's
# imported by the test suite or run directly as the hook's entry point.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from validate_verdict import isfile_exact, load_verdict, validate_verdict

# The second half of a two-stage filter, and the two stages are NOT
# interchangeable. hooks.json decides which tool calls reach this process at
# all; this decides what to do with the ones that arrive. A tool the JSON
# matcher does not route is a tool this function never sees in production,
# however broad this pattern is -- which is exactly how the runtime-invoke
# gating below was dead for a while: the verbs were added here and the JSON
# matcher had no `(appian_)?` allowance, so `appian_invoke_process_model`
# matched here and was never routed. Found by an outside reading, not by
# these tests, because the tests call scope_gate directly and bypass the
# matcher entirely.
#
# So the invariant to hold is: **hooks.json must route everything this
# pattern gates.** This side is deliberately NARROWER on the runtime verbs
# (the JSON side routes a bare `invoke|start|run|test`, this one names the
# specific tools), which is safe -- extra routing costs one no-op call.
# Broader here than there is the unsafe direction, and it is silent.
#
# `test_matcher_parity.py` is what holds it, and it exists because the
# invariant spent a while written down and unchecked. It reads hooks.json,
# applies both patterns to the real tool catalogue of the two Appian MCP
# servers, and fails if anything this gates would not be routed.
#
# Which is also why there is no re.IGNORECASE here any more. Claude Code
# applies the JSON matcher as written and has no flag to make it
# case-insensitive -- that matcher spells `[Aa]ppian` by hand for exactly
# that reason. A case-insensitive pattern on this side is therefore broader
# than the routing, the unsafe direction, so the character classes below
# mirror the JSON ones literally rather than leaning on a flag the other
# half does not have.
WRITE_TOOL_RE = re.compile(
    r"^mcp__[a-zA-Z0-9_-]*[Aa]ppian[a-zA-Z0-9_-]*__"
    # The `appian` runtime server prefixes every tool with `appian_`, so the
    # verb is not where a reader expects it: the tool is
    # `appian_invoke_process_model`, not `invoke_process_model`.
    r"(?:appian_)?"
    r"(create|update|add|insert|configure|reorder|upload|replace|delete|remove"
    r"|invoke_process_model|invoke_agent|start_process|execute"
    r"|testProcessModel)",
)

# Two corrections are folded into that pattern, and both were measured
# against real tool names rather than reasoned about:
#
# It used to begin `^mcp__.*__`, which matched ANY MCP server. With the
# config present, `mcp__claude_ai_Supabase__create_project`,
# `Supabase__delete_branch`, `Figma__create_new_file` and
# `Google_Drive__create_file` were all measured against an Appian task's
# allowedObjects -- and inconsistently, since `Notion__notion-create-pages`
# escaped because the verb has to follow the separator. Requiring `appian`
# in the server name keeps the gate on the environment it reasons about.
#
# The worse half was the other direction. The verb list described the
# design catalogue and said nothing about the runtime, so
# `mcp__appian__appian_invoke_process_model` -- which starts a real process
# and writes real data in a shared environment -- passed with no gate at
# all, as did `appian_invoke_agent` and `appian-dev__testProcessModel`.
# `invoke_process_model`, `invoke_agent`, `start_process`, `execute` and
# `testProcessModel` close that.
#
# Those runtime verbs are spelled out rather than matched as a bare
# `invoke|run|test` prefix, and that precision is the point: an expression
# rule has no side effects, so `invoke_expression_rule` and `testRule` are
# reads, and `runAllInterfaceTestCases` replays stored cases, which is what
# a verification step is supposed to do freely. Gating those would put
# friction on discovery and on verification -- the two things this harness
# most wants to be cheap.
#
# Both corrections were measured, not reasoned, and the measurement is
# `test_matcher_parity.py` rather than a number in this comment -- a claim
# about a count nobody can re-run is the kind of evidence this plugin
# refuses everywhere else. The first version of this pattern was written
# from memory and missed that the `appian` server prefixes its tools with
# `appian_`, which is why the corpus in that test is the real catalogue.

# The irreversible half of an asymmetric pair. An update is versioned and
# recoverable; a deletion is not, and neither is a dropped column. These get
# a different treatment from every other write, and the difference is not a
# stricter version of the same check -- it is a different question.
#
# It has to stay a SUBSET of WRITE_TOOL_RE, which is why its classes mirror
# that pattern's rather than being written independently: `scope_gate`
# returns early for anything `_is_write_tool` rejects, so a name this
# matched and that did not would skip the confirmation on the one class of
# call that cannot be undone.
DESTRUCTIVE_TOOL_RE = re.compile(
    r"^mcp__[a-zA-Z0-9_-]*[Aa]ppian[a-zA-Z0-9_-]*__(?:appian_)?"
    r"(delete|remove"
    # `updateRecordData` belongs here and it took an outside reading to see
    # it. The premise separating destructive from ordinary -- "an update is
    # versioned and recoverable" -- is true of DESIGN objects and false of
    # RECORD DATA: a row has no version history, so overwriting one is
    # exactly as irreversible as deleting it, and just as unbounded by
    # `allowedObjects`. Grouping it with `updateInterface` because both are
    # spelled "update" was reasoning from the verb instead of from what the
    # verb does.
    r"|updateRecordData)",
)

# Where a task records what it found before deleting. One file per task,
# keyed by object, because an object name is not safe to put in a filename.
DEPENDENTS_RECORD_NAME = "dependents.json"

# Candidate keys for the object a write tool targets. Appian MCP tools don't
# share one argument name for "the object", so every one of these is read and
# they are treated as alternative spellings of the SAME target rather than as
# a list of different objects -- which is what makes "in scope if any of them
# matches" the correct rule and not a loosening of the gate.
#
# Preferring one key over the others was wrong against the real schemas.
# `updateInterface` takes a `uuid` and usually carries no `name`;
# `addRecordTypeField(uuid, fieldName)` has no `name` at all; and
# `updateProcessModelNode(processModelUuid, nodeId, name)` has a `name` that
# belongs to the *node*, not to the object the task scoped. So most
# post-create writes compared a string that was never going to be in
# allowedObjects, and asked.
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
# allow-list of exemptions rather than a list of what to check, so a phase
# added later is checked by default -- see `_staleness_error`, which had it
# the other way round and left the high-risk tier's extra verdict immortal.
STALENESS_EXEMPT_PHASES = ("design",)

# Proportionality, in the layer that actually enforces it. The doctrine has
# always graduated by risk -- the calibration table in appian-best-practices,
# the entry threshold in appian-review -- while the gates applied one ceremony
# to everything. So a text fix cost four verdicts, and the way people escape
# that is to stop declaring tasks at all, which loses the record entirely.
#
# `risk` is declared in the plan and copied into the active task file:
#
#   trivial   -- cosmetic, local, touches no data, permissions or queries.
#                One verdict. It is still a recorded task with evidence,
#                which is the point: the alternative people actually choose
#                is no task at all.
#   standard  -- the default, and what an absent or unrecognised value means.
#   high      -- data model, security, architecture, integrations. Adds an
#                adversarial pass whose question is "how does this fail?"
#                rather than "does this meet the contract?" -- a different
#                premise, which is the only reason a fourth reviewer earns
#                its cost.
#
# Declaring `trivial` is a downgrade the builder can write, like everything
# else here. It is not prevented; it is logged (see _log_risk_downgrade), so
# "was this really trivial?" is answerable afterwards.
RISK_CLOSURE_PHASES = {
    "trivial": ("implementation",),
    "standard": CLOSURE_PHASES,
    "high": CLOSURE_PHASES + ("risk",),
}
DEFAULT_RISK = "standard"

# Writing to Appian through the design MCP requires the official Appian skill
# (github.com/appian/dev-mcp-skills), which carries what the tool schemas
# cannot express: naming conventions, both sides of a relationship, the order
# objects must be created in, and real UUIDs versus invented ones. None of
# that is anything this plugin's gates measure -- they check the contract,
# atomicity and the presence of a verdict -- so a write issued without it
# fails in a way nothing here would catch.
#
# A hook cannot see whether a skill is in an agent's context; that limit is
# the same one this plugin already states about its own doctrine. What a hook
# CAN open is a file, so the requirement is enforced the way the design audit
# already is: the build records the load per task, and the gate reads it.
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

# The official skill declares the environment's version in its own SKILL.md as
# `**Appian Version:** 26.7`. That field is the one thing in the record that
# cannot be filled in without having opened the skill, which is what makes it
# worth checking rather than decorative -- and when the project points at the
# installed skill, the claim stops being self-reported and gets compared
# against the file on disk.
APPIAN_VERSION_RE = re.compile(r"^\s*\*\*Appian Version:\*\*\s*(\S+)", re.MULTILINE)


def _is_write_tool(tool_name):
    return bool(WRITE_TOOL_RE.match(tool_name or ""))


def _evidence_dir(config):
    """The evidence root, surviving a key that is present and null.

    `config.get(k, DEFAULT)` returns the DEFAULT only when the key is
    ABSENT. A project whose `.claude/appian-harness.json` says
    `"evidenceDir": null` -- which is what a half-filled template looks
    like -- got `None`, and `os.path.join(None, ...)` raises.

    The crash itself was survivable; where it landed was not. `main()`
    catches everything, and its answers are asymmetric by design: the scope
    gate turns an exception into a loud `ask` and the closure gate into a
    `block`, but the two logging hooks emit `{}` and exit 0. So one null in
    a config file stopped the operations log and the evidence-write log
    **silently**, at the same moment a person started hand-approving a
    stream of "harness hook error" prompts. And an empty write log reads to
    `_staleness_error` as "this task never wrote", which quietly makes every
    stale verdict look fresh.

    Fail-closed held for the gates and the audit trail failed open, which
    is the wrong way round: the gates announce their own failure, the logs
    are what nobody is watching.
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

    The gap this closes: nothing tied a verdict to a version of the thing
    it judged. So a review coming back FAIL, the agent fixing it, and only
    `phase=review` being re-run left the pre-fix `implementation` and `qa`
    verdicts still satisfying the closure gate -- two PASSes certifying an
    artifact that no longer existed. With one builder that is an occasional
    slip; unattended, or with several builders, it is the normal case.

    Only the post-write phases are checked, and the exemption is named
    rather than derived. `design` is *supposed* to predate every write --
    that is the whole argument for running it before the first one -- so
    measuring it against the write log would mark every correct design
    audit stale. Every other phase judges what the writes produced.

    Keying this on `CLOSURE_PHASES` instead was wrong in the one place it
    could least afford to be. `risk` is not in that tuple -- it is appended
    to it for high-risk tasks -- so the fourth verdict, bought precisely
    because a mistake there is expensive, was the only one that never
    expired. Stating the exemption as `design` means a phase added later is
    checked by default and has to argue its way out.

    Equal timestamps count as fresh: the log has one-second resolution, and
    a verdict written in the same second as the write it judges is the
    normal case, not a violation.

    When the verdict was recorded is read from the verdict, not from the
    filesystem. It used to be `getmtime`, which made the file's mtime *be*
    the claim, and mtime is not a claim anyone made: `touch` cleared an
    expiry without re-running a single audit -- the rubber stamp this check
    exists to prevent -- and a clone, a copy or a restore from backup rewrote
    every mtime at once, so freshness did not survive moving the project.
    `recordedAt` is the auditor's own statement about its own verdict.

    mtime stays as the fallback, and deliberately: every verdict written
    before this field existed is on disk without it, and treating those as
    undatable would either expire all of them or exempt all of them. Falling
    back is also what an unparseable value does -- a malformed `recordedAt`
    must not buy a pass it could never buy by being absent.
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
    """Names what's wrong with a phase's verdict; empty list means valid AND
    passing. Both halves matter and neither is optional:

    - validate_verdict answers "is this a well-formed audit of THIS task and
      THIS phase, whose citations resolve?" -- a document-shape question,
      plus the one thing shape alone cannot answer: whether the document is
      about the work whose gate is opening it. Both gates assemble the path
      from a task id and a phase, so both can say what they are opening, and
      they do. Before they did, a verdict reading
      {"task": "TASK-999", "phase": "qa"} satisfied every one of the four
      filenames, and one audit copied four times was indistinguishable from
      four independent ones. It deliberately still says nothing about the
      outcome, and that separation is correct: it is not this function's job
      to duplicate validate_verdict's citation-resolution logic, only to add
      the outcome check on top of it.
    - A phase audit only SATISFIES a gate when verdict == PASS, or
      verdict == NOT_MEASURED with notMeasuredClass == DEFERRED (which
      validate_verdict already guarantees carries an owner and a
      closingCondition). FAIL never satisfies. NOT_MEASURED/BLOCKING never
      satisfies either: DEFERRED is the sanctioned, owned, named escape;
      BLOCKING is the harness saying it could have measured this and did
      not, which is a process failure, not a limitation.

    A missing file, a structurally-invalid file, and a structurally-valid
    file with a non-satisfying outcome are three different problems, and the
    caller (an "ask" or "block" reason shown to a person) needs to be able
    to tell them apart -- "the audit exists and says FAIL" is not the same
    message as "there is no audit".
    """
    path = _verdict_path(config, task_id, phase)
    # isfile_exact rather than os.path.isfile: the documented contract is that
    # a verdict named `practices-QA.json` is one the gate reports as missing,
    # and on Windows or macOS plain isfile finds it and closes the task. The
    # evidence root is the bound -- the project chose that path's case, the
    # agent chose everything below it.
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
        # A deferral is not a permission, it is a named debt -- which is
        # what 10-quality-gates.md always said and nothing ever did. This is
        # the moment the debt is incurred (a gate opening on unmeasured
        # work), so this is where it gets written down. If the register
        # cannot be written the exception propagates: main() turns it into
        # the fail-closed answer, because a gate opening on a deferral
        # nobody recorded is the defect, not a tidy edge case.
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

    The point of the change this supports: `appian-build` used to carry
    `disable-model-invocation: true`, so every task in a twenty-task plan
    needed a human keystroke to start. That put the human gate on *starting
    work* -- high friction, almost no value -- rather than on what is
    irreversible or on a judgement that failed.

    Authorization moves from per-invocation to **per run, granted once and
    bounded**, and it is checked here rather than trusted, so removing that
    frontmatter flag does not turn into "the model may now write whenever
    it likes".

    Opt-in per project, exactly like `leaseFile`: with no `activeRunFile`
    configured this returns nothing and the harness behaves as it always
    did. What it never covers, in any mode, is the irreversible -- see
    `_destructive_errors`, which prompts regardless of any authorization.
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

    # The budget is not decoration on the grant: it is the difference
    # between "the user authorized this run" and "the user authorized
    # everything from here on". So a missing or unreadable one is an error
    # rather than a check that quietly does not run -- three separate
    # spellings used to walk past it, and every one of them widened the
    # grant while leaving the file looking bounded:
    #
    #   no `maxTasks`         -- nothing to spend, so nothing ever spent
    #   `"tasksCompleted": null` -- .get(k, 0) returns None, not 0, so the
    #                            isinstance guard skipped the comparison
    #   `"maxTasks": "5"`     -- same skip, from the other side
    #
    # Silent in all three, because the run keeps working. This is the same
    # rule the risk tier follows: a malformed field buys more ceremony,
    # never less.
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

    §22 of any honest review of this plugin asks for
    `detection -> impact assessment -> guard -> execution -> verification`,
    and until now `delete` shared a code path with `update`. They are not
    the same risk: an update is versioned and recoverable, a deletion is
    not, and its blast radius is not bounded by `allowedObjects` -- it can
    break objects no task ever listed.

    Two things are enforced, and they are different in kind:

    - **The assessment must exist.** The official Appian skill's own
      deletion workflow makes `getObjectDependents` mandatory before any
      delete; this checks that its result was actually recorded for THIS
      object, in this task. Not recorded is not the same as no dependents.
    - **The prompt is unconditional.** Even with the assessment on file and
      zero dependents found, this returns a reason, because the decision to
      destroy something in a shared environment is the one this harness
      should never make quietly on somebody's behalf. The doctrine already
      said "ask first, always"; this is the line of code that means it.

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

    This is the half of concurrency a git worktree cannot cover. A worktree
    gives each builder its own files -- its own active task file, its own
    evidence tree, its own SAIL sources -- and two builders in two
    worktrees calling `createRecordType` still write to the same Appian.
    The worktree isolates the recoverable half and none of the other one.

    So objects get leased. The rule is deliberately one-sided: a lease held
    by a DIFFERENT task blocks, and no lease at all does not. Requiring a
    lease would break every single-builder project, which is the default
    and the common case; refusing one that belongs to somebody else is what
    parallel work actually needs. Protection holds as long as one of two
    colliding builders claimed the object, and `appian-build` claims.

    The file has to be shared across worktrees to mean anything, which is
    the one thing a project has to get right when it turns this on -- a
    lease register inside a worktree is a register each builder has their
    own private copy of, which is worse than none because it looks like
    coordination.
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

    Be clear about what this is worth, in the same terms the rest of this
    plugin uses about itself: it does not prove the skill was loaded. The
    agent writes this file, so the agent can write it without having loaded
    anything. What it removes is the silent case -- writing to a shared
    environment having never opened the domain knowledge, with nothing
    anywhere recording that. And where the project points at the installed
    skill, the version claim is checked against the file rather than taken
    on trust, which is one more cheap route closed.
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
    and it is checked at session start rather than one failure at a time,
    because each link fails in a way that looks like something else:

    - No design MCP and every hook here fires on nothing. The plugin
      installs, its tests pass, and it gates absolutely nothing, which is
      the same silent absence it exists to prevent.
    - No official skill and objects get written with invented names and
      UUIDs, one-sided relationships and the wrong creation order -- none
      of which any gate here measures.
    - No documentation MCP and the official skill's function-availability
      checks come back empty, which reads as "the function does not exist"
      rather than as "nothing was checked".

    `mcpServers` is None when discovery did not run or could not read the
    configuration. That is deliberately different from an empty list: not
    knowing is not the same as knowing there are none, and reporting a
    missing server on the strength of an unreadable file would train the
    reader to ignore this message.
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
    is fixed when the process starts, so a plugin can be installed, enabled
    and validated, with every check on disk green, and still not exist in
    the running session; and after an update the session keeps running the
    old copy until it restarts. From inside there was no way to tell, which
    turns "that was fixed two releases ago" into a lost afternoon.

    `CLAUDE_PLUGIN_ROOT` is the cache directory of the version in use --
    the cache keeps one directory per version -- so this is the one place
    that can answer. Returns None rather than raising: the version is a
    courtesy, the requirements report is not, and a session must never lose
    the second to get the first.
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
    the order the two happen in: the domain knowledge is what a good design
    decision is made with, so a design audited without it was audited
    against the wrong thing.
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

    An unrecognised value is treated as `standard` rather than rejected:
    the failure mode of a typo should be more ceremony than intended, never
    less. A gate that fails open on a misspelling is not a gate.

    Separated from the logging deliberately. The first version wrote the
    downgrade register from inside this function, which made a *query*
    produce a file — and with an empty config that file landed on a
    relative `evidence/` path in whatever the current directory happened to
    be. A unit test asking "which phases does trivial require?" created a
    directory in the plugin's own checkout, which is the exact
    plugin/project contamination this repository has a CI step to prevent.
    Deciding and recording are now two calls, and only the gate makes the
    second.
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

    scope_gate only covers the write itself; review and QA happen after
    writing, so they can only be enforced here. Names exactly which
    verdicts are missing, invalid, or failing so the agent doesn't have to
    guess.

    A task stays in flight from the moment appian-build takes it until
    appian-review closes it, so the builder's own Stop lands here with the
    three verdicts legitimately absent -- the task really is unverified at
    that moment. That block is not a failure report, and its wording says
    so: it names the next phase to run rather than only what is missing.
    (Before 2026-08-09 appian-build deleted the active task file at STOP,
    which left nothing in flight and made this gate approve every nominal
    session without checking a thing.)

    A Stop hook can only approve or block -- there's no third answer -- so
    an unconditional block on missing verdicts is a deadlock with no in-band
    escape whenever they genuinely cannot be produced yet (auditor
    unavailable, a human-dependent step). The first thing anyone does with a
    deadlocked guardrail is disable it, and a disabled guardrail protects
    nothing. Claude Code marks a repeat Stop attempt with
    payload["stop_hook_active"]; on that repeat, this approves instead of
    blocking forever -- but never as a silent pass. It converts the omission
    into named, recorded debt: NOT_MEASURED / BLOCKING, written to the
    project's evidence so a human finds it. That is the plugin's own
    doctrine applied to itself.
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

    That advice is only true of a write, and this hook used to give it to
    every failed call. Both halves of the matcher were wrong here and
    neither had been corrected the way the other paths were: the JSON routed
    a bare `mcp__.*`, so a failed call to any MCP server in the session --
    Figma, Supabase, Drive -- came back described as an Appian write, the
    same over-reach `WRITE_TOOL_RE` was narrowed to fix; and nothing on this
    side asked whether the name was a write at all, the same omission that
    put reads in the write log.

    What it cost: a failed READ was announced as a failed write, and the
    remedy handed to the agent was actively wrong for one. There is nothing
    to have persisted, nothing partial to record, and "do not retry" is the
    opposite of the fix -- a read that fails on a stale table name or a
    misspelled field wants exactly one thing, which is to be issued again
    with the name corrected. So the line gets drawn where the plugin already
    draws it, and a failed read gets no notice: its own error says more than
    this hook can.
    """
    if not _is_write_tool(payload.get("tool_name")):
        return {}
    message = (
        "The write via %s failed. Do not retry this write; check with a read "
        "whether it persisted, record what did and did not, and resume from "
        "the first unverified result." % payload.get("tool_name")
    )
    return {"additionalContext": message}


def _write_result(payload):
    # PostToolUse delivers what the tool returned as `tool_response`, not
    # `tool_result` -- confirmed 2026-08-09 against the hooks reference
    # (code.claude.com/docs/en/hooks, "PostToolUse input": "The input
    # includes both tool_input, the arguments sent to the tool, and
    # tool_response, the result it returned", with a payload example
    # carrying "tool_response"). `tool_result` is read as a fallback so this
    # stays correct under either name: reading only the absent one would log
    # every write as "ok", and a write log that lies is worse than none,
    # because it gets trusted.
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

    It logs *writes*, and it used to log whatever the JSON matcher handed it.
    That matcher routes a bare `invoke|start|execute|run|test` on purpose:
    it is the net that keeps a real write from escaping the scope gate, and
    `test_the_write_log_receives_them_too` holds that direction. Narrowing it
    there would trade a false entry for a missed write, which is the wrong
    trade. So the line gets drawn here, where the plugin already draws it --
    `WRITE_TOOL_RE` has always said an expression rule has no side effects.

    What it cost while missing: three `appian_invoke_expression_rule` calls
    made during an unrelated investigation were recorded as writes of the
    task that happened to be in flight, which expired all three of its
    verdicts and left its closure gate unsatisfiable -- the task could not
    close without re-running audits against an artifact nobody had touched.
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

    The inputs are the evidence tree (every verdict both gates read), the
    harness config (whose mere presence is the activation switch), the
    active task file (the contract the scope gate measures against), the
    run authorization (whether anyone granted these writes at all) and the
    lease register (whether another task holds the object). They are all
    plain files in the project, and the agent the gates constrain can write
    every one of them.

    This list has to grow whenever the gates learn to read something new,
    and it did not: the run authorization and the lease register arrived as
    gate inputs while this function still knew about three files. An agent
    could add `{"authorizedAll": true}` to the run file, or drop another
    task's lease, and the edit left no line -- unlike the same edit to the
    config, which is no more sensitive.
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

    **Logged, not gated, and the choice is deliberate.** Gating was the
    other option and it is the wrong trade here for one reason: the auditor
    *legitimately* writes verdicts into this directory, appian-build
    legitimately writes the active task file, and a hook cannot tell which
    agent is holding the pen -- PostToolUse carries the tool and its
    arguments, not the identity of the subagent that called it. So gating
    would question the harness's own correct operation on every task, which
    is the friction that gets a harness switched off, and once it is off it
    protects nothing. Logging costs nothing, questions nothing, and turns
    "did somebody write their own passing verdict?" from unanswerable into
    a line in a file.

    Be clear about what this is worth: it does not prevent forgery. An agent
    with write access can still author a verdict, and after the task/phase
    check that verdict must at least be internally coherent -- but it can be
    written. What changes is that doing so is no longer invisible.
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

    A half-written line -- an interrupted session, a disk that filled -- must
    not make a register unreadable.

    Which way this fails matters, because `_record_deferred_debt` decides
    whether to append from what comes back. An unreadable register returns
    `[]`, no prior entry is found, and the entry is appended: repeats start
    accumulating again. That is the direction to fail in -- the cost is noise
    in a register a human reads, not a silently missing debt record. Failing
    the other way would suppress a real entry on the strength of a read
    error, which is the kind of silence this plugin exists to refuse.
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

    Deduplicated on (task, phase, criterion) because the scope gate runs on
    every single write: without it, one deferral becomes one register line
    per write attempt, and a register nobody can read is a register nobody
    reads. Re-reading the file each time is affordable -- it holds one line
    per deferred criterion, not one per operation.

    These entries share the file with the closure gate's forced-approval
    entries and are told apart by `notMeasuredClass`: DEFERRED here, a
    sanctioned and owned debt; BLOCKING there, a process failure.
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

    Two corrections, both about saying only what is true:

    The entry used to read "closed via a repeated Stop". It never was a
    close. `activeTask` is re-read from the task file on every invocation,
    so a task that had really closed would have approved at the top of
    `closure_gate` and never reached here -- arriving here *means* the task
    is still in flight. `closure_gate`'s own docstring already separates the
    two cases ("that block is not a failure report"); this now matches it.

    And it appended unconditionally, so a task that sits in flight across
    sessions -- waiting on a human decision, which is the normal reason -- got
    one identical line per session. Measured on a real project: eleven
    entries, ten of them the same sentence, burying the only one that carried
    an owner and a closing condition. Repeats of the same omission are
    therefore skipped. Not deduplicated in place: this register is
    append-only, and rewriting history to keep it tidy is the failure mode it
    exists to prevent. A *different* set of missing phases is new information
    and is still appended.
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


def _discover_mcp_servers(project_root):
    """Every MCP server name this session could see, or None if unknowable.

    Claude Code resolves MCP servers from several places, and a hook cannot
    ask it which ones ended up live -- so this reads the same configuration
    files and reports what is *declared*. Declared and answering are
    different states, which is why the session-start message asks for
    `validateExpression` rather than treating this as proof.

    None means no configuration file could be read at all. Reporting "the
    design MCP is missing" on that basis would be a false alarm, and a
    check that cries wolf is one people learn to scroll past.
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
        # Optional, and only the strong half of the official-skill check
        # depends on it: pointed at the installed skill, the record's
        # version claim is compared against the file instead of trusted.
        # Relative paths resolve against the project, absolute ones (the
        # common case -- the skill usually lives at user scope, outside any
        # project) are taken as given.
        "officialAppianSkillPath": _resolve_optional_path(
            project_root, project_config.get("officialAppianSkillPath")),
        # The session-start requirements check. Names are defaults, not
        # assumptions: a project is free to call its servers anything.
        # Off unless a project turns it on, because sequential is the
        # default and the common case. When on, this path has to be SHARED
        # across worktrees -- a register each builder has a private copy of
        # is worse than none, since it looks like coordination.
        "leaseFile": _resolve_optional_path(project_root, project_config.get("leaseFile")),
        # Opt-in too. Configured, writes must fall inside a run the user
        # granted; absent, the harness behaves exactly as it did when
        # every build was started by hand.
        "activeRunFile": _resolve_optional_path(project_root,
                                                project_config.get("activeRunFile")),
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
