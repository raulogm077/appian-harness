"""The two defects P2-PASADA-7 demonstrated, each pinned on the path that failed.

Defect 1 -- the hook payload's `cwd` is the session's CURRENT directory, not
the project root, and a `cd` inside a Bash call moves it for the rest of the
session. Every hook fired afterwards arrived pointing at a subdirectory, found
no `.claude/appian-harness.json` there, and read the project as UNCONFIGURED:
`state-gate` observed the Edit that carried the grant and returned `{}` without
signing it, the later `request: "close"` was never signed either, and the scope
never reached `closing` or `closed`. Measured: two `PostToolUse:Edit` hook rows
with `cwd` = `evidence/P2-PASADA-7`, stdout `{}`, exit 0.

These tests therefore drive the SUBCOMMANDS over stdin, with a drifted `cwd`,
because that is where the failure lived -- `state_gate()` called directly with
a hand-built config never saw it.

Defect 2 -- `maxAllowedObjects` counted ENTRIES of `allowedObjects`. Section 4.1
lets one object be named by name, by UUID or by both, so two objects declared as
name+UUID counted as four and blew a budget of three.
"""
import json, os, subprocess, sys, tempfile, unittest

HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOOKS_DIR)
sys.path.insert(0, os.path.join(HOOKS_DIR, "..", "scripts"))
import harness_hooks as HH
from test_floor import interface_floor_batch

SCRIPT = os.path.join(HOOKS_DIR, "harness_hooks.py")

TASK = "P2-REGRESION"
INSTANCE = "inst-regresion"
# The two real objects of P2-PASADA-7, in both of their faces.
NAME_A = "PR_Rental_PricePerDay_Input"
UUID_A = "_a-0000ee07-114d-8000-9c40-011c48011c48_2143653"
NAME_B = "PR_Rental_RentalId_ReadOnly"
UUID_B = "_a-0000ee07-114d-8000-9c40-011c48011c48_2143222"
FOUR_ALIASES_TWO_OBJECTS = [NAME_A, UUID_A, NAME_B, UUID_B]

WRITE_TOOL = "mcp__appian-dev__updateInterface"

GRANT = {
    "instanceId": INSTANCE,
    "objects": list(FOUR_ALIASES_TWO_OBJECTS),
    "creates": [],
    "collisions": [],
    "deletions": {},
    "processStarts": [],
    "extensions": [],
    "grantedBy": "Raul",
    "grantedAt": "2026-09-04T10:56:10Z",
}


def scope(**over):
    s = {
        "schemaVersion": 2,
        "id": TASK,
        "instanceId": INSTANCE,
        "kind": "task",
        "risk": None,
        "status": "in-flight",
        "statusWriteSeq": 0,
        "request": None,
        "intent": "cambiar el literal de label de las dos interfaces fragmento",
        "tasks": None,
        "allowedObjects": list(FOUR_ALIASES_TWO_OBJECTS),
        "grant": None,
        "suspendedScope": None,
        "resumeFrom": None,
        "manualEstimateMinutes": None,
        "openedAt": "2026-09-04T10:54:32Z",
        "closedAt": None,
    }
    s.update(over)
    return s


def make_project(root, max_allowed=3, task_id=TASK):
    """A configured project, plus the evidence a write needs: the official
    skill's load record and a passing design verdict."""
    os.makedirs(os.path.join(root, ".claude"))
    with open(os.path.join(root, ".claude", "appian-harness.json"), "w",
              encoding="utf-8") as f:
        json.dump({"evidenceDir": "evidence",
                   "activeTaskFile": os.path.join("tasks", "current.json"),
                   "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
                   "maxAllowedObjects": max_allowed}, f)
    refs = os.path.join(root, "skills", "appian-best-practices", "references")
    os.makedirs(refs)
    with open(os.path.join(refs, "06-security.md"), "w", encoding="utf-8") as f:
        f.write("# Security\n\n## Record level security\nBody.\n")
    task_dir = os.path.join(root, "evidence", task_id)
    os.makedirs(task_dir)
    with open(os.path.join(task_dir, "appian-skill-loaded.json"), "w",
              encoding="utf-8") as f:
        json.dump({"task": task_id, "skill": "appian",
                   "source": "github.com/appian/dev-mcp-skills",
                   "appianVersion": "26.7", "docsMcp": "appian-docs"}, f)
    with open(os.path.join(task_dir, "practices-design.json"), "w",
              encoding="utf-8") as f:
        json.dump({"task": task_id, "phase": "design", "verdict": "PASS",
                   "referencesApplied": ["06-security.md#record-level-security"],
                   "findings": []}, f)
    os.makedirs(os.path.join(root, "tasks"))
    return task_dir


def task_file(root):
    return os.path.join(root, "tasks", "current.json")


def put_scope(root, s):
    with open(task_file(root), "w", encoding="utf-8") as f:
        json.dump(s, f)


def read_scope(root):
    with open(task_file(root), encoding="utf-8") as f:
        return json.load(f)


def projection(root):
    path = os.path.join(root, "evidence", "scope-projection.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def evidence_writes(root):
    path = os.path.join(root, "evidence", "evidence-writes.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


_UNSET = object()


def run(subcommand, payload, root, project_dir=_UNSET):
    """One real hook invocation: the subcommand, its stdin payload, its env.

    `CLAUDE_PROJECT_DIR` is REMOVED unless a test sets it, so a pass here is
    the cwd resolution doing the work and not an environment variable that
    happens to be exported into the test runner.
    """
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    if project_dir is not _UNSET:
        env["CLAUDE_PROJECT_DIR"] = project_dir
    env["CLAUDE_PLUGIN_ROOT"] = root
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.Popen([sys.executable, SCRIPT, subcommand],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)
    out, err = proc.communicate(json.dumps(payload).encode("utf-8"))
    if proc.returncode != 0:
        raise AssertionError("%s exited %d: %s" % (subcommand, proc.returncode,
                                                   err.decode("utf-8", "replace")))
    return json.loads(out.decode("utf-8"))


def drifted(root, task_id=TASK):
    """The exact cwd P2-PASADA-7 drifted into: the task's evidence folder."""
    return os.path.join(root, "evidence", task_id)


def file_write(root, cwd, tool="Edit", permission_mode="default"):
    return run("state-gate",
               {"tool_name": tool, "cwd": cwd, "permission_mode": permission_mode,
                "tool_input": {"file_path": task_file(root)},
                "tool_response": {"success": True}},
               root)


def appian_write(root, cwd, target=UUID_A, permission_mode="default",
                 tool_use_id="toolu_1"):
    return run("scope-gate",
               {"tool_name": WRITE_TOOL, "cwd": cwd, "session_id": "s-1",
                "permission_mode": permission_mode, "tool_use_id": tool_use_id,
                "tool_input": {"uuid": target, "expression": "a!textField()"}},
               root)


def appian_write_landed(root, cwd, target=UUID_A, tool_use_id="toolu_1"):
    """The PostToolUse half: it resolves the reservation the gate opened.

    Without it the write stays `pending` in operations.jsonl and section 7.1
    legitimately refuses to close -- so the cycle test has to run both halves
    or it would be proving the wrong thing.
    """
    return run("log-write",
               {"tool_name": WRITE_TOOL, "cwd": cwd,
                "tool_use_id": tool_use_id,
                "tool_input": {"uuid": target, "expression": "a!textField()"},
                "tool_response": {"uuid": target}},
               root)


def appian_reads_credited(root, cwd, target=UUID_A):
    """The PostToolBatch half: it credits the floor of § 8.

    Without it the scope wrote and never read, and the closure gate
    legitimately refuses to close -- so the cycle test has to run this leg
    too or it would be proving the wrong thing.
    """
    return run("observe-reads",
               {"cwd": cwd, "tool_calls": interface_floor_batch(target)},
               root)


def appian_certified(root, target=UUID_A):
    """The judge's half: a `task` buys one certify, and the close reads it.

    Written straight to disk because that is what a subagent does -- the
    judge holds no MCP and reaches the harness through its verdict file, not
    through a hook.
    """
    from test_certify import write_certify
    return write_certify({"evidenceDir": os.path.join(root, "evidence")},
                         read_scope(root), objects=[target])


def stop(root, cwd):
    return run("closure-gate", {"cwd": cwd, "stop_hook_active": False}, root)


# --- Defect 1 -------------------------------------------------------------

class TestTheProjectRootSurvivesADriftedCwd(unittest.TestCase):
    """The five steps of the pass, every hook fired from the drifted cwd."""

    def test_the_whole_cycle_signs_from_a_subdirectory(self):
        with tempfile.TemporaryDirectory() as root:
            make_project(root)
            here = drifted(root)

            # 1. Opening: signed, even though the hook is fired from
            #    evidence/<task>/ and not from the project root.
            put_scope(root, scope())
            out = file_write(root, here, tool="Write")
            self.assertIn("opened and signed", json.dumps(out),
                          "the opening was not signed")
            self.assertEqual(projection(root)["scope"]["status"], "in-flight")
            self.assertEqual([r["target"] for r in evidence_writes(root)],
                             ["active-task"],
                             "the drifted write was not even logged")

            # 2. The Edit that adds the grant: the projection must carry it,
            #    with the permission mode sealed from the payload.
            put_scope(root, scope(grant=dict(GRANT)))
            file_write(root, here)
            signed_grant = projection(root)["scope"]["grant"]
            self.assertIsNotNone(signed_grant,
                                 "the grant was written but never signed")
            self.assertEqual(signed_grant["objects"], FOUR_ALIASES_TWO_OBJECTS)
            self.assertEqual(signed_grant.get("permissionMode"), "default")

            # 3. A write between grant and close: no ask, and in particular
            #    no ask for a missing permissionMode.
            decision = appian_write(root, here)["hookSpecificOutput"]
            self.assertEqual(decision["permissionDecision"], "allow",
                             decision.get("permissionDecisionReason"))
            appian_write_landed(root, here)
            appian_reads_credited(root, here)
            appian_certified(root)

            # 4. The Edit that asks to close: signed into `closing`.
            current = read_scope(root)
            put_scope(root, dict(current, request="close"))
            file_write(root, here)
            self.assertEqual(projection(root)["scope"]["status"], "closing")

            # 5. Stop: signed into `closed`.
            self.assertEqual(stop(root, here)["decision"], "approve")
            self.assertEqual(projection(root)["scope"]["status"], "closed")
            self.assertIsNotNone(projection(root)["scope"]["closedAt"])

    def test_a_grant_edit_from_the_root_still_signs(self):
        # The exact-cwd hit stays first in the resolution order, so a project
        # that already worked keeps its answer unchanged.
        with tempfile.TemporaryDirectory() as root:
            make_project(root)
            put_scope(root, scope())
            file_write(root, root, tool="Write")
            put_scope(root, scope(grant=dict(GRANT)))
            file_write(root, root)
            self.assertIsNotNone(projection(root)["scope"]["grant"])

    def test_a_cwd_outside_the_tree_falls_back_to_the_session_root(self):
        # The P7 session also moved into ~/.claude/projects/... to read its
        # own transcript: no ancestor of that path is the project, so the only
        # anchor left is the root Claude Code was started in.
        with tempfile.TemporaryDirectory() as root:
            with tempfile.TemporaryDirectory() as elsewhere:
                make_project(root)
                put_scope(root, scope())
                file_write(root, elsewhere, tool="Write")
                self.assertIsNone(projection(root),
                                  "without CLAUDE_PROJECT_DIR there is nothing "
                                  "to resolve to and nothing may be signed")
                run("state-gate",
                    {"tool_name": "Write", "cwd": elsewhere,
                     "permission_mode": "default",
                     "tool_input": {"file_path": task_file(root)}},
                    root, project_dir=root)
                self.assertEqual(projection(root)["scope"]["status"], "in-flight")

    def test_an_unconfigured_directory_stays_inactive(self):
        # The walk must not invent a project: a tree with no config anywhere
        # above it is still "not configured", which is what makes every hook
        # allow instead of gate.
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "sub"))
            out = run("scope-gate",
                      {"tool_name": WRITE_TOOL, "cwd": os.path.join(root, "sub"),
                       "tool_input": {"uuid": UUID_A}}, root)
            self.assertEqual(out["hookSpecificOutput"]["permissionDecision"],
                             "allow")
            self.assertIn("not configured",
                          out["hookSpecificOutput"]["permissionDecisionReason"])

    def test_the_closure_gate_no_longer_approves_in_silence_when_drifted(self):
        # The 11:11 Stop of P2-PASADA-7: fired from evidence/<task>/, it
        # returned a bare approve because the project read as unconfigured,
        # hiding a scope that had written twice and never closed.
        with tempfile.TemporaryDirectory() as root:
            make_project(root)
            put_scope(root, scope(grant=dict(GRANT)))
            file_write(root, drifted(root), tool="Write")
            appian_write(root, drifted(root))
            appian_write_landed(root, drifted(root))
            out = stop(root, drifted(root))
            self.assertIn("still in flight", out.get("systemMessage", ""),
                          "a drifted Stop approved without a word")


class TestTheResolverItself(unittest.TestCase):
    def test_it_walks_up_to_the_configured_root(self):
        with tempfile.TemporaryDirectory() as root:
            make_project(root)
            deep = os.path.join(root, "evidence", TASK)
            self.assertEqual(os.path.normcase(HH._resolve_project_root(deep)),
                             os.path.normcase(os.path.abspath(root)))

    def test_it_returns_an_unconfigured_path_untouched(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(HH._resolve_project_root(root), root)


# --- Defect 2 -------------------------------------------------------------

class TestTheBudgetCountsObjectsNotAliases(unittest.TestCase):
    def test_two_objects_as_name_plus_uuid_count_as_two(self):
        self.assertEqual(HH._canonical_object_count(FOUR_ALIASES_TWO_OBJECTS), 2)

    def test_repeated_aliases_do_not_raise_the_count(self):
        noisy = FOUR_ALIASES_TWO_OBJECTS + [NAME_A, UUID_A, NAME_B, UUID_B, NAME_A]
        self.assertEqual(HH._canonical_object_count(noisy), 2)

    def test_four_real_objects_still_break_a_budget_of_three(self):
        four = ["RGM_INT_A", "RGM_INT_B", "RGM_INT_C", "RGM_INT_D"]
        self.assertEqual(HH._canonical_object_count(four), 4)

    def test_a_name_is_not_mistaken_for_a_uuid(self):
        # The shape test is what keeps the two buckets apart, so it is worth
        # pinning on the two UUID forms Appian actually returns.
        self.assertTrue(HH._UUID_SHAPE.search(UUID_A))
        self.assertTrue(HH._UUID_SHAPE.search(
            "dad2b319-fee0-4114-90c7-2b64045f56cb"))
        self.assertFalse(HH._UUID_SHAPE.search(NAME_A))
        self.assertFalse(HH._UUID_SHAPE.search("RGM_INT_Lista_De_Alquileres"))


class TestTheBudgetAtTheGate(unittest.TestCase):
    """The same cases through scope-gate, which is where P7 got its ask."""

    def _gate(self, root, allowed, target=UUID_A, max_allowed=3, grant=None):
        make_project(root, max_allowed=max_allowed)
        g = dict(GRANT, objects=list(allowed)) if grant is None else grant
        put_scope(root, scope(allowedObjects=list(allowed), grant=g))
        file_write(root, root, tool="Write")
        return appian_write(root, root, target=target)["hookSpecificOutput"]

    def test_two_objects_in_four_entries_are_atomic(self):
        with tempfile.TemporaryDirectory() as root:
            out = self._gate(root, FOUR_ALIASES_TWO_OBJECTS)
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_restating_an_alias_does_not_break_the_budget(self):
        with tempfile.TemporaryDirectory() as root:
            out = self._gate(root, FOUR_ALIASES_TWO_OBJECTS + [NAME_A, UUID_B])
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_four_objects_are_not_atomic(self):
        four = [NAME_A, UUID_A, NAME_B, UUID_B,
                "RGM_INT_Tercera",
                "_a-0000ee07-114d-8000-9c40-011c48011c48_3000001",
                "RGM_INT_Cuarta",
                "_a-0000ee07-114d-8000-9c40-011c48011c48_3000002"]
        with tempfile.TemporaryDirectory() as root:
            out = self._gate(root, four)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("not atomic", out["permissionDecisionReason"])
            self.assertIn("4 objects (8 entries)", out["permissionDecisionReason"])

    def test_the_looser_count_does_not_let_an_ungranted_object_through(self):
        # The fix touches the BUDGET only. Membership in allowedObjects and in
        # the grant is untouched, and it is what actually contains a write.
        with tempfile.TemporaryDirectory() as root:
            out = self._gate(root, FOUR_ALIASES_TWO_OBJECTS,
                             target="_a-0000ee07-114d-8000-9c40-011c48011c48_9999999")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("alcance concedido", out["permissionDecisionReason"])

    def test_an_object_in_scope_but_outside_the_grant_still_asks(self):
        with tempfile.TemporaryDirectory() as root:
            out = self._gate(root, FOUR_ALIASES_TWO_OBJECTS, target=UUID_B,
                             grant=dict(GRANT, objects=[NAME_A, UUID_A]))
            self.assertEqual(out["permissionDecision"], "ask")

    def test_the_budget_is_per_tasks_entry_and_counts_objects_there_too(self):
        # Prueba 3 will exercise this one: the same defect lived in the
        # per-entry branch.
        with tempfile.TemporaryDirectory() as root:
            make_project(root)
            tasks = {"T-1": [NAME_A, UUID_A], "T-2": [NAME_B, UUID_B]}
            put_scope(root, scope(tasks=tasks, grant=dict(GRANT)))
            file_write(root, root, tool="Write")
            out = appian_write(root, root)["hookSpecificOutput"]
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))


if __name__ == "__main__":
    unittest.main()
