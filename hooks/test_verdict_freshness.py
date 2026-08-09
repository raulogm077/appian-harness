"""A verdict is a claim about a version of the work, and it expires.

The gap this closes: nothing tied a verdict to the artifact it judged. A
review comes back FAIL, the agent fixes it -- more writes -- and re-runs
only `phase=review`. The pre-fix `implementation` and `qa` verdicts still
satisfied the closure gate, so the task closed on two PASSes certifying an
artifact that no longer existed. With one builder that is an occasional
slip. Unattended, or with several builders, it is the normal case.
"""
import json, os, sys, time, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import closure_gate, scope_gate, CLOSURE_PHASES
from test_harness_hooks import cfg, make_plugin_root, write_verdict, write_skill_record


def log_write_at(root, task_id, epoch):
    """One entry in the write log, stamped the way the harness stamps it."""
    path = os.path.join(root, "evidence", "operations.jsonl")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch)),
            "task": task_id, "tool": "mcp__appian-dev__updateInterface",
            "object": "A", "result": "ok"}) + "\n")


def age_file(path, epoch):
    os.utime(path, (epoch, epoch))


class TestAVerdictExpiresWhenTheArtifactChanges(unittest.TestCase):
    TASK = "T-1"

    def _setup(self, root, verdict_epoch, write_epoch=None, phases=CLOSURE_PHASES):
        make_plugin_root(root)
        write_skill_record(root, self.TASK)
        for phase in phases:
            write_verdict(root, self.TASK, phase)
            age_file(os.path.join(root, "evidence", self.TASK,
                                  "practices-%s.json" % phase), verdict_epoch)
        if write_epoch is not None:
            log_write_at(root, self.TASK, write_epoch)
        return cfg(root, activeTask={"id": self.TASK, "allowedObjects": ["A"]})

    def test_a_task_with_no_writes_logged_closes_normally(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_verdicts_recorded_after_the_last_write_close_normally(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=2000, write_epoch=1000)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_a_write_after_the_verdicts_blocks_the_close(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000, write_epoch=2000)
            out = closure_gate({}, c)
            self.assertEqual(out["decision"], "block")
            self.assertIn("stale", out["reason"])

    def test_the_block_names_every_stale_phase_not_just_the_first(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000, write_epoch=2000)
            reason = closure_gate({}, c)["reason"]
            for phase in CLOSURE_PHASES:
                self.assertIn("practices-%s" % phase, reason)

    def test_re_running_one_phase_does_not_refresh_the_others(self):
        # The exact fix-and-close sequence this exists to catch.
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000, write_epoch=2000)
            fresh = os.path.join(t, "evidence", self.TASK, "practices-review.json")
            age_file(fresh, 3000)
            out = closure_gate({}, c)
            self.assertEqual(out["decision"], "block")
            self.assertIn("practices-implementation", out["reason"])
            self.assertIn("practices-qa", out["reason"])
            self.assertNotIn("practices-review (", out["reason"])

    def test_re_running_all_of_them_closes_the_task(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000, write_epoch=2000)
            for phase in CLOSURE_PHASES:
                age_file(os.path.join(t, "evidence", self.TASK,
                                      "practices-%s.json" % phase), 3000)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_a_write_in_the_same_second_is_fresh_not_stale(self):
        # The log has one-second resolution, and a verdict recorded in the
        # same second as the write it judges is the normal case.
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=2000, write_epoch=2000)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_another_tasks_writes_do_not_age_this_tasks_verdicts(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000)
            log_write_at(t, "T-OTHER", 5000)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_a_corrupt_write_log_does_not_manufacture_staleness(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000)
            path = os.path.join(t, "evidence", "operations.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write("{not json\n")
                f.write(json.dumps({"task": self.TASK, "timestamp": "not-a-date"}) + "\n")
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_the_design_verdict_is_never_stale_it_is_meant_to_precede_writes(self):
        # Measuring design against the write log would mark every correct
        # design audit stale, since running it before the first write is
        # the entire argument for having it.
        with tempfile.TemporaryDirectory() as t:
            make_plugin_root(t)
            write_skill_record(t, self.TASK)
            write_verdict(t, self.TASK, "design")
            age_file(os.path.join(t, "evidence", self.TASK, "practices-design.json"), 1000)
            log_write_at(t, self.TASK, 2000)
            c = cfg(t, activeTask={"id": self.TASK, "allowedObjects": ["A"]})
            d = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": "A"}}, c)
            self.assertEqual(d["permissionDecision"], "allow")


class TestTheAdversarialVerdictExpiresToo(unittest.TestCase):
    """`risk` is a post-write phase, so it goes stale like the rest.

    The exemption belongs to `design` alone, and for a reason that is about
    *when* the phase runs, not about which tuple it happens to live in:
    design precedes the first write on purpose, every other phase judges
    what the writes produced. `risk` was exempt only because the staleness
    check was keyed on `CLOSURE_PHASES`, which `risk` is not a member of --
    it is appended to that tuple for high-risk tasks. So the tier that buys
    a fourth opinion because a mistake there is expensive was the one tier
    whose extra verdict never expired.
    """
    TASK = "T-1"

    def _setup(self, root, verdict_epoch, write_epoch):
        make_plugin_root(root)
        write_skill_record(root, self.TASK)
        for phase in CLOSURE_PHASES + ("risk",):
            write_verdict(root, self.TASK, phase)
            age_file(os.path.join(root, "evidence", self.TASK,
                                  "practices-%s.json" % phase), verdict_epoch)
        log_write_at(root, self.TASK, write_epoch)
        return cfg(root, activeTask={"id": self.TASK, "allowedObjects": ["A"],
                                     "risk": "high"})

    def test_a_write_after_the_risk_verdict_blocks_the_close(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=1000, write_epoch=2000)
            out = closure_gate({}, c)
            self.assertEqual(out["decision"], "block")
            self.assertIn("practices-risk verdict is stale", out["reason"])

    def test_a_fresh_risk_verdict_still_closes(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._setup(t, verdict_epoch=2000, write_epoch=1000)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")


if __name__ == "__main__":
    unittest.main()
