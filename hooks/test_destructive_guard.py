"""Deleting is not a stricter update, it is a different question.

Until now `delete` shared a code path with `update`, so a deletion in a
shared environment was measured only for scope and atomicity. An update is
versioned and recoverable; a deletion is not, and its blast radius is not
bounded by `allowedObjects` -- it can break objects no task ever listed.
"""
import json, os, sys, unittest, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import scope_gate
from test_harness_hooks import (cfg, make_plugin_root, write_design_verdict,
                                write_skill_record)

TASK = "T-1"
OBJ = "RGM_OldRule"


def record_dependents(root, task_id, obj, dependents=()):
    path = os.path.join(root, "evidence", task_id, "dependents.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = {}
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            existing = json.load(f)
    existing[obj] = {"checkedAt": "2026-08-09T00:00:00Z", "tool": "getObjectDependents",
                     "dependents": list(dependents)}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f)
    return path


class TestDeletionNeedsAnImpactAssessment(unittest.TestCase):

    def _config(self, root):
        make_plugin_root(root)
        write_design_verdict(root, TASK)
        write_skill_record(root, TASK)
        return cfg(root, activeTask={"id": TASK, "allowedObjects": [OBJ]})

    def _delete(self, config, tool="mcp__appian-dev__deleteExpressionRule"):
        return scope_gate({"tool_name": tool, "tool_input": {"name": OBJ}}, config)

    def _update(self, config):
        return scope_gate({"tool_name": "mcp__appian-dev__updateExpressionRule",
                           "tool_input": {"name": OBJ}}, config)

    def test_an_in_scope_update_goes_through_untouched(self):
        # The control: everything else about this task is in order, so any
        # prompt below is about the deletion and not about the setup.
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self._update(self._config(t))["permissionDecision"], "allow")

    def test_a_deletion_with_no_dependency_check_asks_and_says_why(self):
        with tempfile.TemporaryDirectory() as t:
            d = self._delete(self._config(t))
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("getObjectDependents", d["permissionDecisionReason"])

    def test_a_deletion_asks_even_with_the_assessment_on_file(self):
        # Unconditional on purpose. Destroying something in a shared
        # environment is the decision this harness should never make
        # quietly on somebody's behalf.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            record_dependents(t, TASK, OBJ, dependents=[])
            d = self._delete(c)
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("cannot be undone", d["permissionDecisionReason"])

    def test_zero_dependents_found_is_a_different_message_from_never_checked(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            unchecked = self._delete(c)["permissionDecisionReason"]
            record_dependents(t, TASK, OBJ, dependents=[])
            checked = self._delete(c)["permissionDecisionReason"]
            self.assertIn("getObjectDependents", unchecked)
            self.assertNotIn("getObjectDependents", checked)

    def test_an_assessment_of_a_different_object_does_not_count(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            record_dependents(t, TASK, "RGM_SomethingElse")
            self.assertIn("getObjectDependents", self._delete(c)["permissionDecisionReason"])

    def test_record_data_deletion_and_field_removal_are_covered_too(self):
        for tool in ("mcp__appian-dev__deleteRecordData",
                     "mcp__appian-dev__deleteRecordTypeField",
                     "mcp__appian-dev__removeGroupMember",
                     "mcp__appian-dev__deleteApplication"):
            with tempfile.TemporaryDirectory() as t:
                d = self._delete(self._config(t), tool=tool)
                self.assertEqual(d["permissionDecision"], "ask", tool)
                self.assertIn("cannot be undone", d["permissionDecisionReason"], tool)

    def test_a_corrupt_dependents_record_asks_rather_than_being_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            path = os.path.join(t, "evidence", TASK, "dependents.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write("{not json")
            r = self._delete(c)["permissionDecisionReason"]
            self.assertIn("could not be read", r)

    def test_it_still_never_denies(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertNotEqual(self._delete(self._config(t))["permissionDecision"], "deny")

    def test_reading_dependents_is_not_itself_gated(self):
        # The assessment must stay free, or the guard would block the very
        # check it demands.
        with tempfile.TemporaryDirectory() as t:
            d = scope_gate({"tool_name": "mcp__appian-dev__getObjectDependents",
                            "tool_input": {"uuid": OBJ}}, self._config(t))
            self.assertEqual(d["permissionDecision"], "allow")



class TestRecordDataOverwriteIsIrreversibleToo(unittest.TestCase):
    """`updateRecordData` was treated as an ordinary write, and an outside
    reading is what caught it.

    The premise separating destructive from ordinary — "an update is
    versioned and recoverable" — is true of design objects and false of
    record data. A row has no version history, so overwriting one is
    exactly as irreversible as deleting it, and just as unbounded by
    `allowedObjects`. Grouping it with `updateInterface` because both are
    spelled "update" was reasoning from the verb rather than from what the
    verb does."""

    def _config(self, root):
        make_plugin_root(root)
        write_design_verdict(root, TASK)
        write_skill_record(root, TASK)
        return cfg(root, activeTask={"id": TASK, "allowedObjects": [OBJ]})

    def test_overwriting_rows_needs_the_same_treatment_as_deleting_them(self):
        with tempfile.TemporaryDirectory() as t:
            d = scope_gate({"tool_name": "mcp__appian-dev__updateRecordData",
                            "tool_input": {"name": OBJ}}, self._config(t))
            self.assertEqual(d["permissionDecision"], "ask")
            self.assertIn("cannot be undone", d["permissionDecisionReason"])
            self.assertIn("getObjectDependents", d["permissionDecisionReason"])

    def test_updating_a_design_object_is_still_an_ordinary_write(self):
        # The distinction has to stay sharp, or every update becomes a
        # prompt and the prompt stops meaning anything.
        with tempfile.TemporaryDirectory() as t:
            c = self._config(t)
            for tool in ("mcp__appian-dev__updateInterface",
                         "mcp__appian-dev__updateRecordType",
                         "mcp__appian-dev__updateExpressionRule"):
                d = scope_gate({"tool_name": tool, "tool_input": {"name": OBJ}}, c)
                self.assertEqual(d["permissionDecision"], "allow", tool)


class TestConfigNullsDoNotSilenceTheAuditTrail(unittest.TestCase):
    """A key present-but-null used to crash, and where it crashed was the
    problem. `main()` turns a scope-gate exception into a loud `ask` and a
    closure-gate exception into a `block`, but the two logging hooks emit
    `{}` and exit 0. So one `"evidenceDir": null` stopped the operations log
    **silently** — and an empty write log reads to the staleness check as
    "this task never wrote", quietly making every stale verdict look
    fresh."""

    def test_a_null_evidence_dir_does_not_crash_the_write_log(self):
        # Inside a temp cwd, and that is the point rather than tidiness.
        # The null falls back to the DEFAULT, which is the RELATIVE path
        # `evidence` -- correct in production, where the hook runs with the
        # project as its working directory, and a landmine in a test, where
        # the working directory is this repository. The first version of
        # this test wrote `evidence/operations.jsonl` into the plugin's own
        # checkout on every run: the exact plugin/project contamination CI
        # has a step to catch, introduced by the test for a fix against
        # contamination.
        import harness_hooks as HH
        with tempfile.TemporaryDirectory() as t:
            here = os.getcwd()
            os.chdir(t)
            try:
                HH.log_write({}, {"evidenceDir": None})  # must not raise
                self.assertTrue(os.path.isdir(os.path.join(t, HH.DEFAULT_EVIDENCE_DIR)),
                                "the fallback should write somewhere, just not here")
            finally:
                os.chdir(here)

    def test_a_null_atomicity_budget_does_not_crash_the_gate(self):
        with tempfile.TemporaryDirectory() as t:
            c = cfg(t, activeTask={"id": TASK, "allowedObjects": [OBJ]},
                    maxAllowedObjects=None)
            d = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                            "tool_input": {"name": OBJ}}, c)
            self.assertIn(d["permissionDecision"], ("ask", "allow"))

    def test_a_null_evidence_dir_falls_back_rather_than_disappearing(self):
        import harness_hooks as HH
        self.assertEqual(HH._evidence_dir({"evidenceDir": None}),
                         HH.DEFAULT_EVIDENCE_DIR)
        self.assertEqual(HH._evidence_dir({}), HH.DEFAULT_EVIDENCE_DIR)
        self.assertEqual(HH._evidence_dir({"evidenceDir": "ev"}), "ev")

    def test_a_junk_atomicity_budget_falls_back(self):
        import harness_hooks as HH
        for junk in (None, "3", True, [], 0.5):
            self.assertEqual(HH._max_allowed_objects({"maxAllowedObjects": junk}),
                             HH.DEFAULT_MAX_ALLOWED_OBJECTS, repr(junk))
        self.assertEqual(HH._max_allowed_objects({"maxAllowedObjects": 7}), 7)


class TestBuildConfigIsExercisedWithoutASubprocess(unittest.TestCase):
    """`_build_config` is the one function only the launcher tests reached,
    and they are the slow ones behind an opt-out.

    A typo in it — `project__evidence_dir`, from a careless bulk rename —
    survived a green fast loop and was caught only by a clean-room run with
    the slow tests on. That is too narrow a net for the function that
    resolves every path the gates open, so it gets direct coverage here at
    no subprocess cost."""

    import harness_hooks as HH

    def _project(self, root, config):
        os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
        with open(os.path.join(root, ".claude", "appian-harness.json"), "w",
                  encoding="utf-8") as f:
            json.dump(config, f)
        return root

    def test_an_empty_config_resolves_every_default(self):
        with tempfile.TemporaryDirectory() as t:
            cfg_, active, err = self.HH._build_config(self._project(t, {}))
            self.assertTrue(active)
            self.assertIsNone(err)
            self.assertTrue(cfg_["evidenceDir"].endswith(self.HH.DEFAULT_EVIDENCE_DIR))
            self.assertEqual(cfg_["maxAllowedObjects"], self.HH.DEFAULT_MAX_ALLOWED_OBJECTS)
            self.assertEqual(cfg_["designMcpServer"], self.HH.DEFAULT_DESIGN_MCP)

    def test_every_documented_key_round_trips(self):
        with tempfile.TemporaryDirectory() as t:
            cfg_, _, err = self.HH._build_config(self._project(t, {
                "evidenceDir": "ev", "activeTaskFile": "tasks/cur.json",
                "maxAllowedObjects": 7, "leaseFile": "shared/leases.json",
                "activeRunFile": "tasks/run.json", "designMcpServer": "acme-design",
                "docsMcpServer": "acme-docs", "officialAppianSkillPath": "vendor/appian"}))
            self.assertIsNone(err)
            self.assertEqual(cfg_["maxAllowedObjects"], 7)
            self.assertEqual(cfg_["designMcpServer"], "acme-design")
            self.assertEqual(cfg_["docsMcpServer"], "acme-docs")
            for key in ("evidenceDir", "activeTaskFile", "leaseFile", "activeRunFile",
                        "officialAppianSkillPath"):
                self.assertTrue(os.path.isabs(cfg_[key]), "%s not resolved: %r"
                                % (key, cfg_[key]))

    def test_nulls_throughout_resolve_to_defaults_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as t:
            cfg_, _, err = self.HH._build_config(self._project(t, {
                "evidenceDir": None, "activeTaskFile": None, "maxAllowedObjects": None,
                "leaseFile": None, "activeRunFile": None,
                "designMcpServer": None, "docsMcpServer": None,
                "officialAppianSkillPath": None}))
            self.assertIsNone(err)
            self.assertEqual(cfg_["maxAllowedObjects"], self.HH.DEFAULT_MAX_ALLOWED_OBJECTS)
            self.assertEqual(cfg_["designMcpServer"], self.HH.DEFAULT_DESIGN_MCP)
            self.assertIsNone(cfg_["leaseFile"])
            self.assertIsNone(cfg_["activeRunFile"])

    def test_a_project_without_the_config_is_inactive(self):
        with tempfile.TemporaryDirectory() as t:
            cfg_, active, err = self.HH._build_config(t)
            self.assertFalse(active)
            self.assertIsNone(err)

    def test_an_unreadable_config_is_active_and_reports_the_error(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, ".claude"))
            with open(os.path.join(t, ".claude", "appian-harness.json"), "w",
                      encoding="utf-8") as f:
                f.write("{not json")
            cfg_, active, err = self.HH._build_config(t)
            self.assertTrue(active)
            self.assertTrue(err)

if __name__ == "__main__":
    unittest.main()
