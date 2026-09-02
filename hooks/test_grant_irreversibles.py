"""The batch grant, half B (norm § 6.1): the irreversible classes.

What changes against 0.6 is the direction of the ceremony: a deletion the
person approved WITH its dependents in view does not re-prompt per call --
that is the batch authorization the harness exists to give -- and what
protects it is anti-TOCTOU: the dependents re-consulted just before
executing must match the snapshot the person saw, or the question comes
back. Data deletions whose row impact could not be measured do not pass the
grant at all, and process starts are their own granted class.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from test_grant import GRANT, gate, signed_cfg

UUID = "_uuid-vieja"


def deletion_cfg(root, snapshot, fresh, **over):
    """A task scope whose grant approves deleting UUID with `snapshot` in
    view, and whose evidence carries `fresh` as the re-consulted answer."""
    grant = dict(GRANT, objects=[UUID], deletions={UUID: snapshot})
    c = signed_cfg(root, kind="task", intent=None, allowedObjects=[UUID],
                   grant=grant, **over)
    if fresh is not None:
        d = os.path.join(c["evidenceDir"], "F-listados")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "dependents.json"), "w", encoding="utf-8") as f:
            json.dump({UUID: fresh}, f)
    return c


class TestAGrantedDeletionDoesNotRePrompt(unittest.TestCase):
    def test_matching_fresh_dependents_let_the_deletion_flow(self):
        with tempfile.TemporaryDirectory() as root:
            c = deletion_cfg(root, snapshot=["dep-1", "dep-2"],
                             fresh=["dep-2", "dep-1"])
            out = gate(c, "mcp__appian-dev__deleteInterface", uuid=UUID)
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_changed_dependents_bring_the_question_back(self):
        # Anti-TOCTOU (§ 6.1): the person approved a snapshot; if the world
        # moved, the approval no longer describes it.
        with tempfile.TemporaryDirectory() as root:
            c = deletion_cfg(root, snapshot=["dep-1"],
                             fresh=["dep-1", "dep-NUEVO"])
            out = gate(c, "mcp__appian-dev__deleteInterface", uuid=UUID)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("dep-NUEVO", out["permissionDecisionReason"])

    def test_no_fresh_reconsult_is_not_the_same_as_no_dependents(self):
        with tempfile.TemporaryDirectory() as root:
            c = deletion_cfg(root, snapshot=["dep-1"], fresh=None)
            out = gate(c, "mcp__appian-dev__deleteInterface", uuid=UUID)
            self.assertEqual(out["permissionDecision"], "ask")

    def test_a_deletion_outside_the_granted_class_asks(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=[UUID],
                           grant=dict(GRANT, objects=[UUID], deletions={}))
            out = gate(c, "mcp__appian-dev__deleteInterface", uuid=UUID)
            self.assertEqual(out["permissionDecision"], "ask")


class TestDataDeletionImpactIsRowsNotDesign(unittest.TestCase):
    def test_an_unmeasured_row_impact_does_not_pass_the_grant(self):
        # `listRecordData` is {uuid, limit, offset}: it neither filters nor
        # counts, so an unavailable count is NOT MEASURED and blocks (§ 6.1).
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["_rt-1"],
                           grant=dict(GRANT, objects=["_rt-1"],
                                      deletions={"_rt-1": []}))
            out = gate(c, "mcp__appian-dev__deleteRecordData",
                       uuid="_rt-1", csvData="id\n1")
            self.assertEqual(out["permissionDecision"], "ask")

    def test_a_measured_row_impact_flows(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["_rt-1"],
                           grant=dict(GRANT, objects=["_rt-1"],
                                      deletions={"_rt-1": {"rows": 42}}))
            out = gate(c, "mcp__appian-dev__deleteRecordData",
                       uuid="_rt-1", csvData="id\n1")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))


class TestProcessStartsAreTheirOwnClass(unittest.TestCase):
    def test_a_granted_start_flows_without_an_objects_entry(self):
        # A start is not an object edit: § 6.1 lists it as its own
        # irreversible class, so demanding it in allowedObjects would
        # fabricate a false ask.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["GDE_INT_Lista"],
                           grant=dict(GRANT, processStarts=["_pm-alta"]))
            out = gate(c, "mcp__appian__appian_invoke_process_model",
                       uuid="_pm-alta")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_an_ungranted_start_asks(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["GDE_INT_Lista"],
                           grant=dict(GRANT, processStarts=[]))
            out = gate(c, "mcp__appian__appian_invoke_process_model",
                       uuid="_pm-alta")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("processStarts", out["permissionDecisionReason"])


class TestExtensionsExtendCoverage(unittest.TestCase):
    def test_an_extension_object_is_granted_coverage(self):
        # § 6.3: the one extension per scope, written by the hook from the
        # observed answer, extends what the write may touch.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root,
                           allowedObjects=["GDE_INT_Lista", "_uuid-extra"],
                           grant=dict(GRANT, extensions=[
                               {"objects": ["_uuid-extra"],
                                "finding": "certify: el filtro vive en la otra "
                                           "interfaz",
                                "grantedAt": "2026-09-02T11:00:00Z"}]))
            out = gate(c, "mcp__appian-dev__updateInterface", uuid="_uuid-extra")
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))


if __name__ == "__main__":
    unittest.main()
