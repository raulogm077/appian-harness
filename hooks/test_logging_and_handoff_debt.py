"""Claims the harness records but cannot actually know.

A read logged as a write, a handoff logged as a close, a freshness check a
`touch` can clear, a failed read announced as a failed write. Each states
something false where a human will trust it later, and none of them crashes.
"""
import json, os, re, sys, time, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import (closure_gate, failure_notice, log_write, scope_gate,
                           CLOSURE_PHASES)
from test_harness_hooks import cfg, make_plugin_root, write_verdict, write_skill_record
from test_verdict_freshness import log_write_at, age_file
from test_matcher_parity import matcher_for


READS = (
    "mcp__appian__appian_invoke_expression_rule",
    "mcp__appian-dev__testRule",
    "mcp__appian-dev__runAllInterfaceTestCases",
)

# Reads carrying no write verb at all, so they never reach the write log --
# but which the failure path describes as writes unless it asks first. Real
# tool names, taken from calls a session actually made.
PLAIN_READS = (
    "mcp__appian-dev__getRecordTypeField",
    "mcp__appian__appian_data_fabric_sql_query",
    "mcp__appian-dev__listRecordTypes",
    "mcp__appian-dev__validateExpression",
)

# Other vendors' servers. Routed a bare `mcp__.*`, a failed call to any of
# these comes back described as an Appian write.
FOREIGN = (
    "mcp__claude_ai_Figma__get_metadata",
    "mcp__claude_ai_Supabase__create_branch",
    "mcp__claude_ai_Google_Drive__create_file",
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
    """`log_write` asks `WRITE_TOOL_RE` before recording anything.

    The JSON matcher routes a bare `invoke|run|test` on purpose -- the net
    that keeps anything from escaping the scope gate, held by
    `test_the_write_log_receives_them_too` -- so the line is drawn in Python.
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
        """A rule invoked while investigating something else must not expire
        the verdicts of the task that happens to be in flight."""
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
    """A handoff is not a close, and the debt register must not say it is.

    False by construction: `activeTask` is loaded fresh from the task file on
    every invocation, so a task that really closed would be approved at the
    top and never reach the debt path. Reaching it means still in flight.
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
        """Repeated copies of one sentence bury the entries in the register
        that carry an owner and a closing condition."""
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
    """Staleness is the verdict's own `recordedAt`, not the file's mtime.

    With mtime as the claim, `touch` clears an expiry without re-running
    anything -- the rubber stamp this gate exists to prevent -- and a clone,
    copy or restore rewrites every mtime. mtime stays as the fallback for
    verdicts already on disk without a `recordedAt`.
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
        """A verdict on disk without the field is still judged."""
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


class TestAFailedReadIsNotAFailedWrite(unittest.TestCase):
    """The failure path asks `_is_write_tool` too, and it is the louder one.

    The write log is a file someone reads later; this speaks straight into
    the agent's context in the same turn. Calling a failed read a failed
    write and saying not to retry it is backwards for a read whose only
    defect is a stale table name.
    """

    WRITE = "mcp__appian-dev__createInterface"

    def test_a_failed_write_is_still_announced(self):
        out = failure_notice({"tool_name": self.WRITE})
        self.assertIn("do not retry", out["additionalContext"].lower())
        self.assertIn(self.WRITE, out["additionalContext"])

    def test_a_failed_read_is_not_called_a_write(self):
        for name in READS + PLAIN_READS:
            self.assertEqual(failure_notice({"tool_name": name}), {}, name)

    def test_another_vendors_server_is_not_this_plugins_business(self):
        for name in FOREIGN:
            self.assertEqual(failure_notice({"tool_name": name}), {}, name)

    def test_a_nameless_payload_says_nothing_rather_than_guessing(self):
        """A payload with no tool name is an event the hook cannot identify:
        say nothing rather than assert that "unknown tool" failed to write."""
        self.assertEqual(failure_notice({}), {})

    def test_the_json_matcher_routes_write_verbs_and_python_declines_the_rest(self):
        """The JSON matcher routes any server whose tool carries a write verb,
        because `appianMcpToolPrefixes[]` (norm § 7.2) lets a project declare
        servers the static matcher cannot know by name -- narrowing it back to
        `appian` names would reproduce the perimeter failure it fixes. The
        line is drawn in Python: a foreign write wakes the hook and gets
        nothing said about it (asserted above); a verb-less read is not
        routed at all."""
        matcher = re.compile(matcher_for("PostToolUseFailure", "failure-notice"))
        for name in PLAIN_READS + ("mcp__claude_ai_Figma__get_metadata",):
            self.assertIsNone(matcher.match(name), name)
        for name in ("mcp__claude_ai_Supabase__create_branch",
                     "mcp__claude_ai_Google_Drive__create_file",
                     self.WRITE):
            self.assertTrue(matcher.match(name), name)


if __name__ == "__main__":
    unittest.main()
