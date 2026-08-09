import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from harness_hooks import scope_gate, closure_gate, failure_notice

def cfg(root, **over):
    c = {"pluginRoot": root, "evidenceDir": os.path.join(root, "evidence"),
         "activeTask": None, "maxAllowedObjects": 3}
    c.update(over)
    return c

class TestScopeGate(unittest.TestCase):
    def test_no_active_task_asks(self):
        with tempfile.TemporaryDirectory() as t:
            d = scope_gate({"tool_name": "mcp__appian-dev__createInterface", "tool_input": {}}, cfg(t))
            self.assertEqual(d["permissionDecision"], "ask")

    def test_object_outside_contract_asks(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            d = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "B"}}, c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("allowedObjects", d["permissionDecisionReason"])

    def test_too_many_objects_asks_on_atomicity(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A", "B", "C", "D"]})
            d = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "A"}}, c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("atomic", d["permissionDecisionReason"].lower())

    def test_missing_design_audit_asks(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            d = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "A"}}, c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("design", d["permissionDecisionReason"])

    def test_read_tool_is_never_gated(self):
        with tempfile.TemporaryDirectory() as t:
            d = scope_gate({"tool_name": "mcp__appian-dev__getInterface", "tool_input": {}}, cfg(t))
            self.assertEqual(d["permissionDecision"], "allow")

    def test_gate_never_denies(self):
        with tempfile.TemporaryDirectory() as t:
            d = scope_gate({"tool_name": "mcp__appian-dev__createInterface", "tool_input": {}}, cfg(t))
            self.assertNotEqual(d["permissionDecision"], "deny")

class TestClosureGate(unittest.TestCase):
    def test_missing_phase_audit_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            os.makedirs(os.path.join(c["evidenceDir"], "T-1"))
            d = closure_gate({}, c)
            self.assertEqual(d["decision"], "block")
            self.assertIn("practices-review", d["reason"])

class TestFailureNotice(unittest.TestCase):
    def test_notice_forbids_a_blind_retry(self):
        out = failure_notice({"tool_name": "mcp__appian-dev__createInterface"})
        self.assertIn("do not retry", out["additionalContext"].lower())

if __name__ == "__main__":
    unittest.main()
