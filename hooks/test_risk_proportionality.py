"""Ceremony in proportion to the change, in the layer that enforces it.

The doctrine graduated by risk from the start — the calibration table in
`appian-best-practices`, the entry threshold in `appian-review` — while the
gates applied one ceremony to everything. A text fix cost four verdicts, and
the escape people actually take from that is to stop declaring tasks at all,
which loses the record entirely. Cheaper-but-recorded beats
expensive-and-avoided.

The other direction matters equally: `high` adds an adversarial pass whose
question is "how does this fail?" rather than "does this meet the
contract?". A fourth opinion earns its cost only by asking a different
question.
"""
import json, os, sys, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import harness_hooks as H
from harness_hooks import closure_gate, _required_closure_phases, _risk_tier
from test_harness_hooks import cfg, make_plugin_root, write_verdict, write_skill_record

TASK = "T-1"


class TestDecidingIsSeparateFromRecording(unittest.TestCase):
    """A query must not create files. The first version logged from inside
    `_required_closure_phases`, so asking "which phases does trivial need?"
    with an empty config wrote an `evidence/` directory into whatever the
    current directory happened to be — including the plugin's own checkout,
    which is the contamination CI has a step to prevent."""

    def test_asking_the_question_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            here = os.getcwd()
            os.chdir(t)
            try:
                _required_closure_phases({}, {"id": TASK, "risk": "trivial"})
                _risk_tier({"id": TASK, "risk": "trivial"})
            finally:
                os.chdir(here)
            self.assertEqual(os.listdir(t), [])


class TestRequiredPhasesByRisk(unittest.TestCase):
    def test_absent_risk_means_standard(self):
        self.assertEqual(_required_closure_phases({}, {"id": TASK}), H.CLOSURE_PHASES)

    def test_trivial_needs_one_verdict(self):
        self.assertEqual(_required_closure_phases({}, {"id": TASK, "risk": "trivial"}),
                         ("implementation",))

    def test_high_adds_the_adversarial_pass(self):
        self.assertEqual(_required_closure_phases({}, {"id": TASK, "risk": "high"}),
                         H.CLOSURE_PHASES + ("risk",))

    def test_case_and_padding_do_not_change_the_tier(self):
        self.assertEqual(_required_closure_phases({}, {"id": TASK, "risk": "  HIGH "}),
                         H.CLOSURE_PHASES + ("risk",))

    def test_an_unrecognised_value_fails_towards_more_ceremony(self):
        # A typo must never buy a discount. `standard`, not `trivial`.
        for value in ("triival", "", None, 7, ["trivial"]):
            self.assertEqual(_required_closure_phases({}, {"id": TASK, "risk": value}),
                             H.CLOSURE_PHASES, repr(value))


class TestClosureGateHonoursTheTier(unittest.TestCase):
    def _config(self, root, risk=None, phases=()):
        make_plugin_root(root)
        write_skill_record(root, TASK)
        for phase in phases:
            write_verdict(root, TASK, phase)
        task = {"id": TASK, "allowedObjects": ["A"]}
        if risk is not None:
            task["risk"] = risk
        return cfg(root, activeTask=task)

    def test_a_trivial_task_closes_on_one_verdict(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, risk="trivial", phases=("implementation",))
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_the_same_evidence_does_not_close_a_standard_task(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, phases=("implementation",))
            out = closure_gate({}, c)
            self.assertEqual(out["decision"], "block")
            self.assertIn("practices-review", out["reason"])
            self.assertIn("practices-qa", out["reason"])

    def test_a_high_risk_task_is_not_closed_by_the_standard_three(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, risk="high", phases=H.CLOSURE_PHASES)
            out = closure_gate({}, c)
            self.assertEqual(out["decision"], "block")
            self.assertIn("practices-risk", out["reason"])

    def test_a_high_risk_task_closes_with_the_adversarial_verdict(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, risk="high", phases=H.CLOSURE_PHASES + ("risk",))
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_a_trivial_task_still_needs_its_one_verdict(self):
        # Cheaper, not free. The record is the whole reason the cheap tier
        # exists rather than people skipping the task mechanism.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, risk="trivial")
            self.assertEqual(closure_gate({}, c)["decision"], "block")


class TestTheDowngradeIsRecorded(unittest.TestCase):
    """Declaring `trivial` is a downgrade the builder can write, like
    everything else here. Not prevented — logged, so 'was it really
    trivial?' has an answer later."""

    def _entries(self, root):
        path = os.path.join(root, "evidence", "risk-downgrades.jsonl")
        if not os.path.isfile(path):
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(l) for l in f if l.strip()]

    def test_a_trivial_closure_leaves_a_line_behind(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin_root(t)
            write_skill_record(t, TASK)
            write_verdict(t, TASK, "implementation")
            c = cfg(t, activeTask={"id": TASK, "allowedObjects": ["A"], "risk": "trivial"})
            closure_gate({}, c)
            e = self._entries(t)
            self.assertEqual(len(e), 1)
            self.assertEqual(e[0]["task"], TASK)
            self.assertEqual(e[0]["declaredRisk"], "trivial")

    def test_repeated_stops_do_not_repeat_the_line(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin_root(t)
            write_skill_record(t, TASK)
            write_verdict(t, TASK, "implementation")
            c = cfg(t, activeTask={"id": TASK, "allowedObjects": ["A"], "risk": "trivial"})
            for _ in range(3):
                closure_gate({}, c)
            self.assertEqual(len(self._entries(t)), 1)

    def test_a_standard_task_leaves_no_line(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin_root(t)
            write_skill_record(t, TASK)
            for phase in H.CLOSURE_PHASES:
                write_verdict(t, TASK, phase)
            c = cfg(t, activeTask={"id": TASK, "allowedObjects": ["A"]})
            closure_gate({}, c)
            self.assertEqual(self._entries(t), [])


if __name__ == "__main__":
    unittest.main()
