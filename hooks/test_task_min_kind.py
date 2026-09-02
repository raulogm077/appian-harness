"""`task_min_kind(tool, tool_input)` and the observed `risk` (norm §§ 5.2-5.3).

Two pure classifiers with separate outputs -- kind is how much ceremony, risk
is what class of damage -- written against the REAL tool schemas (Phase 0 P6),
including the three field corrections: views and user filters spell the field
`visibilityExpression` while actions spell it `visibilityExpr`; no `update*`
carries `parentFolderUuid`; `updateFolder` has no security fields.

The acid test is the absence of magnitude: a 1,767-line interface rewrite is
`micro`, because the tool always sends the whole expression (§ 5.2).
"""
import json, os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from harness_hooks import task_min_kind, observed_risk

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                      "docs", "design", "fase-0",
                      "appian-dev-tools-2026-09-01.json")

DEV = "mcp__appian-dev__"
RT = "mcp__appian__appian_"


def kind(action, tool_input=None, **kw):
    return task_min_kind(DEV + action, tool_input or {}, **kw)


def risk(action, tool_input=None, **kw):
    return observed_risk(DEV + action, tool_input or {}, **kw)


class TestNoMagnitudeThresholdExists(unittest.TestCase):
    def test_a_full_interface_redesign_is_micro(self):
        # 1,767 lines or one label: the tool sends the whole expression
        # either way, so any magnitude rule would always fire (§ 5.2).
        huge = "a!formLayout(" + "x" * 200000 + ")"
        self.assertEqual(kind("updateInterface",
                              {"uuid": "_i-1", "expression": huge}), "micro")
        self.assertEqual(kind("updateInterface",
                              {"uuid": "_i-1", "expressionFilePath": "/tmp/big.sail"}),
                         "micro")

    def test_interfaces_rules_and_their_cases_are_micro_eligible(self):
        for action in ("createInterface", "updateInterface",
                       "createExpressionRule", "updateExpressionRule",
                       "createInterfaceTestCase", "updateExpressionRuleTestCase"):
            self.assertEqual(kind(action, {"name": "X"}), "micro", action)
            self.assertIsNone(risk(action, {"name": "X"}), action)

    def test_folders_and_documents_are_micro_eligible(self):
        # P6: updateFolder is {uuid, name, description} -- it has no security
        # fields, so the retired "updateFolder when it touches security"
        # branch must not exist in any form.
        for action in ("createFolder", "updateFolder", "uploadDocument",
                       "updateDocument", "replaceDocumentContent"):
            self.assertEqual(kind(action, {"name": "X"}), "micro", action)


class TestWhatForcesTask(unittest.TestCase):
    def test_record_types_their_fields_actions_and_relationships(self):
        for action in ("createRecordType", "updateRecordType",
                       "addRecordTypeField", "updateRecordTypeField",
                       "addRecordTypeRelationship", "updateRecordTypeRelationship",
                       "addRecordTypeAction", "updateRecordTypeAction",
                       "addRecordTypeView", "addRecordTypeUserFilter"):
            self.assertEqual(kind(action, {"name": "X"}), "task", action)

    def test_the_two_families_no_glob_can_catch(self):
        # § 5.2 names them because `*RecordType*` does not match them, and
        # a sync-time calculated field skips field-level security.
        for action in ("addCustomRecordField", "updateCustomRecordField",
                       "configureRecordEvents"):
            self.assertEqual(kind(action, {"recordTypeUuid": "_r"}), "task", action)

    def test_groups_data_sites_apps_and_integration_surface(self):
        for action in ("createGroup", "updateGroup", "addGroupMembers",
                       "removeGroupMember", "insertRecordData", "updateRecordData",
                       "createSite", "updateSite", "createApplication",
                       "updateApplication", "addObjectsToApplication",
                       "createProcessModel", "updateProcessModel",
                       "createProcessModelNode", "updateProcessModelNode",
                       "createConnectedSystem", "updateConnectedSystem",
                       "createWebApi", "updateWebApi",
                       "createIntegration", "updateIntegration"):
            self.assertEqual(kind(action, {"name": "X"}), "task", action)

    def test_every_deletion_and_every_process_start(self):
        for action in ("deleteConstant", "deleteInterface", "deleteRecordType",
                       "deleteFolder", "removeGroupMember", "testProcessModel"):
            self.assertEqual(kind(action, {"uuid": "_x"}), "task", action)
        for name in (RT + "invoke_process_model", RT + "invoke_agent"):
            self.assertEqual(task_min_kind(name, {"uuid": "_x"}), "task", name)
            self.assertEqual(observed_risk(name, {"uuid": "_x"}), "high", name)

    def test_an_unclassified_write_tool_buys_ceremony(self):
        # The unknown must never default to the cheap lane (§ 5.2).
        self.assertEqual(kind("configureBrandNewSurface", {"name": "X"}), "task")


class TestVisibilityIsPerFieldAndPerTool(unittest.TestCase):
    """P6's first correction: same concept, two spellings, by tool."""

    def test_views_and_user_filters_are_micro_without_the_field(self):
        for action in ("updateRecordTypeView", "updateRecordTypeUserFilter"):
            self.assertEqual(kind(action, {"uuid": "_v", "nameExpr": "x"}),
                             "micro", action)
            self.assertIsNone(risk(action, {"uuid": "_v"}), action)

    def test_passing_the_field_buys_task_and_high(self):
        for action in ("updateRecordTypeView", "updateRecordTypeUserFilter"):
            payload = {"uuid": "_v", "visibilityExpression": "loggedInUser()..."}
            self.assertEqual(kind(action, payload), "task", action)
            self.assertEqual(risk(action, payload), "high", action)

    def test_clearing_the_field_is_still_passing_it(self):
        # An explicit null clears the security expression: that changes who
        # sees what exactly as much as setting one.
        payload = {"uuid": "_v", "visibilityExpression": None}
        self.assertEqual(kind("updateRecordTypeView", payload), "task")

    def test_actions_spell_it_visibilityExpr(self):
        payload = {"uuid": "_a", "visibilityExpr": "true"}
        self.assertEqual(risk("updateRecordTypeAction", payload), "high")

    def test_reordering_views_is_always_task_and_high(self):
        payload = {"uuid": "_r", "urlStubs": ["a", "b"]}
        self.assertEqual(kind("reorderRecordTypeViews", payload), "task")
        self.assertEqual(risk("reorderRecordTypeViews", payload), "high")


class TestConstantsBySecurityType(unittest.TestCase):
    def test_a_text_constant_is_micro(self):
        self.assertEqual(kind("createConstant",
                              {"name": "C", "type": "TEXT"}), "micro")

    def test_security_types_buy_task_and_high(self):
        # P6 widened the list: USER_OR_GROUP exists in the real vocabulary
        # and GROUP_TYPE feeds the same security expressions.
        for ctype in ("GROUP", "USER", "USER_OR_GROUP", "GROUP_TYPE"):
            payload = {"name": "C", "type": ctype}
            self.assertEqual(kind("createConstant", payload), "task", ctype)
            self.assertEqual(risk("createConstant", payload), "high", ctype)

    def test_an_update_without_type_buys_task_unless_context_supplies_it(self):
        # § 5.2: the type may not travel in the call; the grant supplies it
        # from the preflight, and its ABSENCE buys task.
        self.assertEqual(kind("updateConstant", {"uuid": "_c", "value": "3"}), "task")
        self.assertEqual(kind("updateConstant", {"uuid": "_c", "value": "3"},
                              constant_type="TEXT"), "micro")
        self.assertEqual(kind("updateConstant", {"uuid": "_c", "value": "3"},
                              constant_type="GROUP"), "task")


class TestSecurityAndDataRisk(unittest.TestCase):
    def test_object_security_and_data_writes_are_high(self):
        self.assertEqual(risk("updateObjectSecurity", {"uuid": "_x"}), "high")
        for action in ("insertRecordData", "updateRecordData", "deleteRecordData"):
            self.assertEqual(risk(action, {"uuid": "_x"}), "high", action)

    def test_ordinary_micro_writes_carry_no_risk_label(self):
        self.assertIsNone(risk("updateInterface", {"uuid": "_i", "expression": "1"}))
        self.assertIsNone(risk("createFolder", {"name": "F"}))


class TestDeclaredPrefixesReachTheClassifier(unittest.TestCase):
    def test_a_renamed_server_classifies_the_same(self):
        cfg = {"appianMcpToolPrefixes": ["mcp__lcp__"]}
        self.assertEqual(task_min_kind("mcp__lcp__createRecordType",
                                       {"name": "R"}, config=cfg), "task")
        self.assertEqual(task_min_kind("mcp__lcp__updateInterface",
                                       {"uuid": "_i"}, config=cfg), "micro")


class TestAgainstTheRealCorpus(unittest.TestCase):
    """The 145 dumped tools (Phase 0), so 'no false ask over the corpus' has
    a deterministic half: every write tool classifies, none crashes, and the
    micro-eligible set is exactly the declared one."""

    MICRO_ELIGIBLE = {
        "createConstant", "updateConstant", "createFolder", "updateFolder",
        "uploadDocument", "updateDocument", "replaceDocumentContent",
        "createInterface", "updateInterface",
        "createExpressionRule", "updateExpressionRule",
        "createInterfaceTestCase", "createInterfaceTestCases",
        "updateInterfaceTestCase",
        "createExpressionRuleTestCase", "createExpressionRuleTestCases",
        "updateExpressionRuleTestCase",
        "updateRecordTypeView", "updateRecordTypeUserFilter",
    }

    def test_every_write_tool_in_the_corpus_classifies(self):
        with open(CORPUS, encoding="utf-8") as f:
            dump = json.load(f)
        tools = dump["tools"] if isinstance(dump, dict) and "tools" in dump else dump
        names = [t["name"] if isinstance(t, dict) else t for t in tools]
        self.assertGreater(len(names), 100)
        micro = set()
        for name in names:
            full = DEV + name
            got = task_min_kind(full, {"name": "X"})
            self.assertIn(got, ("micro", "task"), name)
            if got == "micro":
                micro.add(name)
        # Deletions never appear on the cheap lane, whatever the list says.
        self.assertFalse({n for n in micro if n.startswith(("delete", "remove"))})
        # Constants drop out here because this sweep passes no `type`, and
        # a constant of unknown type buys task (§ 5.2).
        self.assertEqual(micro, (self.MICRO_ELIGIBLE
                                 - {"createConstant", "updateConstant"}) & set(names))


if __name__ == "__main__":
    unittest.main()
