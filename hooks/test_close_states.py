"""Where a close lands is part of the record, not a courtesy message.

0.7 keeps `closed-pending-human` apart from `closed-with-debt` on purpose:
one means a judgement is still a person's to give, the other that the task
ran out. These tests pin the transition, its register, and the reading of
pre-0.7 task files (no `status`: in flight by definition).
"""
import json, os, sys, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import harness_hooks as HH
from harness_hooks import closure_gate
from test_harness_hooks import cfg, make_plugin_root, write_verdict, DEFERRAL

TASK = "T-1"


def closure_rows(root):
    path = os.path.join(root, "evidence", "task-closures.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def ready(root, **per_phase):
    """A standard-risk task with its three closure verdicts written; a
    phase in `per_phase` overrides its verdict fields (e.g. a deferral)."""
    make_plugin_root(root)
    for phase in ("implementation", "review", "qa"):
        write_verdict(root, TASK, phase, **per_phase.get(phase, {}))
    return cfg(root, activeTask={"id": TASK, "allowedObjects": ["RGM_X"]})


class TestWhichTerminalStateACloseReaches(unittest.TestCase):

    def test_a_clean_close_is_closed(self):
        with tempfile.TemporaryDirectory() as t:
            d = closure_gate({}, ready(t))
            self.assertEqual(d, {"decision": "approve"})
            rows = closure_rows(t)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], HH.STATUS_CLOSED)
            self.assertEqual(rows[0]["from"], HH.STATUS_IN_FLIGHT)
            self.assertEqual(rows[0]["deferred"], [])

    def test_one_accepted_deferral_closes_pending_human(self):
        with tempfile.TemporaryDirectory() as t:
            d = closure_gate({}, ready(t, qa=dict(DEFERRAL)))
            self.assertEqual(d["decision"], "approve")
            self.assertIn("closed-pending-human", d["systemMessage"])
            self.assertIn(DEFERRAL["deferredCriterion"], d["systemMessage"])
            rows = closure_rows(t)
            self.assertEqual(rows[0]["status"], HH.STATUS_CLOSED_PENDING_HUMAN)
            self.assertEqual(rows[0]["deferred"],
                             [{"phase": "qa",
                               "criterion": DEFERRAL["deferredCriterion"]}])

    def test_pending_human_is_not_the_debt_state(self):
        # Folding them would blind the exit gate to whether the fast lane
        # exists or a block was merely relabelled.
        with tempfile.TemporaryDirectory() as t:
            d = closure_gate({}, ready(t, qa=dict(DEFERRAL)))
            self.assertNotIn("UNMEASURED", d.get("systemMessage", ""))
            self.assertEqual(closure_rows(t)[0]["status"],
                             HH.STATUS_CLOSED_PENDING_HUMAN)
            self.assertNotEqual(closure_rows(t)[0]["status"],
                                HH.STATUS_CLOSED_WITH_DEBT)

    def test_the_forced_approve_is_recorded_as_closed_with_debt(self):
        with tempfile.TemporaryDirectory() as t:
            c = ready(t)
            os.remove(os.path.join(t, "evidence", TASK, "practices-qa.json"))
            first = closure_gate({}, c)
            self.assertEqual(first["decision"], "block")
            self.assertEqual(closure_rows(t), [])  # a block is not a close
            forced = closure_gate({"stop_hook_active": True}, c)
            self.assertEqual(forced["decision"], "approve")
            rows = closure_rows(t)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], HH.STATUS_CLOSED_WITH_DEBT)

    def test_closing_twice_records_once(self):
        with tempfile.TemporaryDirectory() as t:
            c = ready(t)
            closure_gate({}, c)
            closure_gate({}, c)
            self.assertEqual(len(closure_rows(t)), 1)


class TestAPre07TaskFileReadsAsInFlight(unittest.TestCase):
    """Norm § 15: without `schemaVersion` the old schema applies, and the
    old schema has no `status` -- the task is in flight, nothing is
    rewritten, and the close above already proves such a file still closes."""

    def test_no_status_field_is_in_flight(self):
        self.assertEqual(HH._scope_status({"id": TASK}), HH.STATUS_IN_FLIGHT)
        self.assertEqual(HH._scope_status({}), HH.STATUS_IN_FLIGHT)
        self.assertEqual(HH._scope_status(None), HH.STATUS_IN_FLIGHT)

    def test_junk_status_is_in_flight_a_declared_one_passes_through(self):
        self.assertEqual(HH._scope_status({"status": "   "}), HH.STATUS_IN_FLIGHT)
        self.assertEqual(HH._scope_status({"status": 7}), HH.STATUS_IN_FLIGHT)
        self.assertEqual(HH._scope_status({"status": "closing"}), "closing")


if __name__ == "__main__":
    unittest.main()
