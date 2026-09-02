"""The batch grant, half A (norm § 6.1): identity, creates with a type, and
the contract's anchoring -- one prompt covers the whole scope, and what makes
that safe is that every write is checked against what the person actually saw.

The false-ask half matters as much as the ask half: `appUuid`, parent folders
and the record-type references inside field/view/action calls are CONTEXT,
not targets, or every create would prompt (§ 6.1). The corpus test at the
bottom is the deterministic half of the DoD's "no false ask over the corpus":
for every real write tool, the extractor knows which property names its
mutated target.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import _target_keys, _tool_action, scope_gate, state_gate
from test_harness_hooks import (cfg, make_plugin_root, write_design_verdict,
                                write_skill_record)
from test_scope_schema import v2_scope

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                      "docs", "design", "fase-0",
                      "appian-dev-tools-2026-09-01.json")

GRANT = {
    "instanceId": "inst-1",
    "objects": ["GDE_INT_Lista", "_uuid-lista"],
    "creates": [{"name": "GDE_QRY_Nueva", "type": "expressionRule",
                 "status": "to-be-created"}],
    "collisions": [],
    "deletions": {},
    "processStarts": [],
    "extensions": [],
    "grantedBy": "Raúl",
    "grantedAt": "2026-09-02T10:00:00Z",
    "permissionMode": "default",
}


def signed_cfg(root, **scope_over):
    """A signed v07 scope with grant, skill record and design verdict: the
    fixture where a write SHOULD flow, so each test breaks one thing."""
    scope_over.setdefault("grant", dict(GRANT))
    scope_over.setdefault("allowedObjects", ["GDE_INT_Lista", "_uuid-lista"])
    scope = v2_scope(**scope_over)
    make_plugin_root(root)
    write_skill_record(root, scope["id"])
    write_design_verdict(root, scope["id"])
    c = cfg(root, activeTask=scope)
    path = c["activeTaskFile"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scope, f)
    state_gate({"tool_name": "Write", "tool_input": {"file_path": path}}, c)
    return c


def gate(c, tool, **tool_input):
    return scope_gate({"tool_name": tool, "session_id": "s-1",
                       "tool_input": tool_input}, c)


class TestAWriteWithoutAGrantAsks(unittest.TestCase):
    def test_no_grant_is_the_authorization_question_itself(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, grant=None)
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="_uuid-lista")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("grant", out["permissionDecisionReason"])

    def test_a_grant_from_another_instance_is_no_grant(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, grant=dict(GRANT, instanceId="inst-OLD"))
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="_uuid-lista")
            self.assertEqual(out["permissionDecision"], "ask")

    def test_bypass_permissions_did_not_come_from_a_person(self):
        # § 6.1: the hook records the mode and does not treat the grant as
        # human-approved when the whole permission system was off.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, grant=dict(GRANT,
                                            permissionMode="bypassPermissions"))
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="_uuid-lista")
            self.assertEqual(out["permissionDecision"], "ask")

    def test_a_granted_write_flows(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="_uuid-lista")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))


class TestCreatesCarryTheirType(unittest.TestCase):
    def _task_cfg(self, root, creates):
        return signed_cfg(root, kind="task", intent=None,
                          allowedObjects=["GDE_QRY_Nueva"],
                          grant=dict(GRANT, objects=[], creates=creates))

    def test_a_granted_create_with_the_right_type_flows(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._task_cfg(root, [{"name": "GDE_QRY_Nueva",
                                       "type": "expressionRule",
                                       "status": "to-be-created"}])
            out = gate(c, "mcp__appian-dev__createExpressionRule",
                       name="GDE_QRY_Nueva", expression="1+1")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_the_person_approved_a_surface_not_a_string(self):
        # § 6.1: a name approved as an expression rule must not be created
        # as something else.
        with tempfile.TemporaryDirectory() as root:
            c = self._task_cfg(root, [{"name": "GDE_QRY_Nueva",
                                       "type": "connectedSystem",
                                       "status": "to-be-created"}])
            out = gate(c, "mcp__appian-dev__createExpressionRule",
                       name="GDE_QRY_Nueva", expression="1+1")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("connectedSystem", out["permissionDecisionReason"])

    def test_an_ungranted_create_asks(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._task_cfg(root, [])
            out = gate(c, "mcp__appian-dev__createExpressionRule",
                       name="GDE_QRY_Otra", expression="1+1")
            self.assertEqual(out["permissionDecision"], "ask")


class TestContextKeysDoNotNeedAConcession(unittest.TestCase):
    def test_a_parent_folder_is_context_not_a_second_object(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["GDE_QRY_Nueva"],
                           grant=dict(GRANT, objects=[]))
            out = gate(c, "mcp__appian-dev__createExpressionRule",
                       name="GDE_QRY_Nueva", parentFolderUuid="_folder-9",
                       expression="1+1")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_a_field_write_targets_its_record_type(self):
        # Real schema (P6): addRecordTypeField's `uuid` IS the record type;
        # `fieldName` is a property of the change, not a second object.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["_rt-1"],
                           grant=dict(GRANT, objects=["_rt-1"]))
            out = gate(c, "mcp__appian-dev__addRecordTypeField",
                       uuid="_rt-1", fieldName="estado", fieldType="TEXT")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))


class TestTheMinimumKindIsImposed(unittest.TestCase):
    def test_a_record_type_write_does_not_fit_in_micro(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, allowedObjects=["_rt-1"],
                           grant=dict(GRANT, objects=["_rt-1"]))
            out = gate(c, "mcp__appian-dev__addRecordTypeField",
                       uuid="_rt-1", fieldName="estado")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("micro", out["permissionDecisionReason"])


class TestAtomicityIsPerTasksEntry(unittest.TestCase):
    def test_a_partitioned_task_is_measured_entry_by_entry(self):
        # § 15: maxAllowedObjects is evaluated per tasks{} entry, never on
        # the union -- a five-task feature of two objects each is atomic.
        objects = ["O%d" % i for i in range(10)]
        tasks = {"T-%d" % i: objects[2 * i:2 * i + 2] for i in range(5)}
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None, tasks=tasks,
                           allowedObjects=objects,
                           grant=dict(GRANT, objects=objects))
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="O1")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_one_oversized_entry_still_asks(self):
        objects = ["O%d" % i for i in range(5)]
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           tasks={"T-1": objects},
                           allowedObjects=objects,
                           grant=dict(GRANT, objects=objects))
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="O1")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("atomic", out["permissionDecisionReason"].lower())


class TestTheExtractorKnowsTheRealCorpus(unittest.TestCase):
    def test_every_write_tool_declares_a_target_the_schema_carries(self):
        # The deterministic half of "no false ask over the corpus": a write
        # tool whose target keys name no property of its real schema is a
        # tool the gate can never match -- a guaranteed false ask.
        with open(CORPUS, encoding="utf-8") as f:
            tools = json.load(f)["tools"]
        from harness_hooks import _is_write_tool
        misses = []
        for tool in tools:
            name = "mcp__appian-dev__" + tool["name"]
            if not _is_write_tool(name):
                continue
            props = set((tool.get("inputSchema") or {}).get("properties") or {})
            keys = _target_keys(_tool_action(name))
            if not props & set(keys):
                misses.append("%s: target keys %r vs properties %r"
                              % (tool["name"], keys, sorted(props)))
        self.assertEqual(misses, [])


if __name__ == "__main__":
    unittest.main()
