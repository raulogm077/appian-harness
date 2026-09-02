"""The declared perimeter (norm § 7.2) and its migration ask (norm § 15).

The failure this whole file exists to catch: a project registers its Appian
MCP server under a name without `appian` in it, every hook runs and answers,
and nothing is governed -- the plugin's gravest silent failure, paid once in
0.5.2. With `appianMcpToolPrefixes[]` declared, the gates match by prefix;
without it they fall back to the 0.6 regex, session-start says the literal
phrase, and the first write of the session is an ask, not a notice.
"""
import json, os, re, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import (PERIMETER_BLIND_PHRASE, _is_destructive_tool,
                           _is_write_tool, scope_gate, session_start)

HOOKS_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hooks.json")


def declared(*prefixes):
    return {"appianMcpToolPrefixes": list(prefixes)}


class TestDeclaredPrefixesGateARenamedServer(unittest.TestCase):
    """§ 7.2: the perimeter is read from configuration, not guessed."""

    CFG = declared("mcp__lcp__", "mcp__lcp-runtime__")

    def test_a_write_on_a_declared_server_is_gated_whatever_its_name(self):
        self.assertTrue(_is_write_tool("mcp__lcp__createRecordType", self.CFG))
        self.assertTrue(_is_write_tool("mcp__lcp__updateInterface", self.CFG))

    def test_the_runtime_style_prefix_is_covered_too(self):
        # Declaring only the design server would un-gate process starts in
        # silence -- the same failure in different clothes (§ 7.2).
        self.assertTrue(_is_write_tool(
            "mcp__lcp-runtime__appian_invoke_process_model", self.CFG))

    def test_verbs_still_decide_after_the_prefix(self):
        # The perimeter says which servers are Appian; it must not turn
        # reads and replays on those servers into gated writes.
        for name in ("mcp__lcp__getRecordType",
                     "mcp__lcp__listRecordTypes",
                     "mcp__lcp__validateExpression",
                     "mcp__lcp-runtime__appian_invoke_expression_rule"):
            self.assertFalse(_is_write_tool(name, self.CFG), name)

    def test_an_undeclared_server_is_outside_the_perimeter(self):
        # Declared wins entirely: the fallback regex serves configurations
        # that do not declare, never a declared one (§ 7.2 piece 3).
        self.assertFalse(_is_write_tool("mcp__appian-dev__createRecordType", self.CFG))
        self.assertFalse(_is_write_tool("mcp__claude_ai_Supabase__execute_sql", self.CFG))

    def test_destructive_follows_the_declared_perimeter(self):
        self.assertTrue(_is_destructive_tool("mcp__lcp__deleteConstant", self.CFG))
        self.assertFalse(_is_destructive_tool("mcp__lcp__createConstant", self.CFG))
        self.assertFalse(_is_destructive_tool("mcp__appian-dev__deleteConstant", self.CFG))

    def test_destructive_stays_a_subset_of_write(self):
        # scope_gate returns early for what _is_write_tool rejects, so a
        # name only the destructive half matched would skip the one
        # confirmation that cannot be skipped.
        for name in ("mcp__lcp__deleteConstant", "mcp__lcp__removeGroupMember",
                     "mcp__lcp__updateRecordData"):
            if _is_destructive_tool(name, self.CFG):
                self.assertTrue(_is_write_tool(name, self.CFG), name)


class TestTheFallbackServesUndeclaredConfigurations(unittest.TestCase):
    def test_no_config_and_no_key_behave_like_06(self):
        for cfg in (None, {}, {"appianMcpToolPrefixes": None}):
            self.assertTrue(_is_write_tool("mcp__appian-dev__createRecordType", cfg))
            self.assertFalse(_is_write_tool("mcp__lcp__createRecordType", cfg))
            self.assertTrue(_is_destructive_tool("mcp__appian-dev__deleteConstant", cfg))

    def test_junk_values_are_an_undeclared_perimeter_never_a_crash(self):
        # An empty list is a missing key (§ 7.2: "falta o está vacía"), and
        # junk entries must not widen nor narrow the gate silently.
        for junk in ([], [""], [42, None], "mcp__lcp__", {"a": 1}):
            cfg = {"appianMcpToolPrefixes": junk}
            self.assertTrue(_is_write_tool("mcp__appian-dev__createRecordType", cfg),
                            repr(junk))
            self.assertFalse(_is_write_tool("mcp__lcp__createRecordType", cfg),
                             repr(junk))


class TestSessionStartRepeatsThePhrase(unittest.TestCase):
    """§ 7.2 piece 3: checked every session, said with these words."""

    def _context(self, cfg):
        return session_start({}, cfg).get("additionalContext", "")

    def test_a_missing_or_empty_key_produces_the_literal_phrase(self):
        for cfg in ({"mcpServers": None}, {"mcpServers": None, "appianMcpToolPrefixes": []}):
            out = self._context(cfg)
            self.assertIn(PERIMETER_BLIND_PHRASE, out)
            self.assertIn("appian-init", out)  # the remedy that exists (§ 15)

    def test_a_declared_perimeter_does_not_warn(self):
        out = self._context({"mcpServers": None,
                             "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"]})
        self.assertNotIn(PERIMETER_BLIND_PHRASE, out)


class TestTheFirstWriteWithoutTheKeyIsAnAsk(unittest.TestCase):
    """§ 15: a notice is not enough when what failed is the perimeter."""

    TOOL = "mcp__appian-dev__updateConstant"

    def _cfg(self, root):
        return {"evidenceDir": os.path.join(root, "evidence"),
                "activeTask": {"id": "T-1", "allowedObjects": ["PR_CONST"]}}

    def _payload(self, session):
        return {"tool_name": self.TOOL, "session_id": session,
                "tool_input": {"name": "PR_CONST"}}

    def test_it_asks_once_per_session_and_records_it(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = self._cfg(root)
            first = scope_gate(self._payload("s-1"), cfg)
            self.assertEqual(first["permissionDecision"], "ask")
            self.assertIn("appianMcpToolPrefixes", first["permissionDecisionReason"])

            # The decision was recorded against the session, so the same
            # session does not pay the prompt twice ...
            second = scope_gate(self._payload("s-1"), cfg)
            self.assertNotIn("appianMcpToolPrefixes",
                             second["permissionDecisionReason"])

            # ... and a new session pays it again: the remedy is running
            # /appian-init --adopt, not surviving one prompt.
            third = scope_gate(self._payload("s-2"), cfg)
            self.assertIn("appianMcpToolPrefixes", third["permissionDecisionReason"])

            rows = []
            with open(os.path.join(root, "evidence", "gate-decisions.jsonl"),
                      encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line)
                    if entry.get("event") == "perimeter-ask":
                        rows.append(entry.get("sessionId"))
            self.assertEqual(rows, ["s-1", "s-2"])

    def test_a_declared_perimeter_never_pays_this_ask(self):
        with tempfile.TemporaryDirectory() as root:
            cfg = dict(self._cfg(root),
                       appianMcpToolPrefixes=["mcp__appian-dev__", "mcp__appian__"])
            out = scope_gate(self._payload("s-1"), cfg)
            self.assertNotIn("appianMcpToolPrefixes",
                             out.get("permissionDecisionReason", ""))


class TestHooksJsonRoutesAnyDeclarablePrefix(unittest.TestCase):
    """The static matcher cannot read configuration, so it must route every
    MCP name a declaration could make gateable -- the Python side filters."""

    def _matcher(self, event, handler):
        with open(HOOKS_JSON, encoding="utf-8") as f:
            hooks = json.load(f)["hooks"]
        for entry in hooks[event]:
            if any(handler in h["command"] for h in entry["hooks"]):
                return re.compile(entry["matcher"])
        raise AssertionError("no %s entry routes %r" % (event, handler))

    def test_a_renamed_server_reaches_the_gate_and_the_log(self):
        for event, handler in (("PreToolUse", "scope-gate"),
                               ("PostToolUse", "log-write"),
                               ("PostToolUseFailure", "failure-notice")):
            matcher = self._matcher(event, handler)
            for name in ("mcp__lcp__createRecordType",
                         "mcp__lcp-runtime__appian_invoke_process_model",
                         "mcp__appdev__deleteConstant"):
                self.assertTrue(matcher.match(name), "%s: %s" % (event, name))


if __name__ == "__main__":
    unittest.main()
