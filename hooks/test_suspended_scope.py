"""`suspended`: the hotfix path (norm § 4.5).

Embedded with a cap of one, disjoint by objects, resumed for free when the
hotfix closes, and expiring by SESSIONS -- never by clock. The trap this
closes: without the exit, a two-minute bug costs closing or abandoning a
whole feature, and the real consequence is operating OUTSIDE the harness.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import harness_hooks as HH
from harness_hooks import closure_gate, scope_gate, session_start, state_gate
from test_grant import GRANT, signed_cfg
from test_state_gate import (decisions, observe, projection, read_scope,
                             write_scope)
from test_scope_schema import v2_scope


def suspend(c):
    scope = read_scope(c)
    scope["request"] = "suspend"
    c = write_scope(c, scope)
    observe(c)
    return dict(c, activeTask=read_scope(c))


def open_hotfix(c, embed=True, objects=("PR_CONST_HOTFIX",), instance="inst-hf"):
    embedded = read_scope(c) if embed else None
    hotfix = v2_scope(id="F-hotfix", instanceId=instance,
                      intent="arreglar el literal roto",
                      allowedObjects=list(objects),
                      grant=dict(GRANT, instanceId=instance,
                                 objects=list(objects)),
                      suspendedScope=embedded,
                      resumeFrom=embedded.get("id") if embedded else None)
    c = write_scope(c, hotfix)
    observe(c)
    return dict(c, activeTask=read_scope(c))


class TestOneSuspendedScopeAtMost(unittest.TestCase):
    def test_a_second_suspend_is_rejected_with_the_remedy(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            c = open_hotfix(c)
            scope = read_scope(c)
            scope["request"] = "suspend"
            c = write_scope(c, scope)
            out = observe(c)
            self.assertEqual(read_scope(c)["status"], "in-flight")
            self.assertIn("suspendido", out.get("additionalContext", ""))


class TestTheHotfixEmbedsTheSuspendedScope(unittest.TestCase):
    def test_a_disjoint_hotfix_opens_and_signs(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            c = open_hotfix(c)
            p = projection(c)
            self.assertEqual(p["instanceId"], "inst-hf")
            self.assertEqual(p["scope"]["suspendedScope"]["instanceId"], "inst-1")
            self.assertEqual(p["scope"]["suspendedScope"]["status"], "suspended")

    def test_the_embedded_copy_is_the_signed_one_not_the_agents(self):
        # The constructor copies the suspended scope into the new file; the
        # hook re-embeds its own signed copy, so a doctored copy buys nothing.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            doctored = read_scope(c)
            doctored["allowedObjects"] = ["OTRA_COSA"]
            hotfix = v2_scope(id="F-hotfix", instanceId="inst-hf",
                              intent="arreglo",
                              allowedObjects=["PR_CONST_HOTFIX"],
                              grant=dict(GRANT, instanceId="inst-hf",
                                         objects=["PR_CONST_HOTFIX"]),
                              suspendedScope=doctored, resumeFrom=doctored["id"])
            c = write_scope(c, hotfix)
            observe(c)
            embedded = projection(c)["scope"]["suspendedScope"]
            self.assertEqual(embedded["allowedObjects"],
                             ["GDE_INT_Lista", "_uuid-lista"])

    def test_an_overlapping_hotfix_is_a_persons_decision(self):
        # § 4.5: working on an object with a live verdict from another
        # scope IS a decision, so the write asks instead of flowing.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            c = open_hotfix(c, objects=("GDE_INT_Lista",), instance="inst-hf2")
            # Not signed: the projection still holds the suspended scope.
            self.assertEqual(projection(c)["instanceId"], "inst-1")
            out = scope_gate({"tool_name": "mcp__appian-dev__updateConstant",
                              "session_id": "s-1",
                              "tool_input": {"name": "GDE_INT_Lista"}}, c)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("suspendido", out["permissionDecisionReason"])


class TestClosingTheHotfixResumesForFree(unittest.TestCase):
    def test_the_suspended_scope_comes_back_in_flight_with_its_grant(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            c = open_hotfix(c)
            scope = read_scope(c)
            scope["request"] = "close"
            c = write_scope(c, scope)
            observe(c)
            out = closure_gate({}, dict(c, activeTask=read_scope(c)))
            self.assertEqual(out["decision"], "approve")
            restored = read_scope(c)
            self.assertEqual(restored["instanceId"], "inst-1")
            self.assertEqual(restored["status"], "in-flight")
            self.assertIsNone(restored["suspendedScope"])
            # No new grant and nothing re-issued (§ 4.5): the original
            # grant is intact and a write on the original object flows.
            self.assertEqual(restored["grant"]["instanceId"], "inst-1")
            out = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                              "session_id": "s-1",
                              "tool_input": {"uuid": "_uuid-lista"}},
                             dict(c, activeTask=restored))
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))


class TestExpiryCountsSessionsNotClocks(unittest.TestCase):
    def _session(self, c, session_id):
        return session_start({"session_id": session_id,
                              "transcript_path": "/tmp/t.jsonl"}, c)

    def test_sessions_seen_increments_once_per_session(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            c = open_hotfix(c)
            self._session(c, "s-1")
            self._session(c, "s-1")
            c = dict(c, activeTask=read_scope(c))
            self.assertEqual(read_scope(c)["suspendedScope"]["sessionsSeen"], 1)
            self._session(c, "s-2")
            self.assertEqual(read_scope(c)["suspendedScope"]["sessionsSeen"], 2)

    def test_the_third_session_kills_the_grant_not_the_scope(self):
        # § 4.5: expiring kills the grant; the scope stays suspended and
        # keeps being announced. Resuming then requires a NEW grant, which
        # materialises as the restored scope carrying none.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            c = suspend(c)
            c = open_hotfix(c)
            for session in ("s-1", "s-2", "s-3"):
                out = self._session(dict(c, activeTask=read_scope(c)), session)
            self.assertIn("grant", out.get("additionalContext", ""))
            scope = read_scope(c)
            self.assertEqual(scope["suspendedScope"]["sessionsSeen"], 3)
            self.assertEqual(scope["status"], "in-flight")
            # Close the hotfix: the restored scope has no grant left.
            scope["request"] = "close"
            c = write_scope(c, scope)
            observe(c)
            closure_gate({}, dict(c, activeTask=read_scope(c)))
            restored = read_scope(c)
            self.assertEqual(restored["instanceId"], "inst-1")
            self.assertIsNone(restored["grant"])
            out = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                              "session_id": "s-9",
                              "tool_input": {"uuid": "_uuid-lista"}},
                             dict(c, activeTask=restored))
            self.assertEqual(out["permissionDecision"], "ask")

    def test_sessions_jsonl_records_the_session(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            self._session(c, "s-7")
            path = os.path.join(c["evidenceDir"], "sessions.jsonl")
            with open(path, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(rows[0]["sessionId"], "s-7")
            self.assertEqual(rows[0]["transcriptPath"], "/tmp/t.jsonl")


if __name__ == "__main__":
    unittest.main()
