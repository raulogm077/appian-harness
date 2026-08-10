"""Three defects found together, on a project where a task sat in flight for
two days: reads recorded as writes, handoffs recorded as closes, and a
freshness check a `touch` could clear.

They share a root: each one states something the harness cannot actually
know, and states it in a file a human is meant to trust later. The write log
said an expression-rule invocation was a write. The debt register said a task
closed when it had not. The staleness check said a verdict was recorded when
the file was last modified. None of the three is a crash, and that is exactly
why they survived 167 passing tests.
"""
import json, os, sys, time, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import closure_gate, log_write, scope_gate, CLOSURE_PHASES
from test_harness_hooks import cfg, make_plugin_root, write_verdict, write_skill_record
from test_verdict_freshness import log_write_at, age_file


READS = (
    "mcp__appian__appian_invoke_expression_rule",
    "mcp__appian-dev__testRule",
    "mcp__appian-dev__runAllInterfaceTestCases",
)


def read_log(root):
    path = os.path.join(root, "evidence", "operations.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def read_debt(root):
    path = os.path.join(root, "evidence", "deferred-debt.jsonl")
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


class TestAReadIsNotAWrite(unittest.TestCase):
    """`WRITE_TOOL_RE` already says an expression rule has no side effects.
    `log_write` never asked it.

    The JSON matcher routes a bare `invoke|run|test` on purpose -- it is the
    net that keeps anything from escaping the scope gate, and
    `test_the_write_log_receives_them_too` holds that direction. So the fix
    belongs in Python, which is where the plugin already draws the line.
    """

    TASK = "T-1"

    def _cfg(self, root):
        return cfg(root, activeTask={"id": self.TASK, "allowedObjects": ["A"]})

    def test_invoking_a_rule_does_not_land_in_the_write_log(self):
        for name in READS:
            with tempfile.TemporaryDirectory() as root:
                log_write({"tool_name": name, "tool_input": {}}, self._cfg(root))
                self.assertEqual(read_log(root), [], name)

    def test_a_real_write_still_lands(self):
        with tempfile.TemporaryDirectory() as root:
            log_write({"tool_name": "mcp__appian-dev__updateRecordType",
                       "tool_input": {"recordTypeUuid": "A"}}, self._cfg(root))
            self.assertEqual(len(read_log(root)), 1)

    def test_a_read_does_not_stale_a_verdict(self):
        """The whole point, stated as the symptom it caused: a rule invoked
        while investigating something else must not expire the verdicts of
        the task that happens to be in flight."""
        with tempfile.TemporaryDirectory() as root:
            make_plugin_root(root)
            write_skill_record(root, self.TASK)
            for phase in CLOSURE_PHASES:
                write_verdict(root, self.TASK, phase)
            c = self._cfg(root)
            log_write({"tool_name": "mcp__appian__appian_invoke_expression_rule",
                       "tool_input": {}}, c)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")


class TestAHandoffIsNotAClose(unittest.TestCase):
    """`closure_gate`'s own docstring separates the two cases -- "that block
    is not a failure report" -- and then the debt register calls every one of
    them a close.

    It is false by construction, not merely sometimes: `activeTask` is loaded
    fresh from the task file on every invocation, so if the task had really
    closed, the gate would have approved at the top and never reached here.
    Reaching the debt path *means* the task is still in flight.
    """

    TASK = "T-2"

    def _cfg(self, root):
        make_plugin_root(root)
        write_skill_record(root, self.TASK)
        c = cfg(root, activeTask={"id": self.TASK, "allowedObjects": ["A"]})
        os.makedirs(os.path.dirname(c["activeTaskFile"]), exist_ok=True)
        with open(c["activeTaskFile"], "w", encoding="utf-8") as f:
            json.dump({"id": self.TASK, "allowedObjects": ["A"]}, f)
        return c

    def test_the_entry_does_not_claim_the_task_closed(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            closure_gate({"stop_hook_active": True}, c)
            entries = read_debt(root)
            self.assertEqual(len(entries), 1)
            self.assertNotIn("closed", entries[0]["reason"],
                             "the task is still in flight: %r" % entries[0]["reason"])

    def test_repeated_sessions_do_not_pile_up_identical_entries(self):
        """Ten copies of one sentence buried the only entry in the register
        that carried an owner and a closing condition."""
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            for _ in range(5):
                closure_gate({"stop_hook_active": True}, c)
            self.assertEqual(len(read_debt(root)), 1)

    def test_a_different_omission_is_still_recorded(self):
        """Deduplication must not swallow new information."""
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            closure_gate({"stop_hook_active": True}, c)
            write_verdict(root, self.TASK, "qa")
            closure_gate({"stop_hook_active": True}, c)
            entries = read_debt(root)
            self.assertEqual(len(entries), 2)
            self.assertNotEqual(entries[0]["missingPhases"], entries[1]["missingPhases"])

    def test_it_still_approves_so_the_gate_never_deadlocks(self):
        with tempfile.TemporaryDirectory() as root:
            c = self._cfg(root)
            self.assertEqual(
                closure_gate({"stop_hook_active": True}, c)["decision"], "approve")


class TestFreshnessSurvivesATouch(unittest.TestCase):
    """Staleness was measured with `os.path.getmtime`, so the file's mtime
    *was* the claim. Two consequences nobody wrote down: `touch` clears an
    expiry without re-running anything -- the rubber stamp this gate exists
    to prevent -- and a clone, a copy or a restore rewrites every mtime, so
    freshness does not survive moving the project.

    The verdict should carry its own `recordedAt`, with mtime kept as the
    fallback for the verdicts already on disk without one.
    """

    TASK = "T-3"

    def _setup(self, root, write_epoch, recorded_at=None, mtime=None):
        make_plugin_root(root)
        write_skill_record(root, self.TASK)
        over = {"recordedAt": recorded_at} if recorded_at else {}
        for phase in CLOSURE_PHASES:
            write_verdict(root, self.TASK, phase, **over)
            if mtime is not None:
                age_file(os.path.join(root, "evidence", self.TASK,
                                      "practices-%s.json" % phase), mtime)
        log_write_at(root, self.TASK, write_epoch)
        return cfg(root, activeTask={"id": self.TASK, "allowedObjects": ["A"]})

    @staticmethod
    def _iso(epoch):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))

    def test_touching_the_file_does_not_clear_staleness(self):
        now = int(time.time())
        with tempfile.TemporaryDirectory() as root:
            # Recorded an hour before the write, then touched to now.
            c = self._setup(root, write_epoch=now - 1800,
                            recorded_at=self._iso(now - 3600), mtime=now)
            self.assertEqual(closure_gate({}, c)["decision"], "block")

    def test_a_verdict_recorded_after_the_write_is_fresh(self):
        now = int(time.time())
        with tempfile.TemporaryDirectory() as root:
            c = self._setup(root, write_epoch=now - 3600,
                            recorded_at=self._iso(now - 60), mtime=now - 7200)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_without_recordedAt_it_still_falls_back_to_mtime(self):
        """Every verdict already on disk predates this field."""
        now = int(time.time())
        with tempfile.TemporaryDirectory() as root:
            c = self._setup(root, write_epoch=now - 1800, mtime=now - 3600)
            self.assertEqual(closure_gate({}, c)["decision"], "block")
        with tempfile.TemporaryDirectory() as root:
            c = self._setup(root, write_epoch=now - 3600, mtime=now - 60)
            self.assertEqual(closure_gate({}, c)["decision"], "approve")

    def test_an_unparseable_recordedAt_falls_back_rather_than_passing(self):
        now = int(time.time())
        with tempfile.TemporaryDirectory() as root:
            c = self._setup(root, write_epoch=now - 1800,
                            recorded_at="whenever", mtime=now - 3600)
            self.assertEqual(closure_gate({}, c)["decision"], "block")


if __name__ == "__main__":
    unittest.main()
