"""Authorization is per run, not per keystroke.

`appian-build` used to carry `disable-model-invocation: true`, so every task
in a twenty-task plan needed a human keystroke to start. That put the human
gate on *starting work* -- high friction, almost no value -- instead of on
what is irreversible or on a judgement that failed.

Removing that flag only makes sense if something checks that a run was
actually authorized, rather than trusting that it was. This is that
something.
"""
import json, os, sys, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import scope_gate
from test_harness_hooks import (cfg, make_plugin_root, write_design_verdict,
                                write_skill_record)

TASK = "T-1"


def write_run(root, **fields):
    path = os.path.join(root, "tasks", "run.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fields, f)
    return path


class TestRunAuthorization(unittest.TestCase):

    def _config(self, root, run=None, **over):
        make_plugin_root(root)
        write_design_verdict(root, TASK)
        write_skill_record(root, TASK)
        path = None
        if run is not None:
            path = write_run(root, **run)
        elif over.pop("expect_run_file", False):
            path = os.path.join(root, "tasks", "run.json")
        return cfg(root, activeTask={"id": TASK, "allowedObjects": ["A"]},
                   activeRunFile=path, **over)

    def _write(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                           "tool_input": {"name": "A"}}, config)

    def test_no_run_file_configured_behaves_exactly_as_before(self):
        # Opt-in per project. A project that never turns this on must not
        # notice it exists.
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self._write(self._config(t))["permissionDecision"], "allow")

    def test_configured_but_absent_means_nobody_granted_anything(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, expect_run_file=True)
            d = self._write(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("no authorized run", d["permissionDecisionReason"])

    def test_a_task_inside_the_authorized_list_writes_freely(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedTasks": ["T-1", "T-2"], "grantedBy": "raul",
                                     "maxTasks": 2, "tasksCompleted": 0})
            self.assertEqual(self._write(c)["permissionDecision"], "allow")

    def test_a_task_outside_the_authorized_list_asks(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedTasks": ["T-7"]})
            d = self._write(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("not in this run's authorized tasks", d["permissionDecisionReason"])

    def test_authorized_all_covers_the_whole_plan(self):
        # "The whole plan" is still a number of tasks. `authorizedAll`
        # spares the user from listing them, not from bounding them --
        # see TestTheBudgetIsWhatMakesItARun.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedAll": True, "grantedBy": "raul",
                                     "maxTasks": 20, "tasksCompleted": 3})
            self.assertEqual(self._write(c)["permissionDecision"], "allow")

    def test_a_run_that_authorizes_nothing_in_particular_is_not_authorization(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"grantedBy": "raul"})
            d = self._write(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("authorizes nothing in particular", d["permissionDecisionReason"])

    def test_a_spent_budget_stops_the_run(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedAll": True, "maxTasks": 5, "tasksCompleted": 5})
            d = self._write(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("budget is spent", d["permissionDecisionReason"])

    def test_a_budget_with_room_left_does_not_stop_it(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedAll": True, "maxTasks": 5, "tasksCompleted": 4})
            self.assertEqual(self._write(c)["permissionDecision"], "allow")

    def test_an_unreadable_run_file_asks(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedAll": True})
            with open(c["activeRunFile"], "w", encoding="utf-8") as f:
                f.write("{not json")
            self.assertEqual(self._write(c)["permissionDecision"], "ask")

    def test_authorization_never_covers_a_deletion(self):
        # The one thing a run may not pre-approve. An authorization that
        # silently covered deletes would be a master key, which is the
        # opposite of what granting a run is for.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedAll": True})
            d = scope_gate({"tool_name": "mcp__appian-dev__deleteRecordType",
                            "tool_input": {"name": "A"}}, c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("cannot be undone", d["permissionDecisionReason"])

    def test_it_never_denies(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, run={"authorizedTasks": ["T-9"]})
            self.assertNotEqual(self._write(c)["permissionDecision"], "deny")

    def test_reads_are_never_affected_by_run_authorization(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t, expect_run_file=True)
            d = scope_gate({"tool_name": "mcp__appian-dev__getInterface",
                            "tool_input": {"name": "A"}}, c)
            self.assertEqual(d["permissionDecision"], "allow")


class TestTheBudgetIsWhatMakesItARun(unittest.TestCase):
    """"Granted once and **bounded**" -- and the bound has to exist.

    The budget was the only thing standing between "the user authorized
    this run" and "the user authorized everything from now on", and three
    separate ways of writing the file walked straight past it:

    - no `maxTasks` at all, so there was nothing to spend;
    - `"tasksCompleted": null`, which `.get(k, 0)` returns as `None`
      rather than `0`, so `isinstance(done, int)` was False and the whole
      comparison was skipped;
    - `"maxTasks": "5"`, same skip from the other side.

    Every one of them read as a *wider* grant than the file appears to
    make, which is the direction this plugin refuses everywhere else: a
    malformed field buys more ceremony, never less. And the failure is
    silent -- the run keeps working, so nobody finds out the cap was never
    armed.
    """

    def _config_with(self, root, run):
        make_plugin_root(root)
        write_design_verdict(root, TASK)
        write_skill_record(root, TASK)
        return cfg(root, activeTask={"id": TASK, "allowedObjects": ["A"]},
                   activeRunFile=write_run(root, **run))

    def _write(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                           "tool_input": {"name": "A"}}, config)

    def test_a_run_with_no_budget_authorizes_nothing(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write(self._config_with(t, {"authorizedAll": True}))
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("maxTasks", d["permissionDecisionReason"])

    def test_a_null_tasks_completed_does_not_disarm_the_cap(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write(self._config_with(
                t, {"authorizedAll": True, "maxTasks": 1, "tasksCompleted": None}))
            self.assertEqual(d["permissionDecision"], "ask")

    def test_a_budget_written_as_a_string_is_not_a_budget(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write(self._config_with(
                t, {"authorizedAll": True, "maxTasks": "5", "tasksCompleted": 0}))
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("maxTasks", d["permissionDecisionReason"])

    def test_a_boolean_is_not_a_count_even_though_python_says_it_is(self):
        # `isinstance(True, int)` is True, so `"maxTasks": true` would have
        # passed for a budget of one without this.
        with tempfile.TemporaryDirectory() as t:
            d = self._write(self._config_with(
                t, {"authorizedAll": True, "maxTasks": True, "tasksCompleted": 0}))
            self.assertEqual(d["permissionDecision"], "ask")

    def test_a_properly_bounded_run_still_allows_the_write(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write(self._config_with(
                t, {"authorizedAll": True, "maxTasks": 5, "tasksCompleted": 2}))
            self.assertEqual(d["permissionDecision"], "allow")

    def test_a_spent_budget_still_stops_the_run(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._write(self._config_with(
                t, {"authorizedAll": True, "maxTasks": 3, "tasksCompleted": 3}))
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("budget is spent", d["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
