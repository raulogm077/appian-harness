"""One honest v07 lifecycle, end to end, twice (§ 16 Phase 2's DoD, the
deterministic half): a micro and a task with tasks{} open, write and close
with ZERO asks along the way -- every gate decision on the way is an allow,
and the close is a signed terminal state, not a declared one.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import closure_gate, log_write, scope_gate, state_gate
from test_grant import GRANT, signed_cfg
from test_state_gate import projection, read_scope, write_scope


class LifecycleMixin:
    def _write(self, c, tool, tool_use_id, **tool_input):
        out = scope_gate({"tool_name": tool, "session_id": "s-e2e",
                          "tool_use_id": tool_use_id,
                          "tool_input": tool_input}, c)
        self.assertEqual(out["permissionDecision"], "allow",
                         out.get("permissionDecisionReason"))
        log_write({"tool_name": tool, "tool_use_id": tool_use_id,
                   "tool_input": tool_input,
                   "tool_response": json.dumps({"uuid": tool_input.get("uuid")
                                                or "_uuid-nuevo",
                                                "versionId": 1})}, c)

    def _close(self, c):
        scope = read_scope(c)
        scope["request"] = "close"
        c = write_scope(c, scope)
        state_gate({"tool_name": "Write",
                    "tool_input": {"file_path": c["activeTaskFile"]}}, c)
        c = dict(c, activeTask=read_scope(c))
        out = closure_gate({}, c)
        self.assertEqual(out["decision"], "approve", out)
        return c


class TestAMicroOpensWritesAndCloses(LifecycleMixin, unittest.TestCase):
    def test_the_whole_lane_without_one_ask(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            self._write(c, "mcp__appian-dev__updateInterface", "tu-1",
                        uuid="_uuid-lista", expression="a!textField()")
            c = self._close(c)
            final = read_scope(c)
            self.assertEqual(final["status"], "closed")
            self.assertEqual(projection(c)["scope"]["status"], "closed")
            closures = os.path.join(c["evidenceDir"], "task-closures.jsonl")
            with open(closures, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            self.assertEqual(rows[-1]["status"], "closed")


class TestATaskWithTasksOpensWritesAndCloses(LifecycleMixin, unittest.TestCase):
    def test_two_entries_two_writes_one_close(self):
        objects = ["_uuid-a", "_uuid-b"]
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           tasks={"T-1": ["_uuid-a"], "T-2": ["_uuid-b"]},
                           allowedObjects=objects,
                           grant=dict(GRANT, objects=objects))
            self._write(c, "mcp__appian-dev__updateInterface", "tu-1",
                        uuid="_uuid-a", expression="a!textField()")
            self._write(c, "mcp__appian-dev__updateExpressionRule", "tu-2",
                        uuid="_uuid-b", expression="1+1")
            c = self._close(c)
            self.assertEqual(read_scope(c)["status"], "closed")
            ops = os.path.join(c["evidenceDir"], "operations.jsonl")
            with open(ops, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            resolved = [r for r in rows if r["result"] == "ok"]
            self.assertEqual({r["writeSeq"] for r in resolved}, {1, 2})


if __name__ == "__main__":
    unittest.main()
