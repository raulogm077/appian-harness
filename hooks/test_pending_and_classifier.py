"""The pending row, the writeSeq, and the P3 classifier (norm §§ 7.1, 7.6).

One vertical on purpose: the scope gate reserves the sequence and writes the
intention BEFORE the call leaves; the write log resolves it BY tool_use_id --
never "the last pending", because parallel writes come back out of order --
against the response shapes Phase 0 captured from the live environment. What
no shape matches is `ambiguous`, which never counts and demands a re-read.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import harness_hooks as HH
from harness_hooks import closure_gate, failure_notice, log_write, scope_gate
from test_grant import GRANT, signed_cfg


def ops(c):
    path = os.path.join(c["evidenceDir"], "operations.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def gate(c, tool, tool_use_id, **tool_input):
    return scope_gate({"tool_name": tool, "session_id": "s-1",
                       "tool_use_id": tool_use_id, "tool_input": tool_input}, c)


def resolve(c, tool, tool_use_id, response, **tool_input):
    return log_write({"tool_name": tool, "tool_use_id": tool_use_id,
                      "tool_input": tool_input, "tool_response": response}, c)


class TestTheAllowReservesTheSequence(unittest.TestCase):
    def test_an_allowed_write_leaves_a_pending_row_first(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            out = gate(c, "mcp__appian-dev__updateInterface", "tu-1",
                       uuid="_uuid-lista", expression="1")
            self.assertEqual(out["permissionDecision"], "allow")
            rows = ops(c)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["result"], "pending")
            self.assertEqual(rows[0]["writeSeq"], 1)
            self.assertEqual(rows[0]["toolUseId"], "tu-1")
            self.assertTrue(rows[0]["inScope"])

    def test_sequences_grow_monotonically(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            gate(c, "mcp__appian-dev__updateInterface", "tu-1", uuid="_uuid-lista")
            gate(c, "mcp__appian-dev__updateInterface", "tu-2", uuid="_uuid-lista")
            self.assertEqual([r["writeSeq"] for r in ops(c)], [1, 2])

    def test_an_asked_write_reserves_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, grant=None)
            out = gate(c, "mcp__appian-dev__updateInterface", "tu-1",
                       uuid="_uuid-lista")
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertEqual(ops(c), [])


class TestResolutionIsByToolUseId(unittest.TestCase):
    """P3's real shapes, resolved against the reservation they belong to."""

    def _reserved(self, root):
        c = signed_cfg(root)
        gate(c, "mcp__appian-dev__updateInterface", "tu-1", uuid="_uuid-lista",
             expression="a!textField()")
        gate(c, "mcp__appian-dev__updateInterface", "tu-2", uuid="_uuid-lista",
             expression="a!textField()")
        return c

    def _last_for(self, c, tool_use_id):
        rows = [r for r in ops(c) if r.get("toolUseId") == tool_use_id]
        return rows[-1]

    def test_ok_json_with_uuid_resolves_ok_out_of_order(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._reserved(root)
            # tu-2 answers first: parallel writes invert response order.
            resolve(c, "mcp__appian-dev__updateInterface", "tu-2",
                    json.dumps({"uuid": "_uuid-lista", "versionId": 7}),
                    uuid="_uuid-lista", expression="a!textField()")
            last = self._last_for(c, "tu-2")
            self.assertEqual(last["result"], "ok")
            self.assertEqual(last["writeSeq"], 2)
            self.assertEqual(self._last_for(c, "tu-1")["result"], "pending")

    def test_the_delete_shape_without_identity_is_still_ok(self):
        # The Phase 0 cleanup's gift: a successful delete answers
        # {"result": "Deleted successfully"} with no uuid and no versionId.
        with tempfile.TemporaryDirectory() as root:
            c = self._reserved(root)
            resolve(c, "mcp__appian-dev__updateInterface", "tu-1",
                    json.dumps({"result": "Deleted successfully"}),
                    uuid="_uuid-lista")
            self.assertEqual(self._last_for(c, "tu-1")["result"], "ok")

    def test_the_two_failed_shapes(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._reserved(root)
            resolve(c, "mcp__appian-dev__updateInterface", "tu-1",
                    "API error (HTTP 400): Parent folder not found: _x",
                    uuid="_uuid-lista")
            resolve(c, "mcp__appian-dev__updateInterface", "tu-2",
                    "Unexpected error: 'TIPO_INEXISTENTE' is not a valid "
                    "CreateConstantRequestType", uuid="_uuid-lista")
            self.assertEqual(self._last_for(c, "tu-1")["result"], "failed")
            self.assertEqual(self._last_for(c, "tu-2")["result"], "failed")

    def test_a_tool_use_error_envelope_is_failed(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._reserved(root)
            resolve(c, "mcp__appian-dev__updateInterface", "tu-1",
                    "<tool_use_error>timed out</tool_use_error>",
                    uuid="_uuid-lista")
            self.assertEqual(self._last_for(c, "tu-1")["result"], "failed")

    def test_an_echo_without_identity_is_ambiguous(self):
        # reorderRecordTypeViews' real answer: 200 with a re-canonicalised
        # echo, no uuid, no versionId, no error marker (P3).
        with tempfile.TemporaryDirectory() as root:
            c = self._reserved(root)
            resolve(c, "mcp__appian-dev__updateInterface", "tu-1",
                    json.dumps({"views": [{"nameExpr": "x"}]}),
                    uuid="_uuid-lista")
            self.assertEqual(self._last_for(c, "tu-1")["result"], "ambiguous")

    def test_a_failed_call_resolves_through_the_failure_notice(self):
        # P5: a tool error produces PostToolUseFailure, not PostToolUse, so
        # the notice is what keeps the reservation from dangling.
        with tempfile.TemporaryDirectory() as root:
            c = self._reserved(root)
            failure_notice({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_use_id": "tu-1",
                            "tool_input": {"uuid": "_uuid-lista"}}, c)
            self.assertEqual(self._last_for(c, "tu-1")["result"], "failed")


class TestBehaviouralIsDecidedFromThePayload(unittest.TestCase):
    def _row(self, root, tool_input, response=None):
        c = signed_cfg(root)
        resolve(c, "mcp__appian-dev__updateInterface", "tu-9",
                response or json.dumps({"uuid": "_uuid-lista", "versionId": 1}),
                **tool_input)
        return ops(c)[-1], c

    def test_description_only_is_not_behavioural(self):
        with tempfile.TemporaryDirectory() as root:
            row, _ = self._row(root, {"uuid": "_uuid-lista",
                                      "description": "mejor texto"})
            self.assertFalse(row["behavioural"])

    def test_an_expression_is_behavioural_and_hashed(self):
        with tempfile.TemporaryDirectory() as root:
            row, _ = self._row(root, {"uuid": "_uuid-lista",
                                      "expression": "a!textField()"})
            self.assertTrue(row["behavioural"])
            self.assertTrue(row["expressionHash"])

    def test_a_rename_is_behavioural(self):
        # `name` is not metadata (§ 3.2): rules are invoked by name.
        with tempfile.TemporaryDirectory() as root:
            row, _ = self._row(root, {"uuid": "_uuid-lista", "name": "GDE_INT_L2"})
            self.assertTrue(row["behavioural"])

    def test_the_file_path_is_read_from_disk_for_the_hash(self):
        with tempfile.TemporaryDirectory() as root:
            sail = os.path.join(root, "big.sail")
            with open(sail, "w", encoding="utf-8") as f:
                f.write("a!formLayout()")
            row, _ = self._row(root, {"uuid": "_uuid-lista",
                                      "expressionFilePath": sail})
            self.assertTrue(row["behavioural"])
            self.assertTrue(row["expressionHash"])

    def test_an_unreadable_file_fails_to_the_expensive_side(self):
        with tempfile.TemporaryDirectory() as root:
            row, _ = self._row(root, {"uuid": "_uuid-lista",
                                      "expressionFilePath":
                                          os.path.join(root, "no-existe.sail")})
            self.assertTrue(row["behavioural"])
            self.assertIsNone(row["expressionHash"])

    def test_a_non_expression_type_is_always_behavioural(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["_rt-1"],
                           grant=dict(GRANT, objects=["_rt-1"]))
            resolve(c, "mcp__appian-dev__updateRecordType", "tu-9",
                    json.dumps({"uuid": "_rt-1", "versionId": 2}),
                    uuid="_rt-1", description="solo descripción")
            self.assertTrue(ops(c)[-1]["behavioural"])


class TestCreatedUuidsLinkWithoutAFalseAsk(unittest.TestCase):
    def test_the_refine_by_uuid_flow(self):
        # § 4.1: create by granted name, then refine by the UUID Appian
        # returned. The link the hook wrote is what keeps the second write
        # from asking (eval safety-created-uuid-no-false-ask).
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["GDE_QRY_Nueva"],
                           grant=dict(GRANT, objects=[]))
            first = gate(c, "mcp__appian-dev__createExpressionRule", "tu-1",
                         name="GDE_QRY_Nueva", expression="1+1")
            self.assertEqual(first["permissionDecision"], "allow",
                             first.get("permissionDecisionReason"))
            resolve(c, "mcp__appian-dev__createExpressionRule", "tu-1",
                    json.dumps({"uuid": "_uuid-nueva", "versionId": 1}),
                    name="GDE_QRY_Nueva", expression="1+1")
            second = gate(c, "mcp__appian-dev__updateExpressionRule", "tu-2",
                          uuid="_uuid-nueva", expression="2+2")
            self.assertEqual(second["permissionDecision"], "allow",
                             second.get("permissionDecisionReason"))

    def test_an_unlinked_uuid_still_asks(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None,
                           allowedObjects=["GDE_QRY_Nueva"],
                           grant=dict(GRANT, objects=[]))
            out = gate(c, "mcp__appian-dev__updateExpressionRule", "tu-2",
                       uuid="_uuid-desconocida", expression="2+2")
            self.assertEqual(out["permissionDecision"], "ask")


class TestAPendingWithoutAnAnswerBlocksTheClose(unittest.TestCase):
    def test_the_case_ambiguous_does_not_cover(self):
        # § 7.1: no answer at all -- MCP down, timeout, session killed. The
        # closure gate treats it like ambiguous: re-read before closing.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            gate(c, "mcp__appian-dev__updateInterface", "tu-1",
                 uuid="_uuid-lista", expression="1")
            scope = json.load(open(c["activeTaskFile"], encoding="utf-8"))
            scope["request"] = "close"
            with open(c["activeTaskFile"], "w", encoding="utf-8") as f:
                json.dump(scope, f)
            # _build_config re-reads the file per hook invocation; mirror it.
            c = dict(c, activeTask=scope)
            HH.state_gate({"tool_name": "Write",
                           "tool_input": {"file_path": c["activeTaskFile"]}}, c)
            out = closure_gate({}, dict(c, activeTask=json.load(
                open(c["activeTaskFile"], encoding="utf-8"))))
            self.assertEqual(out["decision"], "block")
            self.assertIn("pending", out["reason"])


if __name__ == "__main__":
    unittest.main()
