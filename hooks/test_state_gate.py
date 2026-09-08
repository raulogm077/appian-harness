"""The single writer of `status` (norm §§ 4.3-4.4) and what makes it single.

The machinery under test: `state-gate` observes every file write; on the v07
scope file it validates, transitions from `request`, and signs by rewriting
the hook-owned projection (`evidence/scope-projection.json`). A status nobody
signed reverts; a scope with no signed state does not exist for the gates;
an agent write into a hook-owned journal poisons trust for that instance.

The cheap exits this closes: hand-writing `"status": "closed"` and stopping,
and hand-writing a plausible transition row for the hook to "remember".
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import harness_hooks as HH
from harness_hooks import closure_gate, scope_gate, state_gate
from test_harness_hooks import cfg
from test_grant import GRANT
from test_scope_schema import v2_scope

WRITE_TOOL = "mcp__appian-dev__updateConstant"


def write_scope(c, scope):
    path = c["activeTaskFile"]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scope, f)
    return dict(c, activeTask=scope)


def observe(c):
    """One state-gate pass over the scope file, as PostToolUse would run it."""
    return state_gate({"tool_name": "Write",
                       "tool_input": {"file_path": c["activeTaskFile"]}}, c)


def read_scope(c):
    with open(c["activeTaskFile"], encoding="utf-8") as f:
        return json.load(f)


def projection(c):
    path = os.path.join(c["evidenceDir"], "scope-projection.json")
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def decisions(c, event=None):
    path = os.path.join(c["evidenceDir"], "gate-decisions.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        rows = [json.loads(l) for l in f if l.strip()]
    return [r for r in rows if event is None or r.get("event") == event]


def gate(c, obj="GDE_INT_Lista"):
    return scope_gate({"tool_name": WRITE_TOOL, "session_id": "s-1",
                       "tool_input": {"name": obj}}, c)


class TestOpeningSignsTheScope(unittest.TestCase):
    def test_a_fresh_in_flight_scope_gets_a_projection_and_a_row(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            p = projection(c)
            self.assertIsNotNone(p)
            self.assertEqual(p["instanceId"], "inst-1")
            self.assertEqual(p["scope"]["status"], "in-flight")
            rows = decisions(c, "transition")
            self.assertEqual([(r["from"], r["to"]) for r in rows],
                             [(None, "in-flight")])

    def test_an_unsigned_scope_does_not_exist_for_the_scope_gate(self):
        # § 4.3: with no signed state to revert to, the scope does not exist
        # for the gate -- nothing is inferred from what the file says.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            out = gate(c)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("firmado", out["permissionDecisionReason"])

    def test_a_signed_scope_passes_the_integrity_check(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            out = gate(c)
            self.assertNotIn("firmado", out.get("permissionDecisionReason", ""))

    def test_a_file_born_with_a_terminal_status_is_not_signed(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope(status="closed"))
            observe(c)
            self.assertIsNone(projection(c))
            self.assertEqual(gate(c)["permissionDecision"], "ask")

    def test_a_file_born_open_fails_the_schema_before_the_state_machine(self):
        # `open` is not one of the seven states of § 4.2, so this file never
        # reaches `_enforce_state_machine`: it is refused one step earlier, by
        # the schema, and the reader is told which field is wrong. A different
        # branch from the terminal-status case above, and the one a builder
        # actually hits -- P2-PASADA-8 reached for `open` because the skill
        # only ever showed the 0.6 two-field shape.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope(status="open"))
            out = observe(c)
            self.assertIn("schema v2", out.get("additionalContext", ""))
            self.assertIn("status 'open'", out.get("additionalContext", ""))
            self.assertIsNone(projection(c))
            self.assertEqual(decisions(c, "transition"), [])
            self.assertEqual(gate(c)["permissionDecision"], "ask")


class TestRequestsDriveTransitions(unittest.TestCase):
    def _signed(self, root, **over):
        c = write_scope(cfg(root), v2_scope(**over))
        observe(c)
        return c

    def _rewrite(self, c, **changes):
        scope = read_scope(c)
        scope.update(changes)
        return write_scope(c, scope)

    def test_request_close_becomes_a_signed_closing(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._signed(root)
            c = self._rewrite(c, request="close")
            observe(c)
            after = read_scope(c)
            self.assertEqual(after["status"], "closing")
            self.assertIsNone(after["request"])
            self.assertEqual(projection(c)["scope"]["status"], "closing")
            self.assertIn(("in-flight", "closing"),
                          [(r["from"], r["to"]) for r in decisions(c, "transition")])

    def test_an_illegal_request_is_a_remedy_not_a_transition(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._signed(root)
            c = self._rewrite(c, request="resume")
            out = observe(c)
            after = read_scope(c)
            self.assertEqual(after["status"], "in-flight")
            self.assertIsNone(after["request"])
            self.assertIn("request", out.get("additionalContext", ""))

    def test_abandon_needs_its_reason(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._signed(root)
            c = self._rewrite(c, request="abandon")
            out = observe(c)
            self.assertEqual(read_scope(c)["status"], "in-flight")
            self.assertIn("abandon: ", out.get("additionalContext", ""))

    def test_abandon_with_a_reason_lands_and_registers_debt(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._signed(root)
            c = self._rewrite(c, request="abandon: era trabajo duplicado")
            observe(c)
            self.assertEqual(read_scope(c)["status"], "abandoned")
            debt = os.path.join(c["evidenceDir"], "deferred-debt.jsonl")
            with open(debt, encoding="utf-8") as f:
                rows = [json.loads(l) for l in f if l.strip()]
            self.assertTrue(any("duplicado" in json.dumps(r) for r in rows))

    def test_resume_reopens_a_closing_scope(self):
        # § 4.4 row 6, the remediation path back to work.
        with tempfile.TemporaryDirectory() as root:
            c = self._signed(root)
            c = self._rewrite(c, request="close")
            observe(c)
            c = self._rewrite(c, request="resume")
            observe(c)
            self.assertEqual(read_scope(c)["status"], "in-flight")


class TestHandWrittenStatesRevert(unittest.TestCase):
    def test_the_cheap_exit_is_closed(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            scope = read_scope(c)
            scope["status"] = "closed"
            scope["statusWriteSeq"] = 99
            c = write_scope(c, scope)
            out = observe(c)
            after = read_scope(c)
            self.assertEqual(after["status"], "in-flight")
            self.assertEqual(after["statusWriteSeq"], 0)
            self.assertTrue(decisions(c, "state-revert"))
            self.assertIn("request", out.get("additionalContext", ""))

    def test_swapping_the_instance_under_a_live_scope_asks(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            c = write_scope(c, v2_scope(instanceId="inst-2"))
            observe(c)
            out = gate(c)
            self.assertEqual(out["permissionDecision"], "ask")

    def test_a_terminal_projection_lets_a_new_instance_open(self):
        # Row 12: nothing leaves a terminal state -- working again means a
        # NEW scope, and that one signs normally.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            c = self._close(c)
            c = write_scope(c, v2_scope(id="F-2", instanceId="inst-2"))
            observe(c)
            self.assertEqual(projection(c)["instanceId"], "inst-2")

    def _close(self, c):
        scope = read_scope(c)
        scope["request"] = "abandon: terminado el experimento"
        c = write_scope(c, scope)
        observe(c)
        return c


class TestJournalTamperPoisonsTrust(unittest.TestCase):
    def test_an_agent_write_into_a_journal_is_recorded_and_asks(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            journal = os.path.join(c["evidenceDir"], "gate-decisions.jsonl")
            state_gate({"tool_name": "Write",
                        "tool_input": {"file_path": journal}}, c)
            self.assertTrue(decisions(c, "journal-tamper"))
            out = gate(c)
            self.assertEqual(out["permissionDecision"], "ask")

    def test_a_verdict_under_the_task_directory_is_not_tampering(self):
        # The auditor legitimately writes verdicts below evidence/<task>/;
        # the journals are the root-level registers and the projection.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            verdict = os.path.join(c["evidenceDir"], "F-listados",
                                   "practices-certify.json")
            state_gate({"tool_name": "Write",
                        "tool_input": {"file_path": verdict}}, c)
            self.assertFalse(decisions(c, "journal-tamper"))


class TestLegacyScopesKeepTheOldObserver(unittest.TestCase):
    def test_a_06_scope_is_logged_never_signed(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), {"id": "T-1", "allowedObjects": ["A"]})
            observe(c)
            self.assertIsNone(projection(c))
            log = os.path.join(c["evidenceDir"], "evidence-writes.jsonl")
            self.assertTrue(os.path.isfile(log))


class TestClosureGateWritesTheTerminalStates(unittest.TestCase):
    def _stopped(self, c, repeat=False):
        payload = {"stop_hook_active": True} if repeat else {}
        return closure_gate(payload, dict(c, activeTask=read_scope(c)))

    def test_closing_closes_and_is_signed(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            scope = read_scope(c)
            scope["request"] = "close"
            c = write_scope(c, scope)
            observe(c)
            out = self._stopped(c)
            self.assertEqual(out["decision"], "approve")
            self.assertEqual(read_scope(c)["status"], "closed")
            self.assertEqual(projection(c)["scope"]["status"], "closed")

    def test_in_flight_without_writes_is_a_handoff_not_a_close(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            for _ in range(4):
                out = self._stopped(c)
                self.assertEqual(out["decision"], "approve")
            self.assertEqual(read_scope(c)["status"], "in-flight")

    def test_the_third_stop_with_writes_blocks_then_closes_with_debt(self):
        # § 7.1 and row 13: write to Appian and walk away, and the third
        # Stop blocks once; the repeat closes `closed-with-debt`, debt
        # `never-closed`.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            HH._append_jsonl(os.path.join(c["evidenceDir"], "operations.jsonl"),
                             {"instanceId": "inst-1", "writeSeq": 1,
                              "task": "F-listados", "result": "ok"})
            self.assertEqual(self._stopped(c)["decision"], "approve")
            self.assertEqual(self._stopped(c)["decision"], "approve")
            third = self._stopped(c)
            self.assertEqual(third["decision"], "block")
            self.assertEqual(read_scope(c)["status"], "in-flight")
            fourth = self._stopped(c, repeat=True)
            self.assertEqual(fourth["decision"], "approve")
            self.assertEqual(read_scope(c)["status"], "closed-with-debt")
            debt = os.path.join(c["evidenceDir"], "deferred-debt.jsonl")
            with open(debt, encoding="utf-8") as f:
                self.assertIn("never-closed", f.read())


class TestRiskIsReimposedNotDrifted(unittest.TestCase):
    def test_a_stale_rewrite_cannot_lower_the_observed_risk(self):
        # § 5.3: `risk` is the hook's field. An agent rewriting the scope
        # file from a stale copy (or on purpose) gets it re-imposed; it must
        # neither stick as lowered nor poison the instance as drift.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            # The hook stamps high risk (as _note_observed_risk would).
            signed = projection(c)["scope"]
            HH._write_json_atomic(
                os.path.join(c["evidenceDir"], "scope-projection.json"),
                {"instanceId": "inst-1", "scope": dict(signed, risk="high"),
                 "signedAt": "2026-09-02T00:00:00Z"})
            HH._write_json_atomic(c["activeTaskFile"], dict(signed, risk="high"))
            # The agent rewrites the whole file from its stale copy.
            stale = dict(signed)  # risk is None here
            c = write_scope(c, stale)
            observe(c)
            self.assertEqual(read_scope(c)["risk"], "high")
            self.assertFalse(decisions(c, "anchored-drift"))


class TestTheAnchorSurvivesARequest(unittest.TestCase):
    """§ 4.1's anchor, on the path that used to walk around it.

    A single Write can carry both a `request` and a widened contract. While
    the request was handled first, `_sign_transition` signed the agent's
    file -- widening included -- and no drift was ever recorded, so any
    request laundered a bigger grant. These are the tests that were missing:
    a mutation removing the anchor entirely left the whole suite green.
    """

    def _signed_with_a_write(self, root, **over):
        c = write_scope(cfg(root), v2_scope(grant=GRANT, **over))
        observe(c)
        HH._reserve_write(c, read_scope(c),
                          {"tool_name": WRITE_TOOL, "tool_use_id": "tu-0",
                           "tool_input": {"name": "GDE_INT_Lista"}})
        return c

    def _widen(self, c, **extra):
        scope = read_scope(c)
        scope["allowedObjects"] = list(scope["allowedObjects"]) + ["GDE_INT_ROBADO"]
        scope["grant"] = dict(scope["grant"],
                              objects=list(scope["grant"]["objects"]) + ["GDE_INT_ROBADO"])
        scope.update(extra)
        return write_scope(c, scope)

    def test_a_widened_contract_riding_a_request_is_drift_not_a_transition(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._signed_with_a_write(root)
            c = self._widen(c, request="close")
            observe(c)
            self.assertTrue(decisions(c, "anchored-drift"))
            # Nothing signed: the transition would have carried the widening.
            self.assertEqual(projection(c)["scope"]["status"], "in-flight")
            self.assertNotIn("GDE_INT_ROBADO",
                             projection(c)["scope"]["allowedObjects"])

    def test_an_illegal_request_launders_nothing_either(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._signed_with_a_write(root)
            c = self._widen(c, request="resume")
            observe(c)
            self.assertTrue(decisions(c, "anchored-drift"))
            self.assertNotIn("GDE_INT_ROBADO",
                             projection(c)["scope"]["allowedObjects"])

    def test_a_clean_request_still_transitions(self):
        # The control: the fix must not cost the ordinary close its path.
        with tempfile.TemporaryDirectory() as root:
            c = self._signed_with_a_write(root)
            scope = read_scope(c)
            scope["request"] = "close"
            c = write_scope(c, scope)
            observe(c)
            self.assertEqual(read_scope(c)["status"], "closing")
            self.assertFalse(decisions(c, "anchored-drift"))

    def test_the_anchor_covers_the_suspended_scope(self):
        # § 4.5: the embedded copy carries its own grant and objects, so an
        # unanchored one is a second contract -- and closing the hotfix
        # would sign it straight back in.
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope(grant=GRANT))
            observe(c)
            base = read_scope(c)
            c = write_scope(c, dict(base, request="suspend"))
            observe(c)
            suspended = read_scope(c)
            hotfix = dict(base, id="F-hotfix", instanceId="inst-hot",
                          status="in-flight", statusWriteSeq=0, request=None,
                          allowedObjects=["_uuid-hot"],
                          grant=dict(GRANT, instanceId="inst-hot",
                                     objects=["_uuid-hot"]),
                          suspendedScope=suspended)
            c = write_scope(c, hotfix)
            observe(c)
            tampered = read_scope(c)
            tampered["suspendedScope"] = dict(tampered["suspendedScope"],
                                              allowedObjects=["_uuid-NUNCA"])
            c = write_scope(c, tampered)
            observe(c)
            kept = read_scope(c)["suspendedScope"]["allowedObjects"]
            self.assertNotIn("_uuid-NUNCA", kept)


class TestThePermissionModeIsSealedWhereverTheGrantAppears(unittest.TestCase):
    """§ 6.1. Sealing only fired when the grant arrived in a LATER edit, so
    the flow § 4.1's table documents -- the constructor writing the grant as
    it opens the scope -- produced a grant with no mode at all, which is
    indistinguishable from the permission system having been off."""

    def _grant_without_a_mode(self):
        return {k: v for k, v in GRANT.items() if k != "permissionMode"}

    def test_a_grant_present_at_opening_is_sealed(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope(grant=self._grant_without_a_mode()))
            state_gate({"tool_name": "Write", "permission_mode": "bypassPermissions",
                        "tool_input": {"file_path": c["activeTaskFile"]}}, c)
            self.assertEqual(read_scope(c)["grant"]["permissionMode"],
                             "bypassPermissions")

    def test_a_grant_arriving_later_is_still_sealed(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope())
            observe(c)
            scope = read_scope(c)
            scope["grant"] = self._grant_without_a_mode()
            c = write_scope(c, scope)
            state_gate({"tool_name": "Write", "permission_mode": "default",
                        "tool_input": {"file_path": c["activeTaskFile"]}}, c)
            self.assertEqual(read_scope(c)["grant"]["permissionMode"], "default")

    def test_an_already_sealed_mode_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as root:
            c = write_scope(cfg(root), v2_scope(grant=dict(GRANT)))
            state_gate({"tool_name": "Write", "permission_mode": "bypassPermissions",
                        "tool_input": {"file_path": c["activeTaskFile"]}}, c)
            self.assertEqual(read_scope(c)["grant"]["permissionMode"], "default")


if __name__ == "__main__":
    unittest.main()
