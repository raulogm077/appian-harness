import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from harness_hooks import scope_gate, closure_gate, failure_notice, log_write
from validate_verdict import DEFERRABLE_CRITERIA

# The one shape of NOT_MEASURED that opens a gate: sanctioned, owned, with a
# closing condition, and naming which criterion off the plugin's closed list
# is being deferred.
DEFERRAL = {
    "verdict": "NOT_MEASURED",
    "notMeasuredClass": "DEFERRED",
    "owner": "the accessibility lead",
    "closingCondition": "before the site is released",
    "deferredCriterion": DEFERRABLE_CRITERIA[0],
}

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

def write_verdict(root, task_id, phase, filename=None, **over):
    """Writes one verdict under <root>/evidence/<task_id>/.

    `filename` is separate from `phase` on purpose: the tests that matter
    here are the ones where the document and the path disagree."""
    v = {
        "task": task_id,
        "phase": phase,
        "verdict": "PASS",
        "referencesApplied": ["06-security.md#record-level-security"],
        "findings": [],
    }
    v.update(over)
    d = os.path.join(root, "evidence", task_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, filename or ("practices-%s.json" % phase)), "w",
              encoding="utf-8") as f:
        json.dump(v, f)


def write_design_verdict(root, task_id, **over):
    write_verdict(root, task_id, "design", **over)

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
            write_design_verdict(t, "T-1", **DEFERRAL)
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

class TestDeferralIsRecordedNotMerelyPermitted(unittest.TestCase):
    """`10-quality-gates.md` says a deferral "goes into the project's
    deferred-debt register with task, criterion, reason, owner and closing
    condition". Nothing wrote it there, so a deferral was a permission and
    the register was a sentence. A deferral that opens a gate now leaves a
    line behind."""

    def _config(self, root):
        make_plugin_root(root)
        return cfg(root, activeTask={"id": "T-1", "allowedObjects": ["A"]})

    def _write_call(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "A"}}, config)

    def _register(self, config):
        path = os.path.join(config["evidenceDir"], "deferred-debt.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def test_a_deferral_that_opens_the_gate_is_appended_to_the_register(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_design_verdict(t, "T-1", **DEFERRAL)
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")
            entries = self._register(c)
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e["task"], "T-1")
            self.assertEqual(e["phase"], "design")
            self.assertEqual(e["criterion"], DEFERRABLE_CRITERIA[0])
            self.assertEqual(e["notMeasuredClass"], "DEFERRED")
            self.assertEqual(e["owner"], DEFERRAL["owner"])
            self.assertEqual(e["closingCondition"], DEFERRAL["closingCondition"])

    def test_repeated_writes_do_not_duplicate_the_entry(self):
        # The scope gate runs on every write. A naive append would turn one
        # deferral into one register line per write attempt.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_design_verdict(t, "T-1", **DEFERRAL)
            for _ in range(4):
                self._write_call(c)
            self.assertEqual(len(self._register(c)), 1)

    def test_a_passing_verdict_writes_nothing_to_the_register(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_design_verdict(t, "T-1", verdict="PASS")
            self._write_call(c)
            self.assertEqual(self._register(c), [])

    def test_a_second_phase_deferring_the_same_criterion_is_its_own_entry(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            for phase in ("implementation", "review", "qa"):
                write_verdict(t, "T-1", phase, **DEFERRAL)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")
            self.assertEqual(sorted(e["phase"] for e in self._register(c)),
                             ["implementation", "qa", "review"])

    def test_a_deferral_naming_no_criterion_does_not_open_the_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            deferral = dict(DEFERRAL)
            del deferral["deferredCriterion"]
            write_design_verdict(t, "T-1", **deferral)
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("deferredCriterion", d["permissionDecisionReason"])
            self.assertEqual(self._register(c), [])


class TestVerdictMustAgreeWithItsPath(unittest.TestCase):
    """The gates open one exact path per phase. Until they also told the
    validator *which* task and phase they were opening, the document could
    say anything: one audit copied into four filenames satisfied the whole
    four-phase guarantee."""

    def _config(self, root):
        make_plugin_root(root)
        return cfg(root, activeTask={"id": "TASK-3", "allowedObjects": ["A"]})

    def _write_call(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "A"}}, config)

    def test_verdict_naming_another_task_does_not_satisfy_the_scope_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_verdict(t, "TASK-3", "design", task="TASK-999")
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("TASK-999", d["permissionDecisionReason"])

    def test_verdict_naming_another_phase_does_not_satisfy_the_scope_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_verdict(t, "TASK-3", "qa", filename="practices-design.json")
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("design", d["permissionDecisionReason"])

    def test_agreeing_verdict_still_satisfies_the_scope_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_verdict(t, "TASK-3", "design")
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")

    def test_one_audit_copied_to_four_names_does_not_close_a_task(self):
        """The probe, end to end: a single `{"task":"TASK-999","phase":"qa"}`
        document placed under all four filenames used to open every gate."""
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            for name in ("design", "implementation", "review", "qa"):
                write_verdict(t, "TASK-3", "qa", filename="practices-%s.json" % name,
                              task="TASK-999")
            self.assertEqual(self._write_call(c)["permissionDecision"], "ask")
            d = closure_gate({}, c)
            self.assertEqual(d["decision"], "block")
            for phase in ("implementation", "review", "qa"):
                self.assertIn("practices-%s" % phase, d["reason"])

    def test_four_genuine_verdicts_still_close_the_task(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            for phase in ("implementation", "review", "qa"):
                write_verdict(t, "TASK-3", phase)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")


class TestVerdictLookupIsCaseSensitive(unittest.TestCase):
    """`practices-QA.json` is documented as a verdict the gate reports
    missing. On a case-insensitive filesystem it was found and the task
    closed, so the harness behaved differently on a laptop than in CI."""

    def test_verdict_named_with_the_wrong_case_is_reported_missing(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin_root(t)
            c = cfg(t, activeTask={"id": "TASK-3", "allowedObjects": ["A"]})
            write_verdict(t, "TASK-3", "implementation")
            write_verdict(t, "TASK-3", "review")
            write_verdict(t, "TASK-3", "qa", filename="practices-QA.json")
            d = closure_gate({}, c)
            self.assertEqual(d["decision"], "block")
            self.assertIn("practices-qa", d["reason"])


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

class TestWriteLog(unittest.TestCase):
    """A write log that lies is worse than no write log, because it gets
    trusted. PostToolUse delivers the tool's return value as `tool_response`;
    reading only `tool_result` would record every failed write as "ok", so
    both names are pinned here."""

    def _logged_result(self, root, payload):
        c = cfg(root, activeTask={"id": "T-1", "allowedObjects": ["A"]})
        log_write(payload, c)
        with open(os.path.join(c["evidenceDir"], "operations.jsonl"), encoding="utf-8") as f:
            return json.loads(f.readline())["result"]

    def test_failed_write_under_tool_response_is_logged_as_error(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self._logged_result(t, {
                "tool_name": "mcp__appian-dev__updateInterface",
                "tool_input": {"name": "A"},
                "tool_response": {"is_error": True, "error": "Access denied"}}), "error")

    def test_failed_write_under_legacy_tool_result_is_logged_as_error(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self._logged_result(t, {
                "tool_name": "mcp__appian-dev__updateInterface",
                "tool_input": {"name": "A"},
                "tool_result": {"is_error": True, "error": "Access denied"}}), "error")

    def test_successful_write_is_logged_as_ok(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self._logged_result(t, {
                "tool_name": "mcp__appian-dev__updateInterface",
                "tool_input": {"name": "A"},
                "tool_response": {"uuid": "_a-0000", "success": True}}), "ok")


class TestFailureNotice(unittest.TestCase):
    def test_notice_forbids_a_blind_retry(self):
        out = failure_notice({"tool_name": "mcp__appian-dev__createInterface"})
        self.assertIn("do not retry", out["additionalContext"].lower())

if __name__ == "__main__":
    unittest.main()
