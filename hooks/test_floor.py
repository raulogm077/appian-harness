"""The deterministic floor of § 8: what a scope must have PAID before it
can close, read off the ledger the hook wrote.

The failures this file exists to catch are the ones a green suite hides: a
floor satisfied by a read taken before the write, a failed instrument
counted as coverage, an escalation of size because the environment broke, a
check demanded twice when nothing that could change its result changed.
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


# --- fixtures: the batches that pay each type's floor -------------------

def _e(tool, tool_input, response, tool_use_id=None):
    return {"tool_name": "mcp__appian-dev__" + tool, "tool_input": tool_input,
            "tool_use_id": tool_use_id or ("tu-" + tool),
            "tool_response": response}


def _tree(rows, value="Ana"):
    """An evaluated tree with `rows` value-bearing nodes."""
    contents = [{"#t": "Grid", "label": "Rows", "rowHeader": 1,
                 "emptyGridMessage": "Sin filas",
                 "data": [{"name": value}] * rows if rows else []}]
    for i in range(rows):
        contents.append({"#t": "TextField", "label": "Name %d" % i,
                         "value": value, "saveInto": "enc:%d" % i})
    return {"#t": "Form", "_cId": "c-%d" % rows, "contents": contents,
            "diagnostics": {"durationMs": 10 * (rows + 1)}}


def interface_floor_batch(uuid, populated_rows=3):
    """validate · re-read · a populated render and an empty one (§ 8.1)."""
    return [
        _e("validateDesignObject", {"uuid": uuid}, {"valid": True},
           "tu-val-" + uuid),
        _e("getInterface", {"uuid": uuid},
           {"name": uuid, "expression": "a!textField()"}, "tu-get-" + uuid),
        _e("testInterface", {"uuid": uuid, "testInputs": {"id": 1}},
           _tree(populated_rows), "tu-pob-" + uuid),
        _e("testInterface", {"uuid": uuid, "testInputs": {"id": -999}},
           _tree(0), "tu-vac-" + uuid),
    ]


def rule_floor_batch(uuid):
    """validate · re-read · at least one test case run green (§ 8.1)."""
    return [
        _e("validateDesignObject", {"uuid": uuid}, {"valid": True},
           "tu-val-" + uuid),
        _e("getExpressionRule", {"uuid": uuid}, {"name": uuid, "expression": "1+1"},
           "tu-get-" + uuid),
        _e("runAllExpressionRuleTestCases", {"uuid": uuid},
           {"testCases": [{"name": "happy", "passed": True}]}, "tu-run-" + uuid),
    ]


def _scope(**over):
    scope = {"schemaVersion": 2, "id": "S-1", "instanceId": "inst-1",
             "kind": "micro", "status": "in-flight", "statusWriteSeq": 0,
             "intent": "cambiar un label",
             "grant": {"instanceId": "inst-1", "permissionMode": "default",
                       "objects": ["_uuid-a"]},
             "allowedObjects": ["_uuid-a"]}
    scope.update(over)
    return scope


class FloorCase(unittest.TestCase):
    """One scope, one write, and whatever reads the case wants credited."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.evidence = os.path.join(self.root, "evidence")
        os.makedirs(self.evidence)
        self.addCleanup(self._tmp.cleanup)

    def config(self, scope=None):
        scope = scope or _scope()
        config = {"projectRoot": self.root, "evidenceDir": self.evidence,
                  "activeTask": scope,
                  "activeTaskFile": os.path.join(self.root, "t.json")}
        hh._write_json_atomic(os.path.join(self.evidence, hh.PROJECTION_NAME),
                              {"instanceId": scope["instanceId"], "scope": scope,
                               "signedAt": hh._now()})
        return config

    def write(self, config, tool, uuid, seq=1, behavioural=True, **extra):
        row = {"timestamp": hh._now(), "task": "S-1", "instanceId": "inst-1",
               "writeSeq": seq, "tool": "mcp__appian-dev__" + tool,
               "toolUseId": "w-%d" % seq, "object": uuid, "candidates": [uuid],
               "uuids": [uuid], "inScope": True, "behavioural": behavioural,
               "result": "ok"}
        row.update(extra)
        hh._append_jsonl(os.path.join(self.evidence, "operations.jsonl"), row)

    def observe(self, config, batch):
        hh.observe_reads({"tool_calls": batch}, config)

    def report(self, config):
        return hh.floor_report(config, config["activeTask"])


class TestTheFloorIsPaidWithObservedReads(FloorCase):

    def test_a_write_with_no_reads_at_all_does_not_close(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        report = self.report(c)
        self.assertTrue(report["missing"])
        self.assertTrue(any("validateDesignObject" in m for m in report["missing"]))

    def test_the_full_interface_floor_closes_clean(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        self.observe(c, interface_floor_batch("_uuid-a"))
        report = self.report(c)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["blocking"], [])
        self.assertEqual(report["notMeasured"], [])

    def test_a_read_taken_before_the_write_does_not_accredit_it(self):
        # The defect `toolUseId` and `writeSeqAtCheck` exist to close: a
        # stale or concurrent read crediting coverage nobody ran for this
        # write.
        c = self.config()
        self.observe(c, interface_floor_batch("_uuid-a"))   # at writeSeq 0
        self.write(c, "updateInterface", "_uuid-a", seq=1)
        report = self.report(c)
        self.assertTrue(report["missing"])

    def test_a_failed_read_is_not_evidence(self):
        # It does not pass, and it does not silently vanish either: an
        # instrument that failed goes to § 8.7, which is a different exit
        # from "the leg was paid".
        c = self.config()
        self.write(c, "updateExpressionRule", "_uuid-a")
        batch = rule_floor_batch("_uuid-a")
        batch[1]["tool_response"] = "API error (HTTP 500): boom"
        self.observe(c, batch)
        report = self.report(c)
        self.assertTrue(report["notMeasured"] or report["missing"])
        self.assertTrue(any(g["leg"] == "reread" for g in report["notMeasured"]))

    def test_a_run_of_zero_cases_does_not_pay_the_behavioural_leg(self):
        c = self.config()
        self.write(c, "updateExpressionRule", "_uuid-a")
        batch = rule_floor_batch("_uuid-a")
        batch[2]["tool_response"] = {"testCases": []}
        self.observe(c, batch)
        self.assertTrue(any("test cases green" in m
                            for m in self.report(c)["missing"]))

    def test_validate_design_object_alone_is_never_coverage(self):
        # § 8.4: a universally green signal. It is a required leg because
        # it is cheap and catches the gross failure, never a substitute.
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        self.observe(c, [interface_floor_batch("_uuid-a")[0]])
        missing = self.report(c)["missing"]
        self.assertTrue(any("read it back" in m for m in missing))
        self.assertTrue(any("render it populated" in m for m in missing))


class TestNoCheckIsDemandedTwice(FloorCase):
    """§ 17.3: repeated checks = 0. A leg satisfied at the last write of an
    object cannot be asked for again while nothing that could change its
    result has changed."""

    def test_a_satisfied_floor_stays_satisfied_across_evaluations(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        self.observe(c, interface_floor_batch("_uuid-a"))
        first = self.report(c)
        second = self.report(c)
        self.assertEqual(first["missing"], [])
        self.assertEqual(second["missing"], [])

    def test_only_a_later_write_reopens_the_floor(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a", seq=1)
        self.observe(c, interface_floor_batch("_uuid-a"))
        self.assertEqual(self.report(c)["missing"], [])
        self.write(c, "updateInterface", "_uuid-a", seq=2)
        self.assertTrue(self.report(c)["missing"])


class TestTheProportionalFloor(FloorCase):
    """§ 8.6: a write the hook classified `behavioural: false` cannot break
    the render chain, so checking in a way that cannot fail is waste."""

    def test_a_description_only_write_pays_validate_and_a_reread(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a", behavioural=False)
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getInterface", {"uuid": "_uuid-a"},
               {"name": "_uuid-a", "description": "nueva"})])
        report = self.report(c)
        self.assertEqual(report["missing"], [])

    def test_it_does_not_pay_the_render_pair(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a", behavioural=False)
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getInterface", {"uuid": "_uuid-a"}, {"name": "_uuid-a"})])
        self.assertNotIn("render", " ".join(self.report(c)["missing"]))

    def test_being_published_in_a_site_does_not_change_it(self):
        # § 5.5 and § 8.6 say this in as many words: exposure modulates the
        # lane, never the floor a non-behavioural write pays.
        c = self.config(_scope(allowedObjects=["_uuid-a", "_uuid-site"],
                               kind="task", intent=None,
                               grant={"instanceId": "inst-1",
                                      "permissionMode": "default",
                                      "objects": ["_uuid-a", "_uuid-site"]}))
        self.write(c, "updateInterface", "_uuid-a", behavioural=False)
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getInterface", {"uuid": "_uuid-a"}, {"name": "_uuid-a"})])
        self.assertEqual(self.report(c)["missing"], [])

    def test_one_behavioural_write_in_the_history_brings_the_whole_floor_back(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a", seq=1, behavioural=True)
        self.write(c, "updateInterface", "_uuid-a", seq=2, behavioural=False)
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getInterface", {"uuid": "_uuid-a"}, {"name": "_uuid-a"})])
        self.assertTrue(any("render" in m for m in self.report(c)["missing"]))


class TestTheRenderGuarantees(FloorCase):
    """§ 8.5, read off rows the hook stamped rather than an artefact the
    agent wrote."""

    def test_two_renders_of_the_same_state_must_agree(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        batch = interface_floor_batch("_uuid-a")
        # Same inputs as the populated one, different content: guarantee 1
        # fails, and everything built on it proves nothing.
        batch.append(_e("testInterface", {"uuid": "_uuid-a", "testInputs": {"id": 1}},
                        _tree(5, value="Otra"), "tu-again"))
        self.observe(c, batch)
        missing = " ".join(self.report(c)["missing"])
        self.assertIn("guarantee 1", missing)

    def test_random_ids_nonces_and_durations_do_not_break_agreement(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        batch = interface_floor_batch("_uuid-a")
        again = json.loads(json.dumps(batch[2]["tool_response"]))
        again["_cId"] = "totally-different"
        again["diagnostics"]["durationMs"] = 99999
        for node in again["contents"]:
            if "saveInto" in node:
                node["saveInto"] = "enc:fresh-nonce"
        batch.append(_e("testInterface",
                        {"uuid": "_uuid-a", "testInputs": {"id": 1}},
                        again, "tu-again"))
        self.observe(c, batch)
        self.assertEqual(self.report(c)["missing"], [])

    def test_a_foreach_that_never_iterated_fails_the_inequality(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        batch = interface_floor_batch("_uuid-a")
        batch[2]["tool_response"] = _tree(0)     # "populated" carries nothing
        self.observe(c, batch)
        self.assertIn("strictly more", " ".join(self.report(c)["missing"]))

    def test_one_render_is_not_a_pair(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        self.observe(c, interface_floor_batch("_uuid-a")[:3])
        self.assertIn("credited render", " ".join(self.report(c)["missing"]))

    def test_a_truncated_render_accredits_nothing(self):
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        batch = interface_floor_batch("_uuid-a")
        batch[2]["tool_response"]["diagnostics"]["truncated"] = True
        self.observe(c, batch)
        self.assertIn("truncated", " ".join(self.report(c)["missing"]))

    def test_the_empty_path_must_use_a_different_mechanism(self):
        # § 8.1: the empty render is reached by the mechanism that screen
        # has, and which one was used is what gets recorded.
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        batch = interface_floor_batch("_uuid-a")
        batch[3]["tool_input"] = {"uuid": "_uuid-a", "testInputs": {"id": 1}}
        batch[3]["tool_response"] = _tree(3)
        self.observe(c, batch)
        self.assertIn("same inputs", " ".join(self.report(c)["missing"]))


class TestTheInstrumentThatCannotMeasure(FloorCase):
    """§ 8.7, the rule that replaced two contradicting sentences: a failure
    of the instrument NEVER changes the kind."""

    def _dashboard(self, config, failure="API error (HTTP 500): Failed to "
                                         "serialize test result"):
        self.write(config, "updateInterface", "_uuid-a")
        return [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getInterface", {"uuid": "_uuid-a"},
               {"name": "_uuid-a", "expression": "a!x()"}),
            _e("testInterface", {"uuid": "_uuid-a", "testInputs": {"id": 1}},
               failure, "tu-pob"),
        ]

    def test_an_undistinguished_failure_closes_pending_human(self):
        # No clean earlier measure, no reproduction without the change, no
        # same failure elsewhere: the doubt resolves to the expensive side.
        c = self.config()
        self.observe(c, self._dashboard(c))
        report = self.report(c)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["blocking"], [])
        classes = [g["class"] for g in report["notMeasured"]]
        self.assertIn("instrument-undistinguished", classes)

    def test_a_clean_earlier_measure_makes_it_a_regression_not_a_limit(self):
        # An instrument that measured and stopped measuring after a write
        # of the agent's is a change of the object (§ 8.7 step 1).
        c = self.config()
        self.observe(c, [_e("testInterface",
                            {"uuid": "_uuid-a", "testInputs": {"id": 1}},
                            _tree(3), "tu-clean")])
        self.observe(c, self._dashboard(c))
        report = self.report(c)
        self.assertTrue(report["blocking"])
        self.assertIn("not a limit of the environment", report["blocking"][0])

    def test_the_same_failure_on_another_object_distinguishes_it(self):
        c = self.config()
        self.observe(c, [_e("testInterface",
                            {"uuid": "_uuid-otra", "testInputs": {}},
                            "API error (HTTP 500): Failed to serialize test result",
                            "tu-family")])
        self.observe(c, self._dashboard(c))
        report = self.report(c)
        self.assertEqual(report["blocking"], [])
        classes = [g["class"] for g in report["notMeasured"]]
        self.assertNotIn("instrument-undistinguished", classes)
        # Two classes fell with the instrument, and the search is per class.
        self.assertIn("accessibility", classes)

    def test_the_search_for_alternative_evidence_is_per_guarantee_class(self):
        # Running the test cases answers for behaviour and produces no
        # tree, so it cannot answer for accessibility. Treating them
        # together would call the floor met when it is met in part.
        c = self.config()
        self.observe(c, [_e("testInterface", {"uuid": "_uuid-otra", "testInputs": {}},
                            "API error (HTTP 500): Failed to serialize test result",
                            "tu-family")])
        batch = self._dashboard(c)
        batch.append(_e("runAllInterfaceTestCases", {"uuid": "_uuid-a"},
                        {"testCases": [{"name": "smoke", "passed": True}]},
                        "tu-cases"))
        self.observe(c, batch)
        classes = [g["class"] for g in self.report(c)["notMeasured"]]
        self.assertNotIn("behavioural", classes)
        self.assertIn("accessibility", classes)

    def test_the_rest_channel_counts_as_another_surface(self):
        # § 8.7 (a). The 500 is the servlet's; the REST surface exists and
        # is documented. It arrives as a Bash call, so without recognising
        # it the acid case has no behavioural alternative at all.
        c = self.config()
        self.observe(c, [_e("testInterface", {"uuid": "_uuid-otra", "testInputs": {}},
                            "API error (HTTP 500): Failed to serialize test result",
                            "tu-family")])
        batch = self._dashboard(c)
        batch.append({
            "tool_name": "Bash", "tool_use_id": "tu-rest",
            "tool_input": {"command": "curl -s -u user:pass https://indra-spain.appiancloud.com"
                                      "/suite/rest/a/lcp-api/latest/interfaces/"
                                      "_uuid-a/test-cases/run"},
            "tool_response": json.dumps({"testCases": [{"name": "smoke",
                                                        "passed": True}]})})
        self.observe(c, batch)
        classes = [g["class"] for g in self.report(c)["notMeasured"]]
        self.assertNotIn("behavioural", classes)

    def test_the_kind_never_changes_because_an_instrument_broke(self):
        c = self.config()
        self.observe(c, self._dashboard(c))
        self.assertEqual(c["activeTask"]["kind"], "micro")
        hh.floor_report(c, c["activeTask"])
        self.assertEqual(c["activeTask"]["kind"], "micro")


class TestTheDefaultRuleAndTheResidues(FloorCase):

    def test_a_type_with_no_floor_row_closes_with_debt_not_blocked(self):
        # § 8.1: whoever wrote with a tool the table does not classify has
        # nothing to fix, so the scope does not wait.
        c = self.config()
        self.write(c, "createAiSkill", "_uuid-a")
        report = self.report(c)
        self.assertEqual(report["missing"], [])
        self.assertEqual([d["kind"] for d in report["debts"]],
                         [hh.DEBT_TYPE_HAS_NO_FLOOR])
        self.assertIn("owner", report["debts"][0])

    def test_a_web_api_carries_its_residue_and_still_closes(self):
        # § 8.4's symmetric residue: persistence-only floor plus a reach
        # outside Appian. A residue is not a failure.
        c = self.config()
        self.write(c, "updateWebApi", "_uuid-a")
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getWebApi", {"uuid": "_uuid-a"}, {"name": "_uuid-a"})])
        report = self.report(c)
        self.assertEqual(report["missing"], [])
        self.assertEqual([d["kind"] for d in report["debts"]],
                         [hh.DEBT_EXTERNAL_EFFECT])

    def test_a_constant_carries_no_residue(self):
        c = self.config()
        self.write(c, "updateConstant", "_uuid-a")
        self.observe(c, [_e("getConstant", {"uuid": "_uuid-a"},
                            {"name": "_uuid-a", "value": "x"})])
        report = self.report(c)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["debts"], [])


class TestCrossReferences(FloorCase):
    """§ 8.2: the class of defect a per-type floor cannot see, because each
    object passes its own row and the set is broken."""

    def _site_scope(self):
        objects = ["_uuid-site", "_uuid-iface"]
        return _scope(kind="task", intent=None, allowedObjects=objects,
                      grant={"instanceId": "inst-1", "permissionMode": "default",
                             "objects": objects})

    def test_a_site_page_pointing_nowhere_is_caught(self):
        c = self.config(self._site_scope())
        self.write(c, "updateSite", "_uuid-site", seq=1)
        self.write(c, "updateInterface", "_uuid-iface", seq=2)
        self.observe(c, interface_floor_batch("_uuid-iface") + [
            _e("getSite", {"uuid": "_uuid-site"},
               {"name": "_uuid-site",
                "pages": [{"urlStub": "home", "targetUuid": "_uuid-borrada"}]},
               "tu-site")])
        missing = " ".join(self.report(c)["missing"])
        self.assertIn("_uuid-borrada", missing)

    def test_a_site_whose_pages_resolve_is_clean(self):
        c = self.config(self._site_scope())
        self.write(c, "updateSite", "_uuid-site", seq=1)
        self.write(c, "updateInterface", "_uuid-iface", seq=2)
        self.observe(c, interface_floor_batch("_uuid-iface") + [
            _e("getSite", {"uuid": "_uuid-site"},
               {"name": "_uuid-site",
                "pages": [{"urlStub": "home", "targetUuid": "_uuid-iface"}]},
               "tu-site")])
        self.assertEqual(self.report(c)["missing"], [])

    def test_never_reading_the_wiring_is_itself_the_finding(self):
        # "Do not assume cross-references are correct because individual
        # object creation succeeded."
        c = self.config(self._site_scope())
        self.write(c, "updateSite", "_uuid-site", seq=1)
        self.write(c, "updateInterface", "_uuid-iface", seq=2)
        self.observe(c, interface_floor_batch("_uuid-iface"))
        self.assertIn("read the wiring", " ".join(self.report(c)["missing"]))

    def test_a_lone_interface_is_not_asked_for_wiring(self):
        # The transversal row fires where there IS wiring. Demanding it of
        # a single interface would be ceremony.
        c = self.config()
        self.write(c, "updateInterface", "_uuid-a")
        self.observe(c, interface_floor_batch("_uuid-a"))
        self.assertEqual(self.report(c)["missing"], [])


class TestTheDeletionFloor(FloorCase):

    def test_a_delete_needs_dependents_and_a_read_back_that_fails(self):
        c = self.config()
        self.write(c, "deleteConstant", "_uuid-a")
        self.observe(c, [
            _e("getObjectDependents", {"uuid": "_uuid-a"}, {"dependents": []}),
            _e("getConstant", {"uuid": "_uuid-a"},
               "API error (HTTP 403): Constant not found", "tu-absence")])
        self.assertEqual(self.report(c)["missing"], [])

    def test_a_delete_whose_object_still_reads_back_is_not_closed(self):
        c = self.config()
        self.write(c, "deleteConstant", "_uuid-a")
        self.observe(c, [
            _e("getObjectDependents", {"uuid": "_uuid-a"}, {"dependents": []}),
            _e("getConstant", {"uuid": "_uuid-a"}, {"name": "_uuid-a"})])
        self.assertIn("read it back after the delete",
                      " ".join(self.report(c)["missing"]))


class TestTheOtherTypeRows(FloorCase):

    def test_security_needs_the_diff_not_the_ok(self):
        c = self.config()
        self.observe(c, [_e("getObjectSecurity", {"uuid": "_uuid-a"},
                            {"roleMap": {"viewers": ["G1"]}}, "tu-pre")])
        self.write(c, "updateObjectSecurity", "_uuid-a")
        self.observe(c, [_e("getObjectSecurity", {"uuid": "_uuid-a"},
                            {"roleMap": {"viewers": ["G1"]}}, "tu-post")])
        # Only one credited state after the write: no diff, no evidence.
        self.assertTrue(self.report(c)["missing"])

    def test_a_record_type_must_be_queryable(self):
        c = self.config()
        self.write(c, "addRecordTypeField", "_uuid-a")
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getRecordType", {"uuid": "_uuid-a"}, {"name": "_uuid-a"}),
            _e("listRecordData", {"uuid": "_uuid-a"}, {"rows": []})])
        self.assertIn("cannot be queried", " ".join(self.report(c)["missing"]))

    def test_a_process_model_with_a_broken_graph_does_not_close(self):
        c = self.config()
        self.write(c, "createProcessModelNode", "_uuid-a")
        nodes = [{"id": 1, "type": "START", "connections": [{"targetNodeId": 3}]},
                 {"id": 3, "type": "XOR",
                  "decision": {"conditions": [{"expression": "=true",
                                               "targetNodeId": 99}],
                               "defaultPath": 2}},
                 {"id": 2, "type": "END", "connections": []}]
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getProcessModel", {"uuid": "_uuid-a"}, {"name": "_uuid-a"}),
            _e("listProcessModelNodes", {"processModelUuid": "_uuid-a"},
               {"nodes": nodes})])
        self.assertIn("list its nodes", " ".join(self.report(c)["missing"]))

    def test_a_process_model_with_a_valid_graph_closes(self):
        c = self.config()
        self.write(c, "createProcessModelNode", "_uuid-a")
        nodes = [{"id": 1, "type": "START", "connections": [{"targetNodeId": 3}]},
                 {"id": 3, "type": "USER_TASK", "connections": [{"targetNodeId": 2}]},
                 {"id": 2, "type": "END", "connections": []}]
        self.observe(c, [
            _e("validateDesignObject", {"uuid": "_uuid-a"}, {"valid": True}),
            _e("getProcessModel", {"uuid": "_uuid-a"}, {"name": "_uuid-a"}),
            _e("listProcessModelNodes", {"processModelUuid": "_uuid-a"},
               {"nodes": nodes})])
        self.assertEqual(self.report(c)["missing"], [])

    def test_an_expression_user_filter_needs_its_body_validated(self):
        c = self.config()
        self.write(c, "addRecordTypeUserFilter", "_uuid-a")
        self.observe(c, [_e("listRecordTypeUserFilters", {"uuid": "_uuid-a"},
                            {"facetType": "EXPRESSION", "name": "_uuid-a"})])
        self.assertTrue(self.report(c)["missing"])
        self.observe(c, [_e("validateExpression", {"uuid": "_uuid-a"},
                            {"valid": True})])
        self.assertEqual(self.report(c)["missing"], [])


if __name__ == "__main__":
    unittest.main()


class TestTypesWithNoWriteTool(FloorCase):
    """§ 8.8: they are configured in Designer, pass through no MCP, and so
    no hook sees them. That is worse than a block -- it is invisible -- and
    the row turns the invisibility into declared debt."""

    def declare(self, config, obj="GDE_DEC_Tarifa"):
        hh._append_jsonl(hh._debt_register(config),
                         {"timestamp": hh._now(), "task": "S-1",
                          "instanceId": "inst-1", "kind": hh.DEBT_MANUAL_STEP,
                          "object": obj, "type": "decision",
                          "owner": "Raúl", "detail": "Decision object, "
                          "configured in Designer"})

    def test_a_declared_manual_step_owes_the_read_that_does_exist(self):
        c = self.config()
        self.declare(c)
        self.assertIn("read whatever surface DOES expose it",
                      " ".join(self.report(c)["missing"]))

    def test_the_read_that_does_exist_settles_it(self):
        c = self.config()
        self.declare(c)
        self.observe(c, [_e("listApplicationObjects", {"uuid": "GDE_DEC_Tarifa"},
                            {"objects": [{"name": "GDE_DEC_Tarifa"}]})])
        self.assertEqual(self.report(c)["missing"], [])

    def test_it_does_not_have_to_share_the_scope_with_a_write(self):
        # Nothing routed through the hook for this object, so a floor that
        # only looked at operations.jsonl would never see it at all.
        c = self.config()
        self.declare(c)
        self.assertEqual(hh._written_objects(c, c["activeTask"]), {})
        self.assertTrue(self.report(c)["missing"])

    def test_connected_systems_are_not_treated_as_manual(self):
        # The Dev MCP does have createConnectedSystem, so § 8.1's own row
        # covers them. The official source is out of date on that point.
        self.assertNotIn("connectedSystem", hh.MANUAL_TYPES)
        self.assertIn("connectedSystem", hh._LEGS_BY_TYPE)
