"""The 0.7 unit of scope: schema v2, the seven states, and the § 15 dispatch.

Two rulebooks coexist on purpose. A scope file without `schemaVersion` opened
under 0.6 and closes under 0.6 -- the whole legacy path stays reachable -- and
one with `schemaVersion: 2` is validated against the closed schema of § 4.1.
The failure this catches: a v2 scope with a typoed field, a state outside the
seven, or a version nobody defined, silently treated as valid.
"""
import os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import (SCOPE_STATUSES, STATUS_ABANDONED, STATUS_CLOSING,
                           STATUS_SUSPENDED, _scope_policy, _scope_schema_errors,
                           scope_gate)
from test_harness_hooks import cfg


def v2_scope(**over):
    scope = {
        "schemaVersion": 2,
        "id": "F-listados",
        "instanceId": "inst-1",
        "kind": "micro",
        "risk": None,
        "status": "in-flight",
        "statusWriteSeq": 0,
        "request": None,
        "intent": "cambiar el label de la lista",
        "tasks": None,
        "allowedObjects": ["GDE_INT_Lista"],
        "grant": None,
        "suspendedScope": None,
        "resumeFrom": None,
        "manualEstimateMinutes": None,
        "openedAt": "2026-09-02T10:00:00Z",
        "closedAt": None,
    }
    scope.update(over)
    return scope


class TestTheDispatchReadsSchemaVersion(unittest.TestCase):
    def test_no_scope_and_no_version_are_the_06_rulebook(self):
        # § 15: an in-flight 0.6 scope closes under the rules it opened with,
        # so the whole legacy path must stay selected for it.
        self.assertEqual(_scope_policy(None), "v06")
        self.assertEqual(_scope_policy({"id": "T-1", "allowedObjects": ["A"]}), "v06")

    def test_version_2_is_the_07_rulebook(self):
        self.assertEqual(_scope_policy(v2_scope()), "v07")

    def test_any_other_version_is_nobodys_schema(self):
        # Fail closed: a version this code does not know is not "roughly v2".
        # 2.0 and True both == 2 in Python; neither is the integer 2 this
        # schema declares, and "roughly v2" is nobody's schema.
        for version in (1, 3, "2", 2.0, True):
            self.assertEqual(_scope_policy({"schemaVersion": version}), "unknown")

    def test_an_unknown_version_asks_at_the_gate(self):
        with tempfile.TemporaryDirectory() as root:
            c = cfg(root, activeTask={"schemaVersion": 3, "id": "T-1",
                                      "allowedObjects": ["A"]})
            out = scope_gate({"tool_name": "mcp__appian-dev__updateConstant",
                              "tool_input": {"name": "A"}}, c)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("schemaVersion", out["permissionDecisionReason"])


class TestTheSevenStatesAreTheSchema(unittest.TestCase):
    def test_the_enum_is_exactly_the_seven_of_4_2(self):
        self.assertEqual(set(SCOPE_STATUSES),
                         {"in-flight", "closing", "closed", "closed-pending-human",
                          "closed-with-debt", "suspended", "abandoned"})
        # The three constants this file adds; the four close outcomes
        # already existed (Phase 1).
        self.assertEqual(STATUS_CLOSING, "closing")
        self.assertEqual(STATUS_SUSPENDED, "suspended")
        self.assertEqual(STATUS_ABANDONED, "abandoned")


class TestSchemaV2Validation(unittest.TestCase):
    def test_a_complete_scope_validates_clean(self):
        self.assertEqual(_scope_schema_errors(v2_scope()), [])

    def test_a_task_with_tasks_and_grant_validates_clean(self):
        scope = v2_scope(kind="task", intent=None,
                         tasks={"O1-A": ["GDE_INT_Lista", "GDE_QRY_Lista"]},
                         grant={"instanceId": "inst-1", "objects": ["GDE_INT_Lista"],
                                "creates": [], "collisions": [], "deletions": {},
                                "processStarts": [], "extensions": [],
                                "grantedBy": "Raúl",
                                "grantedAt": "2026-09-02T10:00:00Z",
                                "permissionMode": "default"})
        self.assertEqual(_scope_schema_errors(scope), [])

    def _has_error_about(self, scope, needle):
        errors = _scope_schema_errors(scope)
        self.assertTrue(any(needle in e for e in errors),
                        "no error about %r in %r" % (needle, errors))

    def test_each_anchored_field_is_required_and_typed(self):
        self._has_error_about(v2_scope(instanceId=None), "instanceId")
        self._has_error_about(v2_scope(id=""), "id")
        self._has_error_about(v2_scope(kind="feature"), "kind")
        self._has_error_about(v2_scope(status="verified"), "status")
        self._has_error_about(v2_scope(statusWriteSeq="41"), "statusWriteSeq")
        self._has_error_about(v2_scope(allowedObjects="GDE_INT_Lista"),
                              "allowedObjects")
        self._has_error_about(v2_scope(request="finish"), "request")
        self._has_error_about(v2_scope(risk="trivial"), "risk")
        self._has_error_about(v2_scope(tasks=["a", "b"]), "tasks")

    def test_micro_requires_its_intent(self):
        # § 4.1 writes it into the schema: "una frase (obligatoria en micro)".
        self._has_error_about(v2_scope(intent=None), "intent")
        self.assertEqual(_scope_schema_errors(
            v2_scope(kind="task", intent=None)), [])

    def test_the_schema_is_closed(self):
        # A field a hook would anchor or compare that the schema does not
        # declare ends in a validator that rejects it (§ 4.1) -- and so does
        # the typo that would otherwise read as "field absent, use default".
        self._has_error_about(v2_scope(alowedObjects=["typo"]), "alowedObjects")

    def test_a_v2_scope_with_schema_errors_asks_at_the_gate(self):
        with tempfile.TemporaryDirectory() as root:
            c = cfg(root, activeTask=v2_scope(kind="feature"))
            out = scope_gate({"tool_name": "mcp__appian-dev__updateConstant",
                              "tool_input": {"name": "GDE_INT_Lista"}}, c)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("kind", out["permissionDecisionReason"])

    def test_a_legacy_scope_is_never_measured_against_schema_v2(self):
        # The 0.6 file has none of the v2 fields; holding it to them would
        # break "closes under the rules it opened with" (§ 15).
        with tempfile.TemporaryDirectory() as root:
            c = cfg(root, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            out = scope_gate({"tool_name": "mcp__appian-dev__updateConstant",
                              "tool_input": {"name": "A"}}, c)
            # It still asks -- no skill record, no design verdict -- but for
            # 0.6 reasons, not for missing v2 fields.
            self.assertNotIn("schemaVersion", out["permissionDecisionReason"])
            self.assertNotIn("instanceId", out["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
