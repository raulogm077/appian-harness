"""The overhead number must be measured, never estimated in silence.

Overlapping hook intervals count once toward the wall-clock share; the
session window covers both transcript and hooks; a missing transcript is
NOT MEASURED; the spawn calibration is labelled an estimate; and the manual
estimate surfaces only its anchored value, with the ratio NOT MEASURED
until the human-wait discriminator exists.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure_evidence as ME

S = 10 ** 9  # 1s in ns


def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def hook_row(t0, t1, sub="scope-gate"):
    return {"subcommand": sub, "t0Ns": t0, "t1Ns": t1, "exit": 0}


def transcript_row(ts):
    return {"type": "assistant", "timestamp": ts}


class TestTheShareIsAUnionNotASum(unittest.TestCase):

    def test_overlaps_count_once_and_the_sum_is_reported_apart(self):
        rows = [hook_row(0, 10 * S), hook_row(5 * S, 12 * S)]
        self.assertEqual(ME.interval_union_ms(rows), 12000.0)
        with tempfile.TemporaryDirectory() as t:
            log = write_jsonl(os.path.join(t, "h.jsonl"), rows)
            r = ME.measure(log, None, None, 0)
            self.assertEqual(r["hooks"]["unionMs"], 12000.0)
            self.assertEqual(r["hooks"]["cumulativeMs"], 17000.0)

    def test_the_share_is_against_the_widest_window(self):
        # The transcript spans 100s; a hook interval sticks out 2s past its
        # end, so the window is 102s and the union 12s.
        with tempfile.TemporaryDirectory() as t:
            log = write_jsonl(os.path.join(t, "h.jsonl"),
                              [hook_row(0, 10 * S),
                               hook_row(100 * S, 102 * S)])
            tr = write_jsonl(os.path.join(t, "t.jsonl"),
                             [transcript_row("1970-01-01T00:00:00.000Z"),
                              transcript_row("1970-01-01T00:01:40.000Z")])
            r = ME.measure(log, tr, None, 0)
            self.assertEqual(r["session"]["wallMs"], 102000.0)
            self.assertAlmostEqual(r["share"]["observed"], 12000.0 / 102000.0,
                                   places=4)


class TestNothingIsEstimatedInSilence(unittest.TestCase):

    def test_no_transcript_is_not_measured(self):
        with tempfile.TemporaryDirectory() as t:
            log = write_jsonl(os.path.join(t, "h.jsonl"), [hook_row(0, S)])
            r = ME.measure(log, None, None, 0)
            self.assertEqual(r["session"]["wallMs"], ME.NOT_MEASURED)
            self.assertEqual(r["share"]["observed"], ME.NOT_MEASURED)
            # The per-invocation numbers are still real measurements.
            self.assertEqual(r["hooks"]["perInvocationMsMedian"], 1000.0)

    def test_no_rows_at_all_exits_not_measured(self):
        with tempfile.TemporaryDirectory() as t:
            rc = ME.main(["--hook-log", os.path.join(t, "absent.jsonl")])
            self.assertEqual(rc, 3)

    def test_the_calibration_is_labelled_an_estimate(self):
        with tempfile.TemporaryDirectory() as t:
            log = write_jsonl(os.path.join(t, "h.jsonl"), [hook_row(0, S)])
            tr = write_jsonl(os.path.join(t, "t.jsonl"),
                             [transcript_row("1970-01-01T00:00:00.000Z"),
                              transcript_row("1970-01-01T00:00:10.000Z")])
            r = ME.measure(log, tr, None, 100.0)
            self.assertTrue(r["share"]["adjustedIsAnEstimate"])
            self.assertAlmostEqual(r["share"]["adjustedCumulative"],
                                   1100.0 / 10000.0, places=4)
            plain = ME.measure(log, tr, None, 0)
            self.assertNotIn("adjustedCumulative", plain["share"])

    def test_garbage_rows_are_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as t:
            path = os.path.join(t, "h.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{broken\n")
                f.write(json.dumps(hook_row(0, S)) + "\n")
                f.write(json.dumps({"t0Ns": "x", "t1Ns": 5}) + "\n")
                f.write(json.dumps({"t0Ns": 9, "t1Ns": 5}) + "\n")
            self.assertEqual(len(ME.read_hook_rows(path)), 1)


class TestTheManualEstimateSurfacesOnlyWhatWasAnchored(unittest.TestCase):

    def _ledger(self, root, rows):
        return write_jsonl(os.path.join(root, "manual-estimates.jsonl"), rows)

    def test_the_anchored_value_is_the_denominator_and_the_ratio_waits(self):
        with tempfile.TemporaryDirectory() as t:
            self._ledger(t, [
                {"task": "T-1", "event": "anchored", "minutes": 90},
                {"task": "T-1", "event": "changed", "minutes": 45,
                 "anchoredMinutes": 90},
            ])
            r = ME.manual_estimate_report(t)
            self.assertEqual(r["minutes"], 90)
            self.assertEqual(r["laterValuesAnnotated"], 1)
            self.assertEqual(r["ratio"], ME.NOT_MEASURED)

    def test_without_measure_there_is_no_denominator(self):
        with tempfile.TemporaryDirectory() as t:
            self._ledger(t, [{"task": "T-1", "event": "ignored", "value": 90}])
            r = ME.manual_estimate_report(t)
            self.assertEqual(r["minutes"], ME.NOT_MEASURED)
            self.assertTrue(r["ignoredWithoutMeasure"])


if __name__ == "__main__":
    unittest.main()
