"""The hooks that enforce the Appian harness's requirements, write and
closure gates. An agent must not be able to mark its own work as passing.

Two rulebooks coexist (norm § 15): a scope file without `schemaVersion`
opened under 0.6 and closes under 0.6; `schemaVersion: 2` selects the 0.7
unit of scope -- seven signed states, one status writer, a batch grant, a
declared perimeter and a write journal with reservations.

- session_start (SessionStart) -- the three links, the declared perimeter
  (§ 7.2), the session row, and the suspended-scope count. Informs, never
  blocks.
- scope_gate (PreToolUse on MCP write tools) -- §§ 4-6: signed state,
  contract, minimum kind, grant coverage, irreversible classes; on allow it
  reserves the writeSeq and leaves the pending row (§ 7.1).
- state_gate (PostToolUse on file writes) -- the single writer of `status`:
  validates, transitions from `request`, signs into the hook-owned
  projection, reverts hand-written states, records journal tampering.
- log_write (PostToolUse) -- resolves the reservation by tool_use_id
  against the real response shapes (P3), writes behavioural + hash, links
  created names to their UUIDs.
- closure_gate (Stop) -- the closure: terminal transitions 3/5/13 under
  v07, the legacy verdict discipline under 0.6.
- failure_notice (PostToolUseFailure) -- do not retry a failed write
  blindly; under v07 it also resolves the reservation as failed.

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
import hashlib
import json
import os
import re
import sys
import time

# validate_verdict.py lives in ../scripts/; inserted unconditionally so this
# module works both imported by the tests and run as the hook entry point.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from validate_verdict import isfile_exact, load_verdict, validate_verdict

# Rule 2's value, and load-bearing: "ask" is the only decision proven to
# produce a prompt; an unrecognized value is ignored silently and the session
# degrades toward allow. Evidence: docs/design/implementacion-0.7.md § P1
# (Claude Code 2.1.248). test_destructive_guard.py guards the literal.
PERMISSION_ASK = "ask"

# The runtime verbs are spelled out rather than matched as a bare
# `invoke|run|test`: `invoke_expression_rule`, `testRule` and
# `runAllInterfaceTestCases` have no side effects and stay ungated.
# Why each verb is in or out: docs/design-notes.md § harness_hooks.py · verbs.
_WRITE_VERBS = (
    r"(create|update|add|insert|configure|reorder|upload|replace|delete|remove"
    r"|invoke_process_model|invoke_agent|start_process|execute"
    r"|testProcessModel)"
)
# The irreversible half of an asymmetric pair, and a strict SUBSET of the
# write verbs: `scope_gate` returns early for anything `_is_write_tool`
# rejects, so a name only this half matched would skip the confirmation on
# the one class of call that cannot be undone.
_DESTRUCTIVE_VERBS = (
    r"(delete|remove"
    # A row has no version history, so overwriting one is as irreversible as
    # deleting it -- the "updates are recoverable" premise covers design
    # objects only.
    r"|updateRecordData)"
)

# The perimeter has two forms and the declared one wins (norm § 7.2). A
# project that declares `appianMcpToolPrefixes[]` is matched by prefix,
# whatever its servers are called; these regexes are the FALLBACK for
# configurations that do not declare, kept byte-compatible with 0.6 so a
# migrated project loses nothing while it is being nudged to declare.
# hooks.json cannot read configuration, so it routes every MCP tool with a
# write verb and the Python side filters; `test_matcher_parity` holds the
# invariant that it routes at least everything gated here.
# The `appian` runtime server prefixes every tool with `appian_`.
_FALLBACK_SERVER = r"^mcp__[a-zA-Z0-9_-]*[Aa]ppian[a-zA-Z0-9_-]*__(?:appian_)?"
WRITE_TOOL_RE = re.compile(_FALLBACK_SERVER + _WRITE_VERBS)
DESTRUCTIVE_TOOL_RE = re.compile(_FALLBACK_SERVER + _DESTRUCTIVE_VERBS)
_WRITE_VERBS_RE = re.compile(r"(?:appian_)?" + _WRITE_VERBS)
_DESTRUCTIVE_VERBS_RE = re.compile(r"(?:appian_)?" + _DESTRUCTIVE_VERBS)

# § 7.2 fixes this sentence literally: it is the loud version of the
# plugin's gravest silent failure (hooks that run, answer, and see nothing).
PERIMETER_BLIND_PHRASE = (
    "Los hooks se están ejecutando pero no ven tus herramientas de Appian: "
    "el plugin está instalado y no gobierna nada.")

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

# The seven states of § 4.2. closed-pending-human is kept apart from
# closed-with-debt on purpose: one is a judgement still owed by a person,
# the other a task that ran out of remediation cycles.
STATUS_IN_FLIGHT = "in-flight"
STATUS_CLOSING = "closing"
STATUS_CLOSED = "closed"
STATUS_CLOSED_PENDING_HUMAN = "closed-pending-human"
STATUS_CLOSED_WITH_DEBT = "closed-with-debt"
STATUS_SUSPENDED = "suspended"
STATUS_ABANDONED = "abandoned"
SCOPE_STATUSES = (STATUS_IN_FLIGHT, STATUS_CLOSING, STATUS_CLOSED,
                  STATUS_CLOSED_PENDING_HUMAN, STATUS_CLOSED_WITH_DEBT,
                  STATUS_SUSPENDED, STATUS_ABANDONED)

# The 0.7 unit of scope (§ 4.1). Its absence selects the whole 0.6 rulebook,
# because an in-flight 0.6 scope closes under the rules it opened with (§ 15).
SCOPE_SCHEMA_VERSION = 2

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


def _declared_prefixes(config):
    """The declared perimeter (§ 7.2), or None when this configuration does
    not declare one.

    Empty and junk collapse to None on purpose: an empty perimeter is a
    missing one, and a malformed entry must neither widen nor narrow the
    gate silently -- the fallback regex takes over, and session-start says
    so out loud.
    """
    raw = (config or {}).get("appianMcpToolPrefixes")
    if not isinstance(raw, list):
        return None
    prefixes = [p for p in raw if isinstance(p, str) and p.strip()]
    return prefixes or None


def _perimeter_match(tool_name, config, verbs_re, fallback_re):
    name = tool_name or ""
    prefixes = _declared_prefixes(config)
    if prefixes is None:
        return bool(fallback_re.match(name))
    # Declared wins entirely: a server left out of the declaration is
    # outside the perimeter even if its name would match the fallback.
    return any(name.startswith(p) and verbs_re.match(name[len(p):])
               for p in prefixes)


def _is_write_tool(tool_name, config=None):
    return _perimeter_match(tool_name, config, _WRITE_VERBS_RE, WRITE_TOOL_RE)


def _tool_action(tool_name, config=None):
    """The tool's own name, server prefix stripped (and the runtime server's
    `appian_` prefix with it). A name outside the perimeter comes back whole,
    which classifies as unknown -- the expensive side."""
    name = tool_name or ""
    prefixes = _declared_prefixes(config)
    if prefixes is None:
        matched = re.match(_FALLBACK_SERVER, name)
        return name[matched.end():] if matched else name
    for prefix in prefixes:
        if name.startswith(prefix):
            rest = name[len(prefix):]
            return rest[7:] if rest.startswith("appian_") else rest
    return name


# The whole of the cheap lane (§ 5.2): a write tool not on this list forces
# `task`, so a new tool is expensive until somebody classifies it. Deletions
# are deliberately absent -- every deletion forces `task` -- and constants,
# views and user filters carry per-payload conditions checked below.
# Checked against the 145 real schemas (Phase 0 P6).
_MICRO_ELIGIBLE_ACTIONS = frozenset((
    "createConstant", "updateConstant",
    "createFolder", "updateFolder",
    "uploadDocument", "updateDocument", "replaceDocumentContent",
    "createInterface", "updateInterface",
    "createExpressionRule", "updateExpressionRule",
    "createInterfaceTestCase", "createInterfaceTestCases",
    "updateInterfaceTestCase",
    "createExpressionRuleTestCase", "createExpressionRuleTestCases",
    "updateExpressionRuleTestCase",
    "updateRecordTypeView", "updateRecordTypeUserFilter",
))

# One concept, two spellings, and it is per tool (Phase 0 P6): Appian calls
# this field the view/filter's *Security Expression* in its own breadcrumbs.
# Key PRESENCE is what matters -- an explicit null clears the expression,
# which changes who sees what exactly as much as setting one.
_VISIBILITY_FIELD_BY_ACTION = {
    "addRecordTypeView": "visibilityExpression",
    "updateRecordTypeView": "visibilityExpression",
    "addRecordTypeUserFilter": "visibilityExpression",
    "updateRecordTypeUserFilter": "visibilityExpression",
    "addRecordTypeAction": "visibilityExpr",
    "updateRecordTypeAction": "visibilityExpr",
}

# Constant types that feed security expressions (§ 5.2). USER_OR_GROUP and
# GROUP_TYPE are P6's additions from the real vocabulary; the schema carries
# no enum, so the strings come from the tool's own description.
_SECURITY_CONSTANT_TYPES = frozenset(("GROUP", "USER", "USER_OR_GROUP",
                                      "GROUP_TYPE"))

# Starts real work in a shared environment; § 5.3 classes them irreversible.
_PROCESS_START_ACTIONS = frozenset(("invoke_process_model", "invoke_agent",
                                    "start_process", "execute",
                                    "testProcessModel"))

_DATA_WRITE_ACTIONS = frozenset(("insertRecordData", "updateRecordData",
                                 "deleteRecordData"))


def _constant_security_type(action, tool_input, constant_type):
    if action not in ("createConstant", "updateConstant"):
        return None
    declared = tool_input.get("type") if isinstance(tool_input, dict) else None
    return declared if isinstance(declared, str) and declared.strip() \
        else constant_type


def observed_risk(tool_name, tool_input, config=None, constant_type=None):
    """None or "high" (§ 5.3): a class of damage the hook observes in the
    payload, never a label the agent declares.

    `constant_type` is the preflight's answer for an update that does not
    carry the type; the classifier itself stays pure.
    """
    if not _is_write_tool(tool_name, config):
        return None
    action = _tool_action(tool_name, config)
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    if action in ("updateObjectSecurity", "reorderRecordTypeViews"):
        return "high"
    field = _VISIBILITY_FIELD_BY_ACTION.get(action)
    if field and field in tool_input:
        return "high"
    ctype = _constant_security_type(action, tool_input, constant_type)
    if isinstance(ctype, str) and ctype.strip().upper() in _SECURITY_CONSTANT_TYPES:
        return "high"
    if action in _DATA_WRITE_ACTIONS:
        return "high"
    if action.startswith(("delete", "remove")):
        return "high"
    if action in _PROCESS_START_ACTIONS:
        return "high"
    return None


def task_min_kind(tool_name, tool_input, config=None, constant_type=None):
    """The minimum `kind` this call forces (§ 5.2): "micro" or "task".

    Tool AND payload, because much of what decides lives in the payload. No
    magnitude rule exists on purpose: `updateInterface` and
    `updateExpressionRule` always send the whole expression, so any count of
    "lines replaced" could only mean "lines sent" and would always fire.
    """
    if observed_risk(tool_name, tool_input, config, constant_type) == "high":
        return "task"
    action = _tool_action(tool_name, config)
    if action not in _MICRO_ELIGIBLE_ACTIONS:
        return "task"
    if action in ("createConstant", "updateConstant"):
        # § 5.2: the type may not travel in the call; the grant supplies it
        # from the preflight, and its absence buys task.
        ctype = _constant_security_type(action, tool_input, constant_type)
        if not (isinstance(ctype, str) and ctype.strip()):
            return "task"
    return "micro"


# § 6.1's extractor, written against the real schemas (P6 dump): which
# property names the MUTATED object of each call. Everything else in the
# payload is context -- `appUuid`, parent folders, the references inside
# field/view/relationship bodies -- and granting context was never asked,
# so reading it as a target fabricates a false ask on every create.
# Test-case tools target their PARENT object: the test case of the object
# being touched is the floor's instrument, not a second front (§ 5.7).
_TARGET_KEYS_BY_ACTION = {
    "createApplication": ("name",),
    "updateApplication": ("appUuid", "name"),
    "deleteApplication": ("appUuid",),
    "addObjectsToApplication": ("appUuid",),
    "createGroup": ("name",),
    "updateGroup": ("groupName", "name"),
    "deleteGroup": ("groupName",),
    "addGroupMembers": ("groupName",),
    "removeGroupMember": ("groupName",),
    "createProcessModelNode": ("processModelUuid",),
    "updateProcessModelNode": ("processModelUuid",),
    "deleteProcessModelNode": ("processModelUuid",),
    "createExpressionRuleTestCase": ("uuid",),
    "createExpressionRuleTestCases": ("uuid",),
    "createInterfaceTestCase": ("uuid",),
    "createInterfaceTestCases": ("uuid",),
}


def _target_keys(action):
    override = _TARGET_KEYS_BY_ACTION.get(action)
    if override:
        return override
    if action.startswith(("create", "upload")):
        return ("name",)
    # Alternative spellings of the same target, as in 0.6: a scope may
    # legitimately carry names, UUIDs or both.
    return ("uuid", "name")


def _target_candidates(tool_name, tool_input, config=None):
    """Identifiers naming the mutated object of this call -- and only it."""
    if not isinstance(tool_input, dict):
        return []
    found = []
    for key in _target_keys(_tool_action(tool_name, config)):
        value = tool_input.get(key)
        if isinstance(value, str) and value and value not in found:
            found.append(value)
    return found


# What surface each create actually opens, for comparing against the type
# the person approved in grant.creates[] (§ 6.1).
_CREATE_TYPE_BY_ACTION = {
    "createApplication": "application",
    "createConnectedSystem": "connectedSystem",
    "createConstant": "constant",
    "createExpressionRule": "expressionRule",
    "createFolder": "folder",
    "createGroup": "group",
    "createIntegration": "integration",
    "createInterface": "interface",
    "createProcessModel": "processModel",
    "createRecordType": "recordType",
    "createSite": "site",
    "createWebApi": "webApi",
    "uploadDocument": "document",
}


def _grant_reasons(config, scope, tool_name, tool_input, candidates):
    """Whether the person's one prompt covered THIS write (§ 6.1)."""
    grant = scope.get("grant")
    if not isinstance(grant, dict):
        return ["appian-harness ha parado %s: el alcance %r no tiene grant todavía — "
                "el «ok» único de la persona con la lista completa y el impacto a la "
                "vista. Arreglo: termina el preflight, escribe el grant en el fichero "
                "de alcance y pide el ok una sola vez. Si no, ninguna escritura sale"
                % (tool_name, scope.get("id"))]
    reasons = []
    if grant.get("instanceId") != scope.get("instanceId"):
        reasons.append("el grant pertenece a otra instancia del alcance: toda edición "
                       "posterior lo invalida entero (§ 6.1). Arreglo: vuelve a pedir "
                       "el ok para esta instancia")
        return reasons
    if grant.get("permissionMode") == "bypassPermissions":
        reasons.append("el grant se concedió con el sistema de permisos apagado "
                       "(bypassPermissions) y no cuenta como aprobado por una persona "
                       "(§ 6.1). Arreglo: repite la concesión con los permisos activos")
        return reasons

    action = _tool_action(tool_name, config)
    if action in _CREATE_TYPE_BY_ACTION:
        name = tool_input.get("name") if isinstance(tool_input, dict) else None
        creates = [e for e in grant.get("creates") or [] if isinstance(e, dict)]
        entry = next((e for e in creates if e.get("name") == name), None)
        if entry is None:
            reasons.append("appian-harness ha parado %s sobre %r: esa creación no está "
                           "en el grant (creates: %r). Arreglo A — es parte de este "
                           "trabajo: añádela al alcance y vuelve a pedir el ok. "
                           "Arreglo B — es otro trabajo: cierra este alcance y abre "
                           "uno nuevo. Si no, la creación no sale"
                           % (tool_name, name,
                              [e.get("name") for e in creates]))
        else:
            approved = entry.get("type")
            actual = _CREATE_TYPE_BY_ACTION[action]
            if approved and _norm_ident(approved) != _norm_ident(actual):
                reasons.append("la persona aprobó %r como %r y esta llamada lo crea "
                               "como %r: se aprueba una superficie, no una cadena "
                               "(§ 6.1). Arreglo: crea el tipo aprobado o vuelve a "
                               "pedir el ok con el tipo real"
                               % (name, approved, actual))
    elif action not in _PROCESS_START_ACTIONS:
        # Starts are their own granted class (processStarts) and are checked
        # with the irreversibles; measuring them against `objects` would
        # fabricate a false ask on every start.
        granted = _granted_objects(grant)
        if candidates and not any(c in granted for c in candidates):
            reasons.append("appian-harness ha parado %s: ningún identificador de la "
                           "llamada %r está entre los objetos concedidos %r. Arreglo "
                           "A — es otro trabajo: cierra o abandona este alcance. "
                           "Arreglo B — falta en el análisis: amplía el alcance y "
                           "vuelve a pedir el ok. Si no, esta escritura no sale"
                           % (tool_name, candidates, granted))
    return reasons


def _granted_objects(grant):
    """The objects the person's prompt covered: the granted list, the names
    approved for creation -- create then refine by UUID is the real flow
    (§ 4.1) -- plus the one remediation extension the hook may have written
    (§ 6.3)."""
    granted = [o for o in grant.get("objects") or [] if isinstance(o, str)]
    for entry in grant.get("creates") or []:
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            granted.append(entry["name"])
    for extension in grant.get("extensions") or []:
        if isinstance(extension, dict):
            granted.extend(o for o in extension.get("objects") or []
                           if isinstance(o, str))
    return granted


def _uuid_links(config, instance_id):
    """uuid -> granted name, admissible only when corroborated by the two
    registers the hook writes separately (§ 4.1): the link row in
    gate-decisions.jsonl AND an `ok` operations row carrying that uuid."""
    ok_uuids = set()
    for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                        "operations.jsonl")):
        if row.get("instanceId") == instance_id and row.get("result") == "ok":
            ok_uuids.update(u for u in row.get("uuids") or []
                            if isinstance(u, str))
    links = {}
    for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                        "gate-decisions.jsonl")):
        if (row.get("event") == "uuid-link"
                and row.get("instanceId") == instance_id
                and row.get("uuid") in ok_uuids
                and isinstance(row.get("name"), str)):
            links[row["uuid"]] = row["name"]
    return links


def _with_linked_names(config, instance_id, candidates):
    links = _uuid_links(config, instance_id)
    extended = list(candidates)
    extended.extend(links[c] for c in candidates
                    if c in links and links[c] not in extended)
    return extended


def _dependents_record(config, task_id):
    data, err = _load_json_file(os.path.join(_evidence_dir(config), task_id,
                                             DEPENDENTS_RECORD_NAME))
    return data if isinstance(data, dict) and not err else {}


def _irreversible_reasons(config, scope, tool_name, tool_input, candidates):
    """§ 6.1's irreversible classes, against the grant the person saw.

    The direction matters: a deletion approved WITH its dependents in view
    does not re-prompt per call -- that is the batch authorization -- and
    what keeps that honest is anti-TOCTOU: the dependents re-consulted just
    before executing must match the approved snapshot, or the question
    comes back.
    """
    action = _tool_action(tool_name, config)
    grant = scope.get("grant") if isinstance(scope.get("grant"), dict) else {}

    if action in _PROCESS_START_ACTIONS:
        starts = [s for s in grant.get("processStarts") or [] if isinstance(s, str)]
        if not candidates or not any(c in starts for c in candidates):
            return ["appian-harness ha parado %s: arrancar un proceso es irreversible "
                    "y este arranque no está en grant.processStarts (%r). Arreglo: "
                    "añádelo al grant y vuelve a pedir el ok. Si no, el arranque no "
                    "sale" % (tool_name, starts)]
        return []

    deletions = grant.get("deletions") if isinstance(grant.get("deletions"), dict) \
        else {}

    if action == "deleteRecordData":
        entry = next((deletions[c] for c in candidates if c in deletions), None)
        rows = entry.get("rows") if isinstance(entry, dict) else None
        if not _is_count(rows):
            return ["appian-harness ha parado %s: el impacto de un borrado de datos "
                    "son filas, no diseño, y aquí está NO MEDIDO — sin conteo, el "
                    "borrado de datos no pasa el grant (§ 6.1). Arreglo: consulta el "
                    "conteo afectado por el MCP de runtime, registra "
                    "grant.deletions[objeto] = {\"rows\": N} y vuelve a pedir el ok"
                    % tool_name]
        return []

    if not action.startswith(("delete", "remove")):
        return []

    snapshot = next((deletions[c] for c in candidates if c in deletions), None)
    if snapshot is None:
        return ["appian-harness ha parado %s: un borrado es irreversible y este "
                "objetivo no está en grant.deletions (con sus dependientes a la "
                "vista). Arreglo: consulta los dependientes, añade el borrado al "
                "grant y vuelve a pedir el ok. Si no, el borrado no sale"
                % tool_name]
    fresh_all = _dependents_record(config, scope["id"])
    normalized = {_norm_ident(k): v for k, v in fresh_all.items()}
    fresh = next((normalized[_norm_ident(c)] for c in candidates
                  if _norm_ident(c) in normalized), None)
    if fresh is None:
        return ["appian-harness ha parado %s: falta la reconsulta de dependientes "
                "justo antes de ejecutar (anti-TOCTOU, § 6.1). Arreglo: vuelve a "
                "llamar a getObjectDependents y registra el resultado en "
                "dependents.json — «no comprobado» no es «sin dependientes»"
                % tool_name]
    if sorted(map(str, fresh if isinstance(fresh, list) else [fresh])) != \
            sorted(map(str, snapshot if isinstance(snapshot, list) else [snapshot])):
        return ["appian-harness ha parado %s: los dependientes cambiaron desde el ok "
                "— aprobados %r, ahora %r. La aprobación ya no describe el mundo: se "
                "vuelve a preguntar (§ 6.1)" % (tool_name, snapshot, fresh)]
    return []


# Structure, security and process-model classes whose task must buy its
# `design` before the first write (§ 5.6); creations join through
# grant.creates. Deletions are exempt: the deletion profile's value already
# lives in the grant.
_DESIGN_DEMANDING_ACTIONS = re.compile(
    r"^(?:(?:create|update|add)RecordType"
    r"|configureRecordEvents|(?:add|update)CustomRecordField"
    r"|updateObjectSecurity"
    r"|(?:create|update)ProcessModel(?:Node)?"
    r"|(?:create|update)Group|addGroupMembers)")


def _design_requirement_reasons(config, scope, action):
    """§ 5.6: design is owed for what the scope DOES, not for its label.

    micro never pays design (its lane buys certify at most, § 5.4); a task
    pays it before the first write when it creates objects or touches
    structure, security or a process model. Merely-modifying tasks choose,
    and that registered choice arrives with the judge (Phase 4).
    """
    if scope.get("kind") != "task":
        return []
    grant = scope.get("grant") or {}
    creates = grant.get("creates") or []
    demanded = bool(creates) or bool(_DESIGN_DEMANDING_ACTIONS.match(action))
    if not demanded:
        return []
    return _phase_errors(config, scope["id"], "design")


def _scope_v07_reasons(config, payload, tool_name, scope):
    """The v07 gate body (§§ 4-6): contract, minimum kind, grant, atomicity
    per tasks{} entry, and the shared checks that survive from 0.6."""
    reasons = []
    tool_input = payload.get("tool_input", {})
    task_id = scope["id"]
    action = _tool_action(tool_name, config)
    candidates = _with_linked_names(config, scope.get("instanceId"),
                                    _target_candidates(tool_name, tool_input,
                                                       config))
    allowed = scope.get("allowedObjects") or []
    if action in _PROCESS_START_ACTIONS:
        # A start is not an object edit: its class lives in the grant
        # (processStarts), not in allowedObjects.
        pass
    elif not candidates:
        reasons.append("could not identify the target object from tool_input; "
                       "cannot check it against allowedObjects")
    elif not any(c in allowed for c in candidates):
        reasons.append("appian-harness ha parado %s: ningún identificador de la "
                       "llamada %r está en el alcance concedido %r. Arreglo A — es "
                       "otro trabajo: di «cierra el alcance» o «abandona el alcance, "
                       "motivo: …». Arreglo B — es el mismo trabajo: amplía el "
                       "alcance y te preguntaré UNA vez por la lista completa. Si "
                       "no, esta escritura no sale y el alcance sigue abierto"
                       % (tool_name, candidates, allowed))

    min_kind = task_min_kind(tool_name, tool_input, config)
    if min_kind == "task" and scope.get("kind") == "micro":
        reasons.append("appian-harness ha parado %s: esta escritura no cabe en micro "
                       "(§ 5.2 la clasifica task como mínimo). Arreglo: di «súbelo a "
                       "task» y te preguntaré UNA vez por la lista completa antes de "
                       "escribir nada. Si no, esta escritura no sale" % tool_name)

    reasons.extend(_grant_reasons(config, scope, tool_name, tool_input, candidates))
    if isinstance(scope.get("grant"), dict):
        reasons.extend(_irreversible_reasons(config, scope, tool_name, tool_input,
                                             candidates))

    max_allowed = _max_allowed_objects(config)
    tasks = scope.get("tasks")
    if isinstance(tasks, dict) and tasks:
        # § 15: evaluated per tasks{} entry, never on the union.
        for entry_id in sorted(tasks):
            objs = tasks[entry_id]
            if isinstance(objs, list) and len(objs) > max_allowed:
                reasons.append("task entry %r touches %d objects, more than "
                               "maxAllowedObjects=%d: not atomic"
                               % (entry_id, len(objs), max_allowed))
    elif len(allowed) > max_allowed:
        reasons.append("scope %r touches %d objects, more than maxAllowedObjects=%d: "
                       "not atomic" % (task_id, len(allowed), max_allowed))

    reasons.extend(_skill_record_errors(config, task_id))
    reasons.extend(_design_requirement_reasons(config, scope, action))
    return reasons


def _scope_policy(active_task):
    """Which rulebook this scope opened under (§ 15).

    No file and no `schemaVersion` are the 0.6 reading -- the legacy path
    stays selected whole, so an old scope closes under the rules it opened
    with. Exactly the integer 2 is the 0.7 unit of scope. Anything else is
    nobody's schema and fails closed: "roughly v2" is not a contract.
    """
    if not isinstance(active_task, dict):
        return "v06"
    version = active_task.get("schemaVersion")
    if version is None:
        return "v06"
    if isinstance(version, int) and not isinstance(version, bool) \
            and version == SCOPE_SCHEMA_VERSION:
        return "v07"
    return "unknown"


def _scope_schema_errors(scope):
    """What keeps this v2 file from being a contract (§ 4.1). Empty = valid.

    The schema is closed: a field it does not declare is rejected, which is
    what catches the typo that would otherwise read as "absent, use the
    default" -- the cheap way to lose an anchored field.
    """
    if not isinstance(scope, dict):
        return ["the scope file is not a JSON object"]
    errors = []
    known = {"schemaVersion", "id", "instanceId", "kind", "risk", "status",
             "statusWriteSeq", "request", "intent", "tasks", "allowedObjects",
             "grant", "suspendedScope", "resumeFrom", "manualEstimateMinutes",
             "openedAt", "closedAt"}
    for field in sorted(set(scope) - known):
        errors.append("%r is not a field of scope schema v2; the schema is closed, so a "
                      "misspelt field must fail rather than fall back" % field)

    def text(field):
        value = scope.get(field)
        return isinstance(value, str) and value.strip()

    if not text("id"):
        errors.append("id must be a non-empty string")
    if not text("instanceId"):
        errors.append("instanceId must be a non-empty string")
    kind = scope.get("kind")
    if kind not in ("micro", "task"):
        errors.append("kind must be 'micro' or 'task', found %r -- 'feature' is a 0.6 "
                      "reading, not a v2 value (§ 5.1)" % (kind,))
    if scope.get("risk") not in (None, "high"):
        errors.append("risk must be null or 'high', found %r (§ 5.3)"
                      % (scope.get("risk"),))
    if scope.get("status") not in SCOPE_STATUSES:
        errors.append("status %r is not one of the seven states of § 4.2"
                      % (scope.get("status"),))
    seq = scope.get("statusWriteSeq")
    if not (isinstance(seq, int) and not isinstance(seq, bool) and seq >= 0):
        errors.append("statusWriteSeq must be a non-negative integer, found %r" % (seq,))
    request = scope.get("request")
    if not (request is None
            or request in ("close", "suspend", "abandon", "resume")
            # § 4.4 rows 9-10 demand a reason and the closed schema has no
            # field for it, so it rides in the request itself.
            or (isinstance(request, str) and request.startswith("abandon:"))):
        errors.append("request must be null or one of close, suspend, resume, "
                      "'abandon: <motivo>'; found %r" % (request,))
    if kind == "micro" and not text("intent"):
        errors.append("intent is required in micro: one sentence (§ 4.1)")
    elif scope.get("intent") is not None and not isinstance(scope.get("intent"), str):
        errors.append("intent must be a string when present")
    allowed = scope.get("allowedObjects")
    if not (isinstance(allowed, list)
            and all(isinstance(o, str) and o.strip() for o in allowed)):
        errors.append("allowedObjects must be a list of object names or UUIDs")
    tasks = scope.get("tasks")
    if tasks is not None:
        if not (isinstance(tasks, dict)
                and all(isinstance(v, list) and all(isinstance(o, str) for o in v)
                        for v in tasks.values())):
            errors.append("tasks must be null or an object mapping task id to its object "
                          "list")
        elif kind == "micro":
            errors.append("tasks is absent in micro (§ 5.1): a partitioned scope is a task")
    if scope.get("grant") is not None and not isinstance(scope.get("grant"), dict):
        errors.append("grant must be null or an object (§ 6)")
    if scope.get("suspendedScope") is not None \
            and not isinstance(scope.get("suspendedScope"), dict):
        errors.append("suspendedScope must be null or the embedded scope (§ 4.5)")
    if scope.get("resumeFrom") is not None \
            and not isinstance(scope.get("resumeFrom"), str):
        errors.append("resumeFrom must be null or a scope id")
    estimate = scope.get("manualEstimateMinutes")
    if estimate is not None and (isinstance(estimate, bool)
                                 or not isinstance(estimate, (int, float))):
        errors.append("manualEstimateMinutes must be null or a number")
    return errors


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


def _is_destructive_tool(tool_name, config=None):
    return _perimeter_match(tool_name, config, _DESTRUCTIVE_VERBS_RE,
                            DESTRUCTIVE_TOOL_RE)


def _destructive_errors(config, task_id, tool_name, candidates):
    """The impact assessment a deletion needs before it is allowed to run.

    A deletion's blast radius is not bounded by `allowedObjects`, so two
    things are enforced and they differ in kind: the assessment must EXIST
    (the official skill makes `getObjectDependents` mandatory, and this
    checks its result was recorded for THIS object in this task), and the
    prompt is UNCONDITIONAL even when zero dependents were found.

    Returns reasons, never a refusal -- the gate still only ever asks.
    """
    if not _is_destructive_tool(tool_name, config):
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
    _record_session(config, payload)
    missing = requirements_errors(config)
    perimeter = _perimeter_note(config) + _suspended_session_note(config, payload)
    if not missing:
        return {"additionalContext": (
            "%s: all three requirements are present (design MCP, official " % _banner(config) +
            "Appian skill, documentation MCP). Configured is not the same as answering: "
            "before the first write of this session, confirm the design MCP really "
            "responds with `validateExpression(\"1 + 1\")` -- listing tools proves "
            "nothing, it never reaches Appian. Then follow the phases: "
            "appian-specify -> appian-plan -> appian-build -> appian-verify -> "
            "appian-review, consulting `appian-best-practices` for the domains each "
            "change touches, and loading the official Appian skill before every build."
            + perimeter)}
    return {"additionalContext": (
        "%s: WRITING TO APPIAN IS NOT SAFE IN THIS SESSION. %d of the three "
        "requirements %s missing:\n\n- %s\n\nReading, specifying and planning are fine. "
        "Do not issue create or update calls against Appian until this is resolved -- and "
        "say so plainly rather than working around it." % (
            _banner(config), len(missing), "is" if len(missing) == 1 else "are",
            "\n- ".join(missing)) + perimeter)}


def _record_session(config, payload):
    """One row per session in sessions.jsonl (§ 11.3): the id that counts
    suspended-scope expiry and the transcript path that measure_evidence
    reads (§ 17.6). Deduplicated -- SessionStart can fire on resume too."""
    session = payload.get("session_id")
    if not session or not config.get("evidenceDir"):
        return
    path = os.path.join(_evidence_dir(config), "sessions.jsonl")
    for row in _read_jsonl(path):
        if row.get("sessionId") == session:
            return
    _append_jsonl(path, {"timestamp": _now(), "sessionId": session,
                         "transcriptPath": payload.get("transcript_path")})


def _suspended_session_note(config, payload):
    """§ 4.5's expiry, counted in sessions and never in clocks: the first
    sight per session increments `suspendedScope.sessionsSeen` (file and
    projection together), and from the third the announcement offers to
    close or abandon -- the grant is dead, the scope is not."""
    scope = config.get("activeTask")
    if _scope_policy(scope) != "v07" or not config.get("evidenceDir"):
        return ""
    embedded = scope.get("suspendedScope")
    if not isinstance(embedded, dict) or not embedded.get("instanceId"):
        return ""
    projection = _load_projection(config)
    if not projection or projection.get("instanceId") != scope.get("instanceId"):
        return ""
    session = payload.get("session_id") or "unknown-session"
    seen = any(row.get("event") == "suspended-seen"
               and row.get("instanceId") == embedded.get("instanceId")
               and row.get("sessionId") == session
               for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                                   "gate-decisions.jsonl")))
    count = embedded.get("sessionsSeen") or 0
    if not seen:
        count += 1
        _append_jsonl(os.path.join(_evidence_dir(config), "gate-decisions.jsonl"),
                      {"timestamp": _now(), "event": "suspended-seen",
                       "instanceId": embedded.get("instanceId"),
                       "sessionId": session})
        updated = dict(projection.get("scope") or {},
                       suspendedScope=dict(embedded, sessionsSeen=count))
        _write_json_atomic(_projection_path(config),
                           {"instanceId": scope.get("instanceId"),
                            "scope": updated, "signedAt": _now()})
        _write_json_atomic(config["activeTaskFile"], updated)
    if count >= 3:
        return ("\n\nALCANCE SUSPENDIDO: %r lleva %d sesiones suspendido. Ciérralo "
                "o abandónalo; su grant está muerto y reanudarlo exigirá un grant "
                "nuevo (§ 4.5)." % (embedded.get("id"), count))
    return ("\n\nALCANCE SUSPENDIDO: %r (sesión %d de 3 antes de que caduque su "
            "grant). Se reanuda solo al cerrar %r."
            % (embedded.get("id"), count, scope.get("id")))


def _perimeter_note(config):
    """The § 7.2 session-start warning, or "" with a declared perimeter.

    The sentence is the norm's, verbatim and in its language: it is the loud
    form of the failure where every hook runs and none of them sees the
    project's Appian servers.
    """
    if _declared_prefixes(config) is not None:
        return ""
    return ("\n\nPERÍMETRO (§ 7.2): la configuración no declara appianMcpToolPrefixes[]. "
            + PERIMETER_BLIND_PHRASE +
            " Rellénala con /appian-init --adopt; mientras falte, los gates usan el "
            "respaldo por nombre de servidor y la primera escritura de cada sesión "
            "pedirá permiso.")


def _perimeter_first_write_reason(config, payload):
    """§ 15's migration ask: without the declared perimeter, the first write
    of each session is a question, not a notice.

    Once per session, recorded in gate-decisions.jsonl -- the record is what
    keeps one nudge from becoming a prompt per write. Deciding and recording
    live together here because the deduplication IS the behaviour.
    """
    if _declared_prefixes(config) is not None:
        return []
    session = payload.get("session_id") or "unknown-session"
    path = os.path.join(_evidence_dir(config), "gate-decisions.jsonl")
    for row in _read_jsonl(path):
        if row.get("event") == "perimeter-ask" and row.get("sessionId") == session:
            return []
    _append_jsonl(path, {"timestamp": _now(), "event": "perimeter-ask",
                         "sessionId": session, "tool": payload.get("tool_name")})
    return ["appian-harness ha parado %s: este proyecto no declara appianMcpToolPrefixes[] "
            "y el perímetro de los gates se está adivinando por el nombre del servidor en "
            "vez de leerse de la configuración. Arreglo: ejecuta /appian-init --adopt para "
            "declararlo, una vez por proyecto. Si continúas sin declararlo, esta pregunta "
            "no se repite en esta sesión y las escrituras quedan gateadas solo por el "
            "respaldo." % (payload.get("tool_name"),)]


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
    if not _is_write_tool(tool_name, config):
        return {"permissionDecision": "allow", "permissionDecisionReason": "not a write tool"}

    reasons = []
    reasons.extend(_perimeter_first_write_reason(config, payload))
    active_task = config.get("activeTask")
    policy = _scope_policy(active_task)
    if policy == "unknown":
        reasons.append("the scope file declares schemaVersion %r, which no rulebook of "
                       "this plugin defines -- neither the 0.6 reading (no schemaVersion) "
                       "nor v2. Reopen the scope through appian-build rather than editing "
                       "the version" % (active_task.get("schemaVersion"),))
    elif policy == "v07":
        schema_errors = _scope_schema_errors(active_task)
        if schema_errors:
            reasons.extend(schema_errors)
        else:
            reasons.extend(_state_integrity_reasons(config, active_task))
            if not reasons:
                reasons.extend(_scope_v07_reasons(config, payload, tool_name,
                                                  active_task))
    elif not active_task or not active_task.get("id"):
        reasons.append("no active task: nothing has been scoped and approved for this session")
    else:
        reasons.extend(_scope_shared_reasons(config, payload, tool_name, active_task))

    if reasons:
        return {"permissionDecision": PERMISSION_ASK,
                "permissionDecisionReason": " · ".join(reasons)}
    if policy == "v07":
        # § 7.1: the allow reserves the sequence and leaves the intention
        # row BEFORE the call goes out, so a write that never answers is a
        # dangling `pending` and not a hole in the log.
        _reserve_write(config, active_task, payload)
        signed = (_load_projection(config) or {}).get("scope") or {}
        if signed.get("status") == STATUS_CLOSING:
            # Retired ask (§ 7.3): a race between the close and a late
            # write is nobody's decision. The write goes through -- the
            # verdicts it may expire are protected by writeSeq -- and the
            # model gets the honest fix.
            return {"permissionDecision": "allow",
                    "permissionDecisionReason":
                        "el alcance está cerrando: abre uno nuevo o pide "
                        "`request: \"resume\"`"}
    return {"permissionDecision": "allow",
            "permissionDecisionReason": "scope and design audit check out"}


def _state_integrity_reasons(config, scope):
    """Whether the scope the file claims is the one the hook signed (§ 4.3).

    Compared against the projection, not against journal rows: rows are
    greppable and forgeable, the projection is rewritten whole by the hook
    on every accepted transition. With no signed state the scope does not
    exist for this gate, whatever the file says.
    """
    projection = _load_projection(config)
    signed = (projection or {}).get("scope") or {}
    if (projection is None
            or projection.get("instanceId") != scope.get("instanceId")
            or (scope.get("status"), scope.get("statusWriteSeq"))
            != (signed.get("status"), signed.get("statusWriteSeq"))):
        for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                            "gate-decisions.jsonl")):
            if row.get("event") == "suspended-overlap" \
                    and row.get("instanceId") == scope.get("instanceId"):
                return ["el alcance del hotfix toca objetos del alcance suspendido "
                        "(%s): trabajar sobre un objeto con un veredicto vivo de "
                        "otro alcance sí es una decisión (§ 4.5). Arreglo: deja esos "
                        "objetos fuera del hotfix, o cierra/abandona el alcance "
                        "suspendido primero" % row.get("detail")]
        return ["el estado del alcance no está firmado por el harness: el fichero no "
                "coincide con ninguna transición firmada. Arreglo: abre el alcance por "
                "la vía normal (appian-build escribe tasks/current.json y el hook lo "
                "firma al observarlo); si esto era un alcance viejo, ciérralo o "
                "abandónalo desde esa vía"]
    reasons = []
    for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                        "gate-decisions.jsonl")):
        if row.get("instanceId") != scope.get("instanceId"):
            continue
        if row.get("event") == "journal-tamper":
            reasons.append("un registro del harness fue escrito por el agente durante "
                           "esta instancia (%s): la memoria del gate está contaminada. "
                           "Arreglo: cierra o abandona este alcance y abre uno nuevo; "
                           "si no, cada escritura seguirá pidiendo permiso"
                           % row.get("detail"))
            break
        if row.get("event") == "anchored-drift":
            # § 7.3 cause 5: the contract changed under the permission WITH
            # agent writes in between -- that is a person's decision.
            reasons.append("el contrato del alcance cambió bajo el permiso con "
                           "escrituras ya aplicadas (%s). Arreglo: cierra o abandona "
                           "este alcance y abre uno nuevo con el contrato real; si "
                           "no, cada escritura seguirá pidiendo permiso"
                           % row.get("detail"))
            break
    status = signed.get("status")
    if status == STATUS_CLOSING:
        # Not a person's decision (§ 7.3): a race between the close and a
        # late write. The write goes through; the verdicts it may expire are
        # protected by writeSeq, and the model is told the honest fix.
        pass
    elif status in TERMINAL_STATUSES:
        reasons.append("el alcance %r ya terminó (%s) y su grant murió con la "
                       "instancia. Arreglo: abre un alcance nuevo para este trabajo; "
                       "si no, esta escritura no sale" % (scope.get("id"), status))
    elif status == STATUS_SUSPENDED:
        reasons.append("el alcance %r está suspendido: reanúdalo con `request: "
                       "\"resume\"` o abre el alcance nuevo que motivó la suspensión "
                       "antes de escribir" % (scope.get("id"),))
    return reasons


def _scope_shared_reasons(config, payload, tool_name, active_task):
    """The checks both rulebooks run today, verbatim from 0.6.

    The v07 path forks away from this helper unit by unit as Phase 2 lands
    (grant, pending row, task_min_kind); what stays shared stays here.
    """
    reasons = []
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
    return reasons


def _scope_status(active_task):
    """The scope state as read, migrated: a pre-0.7 task file has no
    `status` and is in flight by definition (norm § 15). Never rewrites."""
    status = (active_task or {}).get("status")
    if isinstance(status, str) and status.strip():
        return status
    return STATUS_IN_FLIGHT


def _close_state(deferred):
    """Which terminal state a clean close reaches (norm § 4.4 rows 3-4).

    One accepted deferral means every gate the harness can measure is met
    and a judgement is still a person's to give. Every criterion in
    DEFERRABLE_CRITERIA is that kind of judgement; the § 9.5 split of
    guarantee-residue ids arrives with that id vocabulary."""
    return STATUS_CLOSED_PENDING_HUMAN if deferred else STATUS_CLOSED


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
    policy = _scope_policy(active_task)
    if policy == "v07":
        return _closure_gate_v07(payload, config, active_task)
    if policy == "unknown":
        if payload.get("stop_hook_active"):
            return {"decision": "approve",
                    "systemMessage": "appian-harness: the scope file declares a "
                                     "schemaVersion nobody defines; nothing was "
                                     "validated at this close."}
        return {"decision": "block",
                "reason": "the scope file declares schemaVersion %r, which no rulebook "
                          "defines. Fix the file or reopen the scope before closing."
                          % (active_task.get("schemaVersion"),)}
    if not active_task or not active_task.get("id"):
        return {"decision": "approve"}

    task_id = active_task["id"]
    _note_manual_estimate(config)
    # Read once for all phases rather than once each: the write log grows
    # with the project and this is the only place they are all measured
    # against it.
    last_write = _latest_write_epoch(config, task_id)
    required = _required_closure_phases(config, active_task)
    if _risk_tier(active_task) == "trivial":
        _log_risk_downgrade(config, task_id, active_task.get("risk"))
    missing_phases = []
    missing_details = []
    deferred = []
    for phase in required:
        errs = _phase_errors(config, task_id, phase, last_write)
        if errs:
            missing_phases.append(phase)
            missing_details.append("practices-%s (%s)" % (phase, "; ".join(errs)))
        else:
            verdict = load_verdict(_verdict_path(config, task_id, phase))
            if verdict.get("verdict") == "NOT_MEASURED":
                deferred.append((phase, verdict.get("deferredCriterion")))

    if not missing_details:
        state = _close_state(deferred)
        _log_task_closure(config, task_id, _scope_status(active_task), state, deferred)
        if state == STATUS_CLOSED_PENDING_HUMAN:
            return {"decision": "approve",
                    "systemMessage": (
                        "Task %r closes %s: every gate the harness can measure is met, "
                        "and %s still needs a person. Owner and closing condition are in "
                        "deferred-debt.jsonl; the close is recorded in task-closures.jsonl."
                        % (task_id, STATUS_CLOSED_PENDING_HUMAN,
                           ", ".join("practices-%s (%s)" % (p, c) for p, c in deferred)))}
        return {"decision": "approve"}

    if payload.get("stop_hook_active"):
        debt_path = _record_deferred_debt(config, task_id, missing_phases)
        _log_task_closure(config, task_id, _scope_status(active_task),
                          STATUS_CLOSED_WITH_DEBT, deferred)
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


def _v07_closure_missing(config, scope):
    """What a v07 close can demand in Phase 2: the state machine plus the
    one § 7.1 rule that already has its data -- a reservation nobody ever
    answered. The floor by sequences plugs in here in Phase 3 and the
    judge's verdicts in Phase 4 (§ 16 places them there), so "closes clean"
    today means the machine and the write log were respected, not that any
    floor was satisfied."""
    unresolved = _unresolved_pendings(config, scope.get("instanceId"))
    if unresolved:
        return ["hay %d escritura(s) sin respuesta (pending) en operations.jsonl — "
                "ni ok, ni failed, ni ambiguous: MCP caído, timeout o sesión cortada. "
                "Relee cada objeto afectado y registra lo que persistió antes de "
                "cerrar (§ 7.1)" % len(unresolved)]
    return []


def _unresolved_pendings(config, instance_id):
    """Reservations whose LAST correlated row is still `pending`: the case
    `ambiguous` does not cover, because there was no response at all."""
    last = {}
    for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                        "operations.jsonl")):
        if row.get("instanceId") != instance_id:
            continue
        key = row.get("toolUseId") or "seq-%s" % row.get("writeSeq")
        last[key] = row
    return [r for r in last.values() if r.get("result") == "pending"]


def _closure_gate_v07(payload, config, scope):
    """Stop under the v07 rulebook: only the closure is its business.

    in-flight approves as a handoff -- except the third Stop of an instance
    with applied writes that never entered closing, which blocks once and
    then closes `closed-with-debt` with `never-closed` debt (§ 7.1, § 4.4
    row 13). closing validates and signs transition 3 (or 5 on the forced
    repeat). Terminal and suspended states approve: nothing to gate.
    """
    _note_manual_estimate(config)
    projection = _load_projection(config)
    if projection is None or projection.get("instanceId") != scope.get("instanceId"):
        # No signed scope: it does not exist for the gates (§ 4.3).
        return {"decision": "approve"}
    signed = projection.get("scope") or {}
    status = signed.get("status")
    instance = signed.get("instanceId") or scope.get("instanceId")
    if status in TERMINAL_STATUSES or status == STATUS_SUSPENDED:
        return {"decision": "approve"}

    decisions = _read_jsonl(os.path.join(_evidence_dir(config),
                                         "gate-decisions.jsonl"))
    if status == STATUS_IN_FLIGHT:
        seq = _observed_write_seq(config, instance)
        entered_closing = any(r.get("event") == "transition"
                              and r.get("instanceId") == instance
                              and r.get("to") == STATUS_CLOSING for r in decisions)
        if seq == 0 or entered_closing:
            return {"decision": "approve"}
        prior_stops = sum(1 for r in decisions
                          if r.get("event") == "stop-observed"
                          and r.get("instanceId") == instance)
        _record_state_event(config, "stop-observed", instance,
                            "stop #%d in flight with writes applied" % (prior_stops + 1))
        if prior_stops < 2:
            return {"decision": "approve",
                    "systemMessage": "appian-harness: scope %r is still in flight with "
                                     "writes applied; this stop is a handoff, not a "
                                     "close. Ask to close it with `request: \"close\"`."
                                     % signed.get("id")}
        if payload.get("stop_hook_active"):
            _append_jsonl(_debt_register(config),
                          {"timestamp": _now(), "task": signed.get("id"),
                           "instanceId": instance, "kind": "never-closed",
                           "reason": "writes were applied and the scope never entered "
                                     "closing; the repeated Stop closed it with debt "
                                     "(§ 4.4 row 13)"})
            _sign_transition(config, signed, STATUS_IN_FLIGHT,
                             STATUS_CLOSED_WITH_DEBT, "third-stop")
            _log_task_closure(config, signed.get("id"), STATUS_IN_FLIGHT,
                              STATUS_CLOSED_WITH_DEBT, [])
            _restore_suspended_if_any(config, signed)
            return {"decision": "approve",
                    "systemMessage": "appian-harness: scope %r closed WITH DEBT "
                                     "(never-closed): it wrote to Appian and was "
                                     "never asked to close. The debt and its owner "
                                     "are in deferred-debt.jsonl." % signed.get("id")}
        return {"decision": "block",
                "reason": "scope %r has %d writes applied and was never asked to "
                          "close. Ask to close it (`request: \"close\"`), or abandon "
                          "it with a reason; stopping again closes it with "
                          "`never-closed` debt." % (signed.get("id"), seq)}

    # status == closing
    missing = _v07_closure_missing(config, scope)
    if not missing:
        _sign_transition(config, signed, STATUS_CLOSING, STATUS_CLOSED, "stop-clean")
        _log_task_closure(config, signed.get("id"), STATUS_CLOSING, STATUS_CLOSED, [])
        _restore_suspended_if_any(config, signed)
        return {"decision": "approve"}
    if payload.get("stop_hook_active"):
        _append_jsonl(_debt_register(config),
                      {"timestamp": _now(), "task": signed.get("id"),
                       "instanceId": instance, "kind": "closed-with-debt",
                       "missing": missing})
        _sign_transition(config, signed, STATUS_CLOSING,
                         STATUS_CLOSED_WITH_DEBT, "stop-forced")
        _log_task_closure(config, signed.get("id"), STATUS_CLOSING,
                          STATUS_CLOSED_WITH_DEBT, [])
        _restore_suspended_if_any(config, signed)
        return {"decision": "approve",
                "systemMessage": "appian-harness: scope %r closed WITH DEBT; still "
                                 "missing: %s" % (signed.get("id"), "; ".join(missing))}
    return {"decision": "block",
            "reason": "the close is not complete: %s" % "; ".join(missing)}


def failure_notice(payload, config=None):
    """PostToolUseFailure: turns 'remember to be idempotent' into a reminder.

    A failed write leaves the agent guessing whether it landed. This tells
    it not to guess: read first, record the partial state, then resume from
    the first thing it never confirmed.

    A failed READ gets no notice, and that asymmetry is the point: nothing
    persisted, nothing partial to record, and "do not retry" is the opposite
    of the fix -- a read that failed on a misspelled field wants reissuing.
    """
    tool_name = payload.get("tool_name")
    if not _is_write_tool(tool_name, config):
        return {}
    # P5: a tool error produces PostToolUseFailure and NOT PostToolUse, so
    # this is what keeps the reservation from dangling as `pending`.
    if config is not None:
        active_task = config.get("activeTask") or {}
        if _scope_policy(active_task) == "v07" \
                and not _scope_schema_errors(active_task) \
                and payload.get("tool_use_id"):
            _log_write_v07(payload, config, active_task,
                           result="failed", uuids=[])
    message = (
        "The write via %s failed. Do not retry this write; check with a read "
        "whether it persisted, record what did and did not, and resume from "
        "the first unverified result." % tool_name
    )
    return {"additionalContext": message}


def _reserve_write(config, scope, payload):
    """Reserves the next writeSeq and persists the pending row, under a
    best-effort lock: read max, reserve N+1, write, release. The journal is
    the only counter -- a counter in the scope file would be a second source
    of truth an agent could edit."""
    lock_path = os.path.join(_evidence_dir(config), ".operations.lock")
    fd = None
    for _ in range(50):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            try:
                if time.time() - os.path.getmtime(lock_path) > 5:
                    os.unlink(lock_path)
                    continue
            except OSError:
                pass
            time.sleep(0.01)
        except OSError:
            break
    try:
        candidates = _target_candidates(payload.get("tool_name"),
                                        payload.get("tool_input", {}), config)
        _append_jsonl(os.path.join(_evidence_dir(config), "operations.jsonl"), {
            "timestamp": _now(),
            "task": scope.get("id"),
            "instanceId": scope.get("instanceId"),
            "writeSeq": _observed_write_seq(config, scope.get("instanceId")) + 1,
            "tool": payload.get("tool_name"),
            "toolUseId": payload.get("tool_use_id"),
            "object": candidates[0] if candidates else None,
            "candidates": candidates,
            "inScope": True,
            "result": "pending",
        })
    finally:
        if fd is not None:
            os.close(fd)
            try:
                os.unlink(lock_path)
            except OSError:
                pass


# The two types whose expression is single, stable and comparable (§ 7.6);
# every other type is behavioural by definition, without computing anything.
_EXPRESSION_ACTIONS = frozenset(("createInterface", "updateInterface",
                                 "createExpressionRule", "updateExpressionRule"))
# The whole whitelist. `name` is deliberately NOT here (§ 3.2): rules are
# invoked by name and constants by cons!, so a rename breaks every caller.
_METADATA_ONLY_FIELDS = frozenset(("description", "documentation"))
_IDENTITY_FIELDS = frozenset(("uuid", "versionId"))


def _behavioural_and_hash(action, tool_input):
    """(behavioural, expressionHash) from the observed payload (§ 7.6).

    The hash is computed HERE, in PostToolUse, over the same bytes the call
    consumed: `expressionFilePath` is a path the MCP server reads at call
    time, and measuring it earlier opens the window where the agent edits
    the file between the measure and the send. Unreadable file => True,
    None: fails to the expensive side.
    """
    if not isinstance(tool_input, dict) or action not in _EXPRESSION_ACTIONS:
        return True, None
    mutated = set(tool_input) - _IDENTITY_FIELDS
    behavioural = bool(mutated - _METADATA_ONLY_FIELDS)
    expression = tool_input.get("expression")
    if expression is None and tool_input.get("expressionFilePath"):
        try:
            with open(tool_input["expressionFilePath"], encoding="utf-8") as f:
                expression = f.read()
        except (OSError, UnicodeDecodeError):
            return True, None
    if not isinstance(expression, str):
        return behavioural, None
    digest = hashlib.sha256(json.dumps(
        {"expression": expression, "inputs": tool_input.get("inputs")},
        sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return behavioural, digest


def _classify_write_response(payload):
    """(result, uuids) against the shapes Phase 0 captured live (P3).

    ok = JSON carrying an identity, or the delete acknowledgement that
    carries none; failed = the API's error prefix, the MCP server's own
    validation error, or the tool-error envelope; EVERYTHING else is
    ambiguous, which never counts and demands a re-read -- the reorder echo
    proved that tail exists for real.
    """
    response = payload.get("tool_response")
    if response is None:
        response = payload.get("tool_result")
    return _classify_response_value(response)


def _classify_response_value(value):
    if isinstance(value, dict):
        if value.get("is_error") or value.get("error"):
            return "failed", []
        uuid = value.get("uuid")
        if isinstance(uuid, str) and uuid:
            return "ok", [uuid]
        if _norm_ident(value.get("result") or "") == "deleted successfully":
            return "ok", []
        return "ambiguous", []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "ambiguous", []
        if "<tool_use_error>" in text:
            return "failed", []
        if text.startswith(("API error (HTTP", "Unexpected error:")):
            return "failed", []
        if text.lower().startswith("error"):
            return "failed", []
        try:
            parsed = json.loads(text)
        except ValueError:
            return "ambiguous", []
        if isinstance(parsed, dict):
            return _classify_response_value(parsed)
    return "ambiguous", []


def _log_write_v07(payload, config, scope, result=None, uuids=None):
    """Resolves the reservation by tool_use_id -- never "the last pending":
    parallel writes come back out of order -- and appends the resolution
    row. Also writes the name<->UUID link for a granted create, and stamps
    the observed `risk` into the signed scope (§ 5.3)."""
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input") or {}
    action = _tool_action(tool_name, config)
    instance = scope.get("instanceId")
    if result is None:
        result, uuids = _classify_write_response(payload)
    uuids = uuids or []
    tool_use_id = payload.get("tool_use_id")

    reserved_seq = None
    if tool_use_id:
        for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                            "operations.jsonl")):
            if row.get("toolUseId") == tool_use_id \
                    and row.get("instanceId") == instance:
                reserved_seq = row.get("writeSeq")
    seq = reserved_seq if reserved_seq is not None \
        else _observed_write_seq(config, instance) + 1

    candidates = _with_linked_names(config, instance,
                                    _target_candidates(tool_name, tool_input,
                                                       config))
    grant = scope.get("grant") if isinstance(scope.get("grant"), dict) else {}
    covered = set(scope.get("allowedObjects") or []) | set(_granted_objects(grant))
    behavioural, expr_hash = _behavioural_and_hash(action, tool_input)
    _append_jsonl(os.path.join(_evidence_dir(config), "operations.jsonl"), {
        "timestamp": _now(),
        "task": scope.get("id"),
        "instanceId": instance,
        "writeSeq": seq,
        "tool": tool_name,
        "toolUseId": tool_use_id,
        "object": candidates[0] if candidates else None,
        "candidates": candidates,
        "uuids": uuids,
        "inScope": bool(candidates) and any(c in covered for c in candidates),
        "behavioural": behavioural,
        "expressionHash": expr_hash,
        "result": result,
    })

    if result == "ok" and action in _CREATE_TYPE_BY_ACTION and uuids:
        name = tool_input.get("name")
        approved = {e.get("name") for e in grant.get("creates") or []
                    if isinstance(e, dict)}
        if name in approved:
            for uuid in uuids:
                _append_jsonl(os.path.join(_evidence_dir(config),
                                           "gate-decisions.jsonl"),
                              {"timestamp": _now(), "event": "uuid-link",
                               "instanceId": instance, "name": name,
                               "uuid": uuid, "toolUseId": tool_use_id})

    _note_observed_risk(config, scope, tool_name, tool_input)
    return {}


def verdict_expiry_errors(config, scope, verdict):
    """Whether a v07 verdict still covers the signed scope (§ 7.6).

    A verdict declares `instanceId` and `coversThroughWriteSeq`, and expires
    only before an `inScope: true`, `behavioural: true` write of ITS
    instance with a higher sequence. A `failed` write changed nothing and
    expires nothing; an `ambiguous` or unresolved one sits on the expensive
    side. `design` is exempt: it is meant to precede every write.

    The full consumer is the certify gate (Phase 4); the mechanics and the
    behavioural rows live here since Phase 2.
    """
    if verdict.get("phase") in STALENESS_EXEMPT_PHASES:
        return []
    if verdict.get("instanceId") != scope.get("instanceId"):
        return ["the verdict belongs to instance %r, not to this scope's %r: a "
                "verdict from another instance never covers this one (§ 11.1)"
                % (verdict.get("instanceId"), scope.get("instanceId"))]
    covers = verdict.get("coversThroughWriteSeq")
    if not (isinstance(covers, int) and not isinstance(covers, bool) and covers >= 0):
        return ["the verdict declares no usable coversThroughWriteSeq (%r), so there "
                "is no way to know what it covers" % (covers,)]
    last = {}
    for row in _read_jsonl(os.path.join(_evidence_dir(config),
                                        "operations.jsonl")):
        if row.get("instanceId") != scope.get("instanceId"):
            continue
        key = row.get("toolUseId") or "seq-%s" % row.get("writeSeq")
        last[key] = row
    expiring = []
    for row in last.values():
        seq = row.get("writeSeq")
        if not (isinstance(seq, int) and seq > covers):
            continue
        if not row.get("inScope"):
            continue
        result = row.get("result")
        if result == "failed":
            continue
        # A resolved non-behavioural write cannot expire anything; a
        # pending or ambiguous one is unknown, and unknown is expensive.
        if result == "ok" and row.get("behavioural") is False:
            continue
        expiring.append(seq)
    if expiring:
        return ["the verdict covers through writeSeq %d and behavioural in-scope "
                "writes happened after it (writeSeq %s): it certifies an artifact "
                "that has since changed. Re-run the phase against the current one"
                % (covers, ", ".join(str(s) for s in sorted(expiring)))]
    return []


def _note_observed_risk(config, scope, tool_name, tool_input):
    """§ 5.3: `risk` is a damage class the hook observes and writes, never a
    label the agent declares. Stamped into file and projection together, so
    the drift check keeps agreeing with itself."""
    if observed_risk(tool_name, tool_input, config) != "high":
        return
    projection = _load_projection(config)
    if not projection or projection.get("instanceId") != scope.get("instanceId"):
        return
    signed = projection.get("scope") or {}
    if signed.get("risk") == "high":
        return
    updated = dict(signed, risk="high")
    _write_json_atomic(_projection_path(config),
                       {"instanceId": scope.get("instanceId"), "scope": updated,
                        "signedAt": _now()})
    _write_json_atomic(config["activeTaskFile"], updated)


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
    if not _is_write_tool(payload.get("tool_name"), config):
        return {}
    active_task = config.get("activeTask") or {}
    if _scope_policy(active_task) == "v07" \
            and not _scope_schema_errors(active_task):
        return _log_write_v07(payload, config, active_task)
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
        # The hook-owned surfaces come first: the projection and the
        # root-level registers are what the state machine trusts, so an
        # agent write there is tampering, not evidence (§ 4.3). Verdicts
        # and renders below evidence/<task>/ stay ordinary evidence.
        if target == os.path.join(evidence, PROJECTION_NAME):
            return "journal"
        if os.path.dirname(target) == evidence and target.endswith(".jsonl"):
            return "journal"
        if target == evidence or target.startswith(evidence + os.sep):
            return "evidence"
    return None


# --- The state machine (norm §§ 4.3-4.4) -------------------------------

# What the hook remembers having written (§ 4.3): a full snapshot of the
# signed scope, rewritten atomically on every accepted transition. The
# journal rows in gate-decisions.jsonl are the audit trail; THIS file is the
# authority the validation compares against, because journal rows are
# greppable and forgeable and a comparison against them would accept a
# hand-written plausible row.
PROJECTION_NAME = "scope-projection.json"

# Statuses a scope can still move from. `suspended` is live on purpose: it
# awaits its resume, so a new scope must not silently replace it.
LIVE_STATUSES = (STATUS_IN_FLIGHT, STATUS_CLOSING, STATUS_SUSPENDED)
TERMINAL_STATUSES = (STATUS_CLOSED, STATUS_CLOSED_PENDING_HUMAN,
                     STATUS_CLOSED_WITH_DEBT, STATUS_ABANDONED)

# § 4.4 as data: (status the hook signed, request) -> new status. Anything
# absent here is illegal, and an illegal request is coordination with the
# model, never a prompt to the person (§ 7.3).
_REQUEST_TRANSITIONS = {
    (STATUS_IN_FLIGHT, "close"): STATUS_CLOSING,       # row 2
    (STATUS_IN_FLIGHT, "suspend"): STATUS_SUSPENDED,   # row 7; § 4.5 conditions
    (STATUS_IN_FLIGHT, "abandon"): STATUS_ABANDONED,   # row 10
    (STATUS_CLOSING, "abandon"): STATUS_ABANDONED,     # row 10
    (STATUS_CLOSING, "resume"): STATUS_IN_FLIGHT,      # row 6
    (STATUS_SUSPENDED, "resume"): STATUS_IN_FLIGHT,    # row 8
    (STATUS_SUSPENDED, "abandon"): STATUS_ABANDONED,   # row 9
}


def _projection_path(config):
    return os.path.join(_evidence_dir(config), PROJECTION_NAME)


def _load_projection(config):
    data, err = _load_json_file(_projection_path(config))
    return data if isinstance(data, dict) and not err else None


def _write_json_atomic(path, obj):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


def _observed_write_seq(config, instance_id):
    """The writeSeq the hook has observed for this instance: the highest
    stamped one, or the row count where rows predate stamping. This is the
    signature's source -- derived from the journal the hook writes, never a
    counter an agent could edit."""
    seq = 0
    count = 0
    for row in _read_jsonl(os.path.join(_evidence_dir(config), "operations.jsonl")):
        if row.get("instanceId") != instance_id:
            continue
        count += 1
        stamped = row.get("writeSeq")
        if isinstance(stamped, int) and not isinstance(stamped, bool):
            seq = max(seq, stamped)
    return max(seq, count if seq == 0 else seq)


def _abandon_reason(request):
    """The motive riding in an abandon request, or None when it is absent --
    and absence is a rejection, not a default (§ 4.4 rows 9-10)."""
    if request == "abandon":
        return None
    if isinstance(request, str) and request.startswith("abandon:"):
        reason = request[len("abandon:"):].strip()
        return reason or None
    return None


def _sign_transition(config, scope, from_status, to_status, trigger):
    """The one place a v07 `status` gets written: file, projection and audit
    row together, in write-ahead order (row, then projection, then file)."""
    seq = _observed_write_seq(config, scope["instanceId"])
    signed = dict(scope)
    signed["status"] = to_status
    signed["statusWriteSeq"] = seq
    signed["request"] = None
    if to_status in TERMINAL_STATUSES and not signed.get("closedAt"):
        signed["closedAt"] = _now()
    _append_jsonl(os.path.join(_evidence_dir(config), "gate-decisions.jsonl"),
                  {"timestamp": _now(), "event": "transition",
                   "instanceId": scope["instanceId"], "scopeId": scope.get("id"),
                   "from": from_status, "to": to_status,
                   "statusWriteSeq": seq, "trigger": trigger})
    _write_json_atomic(_projection_path(config),
                       {"instanceId": scope["instanceId"], "scope": signed,
                        "signedAt": _now()})
    _write_json_atomic(config["activeTaskFile"], signed)
    return signed


def _record_state_event(config, event, instance_id, detail):
    _append_jsonl(os.path.join(_evidence_dir(config), "gate-decisions.jsonl"),
                  {"timestamp": _now(), "event": event,
                   "instanceId": instance_id, "detail": detail})


def _handle_request(config, scope, signed_status):
    """Resolves the agent's `request` against § 4.4. Returns the remedy or
    confirmation for the model; the file ends with `request` consumed either
    way, so a rejected request is not re-litigated on every later edit."""
    request = scope.get("request")
    verb = "abandon" if isinstance(request, str) and request.startswith("abandon") \
        else request
    if verb == "suspend" and isinstance(scope.get("suspendedScope"), dict):
        # § 4.5: one at most. Nesting suspensions would need a stack, and a
        # stack of live grants is exactly what the cap exists to prevent.
        cleared = dict(scope, request=None, status=signed_status)
        _write_json_atomic(config["activeTaskFile"], cleared)
        return {"additionalContext":
                "appian-harness: ya hay un alcance suspendido: ciérralo o reanúdalo "
                "antes de suspender otro (§ 4.5)."}
    target = _REQUEST_TRANSITIONS.get((signed_status, verb))
    if target is None:
        cleared = dict(scope, request=None,
                       status=signed_status)
        _write_json_atomic(config["activeTaskFile"], cleared)
        _record_state_event(config, "request-rejected", scope["instanceId"],
                            "%r is not a legal request from %r" % (request, signed_status))
        return {"additionalContext":
                "appian-harness: request %r is not a legal transition from %r "
                "(§ 4.4). Legal from here: %s. The request was cleared; ask again "
                "with a legal one." % (request, signed_status,
                                       ", ".join(sorted(r for (s, r) in _REQUEST_TRANSITIONS
                                                        if s == signed_status)))}
    if verb == "abandon":
        reason = _abandon_reason(request)
        if reason is None:
            cleared = dict(scope, request=None, status=signed_status)
            _write_json_atomic(config["activeTaskFile"], cleared)
            return {"additionalContext":
                    "appian-harness: abandoning needs its reason (§ 4.4). Write "
                    "`\"request\": \"abandon: <motivo>\"` and the hook will sign it."}
        _append_jsonl(_debt_register(config),
                      {"timestamp": _now(), "task": scope.get("id"),
                       "instanceId": scope["instanceId"], "kind": "abandoned-scope",
                       "reason": reason,
                       "detail": "scope abandoned without evidence; the grant is dead "
                                 "and rework means a new scope"})
    _sign_transition(config, scope, signed_status, target,
                     "request:%s" % verb)
    if target in TERMINAL_STATUSES:
        _restore_suspended_if_any(config, scope)
    return {"additionalContext":
            "appian-harness: scope %r is now %r (signed)." % (scope.get("id"), target)}


def _restore_suspended_if_any(config, closed_scope):
    """§ 4.5: closing the hotfix resumes the suspended scope for free -- no
    new grant, nothing re-issued -- unless its grant expired by sessions, in
    which case the scope comes back in flight carrying none and the next
    write asks for the new grant."""
    embedded = closed_scope.get("suspendedScope")
    if not isinstance(embedded, dict) or not embedded.get("instanceId"):
        return
    restored = dict(embedded)
    sessions = restored.pop("sessionsSeen", 0)
    if isinstance(sessions, int) and not isinstance(sessions, bool) and sessions >= 3:
        restored["grant"] = None
    restored["suspendedScope"] = None
    restored["resumeFrom"] = None
    _sign_transition(config, restored, STATUS_SUSPENDED, STATUS_IN_FLIGHT,
                     "hotfix-closed")


def _enforce_state_machine(config, scope, payload=None):
    """One observation of the v07 scope file against what the hook signed."""
    projection = _load_projection(config)
    instance_id = scope["instanceId"]

    if projection is None or projection.get("instanceId") != instance_id:
        prior = (projection or {}).get("scope", {})
        if projection is not None and prior.get("status") in LIVE_STATUSES:
            if prior.get("status") == STATUS_SUSPENDED \
                    and scope.get("status") == STATUS_IN_FLIGHT:
                embedded = scope.get("suspendedScope")
                if isinstance(embedded, dict) \
                        and embedded.get("instanceId") == projection.get("instanceId"):
                    # The hotfix path (§ 4.5). The hook re-embeds its own
                    # signed copy -- the constructor's copy is not trusted --
                    # and disjointness is a person's decision, so overlap
                    # leaves the scope unsigned and the gate asking.
                    canonical = dict(prior)
                    canonical["sessionsSeen"] = embedded.get("sessionsSeen") \
                        if isinstance(embedded.get("sessionsSeen"), int) \
                        else prior.get("sessionsSeen", 0)
                    overlap = sorted(set(canonical.get("allowedObjects") or [])
                                     & set(scope.get("allowedObjects") or []))
                    if overlap:
                        _record_state_event(config, "suspended-overlap",
                                            instance_id,
                                            "el hotfix toca %r, que pertenece al "
                                            "alcance suspendido" % overlap)
                        return {"additionalContext":
                                "appian-harness: el alcance del hotfix toca %r, que "
                                "pertenece al alcance suspendido: los objetos deben "
                                "ser disjuntos (§ 4.5). El alcance no se firma; la "
                                "próxima escritura preguntará." % overlap}
                    opened = dict(scope, suspendedScope=canonical,
                                  resumeFrom=canonical.get("id"))
                    _sign_transition(config, opened, None, STATUS_IN_FLIGHT,
                                     "open-hotfix")
                    return {"additionalContext":
                            "appian-harness: hotfix %r abierto y firmado; %r queda "
                            "suspendido y embebido." % (scope.get("id"),
                                                        canonical.get("id"))}
            # A different instance over a live scope is a swapped contract:
            # nothing gets signed, and the scope gate will ask (§ 4.1).
            _record_state_event(config, "instance-swap", instance_id,
                                "file claims %r while %r is still %r"
                                % (instance_id, projection.get("instanceId"),
                                   prior.get("status")))
            return {"additionalContext":
                    "appian-harness: there is a live scope (%r, %s) and this file "
                    "names another instance. Close, suspend or abandon the live one "
                    "first." % (projection.get("instanceId"), prior.get("status"))}
        if scope.get("status") == STATUS_IN_FLIGHT:
            _sign_transition(config, scope, None, STATUS_IN_FLIGHT, "open")
            return {"additionalContext":
                    "appian-harness: scope %r opened and signed (instance %s)."
                    % (scope.get("id"), instance_id)}
        # § 4.3: no signed state to revert to means the scope does not exist
        # for the gates -- nothing is inferred from the file.
        _record_state_event(config, "unsigned-scope", instance_id,
                            "born with status %r" % scope.get("status"))
        return {"additionalContext":
                "appian-harness: a scope file must be born `in-flight`; this one says "
                "%r and is not signed. Open the scope through appian-build."
                % scope.get("status")}

    signed = projection.get("scope") or {}
    signed_status = signed.get("status")
    if (scope.get("status"), scope.get("statusWriteSeq")) != \
            (signed_status, signed.get("statusWriteSeq")):
        restored = dict(scope)
        restored["status"] = signed_status
        restored["statusWriteSeq"] = signed.get("statusWriteSeq")
        _write_json_atomic(config["activeTaskFile"], restored)
        _record_state_event(config, "state-revert", instance_id,
                            "hand-written %r reverted to signed %r"
                            % (scope.get("status"), signed_status))
        return {"additionalContext":
                "appian-harness: el estado lo escribe el harness; pide el cambio con "
                "`request`. The hand-written status %r was reverted to the signed %r."
                % (scope.get("status"), signed_status)}

    if scope.get("request"):
        return _handle_request(config, scope, signed_status)

    # An ordinary edit. Anchored fields cannot drift (§ 4.1); the rest of
    # the contract may still be enriched -- the mandatory order is preflight
    # first, scope and grant after -- so the projection follows it.
    # `risk` is the hook's own field (§ 5.3): a file that lost or lowered it
    # -- an agent rewriting from a stale copy, or on purpose -- gets it
    # re-imposed rather than counted as contract drift, or one careless
    # full-file Write would poison the instance with a permanent ask.
    if scope.get("risk") != signed.get("risk"):
        scope = dict(scope, risk=signed.get("risk"))
        _write_json_atomic(config["activeTaskFile"], scope)
    drifted = [f for f in ("kind",) if scope.get(f) != signed.get(f)]
    if signed.get("grant") is not None:
        drifted.extend(f for f in ("grant", "allowedObjects")
                       if scope.get(f) != signed.get(f))
    if drifted:
        if _observed_write_seq(config, instance_id) == 0:
            # Retired ask (§ 7.3): with no agent writes in between, a
            # changed contract is the harness's own problem -- corrected
            # and recorded, never a person's question.
            restored = dict(scope)
            for field in drifted:
                restored[field] = signed.get(field)
            _write_json_atomic(config["activeTaskFile"], restored)
            _write_json_atomic(_projection_path(config),
                               {"instanceId": instance_id, "scope": restored,
                                "signedAt": _now()})
            _record_state_event(config, "anchored-restored", instance_id,
                                "restored %s from the signed projection"
                                % ", ".join(drifted))
            return {"additionalContext":
                    "appian-harness: %s cannot change during an instance (§ 4.1); "
                    "no writes had happened, so the anchored values were restored "
                    "from the signed copy." % ", ".join(drifted)}
        _record_state_event(config, "anchored-drift", instance_id,
                            "fields changed under the instance: %s" % ", ".join(drifted))
        return {"additionalContext":
                "appian-harness: %s cannot change during an instance (§ 4.1). The "
                "change is recorded; the next write will ask. To change the contract, "
                "close or abandon this scope and open a new one." % ", ".join(drifted)}
    updated = dict(scope)
    if signed.get("grant") is None and isinstance(updated.get("grant"), dict):
        # § 6.1: the hook records the permission mode under which the grant
        # arrived; `bypassPermissions` never counts as a person's approval,
        # and the observed value is what the gate later reads.
        mode = (payload or {}).get("permission_mode")
        if isinstance(mode, str) and mode.strip():
            updated["grant"] = dict(updated["grant"], permissionMode=mode)
            _write_json_atomic(config["activeTaskFile"], updated)
    _write_json_atomic(_projection_path(config),
                       {"instanceId": instance_id, "scope": updated,
                        "signedAt": _now()})
    return {}


def state_gate(payload, config):
    """PostToolUse on file writes: the state machine's enforcement point,
    plus the 0.6 observer it grew from.

    Every edit to what the gates read is logged (not gated -- the auditor
    legitimately writes verdicts here). On the v07 scope file it validates,
    transitions and signs; on a hook-owned journal it records tampering; on
    a 0.6 scope file it only observes, because that scope closes under the
    rules it opened with (§ 15).
    """
    file_path = (payload.get("tool_input") or {}).get("file_path")
    target = _evidence_write_target(config, file_path)
    if target is None:
        return {}
    active_task = config.get("activeTask") or {}
    _append_jsonl(os.path.join(_evidence_dir(config),
                                "evidence-writes.jsonl"),
                  {"timestamp": _now(),
                   "task": active_task.get("id"),
                   "tool": payload.get("tool_name"),
                   "target": target,
                   "path": file_path,
                   "result": _write_result(payload)})
    if target == "journal":
        # The hook's own appends are not tool events, so an observed write
        # here is the agent's pen on the hook's memory: provenance is gone
        # for this instance until a new one opens.
        _record_state_event(config, "journal-tamper",
                            (active_task or {}).get("instanceId"),
                            "agent wrote %s via %s" % (file_path,
                                                       payload.get("tool_name")))
        return {"additionalContext":
                "appian-harness: %s is written by the harness, not by the agent. "
                "The write is recorded as tampering and the scope gate will ask "
                "before the next Appian write." % os.path.basename(file_path or "")}
    if target == "active-task":
        _note_manual_estimate(config)
        if _scope_policy(active_task) == "v07":
            schema_errors = _scope_schema_errors(active_task)
            if schema_errors:
                return {"additionalContext":
                        "appian-harness: the scope file does not validate against "
                        "schema v2 and was not signed: %s" % "; ".join(schema_errors)}
            return _enforce_state_machine(config, active_task, payload)
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
        "decision": PERMISSION_ASK,
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


def _log_task_closure(config, task_id, from_status, status, deferred):
    """One durable row per close outcome -- the transition's record until
    the hook signs `status` into the scope file itself (0.7 state-gate).
    Deduped per (task, outcome); read for reporting, never as authority."""
    path = os.path.join(_evidence_dir(config), "task-closures.jsonl")
    for e in _read_jsonl(path):
        if e.get("task") == task_id and e.get("status") == status:
            return
    _append_jsonl(path, {
        "timestamp": _now(), "task": task_id,
        "from": from_status, "status": status,
        "deferred": [{"phase": p, "criterion": c} for p, c in deferred],
    })


def _note_manual_estimate(config):
    """Anchors the constructor's manualEstimateMinutes: write-once with an
    annotation. The first valid value is the denominator of the manual
    metric (reported, never scored); a later different value is annotated
    and does not replace it. Behind `measure: true` -- off, the field is
    inert and one row says so."""
    active_task = config.get("activeTask") or {}
    task_id = active_task.get("id")
    value = active_task.get("manualEstimateMinutes")
    if not task_id or value is None:
        return
    path = os.path.join(_evidence_dir(config), "manual-estimates.jsonl")
    rows = [e for e in _read_jsonl(path) if e.get("task") == task_id]
    if not config.get("measure"):
        if not any(e.get("event") == "ignored" for e in rows):
            _append_jsonl(path, {
                "timestamp": _now(), "task": task_id, "event": "ignored",
                "value": value,
                "reason": "manualEstimateMinutes only exists with measure: true"})
        return
    valid = (isinstance(value, (int, float)) and not isinstance(value, bool)
             and value == value and value != float("inf") and value > 0)
    anchored = next((e for e in rows if e.get("event") == "anchored"), None)
    if anchored is None:
        if valid:
            _append_jsonl(path, {"timestamp": _now(), "task": task_id,
                                 "event": "anchored", "minutes": value})
        elif not any(e.get("event") == "invalid" for e in rows):
            _append_jsonl(path, {"timestamp": _now(), "task": task_id,
                                 "event": "invalid", "value": value})
        return
    if (valid and value != anchored.get("minutes")
            and not any(e.get("event") == "changed" and e.get("minutes") == value
                        for e in rows)):
        _append_jsonl(path, {"timestamp": _now(), "task": task_id,
                             "event": "changed", "minutes": value,
                             "anchoredMinutes": anchored.get("minutes"),
                             "reason": "write-once: the anchored value stands"})


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
        # Opt-in instrumentation (measure: true, off by default): it is
        # what makes manualEstimateMinutes exist at all.
        "measure": project_config.get("measure") is True,
        # The declared perimeter (§ 7.2). Passed through raw: the matchers
        # normalise it, and junk must degrade to the loud fallback there,
        # not be silently dropped here.
        "appianMcpToolPrefixes": project_config.get("appianMcpToolPrefixes"),
        "designMcpServer": project_config.get("designMcpServer") or DEFAULT_DESIGN_MCP,
        "docsMcpServer": project_config.get("docsMcpServer") or DEFAULT_DOCS_MCP,
        "mcpServers": _discover_mcp_servers(project_root),
        # The three paths the gates read, kept so state_gate can
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
            "permissionDecision": PERMISSION_ASK,
            "permissionDecisionReason": "harness config unreadable: %s" % (err or parse_err),
        }})
        return 0

    decision = scope_gate(payload, config)
    if decision["permissionDecision"] == PERMISSION_ASK:
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


def cmd_state_gate():
    payload, parse_err = _read_stdin_json()
    config, active, err = _build_config(payload.get("cwd") or ".")
    if not active or err or parse_err:
        _emit({})
        return 0
    out = state_gate(payload, config)
    if out:
        _emit({"hookSpecificOutput": dict(out, hookEventName="PostToolUse")})
        return 0
    _emit({})
    return 0


def cmd_failure_notice():
    payload, _parse_err = _read_stdin_json()
    _config, active, _err = _build_config(payload.get("cwd") or ".")
    if not active:
        _emit({})
        return 0
    result = failure_notice(payload, config)
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
    "state-gate": cmd_state_gate,
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
                "permissionDecision": PERMISSION_ASK,
                "permissionDecisionReason": "harness hook error: %s" % e,
            }})
        else:
            _emit({})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
