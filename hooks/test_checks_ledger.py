"""`observe-reads`: what the hook credits, to which object, and what it
refuses to credit (norm §§ 7.4, 7.5, 8.4).

The failure this file exists to catch is a ledger that looks full: rows
that credit an object nobody read, a read that predates the write it is
supposed to cover, or a failed instrument counted as evidence.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import harness_hooks as hh  # noqa: E402


def _scope(**over):
    scope = {"schemaVersion": 2, "id": "S-1", "instanceId": "inst-1",
             "kind": "micro", "status": "in-flight", "statusWriteSeq": 0,
             "intent": "cambiar un label",
             "grant": {"instanceId": "inst-1", "permissionMode": "default",
                       "objects": ["GDE_INT_Dashboard"]},
             "allowedObjects": ["GDE_INT_Dashboard"]}
    scope.update(over)
    return scope


def _config(root, scope=None):
    evidence = os.path.join(root, "evidence")
    os.makedirs(evidence, exist_ok=True)
    scope = _scope() if scope is None else scope
    config = {"projectRoot": root, "evidenceDir": evidence,
              "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
              "activeTask": scope, "activeTaskFile": os.path.join(root, "t.json")}
    hh._write_json_atomic(os.path.join(evidence, hh.PROJECTION_NAME),
                          {"instanceId": scope["instanceId"], "scope": scope,
                           "signedAt": hh._now()})
    return config


def _batch(*entries, **over):
    payload = {"hook_event_name": "PostToolBatch", "tool_calls": list(entries)}
    payload.update(over)
    return payload


def _entry(tool, tool_input, response, tool_use_id="tu-1"):
    return {"tool_name": tool, "tool_input": tool_input,
            "tool_use_id": tool_use_id, "tool_response": response}


def _rows(config):
    return hh._read_jsonl(os.path.join(config["evidenceDir"], "checks.jsonl"))


class TestTheCorpusIsDerived(unittest.TestCase):
    """§ 7.4: the verification tools come from the corpus, not a hand list."""

    def test_a_read_whose_type_has_a_write_tool_credits(self):
        for action in ("getInterface", "getExpressionRule", "getRecordType",
                       "listRecordTypeUserFilters", "getObjectSecurity",
                       "listGroupMembers", "listProcessModelNodes", "getSite"):
            self.assertIn(action, hh.VERIFICATION_ACTIONS, action)

    def test_a_read_whose_type_has_no_write_tool_does_not(self):
        # Robotic tasks and AI skills have no write tool in this corpus, so
        # no read of them can accredit anything. Naming them in a hand list
        # is what this derivation replaces.
        for action in ("getRoboticTask", "listRoboticTasks", "getAiSkill",
                       "listAiSkills", "getAgent", "listAgents"):
            self.assertNotIn(action, hh.VERIFICATION_ACTIONS, action)

    def test_the_declared_extras_are_in_and_test_process_model_is_out(self):
        for action in ("validateExpression", "validateDesignObject",
                       "testInterface", "testRule", "listRecordData",
                       "runAllInterfaceTestCases",
                       "runAllExpressionRuleTestCases"):
            self.assertIn(action, hh.VERIFICATION_ACTIONS, action)
        # It starts a real process: an irreversible write, never evidence.
        self.assertNotIn("testProcessModel", hh.VERIFICATION_ACTIONS)

    def test_the_two_corpora_are_disjoint(self):
        # The asymmetry § 7.4 asserts: scope-gate and log-write share the
        # write corpus; observe-reads has the verification one, and an
        # overlap would mean a write crediting itself.
        overlap = [a for a in hh.VERIFICATION_ACTIONS
                   if hh.WRITE_TOOL_RE.match("mcp__appian-dev__" + a)]
        self.assertEqual(overlap, [])
        self.assertTrue(
            hh.WRITE_TOOL_RE.match("mcp__appian-dev__testProcessModel"))


class TestRowsAreTiedToTheCallThatProducedThem(unittest.TestCase):

    def test_the_row_carries_the_object_and_the_tool_use_id(self):
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__getInterface",
                {"uuid": "GDE_INT_Dashboard"},
                {"name": "GDE_INT_Dashboard", "expression": "a!x()"},
                tool_use_id="toolu_ABC")), config)
            rows = _rows(config)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["toolUseId"], "toolu_ABC")
            self.assertEqual(rows[0]["object"], "GDE_INT_Dashboard")
            self.assertEqual(rows[0]["objectType"], "interface")
            self.assertEqual(rows[0]["instanceId"], "inst-1")

    def test_the_row_records_the_sequence_it_was_taken_at(self):
        # "Por secuencias": a read taken before the write cannot credit it,
        # and this field is the only thing that can say so afterwards.
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__getInterface", {"uuid": "GDE_INT_Dashboard"},
                {"name": "GDE_INT_Dashboard"})), config)
            self.assertEqual(_rows(config)[0]["writeSeqAtCheck"], 0)

            hh._append_jsonl(os.path.join(config["evidenceDir"], "operations.jsonl"),
                             {"instanceId": "inst-1", "writeSeq": 1,
                              "result": "ok", "inScope": True,
                              "behavioural": True, "object": "GDE_INT_Dashboard"})
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__getInterface", {"uuid": "GDE_INT_Dashboard"},
                {"name": "GDE_INT_Dashboard"}, tool_use_id="tu-2")), config)
            self.assertEqual(_rows(config)[1]["writeSeqAtCheck"], 1)

    def test_a_batch_of_several_reads_writes_one_row_each(self):
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(
                _entry("mcp__appian-dev__getInterface", {"uuid": "A"},
                       {"name": "A"}, tool_use_id="tu-a"),
                _entry("mcp__appian-dev__validateDesignObject", {"uuid": "A"},
                       {"valid": True}, tool_use_id="tu-b")), config)
            self.assertEqual([r["toolUseId"] for r in _rows(config)],
                             ["tu-a", "tu-b"])


class TestWhatDoesNotCount(unittest.TestCase):

    def test_a_failed_read_is_ambiguous_and_never_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__testInterface", {"uuid": "GDE_INT_Dashboard"},
                "API error (HTTP 500): Failed to serialize test result")), config)
            row = _rows(config)[0]
            self.assertEqual(row["result"], "failed")
            self.assertEqual(row["guaranteeClass"], "ambiguous")

    def test_an_unrecognised_shape_is_ambiguous(self):
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__getInterface", {"uuid": "A"},
                "reordered")), config)
            self.assertEqual(_rows(config)[0]["result"], "ambiguous")
            self.assertEqual(_rows(config)[0]["guaranteeClass"], "ambiguous")

    def test_a_tool_error_envelope_is_failed(self):
        self.assertEqual(
            hh.classify_read_response("<tool_use_error>Unknown</tool_use_error>"),
            "failed")

    def test_a_batch_with_nothing_to_credit_writes_nothing(self):
        # PostToolBatch admits no matcher: this fires on every batch of the
        # session, so the cheap exit is the hook-clock guarantee (§ 17.4).
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(
                _entry("Bash", {"command": "echo A"}, "A"),
                _entry("Bash", {"command": "echo B"}, "B", tool_use_id="tu-2")),
                config)
            self.assertFalse(os.path.exists(
                os.path.join(config["evidenceDir"], "checks.jsonl")))

    def test_no_signed_scope_means_no_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            evidence = os.path.join(root, "evidence")
            os.makedirs(evidence)
            config = {"projectRoot": root, "evidenceDir": evidence,
                      "activeTask": _scope()}
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__getInterface", {"uuid": "A"}, {"name": "A"})),
                config)
            self.assertFalse(os.path.exists(os.path.join(evidence, "checks.jsonl")))


class TestGuaranteeClass(unittest.TestCase):
    """§ 8.4: each row says what it bought, and universally-green signals
    say so instead of passing for coverage."""

    def test_validate_design_object_is_green_signal_only(self):
        self.assertEqual(
            hh.guarantee_class("validateDesignObject", "ok", {"valid": True}),
            "green-signal-only")

    def test_object_security_is_authorization(self):
        self.assertEqual(
            hh.guarantee_class("getObjectSecurity", "ok", {"roleMap": {}}),
            "authorization")

    def test_a_green_test_case_run_is_behavioural(self):
        self.assertEqual(
            hh.guarantee_class("runAllExpressionRuleTestCases", "ok",
                               {"testCases": [{"passed": True}]}),
            "behavioural")

    def test_a_run_of_zero_cases_is_not_behavioural(self):
        # A replay of nothing cannot fail, which is what a green signal is.
        self.assertEqual(
            hh.guarantee_class("runAllExpressionRuleTestCases", "ok",
                               {"testCases": []}),
            "green-signal-only")

    def test_a_red_case_is_not_behavioural_either(self):
        self.assertEqual(
            hh.guarantee_class("runAllInterfaceTestCases", "ok",
                               {"testCases": [{"passed": True},
                                              {"passed": False}]}),
            "green-signal-only")

    def test_a_failed_instrument_buys_nothing_whatever_the_tool(self):
        for action in ("getObjectSecurity", "runAllInterfaceTestCases",
                       "listRecordData", "getInterface"):
            self.assertEqual(hh.guarantee_class(action, "failed", None),
                             "ambiguous", action)

    def test_a_structural_read_is_structure(self):
        self.assertEqual(
            hh.guarantee_class("listProcessModelNodes", "ok", {"nodes": []}),
            "structure")

    def test_a_plain_reread_is_persistence(self):
        self.assertEqual(hh.guarantee_class("getConstant", "ok", {"name": "C"}),
                         "persisted-not-behavioural")


class TestDerivedSignals(unittest.TestCase):

    def test_the_expression_hash_of_a_read_matches_the_write_that_made_it(self):
        # This equality is what turns "the re-read confirms what was
        # written" into an assertion instead of a claim.
        behavioural, written = hh._behavioural_and_hash(
            "updateInterface", {"uuid": "A", "expression": "a!x()",
                                "inputs": [{"name": "ri"}]})
        self.assertTrue(behavioural)
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            hh.observe_reads(_batch(_entry(
                "mcp__appian-dev__getInterface", {"uuid": "A"},
                {"name": "A", "expression": "a!x()",
                 "inputs": [{"name": "ri"}]})), config)
            self.assertEqual(_rows(config)[0]["expressionHash"], written)

    def test_volatile_fields_do_not_move_the_response_digest(self):
        a = {"name": "A", "_cId": "111", "durationMs": 12,
             "diagnostics": {"durationMs": 12}, "value": "keep"}
        b = {"name": "A", "_cId": "999", "durationMs": 87,
             "diagnostics": {"durationMs": 87}, "value": "keep"}
        self.assertEqual(hh._stable_digest(a), hh._stable_digest(b))
        c = dict(a, value="changed")
        self.assertNotEqual(hh._stable_digest(a), hh._stable_digest(c))

    def test_the_non_metadata_digest_ignores_only_the_whitelist(self):
        a = {"name": "A", "description": "old", "expression": "a!x()"}
        b = {"name": "A", "description": "new", "expression": "a!x()"}
        c = {"name": "A", "description": "old", "expression": "a!y()"}
        self.assertEqual(hh._stable_digest(a, drop=hh._METADATA_ONLY_FIELDS),
                         hh._stable_digest(b, drop=hh._METADATA_ONLY_FIELDS))
        self.assertNotEqual(hh._stable_digest(a, drop=hh._METADATA_ONLY_FIELDS),
                            hh._stable_digest(c, drop=hh._METADATA_ONLY_FIELDS))

    def test_cross_references_are_read_from_the_response(self):
        refs = hh.cross_references("getSite", {
            "name": "GDE_SITE", "pages": [{"urlStub": "home",
                                           "targetUuid": "iface-1"},
                                          {"urlStub": "list",
                                           "targetUuid": "iface-2"}]})
        self.assertEqual(sorted(r["target"] for r in refs),
                         ["iface-1", "iface-2"])
        self.assertTrue(all(r["kind"] == "site-page" for r in refs))

    def test_the_five_wirings_are_all_extracted(self):
        self.assertTrue(hh.cross_references(
            "listRecordTypeActions", [{"name": "a", "processModelUuid": "pm-1"}]))
        self.assertTrue(hh.cross_references(
            "getProcessModel", {"name": "pm", "startForm": {"interfaceUuid": "i-1"}}))
        self.assertTrue(hh.cross_references(
            "listRecordTypeViews",
            [{"name": "summary", "interfaceExpression": "rule!GDE_INT_Sum(x)"}]))
        self.assertTrue(hh.cross_references(
            "listRecordTypeRelationships",
            [{"name": "r", "targetRecordTypeUuid": "rt-2"}]))


class TestTheSkillTrailIsWrittenByTheHook(unittest.TestCase):
    """§ 7.5: from what was observed, not from what the agent claims."""

    def _with_skill(self, root):
        skill_root = os.path.join(root, "skills", "appian")
        os.makedirs(os.path.join(skill_root, "references"))
        with open(os.path.join(skill_root, "SKILL.md"), "w",
                  encoding="utf-8") as f:
            f.write("# Appian\n\n**Appian Version:** 26.8\n")
        with open(os.path.join(skill_root, "references", "interfaces.md"), "w",
                  encoding="utf-8") as f:
            f.write("ref\n")
        return skill_root

    def test_the_invocation_and_the_reads_are_what_write_it(self):
        with tempfile.TemporaryDirectory() as root:
            skill_root = self._with_skill(root)
            config = _config(root)
            config["officialAppianSkillPath"] = skill_root
            hh.observe_reads(_batch(
                _entry("Skill", {"skill": "appian"}, "Launching skill: appian",
                       tool_use_id="tu-skill"),
                _entry("Read", {"file_path": os.path.join(skill_root,
                                                          "references",
                                                          "interfaces.md")},
                       "ref", tool_use_id="tu-read")), config)
            path = os.path.join(config["evidenceDir"], "S-1",
                                "appian-skill-loaded.json")
            with open(path, encoding="utf-8") as f:
                record = json.load(f)
            self.assertEqual(record["observedBy"], "observe-reads")
            self.assertTrue(record["skillInvoked"])
            self.assertEqual(record["toolUseId"], "tu-skill")
            self.assertEqual(record["appianVersion"], "26.8")
            self.assertIn(os.path.join("references", "interfaces.md"),
                          record["referencesLoaded"])
            self.assertIsNone(hh.skill_trail_note(config, "S-1"))

    def test_a_failed_skill_invocation_is_not_a_load(self):
        with tempfile.TemporaryDirectory() as root:
            skill_root = self._with_skill(root)
            config = _config(root)
            config["officialAppianSkillPath"] = skill_root
            hh.observe_reads(_batch(_entry(
                "Skill", {"skill": "appian"},
                "<tool_use_error>Unknown skill: appian</tool_use_error>")),
                config)
            self.assertIsNotNone(hh.skill_trail_note(config, "S-1"))

    def test_a_record_the_agent_wrote_credits_nothing(self):
        # The defect this replaces: three fields anybody could type.
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            path = os.path.join(config["evidenceDir"], "S-1",
                                "appian-skill-loaded.json")
            os.makedirs(os.path.dirname(path))
            hh._write_json_atomic(path, {"task": "S-1", "skill": "appian",
                                         "docsMcp": "appian-docs",
                                         "appianVersion": "26.8"})
            note = hh.skill_trail_note(config, "S-1")
            self.assertIsNotNone(note)
            self.assertIn("not written by the hook", note)

    def test_a_missing_trail_is_a_remedy_and_never_an_ask(self):
        # § 7.3 closes the list of ask causes at five, and this is not one
        # of them: 97 of 116 measured asks came from this check.
        with tempfile.TemporaryDirectory() as root:
            config = _config(root)
            os.makedirs(os.path.join(config["evidenceDir"], "S-1"))
            decision = hh.scope_gate(
                {"tool_name": "mcp__appian-dev__updateInterface",
                 "tool_input": {"uuid": "GDE_INT_Dashboard",
                                "expression": "a!x()"}}, config)
            self.assertEqual(decision["permissionDecision"], "allow")
            self.assertIn("official Appian skill",
                          decision.get("additionalContext", ""))


if __name__ == "__main__":
    unittest.main()
