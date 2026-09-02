"""The manual estimate is written once, annotated, and only under `measure`.

`manualEstimateMinutes` is the denominator of a metric that is reported and
never scored. The hook cannot stop the agent editing its own task file, so
write-once is made auditable instead: the first valid value is anchored in
`manual-estimates.jsonl`, later values are annotated as discrepancies and do
not replace it, and without `measure: true` the field is inert -- one row
says so.
"""
import json, os, sys, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import harness_hooks as HH
from test_harness_hooks import cfg, make_plugin_root, write_verdict

TASK = "T-1"


def rows(root):
    path = os.path.join(root, "evidence", "manual-estimates.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def note(root, minutes, measure=True, times=1):
    c = cfg(root, measure=measure,
            activeTask={"id": TASK, "manualEstimateMinutes": minutes})
    for _ in range(times):
        HH._note_manual_estimate(c)
    return c


class TestWriteOnceWithAnnotation(unittest.TestCase):

    def test_the_first_valid_value_is_anchored_once(self):
        with tempfile.TemporaryDirectory() as t:
            note(t, 90, times=3)
            self.assertEqual(rows(t), [rows(t)[0]])
            self.assertEqual(rows(t)[0]["event"], "anchored")
            self.assertEqual(rows(t)[0]["minutes"], 90)

    def test_a_later_value_is_annotated_and_does_not_replace(self):
        with tempfile.TemporaryDirectory() as t:
            note(t, 90)
            note(t, 45, times=2)
            r = rows(t)
            self.assertEqual([e["event"] for e in r], ["anchored", "changed"])
            self.assertEqual(r[0]["minutes"], 90)
            self.assertEqual(r[1]["minutes"], 45)
            self.assertEqual(r[1]["anchoredMinutes"], 90)

    def test_without_measure_the_field_is_inert_and_said_to_be(self):
        with tempfile.TemporaryDirectory() as t:
            note(t, 90, measure=False, times=2)
            r = rows(t)
            self.assertEqual([e["event"] for e in r], ["ignored"])

    def test_invalid_values_never_anchor(self):
        for junk in (0, -5, True, "90", float("nan"), float("inf")):
            with tempfile.TemporaryDirectory() as t:
                note(t, junk)
                r = rows(t)
                self.assertEqual([e["event"] for e in r], ["invalid"], repr(junk))

    def test_no_field_or_null_writes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            HH._note_manual_estimate(cfg(t, measure=True,
                                         activeTask={"id": TASK}))
            HH._note_manual_estimate(cfg(t, measure=True, activeTask={
                "id": TASK, "manualEstimateMinutes": None}))
            self.assertEqual(rows(t), [])


class TestTheTwoObservationPoints(unittest.TestCase):
    """The anchor happens where the hook already looks: an edit of the
    active-task file, and the close as the fallback."""

    def test_an_edit_of_the_task_file_anchors(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, measure=True,
                    activeTask={"id": TASK, "manualEstimateMinutes": 30})
            HH.log_evidence_write(
                {"tool_name": "Write",
                 "tool_input": {"file_path": c["activeTaskFile"]}}, c)
            self.assertEqual([e["event"] for e in rows(t)], ["anchored"])

    def test_an_edit_elsewhere_does_not(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, measure=True,
                    activeTask={"id": TASK, "manualEstimateMinutes": 30})
            HH.log_evidence_write(
                {"tool_name": "Write",
                 "tool_input": {"file_path": os.path.join(t, "elsewhere.md")}}, c)
            self.assertEqual(rows(t), [])

    def test_the_close_anchors_as_fallback(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin_root(t)
            for phase in ("implementation", "review", "qa"):
                write_verdict(t, TASK, phase)
            c = cfg(t, measure=True,
                    activeTask={"id": TASK, "allowedObjects": ["RGM_X"],
                                "manualEstimateMinutes": 30})
            d = HH.closure_gate({}, c)
            self.assertEqual(d["decision"], "approve")
            self.assertEqual([e["event"] for e in rows(t)], ["anchored"])


if __name__ == "__main__":
    unittest.main()
