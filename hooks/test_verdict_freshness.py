"""A verdict is a claim about a version of the work, and it expires.

A verdict is tied to the artifact it judged: a review that fails, is fixed --
more writes -- and re-run for `phase=review` alone must not close the task on
pre-fix `implementation` and `qa` PASSes certifying an artifact that no
longer exists. Unattended, or with several builders, that is the normal case.
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

    The exemption belongs to `design` alone, for a reason about *when* the
    phase runs rather than which tuple it lives in: design precedes the first
    write on purpose, every other phase judges what the writes produced.
    `risk` is appended to `CLOSURE_PHASES` for high-risk tasks rather than
    being a member of it, so a check keyed on that tuple alone exempts it.
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


class TestV07ExpiryIsBySequenceNotByClock(unittest.TestCase):
    """§ 7.6: what expires a verdict is a behavioural in-scope write of its
    instance with a higher sequence -- never a timestamp. The legacy class
    above keeps guarding the 0.6 rulebook (§ 15)."""

    INSTANCE = "inst-9"

    def _cfg(self, root):
        return cfg(root, activeTask={"schemaVersion": 2, "id": "F-x",
                                     "instanceId": self.INSTANCE})

    def _row(self, root, seq, result="ok", behavioural=True, in_scope=True,
             instance=None):
        import harness_hooks as HH
        HH._append_jsonl(os.path.join(root, "evidence", "operations.jsonl"),
                         {"instanceId": instance or self.INSTANCE,
                          "writeSeq": seq, "toolUseId": "tu-%d" % seq,
                          "inScope": in_scope, "behavioural": behavioural,
                          "result": result})

    def _verdict(self, covers, phase="certify", instance=None):
        return {"phase": phase, "instanceId": instance or self.INSTANCE,
                "coversThroughWriteSeq": covers}

    def test_a_later_behavioural_write_expires_it(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3)
            errs = verdict_expiry_errors(c, c["activeTask"], self._verdict(2))
            self.assertTrue(errs and "writeSeq 2" in errs[0])

    def test_a_metadata_only_write_does_not(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3, behavioural=False)
            self.assertEqual(
                verdict_expiry_errors(c, c["activeTask"], self._verdict(2)), [])

    def test_a_failed_write_changed_nothing(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3, result="failed")
            self.assertEqual(
                verdict_expiry_errors(c, c["activeTask"], self._verdict(2)), [])

    def test_ambiguous_and_pending_sit_on_the_expensive_side(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3, result="ambiguous")
            self.assertTrue(
                verdict_expiry_errors(c, c["activeTask"], self._verdict(2)))
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3, result="pending", behavioural=None)
            self.assertTrue(
                verdict_expiry_errors(c, c["activeTask"], self._verdict(2)))

    def test_a_foreign_write_does_not_expire(self):
        # Eval safety-foreign-write-does-not-expire: another instance's
        # write is another contract's history.
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3, instance="inst-OTRA")
            self._row(root, 3, in_scope=False)
            self.assertEqual(
                verdict_expiry_errors(c, c["activeTask"], self._verdict(2)), [])

    def test_design_is_exempt_and_meant_to_predate_writes(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self._row(root, 3)
            self.assertEqual(
                verdict_expiry_errors(c, c["activeTask"],
                                      self._verdict(0, phase="design")), [])

    def test_no_usable_covers_fails_closed(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            for covers in (None, "3", True, -1):
                self.assertTrue(
                    verdict_expiry_errors(c, c["activeTask"],
                                          self._verdict(covers)))

    def test_another_instances_verdict_never_covers_this_one(self):
        from harness_hooks import verdict_expiry_errors
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self.assertTrue(
                verdict_expiry_errors(c, c["activeTask"],
                                      self._verdict(9, instance="inst-vieja")))
