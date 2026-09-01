import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from harness_hooks import (scope_gate, closure_gate, failure_notice, log_write,
                           log_evidence_write, session_start, requirements_errors)
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
         "activeTask": None, "maxAllowedObjects": 3,
         "projectRoot": root,
         "configPath": os.path.join(root, ".claude", "appian-harness.json"),
         "activeTaskFile": os.path.join(root, "tasks", "current.json")}
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


INSTALLED_VERSION = "26.7"


def write_skill_record(root, task_id, **over):
    """Writes this task's official-Appian-skill load record.

    A write now has two preconditions, not one: a passing design audit and
    evidence that the official skill (github.com/appian/dev-mcp-skills) was
    loaded for this task. Tests that exercise one of them write both and
    then break the one under test, so a failure names the thing it is
    about."""
    record = {
        "task": task_id,
        "skill": "appian",
        "source": "github.com/appian/dev-mcp-skills",
        "appianVersion": INSTALLED_VERSION,
        "docsMcp": "appian-docs",
    }
    record.update(over)
    d = os.path.join(root, "evidence", task_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "appian-skill-loaded.json"), "w", encoding="utf-8") as f:
        json.dump(record, f)


def write_installed_skill(root, version=INSTALLED_VERSION):
    """A stand-in for the installed official skill, so the record's version
    claim can be checked against a file instead of trusted. Returns the path
    a project would put in `officialAppianSkillPath`."""
    d = os.path.join(root, "official-skill")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "SKILL.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\nname: appian\n---\n\n## Configuration\n\n"
                "**Appian Version:** %s\n\nBody.\n" % version)
    return d

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

class TestScopeMatchesEitherIdentifier(unittest.TestCase):
    """`allowedObjects` is compared against every identifier in the call.

    Preferring one key is wrong against the real MCP schemas:
    `updateInterface` takes a uuid and usually no name,
    `addRecordTypeField(uuid, fieldName)` has no name at all, and
    `updateProcessModelNode(processModelUuid, nodeId, name)` has a `name`
    that belongs to the node rather than the object.

    A task is scoped by whichever identifier its plan could know, so the
    write is in scope when ANY identifier in the call matches. The keys
    collected are alternative spellings of the same target, not a list of
    distinct objects, which is what makes any-match the right rule rather
    than a loosening."""

    def _gate(self, root, allowed, tool, tool_input):
        make_plugin_root(root)
        c = cfg(root, activeTask={"id": "T-1", "allowedObjects": allowed})
        write_design_verdict(root, "T-1")
        write_skill_record(root, "T-1")
        return scope_gate({"tool_name": tool, "tool_input": tool_input}, c)

    def test_a_task_scoped_by_uuid_admits_a_write_that_carries_only_a_uuid(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._gate(t, ["_a-0000-uuid"], "mcp__appian-dev__updateInterface",
                           {"uuid": "_a-0000-uuid", "definition": "a!x()"})
            self.assertEqual(d["permissionDecision"], "allow")

    def test_a_field_write_matches_on_its_record_type_uuid(self):
        # addRecordTypeField(uuid, fieldName): no `name` key exists at all.
        with tempfile.TemporaryDirectory() as t:
            d = self._gate(t, ["_a-0000-uuid"], "mcp__appian-dev__addRecordTypeField",
                           {"uuid": "_a-0000-uuid", "fieldName": "status"})
            self.assertEqual(d["permissionDecision"], "allow")

    def test_a_node_name_is_not_the_object_and_does_not_have_to_match(self):
        # updateProcessModelNode's `name` is the node's, not the object's:
        # under a "prefer name" rule this asks on every layout fix.
        with tempfile.TemporaryDirectory() as t:
            d = self._gate(t, ["_pm-0000-uuid"], "mcp__appian-dev__updateProcessModelNode",
                           {"processModelUuid": "_pm-0000-uuid", "nodeId": 4,
                            "name": "Send notification"})
            self.assertEqual(d["permissionDecision"], "allow")

    def test_a_task_scoped_by_name_still_admits_a_write_that_carries_a_name(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._gate(t, ["APP_openRequests"], "mcp__appian-dev__createInterface",
                           {"name": "APP_openRequests", "definition": "a!x()"})
            self.assertEqual(d["permissionDecision"], "allow")

    def test_no_identifier_in_the_call_matches_and_the_gate_asks(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._gate(t, ["APP_openRequests"], "mcp__appian-dev__updateInterface",
                           {"uuid": "_somebody-elses-uuid", "name": "APP_closedRequests"})
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("allowedObjects", d["permissionDecisionReason"])
            self.assertIn("_somebody-elses-uuid", d["permissionDecisionReason"])
            self.assertIn("APP_closedRequests", d["permissionDecisionReason"])

    def test_a_call_carrying_no_identifier_at_all_still_asks(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._gate(t, ["APP_openRequests"], "mcp__appian-dev__createInterface",
                           {"definition": "a!x()"})
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("could not identify", d["permissionDecisionReason"])


class TestScopeGateOutcome(unittest.TestCase):
    """validate_verdict only checks that a verdict is well-formed and its
    citations are real; it deliberately says nothing about whether the audit
    passed. These pin down that the gate itself adds the outcome check:
    only PASS, or NOT_MEASURED/DEFERRED with an owner, unlocks the write."""

    def _base_config(self, root):
        make_plugin_root(root)
        write_skill_record(root, "T-1")
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
    condition". A deferral that opens a gate leaves that line behind, or the
    register is a sentence and the deferral is just a permission."""

    def _config(self, root):
        make_plugin_root(root)
        write_skill_record(root, "T-1")
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
    """The gates open one exact path per phase, and tell the validator
    *which* task and phase they are opening -- otherwise the document can say
    anything, and one audit copied into four filenames satisfies the whole
    four-phase guarantee."""

    def _config(self, root):
        make_plugin_root(root)
        write_skill_record(root, "TASK-3")
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
        document placed under all four filenames opens no gate but its own."""
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
    missing. On a case-insensitive filesystem a case-varied name is found and
    the task closes, so the harness behaves differently on a Windows or macOS
    laptop than in CI unless the gate compares the name itself."""

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


class TestEvidenceWritesAreVisible(unittest.TestCase):
    """Every input the gates read is writable by the agent they constrain, so
    an agent can author its own passing verdict. This does not stop that (see
    log_evidence_write's comment on why gating is the wrong trade); it makes
    it visible."""

    def _log(self, config):
        path = os.path.join(config["evidenceDir"], "evidence-writes.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def _write(self, config, file_path, tool="Write"):
        log_evidence_write({"tool_name": tool, "tool_input": {"file_path": file_path},
                            "tool_response": {"success": True}}, config)

    def test_a_verdict_written_by_hand_is_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": "T-1", "allowedObjects": ["A"]})
            self._write(c, os.path.join(c["evidenceDir"], "T-1", "practices-design.json"))
            entries = self._log(c)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["target"], "evidence")
            self.assertEqual(entries[0]["task"], "T-1")
            self.assertEqual(entries[0]["tool"], "Write")

    def test_an_edit_of_the_harness_config_is_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t)
            self._write(c, c["configPath"], tool="Edit")
            self.assertEqual([e["target"] for e in self._log(c)], ["harness-config"])

    def test_a_write_to_the_active_task_file_is_recorded(self):
        # The third input the gates read, and the one appian-build writes
        # legitimately every task -- which is exactly why it is logged
        # rather than questioned.
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t)
            self._write(c, c["activeTaskFile"])
            self.assertEqual([e["target"] for e in self._log(c)], ["active-task"])

    def test_a_write_to_the_run_authorization_is_recorded(self):
        # The gate reads this file to decide whether anyone authorized the
        # writes at all, so an agent that edits it grants itself the run.
        # Same footing as the active task file: this list grows with the
        # gates rather than being written once.
        with tempfile.TemporaryDirectory() as t:
            run = os.path.join(t, "tasks", "run.json")
            c = cfg(t, activeRunFile=run)
            self._write(c, run, tool="Edit")
            self.assertEqual([e["target"] for e in self._log(c)], ["run-authorization"])

    def test_a_write_to_the_lease_register_is_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            lease = os.path.join(t, "tasks", "leases.json")
            c = cfg(t, leaseFile=lease)
            self._write(c, lease)
            self.assertEqual([e["target"] for e in self._log(c)], ["lease-register"])

    def test_an_unrelated_write_is_not_recorded(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t)
            self._write(c, os.path.join(t, "src", "something.py"))
            self.assertEqual(self._log(c), [])

    def test_a_relative_path_is_resolved_against_the_project_root(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t)
            self._write(c, os.path.join("evidence", "T-1", "practices-qa.json"))
            self.assertEqual([e["target"] for e in self._log(c)], ["evidence"])

    def test_the_hook_returns_no_decision(self):
        # PostToolUse, and deliberately so: this observes, it does not gate.
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t)
            out = log_evidence_write({"tool_name": "Write",
                                      "tool_input": {"file_path": c["configPath"]}}, c)
            self.assertEqual(out, {})

    def test_a_call_with_no_file_path_is_ignored_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t)
            self.assertEqual(log_evidence_write({"tool_name": "Write", "tool_input": {}}, c), {})
            self.assertEqual(self._log(c), [])


class TestFailureNotice(unittest.TestCase):
    def test_notice_forbids_a_blind_retry(self):
        out = failure_notice({"tool_name": "mcp__appian-dev__createInterface"})
        self.assertIn("do not retry", out["additionalContext"].lower())

if __name__ == "__main__":
    unittest.main()


class TestOfficialAppianSkillIsRequiredBeforeWriting(unittest.TestCase):
    """Writing through the design MCP requires the official Appian skill
    (github.com/appian/dev-mcp-skills). It carries what the tool schemas
    cannot express -- naming conventions, both sides of a relationship, the
    order objects must be created in, real UUIDs versus invented ones -- and
    no other gate measures any of that.

    A hook cannot see whether a skill is in an agent's context, but it can
    open a file, so the requirement is enforced the way the design audit is:
    recorded per task, read by the gate."""

    def _config(self, root, **over):
        make_plugin_root(root)
        write_design_verdict(root, "T-1")
        return cfg(root, activeTask={"id": "T-1", "allowedObjects": ["A"]}, **over)

    def _write_call(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                           "tool_input": {"name": "A"}}, config)

    def test_a_write_with_no_load_record_asks(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write_call(self._config(t))
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("dev-mcp-skills", d["permissionDecisionReason"])

    def test_a_complete_load_record_lets_the_write_through(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_skill_record(t, "T-1")
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")

    def test_a_record_naming_another_task_does_not_count(self):
        # The same discipline the phase verdicts get: one record copied
        # across tasks is indistinguishable from N real ones unless the
        # gate checks which task it is about.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_skill_record(t, "T-1", task="T-OTHER")
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("T-OTHER", d["permissionDecisionReason"])

    def test_a_record_that_does_not_name_the_docs_mcp_does_not_count(self):
        # The official skill leans on the documentation MCP for its
        # function-availability checks. Without it those come back empty,
        # and empty reads as "the function does not exist".
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_skill_record(t, "T-1", docsMcp="")
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("docsMcp", d["permissionDecisionReason"])

    def test_a_record_with_no_appian_version_does_not_count(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_skill_record(t, "T-1", appianVersion="")
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("appianVersion", d["permissionDecisionReason"])

    def test_the_version_claim_is_checked_against_the_installed_skill(self):
        # The strong half: when the project points at the installed skill,
        # the record's version stops being self-reported.
        with tempfile.TemporaryDirectory() as t:
            skill_dir = write_installed_skill(t, version="26.7")
            c = self._config(t, officialAppianSkillPath=skill_dir)
            write_skill_record(t, "T-1", appianVersion="26.3")
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("26.3", d["permissionDecisionReason"])
            self.assertIn("26.7", d["permissionDecisionReason"])

    def test_a_matching_version_against_the_installed_skill_passes(self):
        with tempfile.TemporaryDirectory() as t:
            skill_dir = write_installed_skill(t, version="26.7")
            c = self._config(t, officialAppianSkillPath=skill_dir)
            write_skill_record(t, "T-1", appianVersion="26.7")
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")

    def test_an_unconfigured_skill_path_leaves_the_presence_check_alone(self):
        # Not configuring `officialAppianSkillPath` weakens the check to
        # presence-only. It must not turn into a failure: the skill is
        # normally installed at user scope, outside any project.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            write_skill_record(t, "T-1", appianVersion="whatever-the-project-says")
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")

    def test_an_unreadable_record_asks_rather_than_allowing(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            d = os.path.join(t, "evidence", "T-1")
            os.makedirs(d, exist_ok=True)
            with open(os.path.join(d, "appian-skill-loaded.json"), "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(self._write_call(c)["permissionDecision"], "ask")

    def test_a_read_is_still_never_gated_by_this(self):
        # The requirement is about writing. Discovery must stay free --
        # preflight is all reads, and gating it would be the friction that
        # gets a harness switched off.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            d = scope_gate({"tool_name": "mcp__appian-dev__getObjectDependents",
                            "tool_input": {"uuid": "A"}}, c)
            self.assertEqual(d["permissionDecision"], "allow")

    def test_it_never_denies(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write_call(self._config(t))
            self.assertNotEqual(d["permissionDecision"], "deny")


class TestSessionStartChecksTheThreeRequirements(unittest.TestCase):
    """Writing to Appian needs three links -- a design MCP, the official
    Appian skill, and a documentation MCP -- and each one fails in a way
    that looks like something else. Discovered one at a time they are three
    confusing afternoons; discovered at session start they are one message.

    This hook informs and never blocks. A session missing a link is still
    worth having for reading, specifying and planning; what must not happen
    is reaching the first write before finding out."""

    def _cfg(self, root, **over):
        base = {"mcpServers": ["appian-dev", "appian-docs"],
                "designMcpServer": "appian-dev", "docsMcpServer": "appian-docs",
                "officialAppianSkillPath": write_installed_skill(root)}
        base.update(over)
        return cfg(root, **base)

    def test_all_three_present_reports_ready_and_still_asks_for_a_liveness_check(self):
        with tempfile.TemporaryDirectory() as t:
            out = session_start({}, self._cfg(t))
            ctx = out["additionalContext"]
            self.assertIn("all three requirements are present", ctx)
            # Configured is not answering. Only a real call tells them apart.
            self.assertIn("validateExpression", ctx)

    def test_the_session_says_which_version_is_actually_loaded(self):
        """Installed is not loaded, and the gap is invisible from the disk.

        The component inventory is fixed when the process starts, so a
        plugin can be installed, enabled, validated -- every check on disk
        green -- and simply not exist in the running session. Someone
        chasing a bug that was fixed two releases ago has no way to tell
        from inside. `CLAUDE_PLUGIN_ROOT` points at the cache directory of
        the version that is running, so this is the one place that knows.
        """
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, ".claude-plugin"))
            with open(os.path.join(t, ".claude-plugin", "plugin.json"), "w",
                      encoding="utf-8") as f:
                json.dump({"name": "appian-harness", "version": "9.9.9"}, f)
            self.assertIn("9.9.9", session_start({}, self._cfg(t))["additionalContext"])

    def test_an_unreadable_version_does_not_cost_the_session_its_warning(self):
        """The version is a courtesy; the requirements report is not. A
        plugin root that cannot be read must lose the first, never the
        second."""
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, pluginRoot=None)
            self.assertIn("all three requirements are present",
                          session_start({}, c)["additionalContext"])

    def test_a_ready_session_is_reminded_of_the_phases_and_the_doctrine(self):
        with tempfile.TemporaryDirectory() as t:
            ctx = session_start({}, self._cfg(t))["additionalContext"]
            for phase in ("appian-specify", "appian-plan", "appian-build",
                          "appian-verify", "appian-review"):
                self.assertIn(phase, ctx)
            self.assertIn("appian-best-practices", ctx)

    def test_a_missing_design_mcp_is_named(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, mcpServers=["appian-docs"])
            errs = requirements_errors(c)
            self.assertEqual(len(errs), 1)
            self.assertIn("appian-dev", errs[0])
            self.assertIn("gates nothing", errs[0])

    def test_a_missing_docs_mcp_is_named(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, mcpServers=["appian-dev"])
            errs = requirements_errors(c)
            self.assertEqual(len(errs), 1)
            self.assertIn("appian-docs", errs[0])
            self.assertIn("does not exist", errs[0])

    def test_a_missing_official_skill_is_named(self):
        with tempfile.TemporaryDirectory() as t:
            # Point at a path that does not exist, so the user-scope
            # fallback cannot rescue it and the absence is the thing tested.
            c = self._cfg(t, officialAppianSkillPath=os.path.join(t, "nope", "SKILL.md"))
            errs = requirements_errors(c)
            self.assertEqual(len(errs), 1)
            self.assertIn("dev-mcp-skills", errs[0])

    def test_all_three_missing_are_reported_together(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, mcpServers=[],
                          officialAppianSkillPath=os.path.join(t, "nope", "SKILL.md"))
            self.assertEqual(len(requirements_errors(c)), 3)
            ctx = session_start({}, c)["additionalContext"]
            self.assertIn("NOT SAFE", ctx)
            self.assertIn("3 of the three", ctx)

    def test_unknown_mcp_configuration_is_not_reported_as_missing(self):
        # None means discovery could not read anything, which is not the
        # same as knowing there are no servers. Crying wolf here trains the
        # reader to scroll past the one message that matters.
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, mcpServers=None)
            self.assertEqual(requirements_errors(c), [])

    def test_a_project_may_name_its_servers_whatever_it_likes(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, mcpServers=["acme-design", "acme-docs"],
                          designMcpServer="acme-design", docsMcpServer="acme-docs")
            self.assertEqual(requirements_errors(c), [])

    def test_the_skill_is_found_at_user_scope_without_being_configured(self):
        # dev-mcp-skills installs at ~/.claude/skills/appian, outside any
        # project. A project should not have to restate that.
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, officialAppianSkillPath=None)
            home_skill = os.path.join(os.path.expanduser("~"), ".claude", "skills",
                                      "appian", "SKILL.md")
            expected = [] if os.path.isfile(home_skill) else ["missing"]
            got = ["missing"] if requirements_errors(c) else []
            self.assertEqual(got, expected)

    def test_session_start_never_blocks(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._cfg(t, mcpServers=[],
                          officialAppianSkillPath=os.path.join(t, "nope", "SKILL.md"))
            out = session_start({}, c)
            self.assertNotIn("decision", out)
            self.assertNotIn("permissionDecision", out)


class TestTheDocsMcpClaimIsCrossChecked(unittest.TestCase):
    """`docsMcp` is the one field in the load record that does not have to
    settle for self-reporting: by write time the gate knows which servers
    are configured, so a claim can be compared rather than believed."""

    def _config(self, root, **over):
        make_plugin_root(root)
        write_design_verdict(root, "T-1")
        write_skill_record(root, "T-1")
        return cfg(root, activeTask={"id": "T-1", "allowedObjects": ["A"]}, **over)

    def _write_call(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                           "tool_input": {"name": "A"}}, config)

    def test_a_claimed_docs_mcp_that_is_not_configured_asks(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, mcpServers=["appian-dev"])
            d = self._write_call(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("appian-docs", d["permissionDecisionReason"])

    def test_a_claimed_docs_mcp_that_is_configured_passes(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, mcpServers=["appian-dev", "appian-docs"])
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")

    def test_unknown_server_configuration_does_not_manufacture_a_failure(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, mcpServers=None)
            self.assertEqual(self._write_call(c)["permissionDecision"], "allow")


class TestObjectLeasesGuardConcurrentBuilders(unittest.TestCase):
    """The half of concurrency a git worktree cannot cover.

    A worktree gives each builder its own files and its own active task
    file, and two builders in two worktrees calling createRecordType still
    write to the same Appian. Worktrees isolate the recoverable half."""

    def _config(self, root, leases=None, task="T-1", **over):
        make_plugin_root(root)
        write_design_verdict(root, task)
        write_skill_record(root, task)
        lease_path = None
        if leases is not None:
            lease_path = os.path.join(root, "shared-leases.json")
            with open(lease_path, "w", encoding="utf-8") as f:
                json.dump(leases, f)
        return cfg(root, activeTask={"id": task, "allowedObjects": ["RGM_Candidate"]},
                   leaseFile=lease_path, **over)

    def _write(self, config, obj="RGM_Candidate"):
        return scope_gate({"tool_name": "mcp__appian-dev__updateRecordType",
                           "tool_input": {"name": obj}}, config)

    def test_no_lease_register_at_all_is_the_sequential_default(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self._write(self._config(t))["permissionDecision"], "allow")

    def test_an_object_leased_to_another_task_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"RGM_Candidate": "T-2"})
            d = self._write(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("T-2", d["permissionDecisionReason"])
            self.assertIn("worktree", d["permissionDecisionReason"])

    def test_an_object_leased_to_this_task_goes_through(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"RGM_Candidate": "T-1"})
            self.assertEqual(self._write(c)["permissionDecision"], "allow")

    def test_an_unleased_object_is_not_blocked(self):
        # Requiring a lease would break every single-builder project, which
        # is the default. Refusing one held by somebody else is the rule.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"RGM_Interview": "T-2"})
            self.assertEqual(self._write(c)["permissionDecision"], "allow")

    def test_the_lease_comparison_ignores_case_and_padding(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"  rgm_candidate ": "T-2"})
            self.assertEqual(self._write(c)["permissionDecision"], "ask")

    def test_a_uuid_lease_matches_a_write_that_carries_only_a_uuid(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"_a-0000-uuid": "T-2"})
            c["activeTask"]["allowedObjects"] = ["_a-0000-uuid"]
            d = scope_gate({"tool_name": "mcp__appian-dev__updateRecordType",
                            "tool_input": {"uuid": "_a-0000-uuid"}}, c)
            self.assertEqual(d["permissionDecision"], "ask")

    def test_an_unreadable_lease_register_asks_rather_than_allowing(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={})
            with open(c["leaseFile"], "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(self._write(c)["permissionDecision"], "ask")

    def test_a_lease_register_of_the_wrong_shape_asks(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases=["RGM_Candidate"])
            self.assertEqual(self._write(c)["permissionDecision"], "ask")

    def test_leases_never_produce_a_deny(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"RGM_Candidate": "T-2"})
            self.assertNotEqual(self._write(c)["permissionDecision"], "deny")

    def test_a_read_is_unaffected_by_any_lease(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, leases={"RGM_Candidate": "T-2"})
            d = scope_gate({"tool_name": "mcp__appian-dev__getRecordType",
                            "tool_input": {"name": "RGM_Candidate"}}, c)
            self.assertEqual(d["permissionDecision"], "allow")


class TestWriteMatcherAimsAtAppianAndAtRuntime(unittest.TestCase):
    """The matcher has to be right in both directions, measured against real
    tool names rather than argued about.

    Too wide: `^mcp__.*__` matches every MCP server, so Supabase, Figma and
    Google Drive writes get measured against an Appian task's contract. Too
    narrow: a verb list describing the design catalogue and ignoring the
    runtime lets invoking a process model -- which starts real work and
    writes real data in a shared environment -- pass with no gate."""

    def _w(self, name):
        return scope_gate({"tool_name": name, "tool_input": {}},
                          cfg(tempfile.gettempdir()))["permissionDecision"]

    def test_appian_design_writes_are_gated(self):
        for name in ("mcp__appian-dev__createRecordType",
                     "mcp__appian-dev__deleteRecordData",
                     "mcp__appian-dev__addRecordTypeField",
                     "mcp__appian-dev__updateInterface"):
            self.assertEqual(self._w(name), "ask", name)

    def test_appian_runtime_execution_is_gated(self):
        # These change real state in a shared environment.
        for name in ("mcp__appian__appian_invoke_process_model",
                     "mcp__appian__appian_invoke_agent",
                     "mcp__appian-dev__testProcessModel"):
            self.assertEqual(self._w(name), "ask", name)

    def test_non_appian_servers_are_not_gated_by_an_appian_harness(self):
        for name in ("mcp__claude_ai_Supabase__create_project",
                     "mcp__claude_ai_Supabase__delete_branch",
                     "mcp__claude_ai_Figma__create_new_file",
                     "mcp__claude_ai_Google_Drive__create_file",
                     "mcp__claude_ai_Notion__notion-create-pages"):
            self.assertEqual(self._w(name), "allow", name)

    def test_reads_and_stored_test_runs_stay_free(self):
        # Discovery and replaying stored cases are what verification does;
        # gating them is the friction that gets a harness switched off.
        for name in ("mcp__appian-dev__getRecordType",
                     "mcp__appian-dev__listInterfaces",
                     "mcp__appian-dev__getObjectDependents",
                     "mcp__appian-dev__validateExpression",
                     "mcp__appian-dev__testInterface",
                     "mcp__appian-dev__runAllInterfaceTestCases",
                     "mcp__appian-dev__runAllExpressionRuleTestCases",
                     "mcp__appian__appian_data_fabric_sql_query"):
            self.assertEqual(self._w(name), "allow", name)
