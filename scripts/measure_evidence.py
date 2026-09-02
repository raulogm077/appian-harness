"""Measures what the harness itself costs, from what a session left behind.

    python3 measure_evidence.py --hook-log FILE [--transcript FILE]
        [--evidence DIR] [--calibration-ms N] [--json]
    0 measured  2 usage  3 NOT MEASURED -- nothing to measure, not a pass

Reports the clock share consumed by the harness's own hooks, and the
manual-estimate denominator when `measure: true` anchored one. A magnitude
it cannot measure is reported NOT MEASURED, never estimated or omitted.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED

NOT_MEASURED = "NOT MEASURED"


def read_hook_rows(path):
    """The launcher's timing rows: one per invocation, garbage skipped."""
    rows = []
    if not path or not os.path.isfile(path):
        return rows
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            t0, t1 = e.get("t0Ns"), e.get("t1Ns")
            if (isinstance(t0, int) and isinstance(t1, int)
                    and not isinstance(t0, bool) and not isinstance(t1, bool)
                    and t1 >= t0):
                rows.append(e)
    return rows


def _parse_ts_ms(value):
    from datetime import datetime, timezone
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(value[:-1], fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue
    return None


def read_transcript_span_ms(path):
    """(first, last) timestamp of the transcript in epoch ms, or None."""
    if not path or not os.path.isfile(path):
        return None
    first = last = None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            ms = _parse_ts_ms(e.get("timestamp")) if isinstance(e, dict) else None
            if ms is None:
                continue
            first = ms if first is None else min(first, ms)
            last = ms if last is None else max(last, ms)
    if first is None:
        return None
    return first, last


def interval_union_ms(rows):
    """Wall-clock occupied by at least one hook: overlaps counted once."""
    spans = sorted((e["t0Ns"], e["t1Ns"]) for e in rows)
    total = 0
    cur_start = cur_end = None
    for t0, t1 in spans:
        if cur_end is None or t0 > cur_end:
            if cur_end is not None:
                total += cur_end - cur_start
            cur_start, cur_end = t0, t1
        else:
            cur_end = max(cur_end, t1)
    if cur_end is not None:
        total += cur_end - cur_start
    return total / 1e6


def manual_estimate_report(evidence_dir):
    """The anchored denominator and its annotations, from the ledger the
    hook writes. The ratio's numerator needs the human-wait discriminator
    (norm section 17.6), so the ratio itself stays NOT MEASURED here."""
    report = {"minutes": NOT_MEASURED, "ratio": NOT_MEASURED}
    if not evidence_dir:
        return report
    path = os.path.join(evidence_dir, "manual-estimates.jsonl")
    if not os.path.isfile(path):
        return report
    changed = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except ValueError:
                continue
            event = e.get("event")
            if event == "anchored" and report["minutes"] == NOT_MEASURED:
                report["minutes"] = e.get("minutes")
            elif event == "changed":
                changed += 1
            elif event == "ignored":
                report["ignoredWithoutMeasure"] = True
    if changed:
        report["laterValuesAnnotated"] = changed
    return report


def measure(hook_log, transcript, evidence_dir, calibration_ms):
    rows = read_hook_rows(hook_log)
    report = {"hooks": {"invocations": len(rows)},
              "session": {}, "share": {},
              "manualEstimate": manual_estimate_report(evidence_dir)}
    if not rows:
        report["hooks"]["note"] = ("no timing rows: run the session with "
                                   "APPIAN_HARNESS_TIME_LOG set")
        report["session"]["wallMs"] = NOT_MEASURED
        report["share"]["observed"] = NOT_MEASURED
        return report

    durations = sorted((e["t1Ns"] - e["t0Ns"]) / 1e6 for e in rows)
    union = interval_union_ms(rows)
    cumulative = sum(durations)
    report["hooks"].update({
        "perInvocationMsMedian": round(durations[len(durations) // 2], 1),
        "perInvocationMsMax": round(durations[-1], 1),
        "cumulativeMs": round(cumulative, 1),
        "unionMs": round(union, 1),
        "bySubcommand": {},
    })
    for e in rows:
        sub = e.get("subcommand") or "?"
        agg = report["hooks"]["bySubcommand"].setdefault(sub, {"n": 0, "ms": 0.0})
        agg["n"] += 1
        agg["ms"] = round(agg["ms"] + (e["t1Ns"] - e["t0Ns"]) / 1e6, 1)

    span = read_transcript_span_ms(transcript)
    hooks_start = min(e["t0Ns"] for e in rows) / 1e6
    hooks_end = max(e["t1Ns"] for e in rows) / 1e6
    if span is None:
        report["session"]["wallMs"] = NOT_MEASURED
        report["share"]["observed"] = NOT_MEASURED
        report["session"]["note"] = ("no transcript timestamps: the share of "
                                     "wall clock cannot be computed")
    else:
        start = min(span[0], hooks_start)
        end = max(span[1], hooks_end)
        wall = max(end - start, 1.0)
        report["session"]["wallMs"] = round(wall, 1)
        report["share"]["observed"] = round(union / wall, 4)
        report["share"]["cumulative"] = round(cumulative / wall, 4)
        if calibration_ms:
            # The sh spawn before the first in-script timestamp is invisible
            # from inside; adding a separately measured constant makes this
            # an ESTIMATE, and it is labelled as one.
            adjusted = cumulative + calibration_ms * len(rows)
            report["share"]["adjustedCumulative"] = round(adjusted / wall, 4)
            report["share"]["adjustedIsAnEstimate"] = True
            report["share"]["calibrationMsPerInvocation"] = calibration_ms
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hook-log")
    ap.add_argument("--transcript")
    ap.add_argument("--evidence")
    ap.add_argument("--calibration-ms", type=float, default=0.0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    report = measure(args.hook_log, args.transcript, args.evidence,
                     args.calibration_ms)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        h, s = report["hooks"], report["share"]
        print("hook invocations: %s" % h["invocations"])
        if h["invocations"]:
            print("per invocation: median %.1f ms, max %.1f ms"
                  % (h["perInvocationMsMedian"], h["perInvocationMsMax"]))
            print("cumulative %.1f ms, union %.1f ms"
                  % (h["cumulativeMs"], h["unionMs"]))
        print("session wall: %s ms" % report["session"].get("wallMs"))
        print("hook share of wall clock (observed): %s" % s.get("observed"))
        if "adjustedCumulative" in s:
            print("adjusted with +%.1f ms/invocation spawn calibration: %s "
                  "(estimate)" % (s["calibrationMsPerInvocation"],
                                  s["adjustedCumulative"]))
        print("manual estimate minutes: %s / ratio: %s"
              % (report["manualEstimate"]["minutes"],
                 report["manualEstimate"]["ratio"]))
    if not report["hooks"]["invocations"]:
        return EXIT_NOT_MEASURED
    return 0


if __name__ == "__main__":
    sys.exit(main())
