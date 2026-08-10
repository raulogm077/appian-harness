"""The matcher has two halves in two languages, and nothing compared them.

`hooks.json` decides which tool calls Claude Code delivers to the hook
process; `WRITE_TOOL_RE` decides what the hook does with the ones that
arrive. A verb present only in the Python half is a gate that cannot fire:
the call is never routed, so the pattern never sees it. That happened --
`appian_invoke_process_model` was added to the Python side alone and was
dead in production while every test passed, because the tests call
`scope_gate` directly and never touch the JSON matcher.

The comment in `harness_hooks.py` has stated the invariant since, and until
this file nothing enforced it -- a plugin whose argument is that an
unchecked claim is not a pass, resting on an unchecked claim.

The names below are real, taken from the tool catalogue of the two Appian
MCP servers as a live session lists them, plus every other MCP server in
that session whose tool name carries a write verb. The point of using the
real catalogue rather than invented names is that the last two defects here
were both found by measuring against it and neither by reasoning.
"""
import json, os, re, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import WRITE_TOOL_RE, DESTRUCTIVE_TOOL_RE, log_write

HOOKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.json")

APPIAN_TOOLS = (
    "mcp__appian-dev__addCustomRecordField",
    "mcp__appian-dev__addGroupMembers",
    "mcp__appian-dev__addObjectsToApplication",
    "mcp__appian-dev__addRecordTypeAction",
    "mcp__appian-dev__addRecordTypeField",
    "mcp__appian-dev__addRecordTypeRelationship",
    "mcp__appian-dev__addRecordTypeUserFilter",
    "mcp__appian-dev__addRecordTypeView",
    "mcp__appian-dev__configureRecordEvents",
    "mcp__appian-dev__createApplication",
    "mcp__appian-dev__createConnectedSystem",
    "mcp__appian-dev__createConstant",
    "mcp__appian-dev__createExpressionRule",
    "mcp__appian-dev__createExpressionRuleTestCase",
    "mcp__appian-dev__createExpressionRuleTestCases",
    "mcp__appian-dev__createFolder",
    "mcp__appian-dev__createGroup",
    "mcp__appian-dev__createIntegration",
    "mcp__appian-dev__createInterface",
    "mcp__appian-dev__createInterfaceTestCase",
    "mcp__appian-dev__createInterfaceTestCases",
    "mcp__appian-dev__createProcessModel",
    "mcp__appian-dev__createProcessModelNode",
    "mcp__appian-dev__createRecordType",
    "mcp__appian-dev__createSite",
    "mcp__appian-dev__createWebApi",
    "mcp__appian-dev__deleteApplication",
    "mcp__appian-dev__deleteConnectedSystem",
    "mcp__appian-dev__deleteConstant",
    "mcp__appian-dev__deleteCustomRecordField",
    "mcp__appian-dev__deleteDocument",
    "mcp__appian-dev__deleteExpressionRule",
    "mcp__appian-dev__deleteExpressionRuleTestCase",
    "mcp__appian-dev__deleteFolder",
    "mcp__appian-dev__deleteGroup",
    "mcp__appian-dev__deleteIntegration",
    "mcp__appian-dev__deleteInterface",
    "mcp__appian-dev__deleteInterfaceTestCase",
    "mcp__appian-dev__deleteProcessModel",
    "mcp__appian-dev__deleteProcessModelNode",
    "mcp__appian-dev__deleteRecordData",
    "mcp__appian-dev__deleteRecordType",
    "mcp__appian-dev__deleteRecordTypeAction",
    "mcp__appian-dev__deleteRecordTypeField",
    "mcp__appian-dev__deleteRecordTypeRelationship",
    "mcp__appian-dev__deleteRecordTypeUserFilter",
    "mcp__appian-dev__deleteRecordTypeView",
    "mcp__appian-dev__deleteSite",
    "mcp__appian-dev__deleteWebApi",
    "mcp__appian-dev__getAgent",
    "mcp__appian-dev__getAiSkill",
    "mcp__appian-dev__getApplication",
    "mcp__appian-dev__getConnectedSystem",
    "mcp__appian-dev__getConnectedSystemType",
    "mcp__appian-dev__getConstant",
    "mcp__appian-dev__getDocument",
    "mcp__appian-dev__getDocumentContent",
    "mcp__appian-dev__getDocumentText",
    "mcp__appian-dev__getExpressionRule",
    "mcp__appian-dev__getExpressionRuleTestCase",
    "mcp__appian-dev__getFolder",
    "mcp__appian-dev__getGroup",
    "mcp__appian-dev__getIntegration",
    "mcp__appian-dev__getInterface",
    "mcp__appian-dev__getInterfaceTestCase",
    "mcp__appian-dev__getObjectDependents",
    "mcp__appian-dev__getObjectSecurity",
    "mcp__appian-dev__getProcessModel",
    "mcp__appian-dev__getProcessModelNode",
    "mcp__appian-dev__getProcessModelNodeTypeSchema",
    "mcp__appian-dev__getRecordEventsConfig",
    "mcp__appian-dev__getRecordType",
    "mcp__appian-dev__getRecordTypeField",
    "mcp__appian-dev__getRoboticTask",
    "mcp__appian-dev__getSite",
    "mcp__appian-dev__getWebApi",
    "mcp__appian-dev__insertRecordData",
    "mcp__appian-dev__listAgents",
    "mcp__appian-dev__listAiSkills",
    "mcp__appian-dev__listApplicationObjects",
    "mcp__appian-dev__listApplications",
    "mcp__appian-dev__listConnectedSystemTypes",
    "mcp__appian-dev__listConnectedSystems",
    "mcp__appian-dev__listConstants",
    "mcp__appian-dev__listDocuments",
    "mcp__appian-dev__listExpressionRuleTestCases",
    "mcp__appian-dev__listExpressionRules",
    "mcp__appian-dev__listFolderContents",
    "mcp__appian-dev__listFolders",
    "mcp__appian-dev__listGroupMembers",
    "mcp__appian-dev__listGroups",
    "mcp__appian-dev__listIntegrations",
    "mcp__appian-dev__listInterfaceTestCases",
    "mcp__appian-dev__listInterfaces",
    "mcp__appian-dev__listProcessModelFolders",
    "mcp__appian-dev__listProcessModelNodeTypes",
    "mcp__appian-dev__listProcessModelNodes",
    "mcp__appian-dev__listProcessModels",
    "mcp__appian-dev__listRecordData",
    "mcp__appian-dev__listRecordTypeActions",
    "mcp__appian-dev__listRecordTypeFields",
    "mcp__appian-dev__listRecordTypeRelationships",
    "mcp__appian-dev__listRecordTypeUserFilters",
    "mcp__appian-dev__listRecordTypeViews",
    "mcp__appian-dev__listRecordTypes",
    "mcp__appian-dev__listRoboticTasks",
    "mcp__appian-dev__listSites",
    "mcp__appian-dev__listWebApis",
    "mcp__appian-dev__removeGroupMember",
    "mcp__appian-dev__reorderRecordTypeViews",
    "mcp__appian-dev__replaceDocumentContent",
    "mcp__appian-dev__runAllExpressionRuleTestCases",
    "mcp__appian-dev__runAllInterfaceTestCases",
    "mcp__appian-dev__runExpressionRuleTestCase",
    "mcp__appian-dev__runInterfaceTestCase",
    "mcp__appian-dev__testInterface",
    "mcp__appian-dev__testProcessModel",
    "mcp__appian-dev__testRule",
    "mcp__appian-dev__updateApplication",
    "mcp__appian-dev__updateConnectedSystem",
    "mcp__appian-dev__updateConstant",
    "mcp__appian-dev__updateCustomRecordField",
    "mcp__appian-dev__updateDocument",
    "mcp__appian-dev__updateExpressionRule",
    "mcp__appian-dev__updateExpressionRuleTestCase",
    "mcp__appian-dev__updateFolder",
    "mcp__appian-dev__updateGroup",
    "mcp__appian-dev__updateIntegration",
    "mcp__appian-dev__updateInterface",
    "mcp__appian-dev__updateInterfaceTestCase",
    "mcp__appian-dev__updateObjectSecurity",
    "mcp__appian-dev__updateProcessModel",
    "mcp__appian-dev__updateProcessModelNode",
    "mcp__appian-dev__updateRecordData",
    "mcp__appian-dev__updateRecordType",
    "mcp__appian-dev__updateRecordTypeAction",
    "mcp__appian-dev__updateRecordTypeField",
    "mcp__appian-dev__updateRecordTypeRelationship",
    "mcp__appian-dev__updateRecordTypeUserFilter",
    "mcp__appian-dev__updateRecordTypeView",
    "mcp__appian-dev__updateSite",
    "mcp__appian-dev__updateWebApi",
    "mcp__appian-dev__uploadDocument",
    "mcp__appian-dev__validateDesignObject",
    "mcp__appian-dev__validateExpression",
    "mcp__appian__appian_aggregate_business_process",
    "mcp__appian__appian_data_fabric_metadata",
    "mcp__appian__appian_data_fabric_sql_query",
    "mcp__appian__appian_discover_cases",
    "mcp__appian__appian_discover_events_in_case",
    "mcp__appian__appian_explore_attributes",
    "mcp__appian__appian_get_agent_status",
    "mcp__appian__appian_get_business_process",
    "mcp__appian__appian_get_filter_reference",
    "mcp__appian__appian_get_insights_status",
    "mcp__appian__appian_get_process_status",
    "mcp__appian__appian_get_recommendations_reference",
    "mcp__appian__appian_get_tool_schema",
    "mcp__appian__appian_invoke_agent",
    "mcp__appian__appian_invoke_expression_rule",
    "mcp__appian__appian_invoke_process_model",
    "mcp__appian__appian_list_business_processes",
    "mcp__appian__appian_model_statistics",
    "mcp__appian__appian_search_tools",
    "mcp__appian__appian_start_insights",
    "mcp__appian__ping",
)

OTHER_SERVERS = (
    "mcp__acme-lowcode__createRecordType",
    "mcp__claude-in-chrome__upload_image",
    "mcp__claude_ai_Figma__add_code_connect_map",
    "mcp__claude_ai_Figma__create_new_file",
    "mcp__claude_ai_Figma__upload_assets",
    "mcp__claude_ai_Google_Drive__create_file",
    "mcp__claude_ai_Supabase__create_branch",
    "mcp__claude_ai_Supabase__create_project",
    "mcp__claude_ai_Supabase__delete_branch",
    "mcp__claude_ai_Supabase__execute_sql",
    "mcp__claude_ai_Vercel__add_toolbar_reaction",
    "mcp__claude_ai_Vercel__update_project_deployment_protection",
)

# counts: 166 12
# Case is the half of this that a corpus of real names cannot test, because
# every real Appian tool is lowercase-initial. It is still the direction that
# matters: Claude Code applies the JSON matcher as written, and that matcher
# spells `[Aa]ppian` precisely because it has no case-insensitive flag to
# lean on. A Python side compiled with re.IGNORECASE would gate these and
# the JSON side would not route them -- broader here than there, which is
# the silent failure the comment warns about.
CASE_VARIANTS = (
    "mcp__APPIAN-dev__createRecordType",
    "mcp__Appian-Dev__DeleteRecordType",
    "mcp__appian-dev__CreateInterface",
    "mcp__appian__APPIAN_INVOKE_PROCESS_MODEL",
)


def matcher_for(event, handler):
    """The matcher on the hooks.json entry that routes to `handler`."""
    with open(HOOKS_JSON, encoding="utf-8") as f:
        hooks = json.load(f)["hooks"]
    for entry in hooks[event]:
        if any(handler in h["command"] for h in entry["hooks"]):
            return entry.get("matcher")
    raise AssertionError("no %s entry routes %r" % (event, handler))


class TestHooksJsonRoutesEverythingThePatternGates(unittest.TestCase):
    """The one invariant that ties the two halves together."""

    ALL = APPIAN_TOOLS + OTHER_SERVERS + CASE_VARIANTS

    def setUp(self):
        # Claude Code matches these as written: no IGNORECASE, and anchored
        # at the start the way `re.match` anchors.
        self.scope = re.compile(matcher_for("PreToolUse", "scope-gate"))
        self.log = re.compile(matcher_for("PostToolUse", "log-write"))

    def _unrouted_by(self, matcher):
        return [n for n in self.ALL if WRITE_TOOL_RE.match(n) and not matcher.match(n)]

    def test_the_scope_gate_receives_every_call_the_pattern_gates(self):
        # The failure this catches: a gate that returns "ask" in a unit test
        # and never runs in production.
        self.assertEqual(self._unrouted_by(self.scope), [])

    def test_the_write_log_receives_them_too(self):
        # Same invariant, second consumer. The freshness check reads this
        # log, so a write that is gated but not logged makes every later
        # verdict look fresh.
        self.assertEqual(self._unrouted_by(self.log), [])

    def test_destructive_is_a_subset_of_write(self):
        # `scope_gate` returns early for anything `_is_write_tool` rejects,
        # so a name matched only by DESTRUCTIVE_TOOL_RE is never asked
        # about -- the confirmation on the one irreversible class would be
        # skipped precisely where it matters.
        self.assertEqual([n for n in self.ALL
                          if DESTRUCTIVE_TOOL_RE.match(n) and not WRITE_TOOL_RE.match(n)], [])

    def test_the_corpus_actually_exercises_the_gate(self):
        # Without this the three assertions above pass on an empty corpus,
        # which is the "nothing checked is not a pass" failure in the shape
        # of a green test.
        gated = [n for n in self.ALL if WRITE_TOOL_RE.match(n)]
        self.assertGreater(len(gated), 40)
        self.assertGreater(len([n for n in self.ALL if DESTRUCTIVE_TOOL_RE.match(n)]), 10)

    def test_the_runtime_verbs_that_were_dead_are_routed_now(self):
        # The specific regression. Each of these starts real work in a
        # shared environment.
        for name in ("mcp__appian__appian_invoke_process_model",
                     "mcp__appian__appian_invoke_agent",
                     "mcp__appian-dev__testProcessModel"):
            self.assertTrue(WRITE_TOOL_RE.match(name), name)
            self.assertTrue(self.scope.match(name), name)

    def test_reads_and_replays_stay_free_on_both_sides(self):
        # Gating discovery and verification is how a harness gets switched
        # off. An expression rule has no side effects and stored test cases
        # are what a verification step is supposed to replay freely.
        #
        # "On both sides" is the name, and for a long time the body checked
        # only one: `WRITE_TOOL_RE`. The other side is not the JSON matcher
        # -- that one routes a bare `invoke|run|test` deliberately, so a real
        # write cannot escape the scope gate -- it is what the hooks DO with
        # what the matcher hands them. `log_write` never asked, and recorded
        # three expression-rule invocations as writes of a task that was
        # merely in flight, expiring every one of its verdicts. The missing
        # assertion is the one that would have caught it.
        for name in ("mcp__appian__appian_invoke_expression_rule",
                     "mcp__appian-dev__testRule",
                     "mcp__appian-dev__runAllInterfaceTestCases",
                     "mcp__appian-dev__getObjectDependents",
                     "mcp__appian-dev__listRecordTypes"):
            self.assertIsNone(WRITE_TOOL_RE.match(name), name)
            with tempfile.TemporaryDirectory() as root:
                log_write({"tool_name": name, "tool_input": {}},
                          {"evidenceDir": os.path.join(root, "evidence"),
                           "activeTask": {"id": "T-1", "allowedObjects": ["A"]}})
                self.assertFalse(
                    os.path.isfile(os.path.join(root, "evidence", "operations.jsonl")),
                    "%s is a read: it must not land in the write log" % name)

    def test_another_vendors_write_tools_are_not_measured_against_appian_scope(self):
        # Before the server name had to carry `appian`, a Supabase branch
        # deletion was checked against an Appian task's allowedObjects.
        for name in OTHER_SERVERS:
            self.assertIsNone(WRITE_TOOL_RE.match(name), name)


if __name__ == "__main__":
    unittest.main()
