import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from harness_hooks import scope_gate, closure_gate, failure_notice

def cfg(root, **over):
    c = {"pluginRoot": root, "evidenceDir": os.path.join(root, "evidence"),
         "activeTask": None, "maxAllowedObjects": 3}
    c.update(over)
    return c

REFDIR = os.path.join("skills", "appian-best-practices", "references")

def make_plugin_root(root):
    """A pluginRoot with one real, resolvable reference section, so a verdict
    citing it passes validate_verdict's structural check and the outcome
    check is what's actually under test."""
    d = os.path.join(root, REFDIR)
    os.makedirs(d)
    with open(os.path.join(d, "06-security.md"), "w", encoding="utf-8") as f:
        f.write("# Security\n\n## Record level security\nBody.\n\n## Field level security\nBody.\n")

def write_design_verdict(root, task_id, **over):
    v = {
        "task": task_id,
        "phase": "design",
        "verdict": "PASS",
        "referencesApplied": ["06-security.md#record-level-security"],
        "findings": [],
    }
    v.update(over)
    d = os.path.join(root, "evidence", task_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "practices-design.json"), "w", encoding="utf-8") as f:
        json.dump(v, f)

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

class TestScopeGateOutcome(unittest.TestCase):
    """validate_verdict only checks that a verdict is well-formed and its
    citations are real; it deliberately says nothing about whether the audit
    passed. These pin down that the gate itself adds the outcome check:
    only PASS, or NOT_MEASURED/DEFERRED with an owner, unlocks the write."""

    def _base_config(self, root):
        make_plugin_root(root)
        return cfg(root, activeTask={"id": "T-1", "allowedObjects": ["A"]})

    def _gate(self, root, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "A"}}, config)

    def test_pass_verdict_satisfies_the_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._base_config(t)
            write_design_verdict(t, "T-1", verdict="PASS")
            d = self._gate(t, c)
            self.assertEqual(d["permissionDecision"], "allow")

    def test_deferred_not_measured_with_owner_satisfies_the_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._base_config(t)
            write_design_verdict(t, "T-1", verdict="NOT_MEASURED", notMeasuredClass="DEFERRED",
                                  owner="a person", closingCondition="when the site ships")
            d = self._gate(t, c)
            self.assertEqual(d["permissionDecision"], "allow")

    def test_fail_verdict_does_not_satisfy_the_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._base_config(t)
            write_design_verdict(t, "T-1", verdict="FAIL")
            d = self._gate(t, c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("FAIL", d["permissionDecisionReason"])

    def test_blocking_not_measured_does_not_satisfy_the_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._base_config(t)
            write_design_verdict(t, "T-1", verdict="NOT_MEASURED", notMeasuredClass="BLOCKING",
                                  owner="a person", closingCondition="when the site ships")
            d = self._gate(t, c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("BLOCKING", d["permissionDecisionReason"])

class TestClosureGate(unittest.TestCase):
    def test_missing_phase_audit_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            os.makedirs(os.path.join(c["evidenceDir"], "T-1"))
            d = closure_gate({}, c)
            self.assertEqual(d["decision"], "block")
            self.assertIn("practices-review", d["reason"])

    def test_repeat_stop_approves_and_records_debt(self):
        """A first block with no in-band escape is a deadlock, and a
        deadlocked guardrail gets disabled. On a repeat Stop the gate must
        approve instead of blocking forever -- but only by converting the
        omission into named, recorded debt, never a silent pass."""
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            os.makedirs(os.path.join(c["evidenceDir"], "T-1"))
            d = closure_gate({"stop_hook_active": True}, c)
            self.assertEqual(d["decision"], "approve")
            self.assertIn("UNMEASURED", d["systemMessage"])

            debt_path = os.path.join(c["evidenceDir"], "deferred-debt.jsonl")
            self.assertTrue(os.path.isfile(debt_path))
            with open(debt_path, encoding="utf-8") as f:
                entry = json.loads(f.readline())
            self.assertEqual(entry["task"], "T-1")
            self.assertEqual(entry["verdict"], "NOT_MEASURED")
            self.assertEqual(entry["notMeasuredClass"], "BLOCKING")
            self.assertIn("implementation", entry["missingPhases"])
            self.assertIn("review", entry["missingPhases"])
            self.assertIn("qa", entry["missingPhases"])

class TestFailureNotice(unittest.TestCase):
    def test_notice_forbids_a_blind_retry(self):
        out = failure_notice({"tool_name": "mcp__appian-dev__createInterface"})
        self.assertIn("do not retry", out["additionalContext"].lower())

if __name__ == "__main__":
    unittest.main()
