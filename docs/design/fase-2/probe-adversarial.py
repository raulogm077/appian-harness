# Sonda adversarial de la Fase 2: martillea los gates con payloads hostiles
# y comprueba dos invariantes, sin mirar cómo está implementado nada:
#   I1  ninguna escritura MCP sobre alcance v07 llega a "allow" sin un grant
#       válido de su instancia (o sin alcance firmado)
#   I2  ningún estado terminal escrito por el agente se acepta como válido:
#       o se revierte, o el gate pregunta; y el closure no aprueba un cierre
#       limpio que el hook no haya firmado
import itertools, json, os, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
REPO = r"C:\Users\rgmoya\Desktop\Proyecto Claude Code Cowork\appian-harness"
sys.path.insert(0, os.path.join(REPO, "hooks"))
sys.path.insert(0, os.path.join(REPO, "scripts"))
import harness_hooks as HH

FAILS = []


def check(name, condition, detail=""):
    if not condition:
        FAILS.append("%s: %s" % (name, detail))


def base_scope(**over):
    s = {"schemaVersion": 2, "id": "F-x", "instanceId": "i-1", "kind": "micro",
         "risk": None, "status": "in-flight", "statusWriteSeq": 0,
         "request": None, "intent": "x", "tasks": None,
         "allowedObjects": ["OBJ", "_u1"], "grant": None,
         "suspendedScope": None, "resumeFrom": None,
         "manualEstimateMinutes": None, "openedAt": "2026-09-02T00:00:00Z",
         "closedAt": None}
    s.update(over)
    return s


def cfg(root, scope):
    c = {"pluginRoot": root, "evidenceDir": os.path.join(root, "evidence"),
         "activeTask": scope, "maxAllowedObjects": 3,
         "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
         "projectRoot": root,
         "configPath": os.path.join(root, ".claude", "appian-harness.json"),
         "activeTaskFile": os.path.join(root, "tasks", "current.json")}
    os.makedirs(os.path.dirname(c["activeTaskFile"]), exist_ok=True)
    with open(c["activeTaskFile"], "w", encoding="utf-8") as f:
        json.dump(scope, f)
    return c


def observe(c):
    return HH.state_gate({"tool_name": "Write",
                          "tool_input": {"file_path": c["activeTaskFile"]}}, c)


GRANTS = [
    None,
    {},                                     # sin instanceId
    {"instanceId": "i-OTRA", "objects": ["OBJ"]},
    {"instanceId": "i-1", "objects": ["OBJ"],
     "permissionMode": "bypassPermissions"},
    [],                                     # tipo equivocado
    "grant",
]
NASTY_INPUTS = [
    None, [], "x", 42,
    {}, {"name": ""}, {"name": None}, {"uuid": 42}, {"uuid": ["_u1"]},
    {"name": "OBJ\u0000"}, {"name": "obj"},   # case distinto: no concedido
    {"uuid": "_u1", "name": "OBJ"},
]
TOOLS = ["mcp__appian-dev__updateInterface", "mcp__appian-dev__createConstant",
         "mcp__appian-dev__deleteConstant", "mcp__appian__appian_invoke_process_model",
         "mcp__appian-dev__updateObjectSecurity"]

# --- I1: allow sin grant válido -----------------------------------------
for grant, tool, tin in itertools.product(GRANTS, TOOLS, NASTY_INPUTS):
    with tempfile.TemporaryDirectory() as root:
        scope = base_scope(grant=grant)
        c = cfg(root, scope)
        observe(c)  # firmar la apertura (el flujo real la firma)
        out = HH.scope_gate({"tool_name": tool, "session_id": "s",
                             "tool_use_id": "t", "tool_input": tin}, c)
        check("I1", out.get("permissionDecision") != "allow",
              "allow con grant=%r tool=%s input=%r" % (grant, tool, tin))

# grant válido pero objetivo fuera / creación no concedida / tipo cambiado
VALID = {"instanceId": "i-1", "objects": ["OBJ", "_u1"],
         "creates": [{"name": "NUEVA", "type": "expressionRule",
                      "status": "to-be-created"}],
         "collisions": [], "deletions": {}, "processStarts": [],
         "extensions": [], "grantedBy": "R", "grantedAt": "t",
         "permissionMode": "default"}
CASES_MUST_NOT_ALLOW = [
    ("mcp__appian-dev__updateInterface", {"uuid": "_uFUERA"}),
    ("mcp__appian-dev__createExpressionRule", {"name": "OTRA"}),
    ("mcp__appian-dev__createWebApi", {"name": "NUEVA"}),      # tipo cambiado
    ("mcp__appian-dev__deleteConstant", {"uuid": "_u1"}),      # sin deletions
    ("mcp__appian__appian_invoke_process_model", {"uuid": "_pm"}),  # sin starts
    ("mcp__appian-dev__deleteRecordData", {"uuid": "_u1"}),    # sin conteo
    ("mcp__appian-dev__addRecordTypeField", {"uuid": "_u1"}),  # micro < task
]
for tool, tin in CASES_MUST_NOT_ALLOW:
    with tempfile.TemporaryDirectory() as root:
        c = cfg(root, base_scope(grant=dict(VALID)))
        observe(c)
        out = HH.scope_gate({"tool_name": tool, "session_id": "s",
                             "tool_use_id": "t", "tool_input": tin}, c)
        check("I1b", out.get("permissionDecision") == "ask",
              "%s %r -> %r" % (tool, tin, out.get("permissionDecision")))

# --- I2: terminales sin firma -------------------------------------------
TERMINALS = ["closed", "closed-pending-human", "closed-with-debt", "abandoned"]
for terminal in TERMINALS:
    # (a) fichero nacido terminal: no se firma y el gate pregunta
    with tempfile.TemporaryDirectory() as root:
        c = cfg(root, base_scope(status=terminal, grant=dict(VALID)))
        observe(c)
        out = HH.scope_gate({"tool_name": TOOLS[0], "session_id": "s",
                             "tool_input": {"uuid": "_u1"}}, c)
        check("I2a", out.get("permissionDecision") == "ask",
              "%s nacido terminal -> %r" % (terminal, out))
        closure = HH.closure_gate({}, c)
        # el closure aprueba (no hay alcance a efectos del gate) pero NO debe
        # haber escrito una transición que lo legitime
        rows = HH._read_jsonl(os.path.join(c["evidenceDir"],
                                           "gate-decisions.jsonl"))
        check("I2a2", not any(r.get("event") == "transition"
                              and r.get("to") == terminal for r in rows),
              "%s: el hook firmó un terminal que no produjo" % terminal)
    # (b) alcance firmado in-flight; el agente escribe el terminal a mano
    with tempfile.TemporaryDirectory() as root:
        c = cfg(root, base_scope(grant=dict(VALID)))
        observe(c)
        scope = json.load(open(c["activeTaskFile"], encoding="utf-8"))
        scope["status"] = terminal
        scope["statusWriteSeq"] = 41
        with open(c["activeTaskFile"], "w", encoding="utf-8") as f:
            json.dump(scope, f)
        c2 = dict(c, activeTask=scope)
        observe(c2)
        after = json.load(open(c2["activeTaskFile"], encoding="utf-8"))
        check("I2b", after["status"] == "in-flight",
              "%s a mano no revertido: %r" % (terminal, after["status"]))

# (c) el agente falsifica proyección + fichero con Write (ambos observados):
# la contaminación debe dejar la escritura siguiente en ask
with tempfile.TemporaryDirectory() as root:
    c = cfg(root, base_scope(grant=dict(VALID)))
    observe(c)
    fake = {"instanceId": "i-1",
            "scope": base_scope(status="closed", statusWriteSeq=9,
                                grant=dict(VALID)),
            "signedAt": "2026-09-02T00:00:00Z"}
    proj_path = os.path.join(c["evidenceDir"], "scope-projection.json")
    with open(proj_path, "w", encoding="utf-8") as f:
        json.dump(fake, f)
    HH.state_gate({"tool_name": "Write",
                   "tool_input": {"file_path": proj_path}}, c)  # observado
    scope = base_scope(status="closed", statusWriteSeq=9, grant=dict(VALID))
    with open(c["activeTaskFile"], "w", encoding="utf-8") as f:
        json.dump(scope, f)
    c2 = dict(c, activeTask=scope)
    HH.state_gate({"tool_name": "Write",
                   "tool_input": {"file_path": c2["activeTaskFile"]}}, c2)
    out = HH.scope_gate({"tool_name": TOOLS[0], "session_id": "s",
                         "tool_input": {"uuid": "_u1"}}, c2)
    check("I2c", out.get("permissionDecision") == "ask",
          "proyección falsificada via Write no contamina: %r" % out)

# --- crash-safety: nada de esto debe lanzar excepción -------------------
print("FALLOS: %d" % len(FAILS))
for f in FAILS:
    print(" -", f[:300])
