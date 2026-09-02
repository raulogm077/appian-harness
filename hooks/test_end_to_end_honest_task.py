"""One honest task, walked end to end through every gate.

The sequence a builder performs, against the real reference corpus rather
than a fixture: an honest task gets through, and the one failure the gates
exist for is still caught. A gate that cries wolf gets switched off.
"""
import json, os, sys, tempfile, time, unittest

HOOKS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HOOKS)
sys.path.insert(0, HOOKS)
sys.path.insert(0, os.path.join(PLUGIN_ROOT, "scripts"))
import harness_hooks as H
from validate_verdict import anchors_of

REFERENCES = os.path.join(PLUGIN_ROOT, "skills", "appian-best-practices", "references")


def a_real_citation():
    """A file and heading that genuinely exist, resolved at run time.

    Hard-coding one rots the first time a heading is reworded, and the
    validator refuses a citation whose anchor does not exist.
    """
    for fname in sorted(os.listdir(REFERENCES)):
        if not fname.endswith(".md"):
            continue
        anchors = sorted(a for a in anchors_of(os.path.join(REFERENCES, fname)) if a)
        if anchors:
            return "%s#%s" % (fname, anchors[0])
    raise AssertionError("no citable heading anywhere in references/")


class TestOneHonestTaskEndToEnd(unittest.TestCase):
    TASK = "TASK-3"
    OBJ = "RGM_Candidate"
    UUID = "_uuid-abc-123"

    def setUp(self):
        self.ref = a_real_citation()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        self.evidence = os.path.join(self.root, "evidence")
        self.cfg = {
            "pluginRoot": PLUGIN_ROOT, "evidenceDir": self.evidence,
            "projectRoot": self.root, "maxAllowedObjects": 3, "activeTask": None,
            "configPath": os.path.join(self.root, ".claude", "appian-harness.json"),
            "activeTaskFile": os.path.join(self.root, "tasks", "current.json"),
            "mcpServers": ["appian-dev", "appian-docs"],
            "designMcpServer": "appian-dev", "docsMcpServer": "appian-docs",
            "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
        }
        self.addCleanup(self._tmp.cleanup)

    # -- helpers -------------------------------------------------------
    def _verdict(self, phase):
        d = os.path.join(self.evidence, self.TASK)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "practices-%s.json" % phase), "w", encoding="utf-8") as f:
            json.dump({"task": self.TASK, "phase": phase, "verdict": "PASS",
                       "referencesApplied": [self.ref],
                       "findings": [{"criterion": "c", "verdict": "PASS",
                                     "evidence": "e", "reference": self.ref}]}, f)

    def _skill_record(self):
        d = os.path.join(self.evidence, self.TASK)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "appian-skill-loaded.json"), "w", encoding="utf-8") as f:
            json.dump({"task": self.TASK, "skill": "appian",
                       "source": "github.com/appian/dev-mcp-skills",
                       "appianVersion": "26.7", "docsMcp": "appian-docs"}, f)

    def _write(self, tool, **tool_input):
        return H.scope_gate({"tool_name": tool, "tool_input": tool_input}, self.cfg)

    def _log(self, tool, **tool_input):
        H.log_write({"tool_name": tool, "tool_input": tool_input, "tool_response": {}}, self.cfg)

    def _take_the_task(self):
        self.cfg["activeTask"] = {"id": self.TASK, "allowedObjects": [self.OBJ]}
        self._skill_record()
        self._verdict("design")

    # -- the walk ------------------------------------------------------
    def test_discovery_is_free_before_anything_is_set_up(self):
        self.assertEqual(self._write("mcp__appian-dev__getRecordType",
                                     name=self.OBJ)["permissionDecision"], "allow")

    def test_the_first_create_passes_with_a_name_only_contract(self):
        # At plan time a UUID does not exist, so the contract can only carry
        # the name. If this asked, every task would start with a prompt.
        self._take_the_task()
        d = self._write("mcp__appian-dev__createRecordType", name=self.OBJ)
        self.assertEqual(d["permissionDecision"], "allow", d["permissionDecisionReason"])

    def test_the_follow_up_writes_pass_once_preflight_adds_the_uuid(self):
        self._take_the_task()
        self.cfg["activeTask"]["allowedObjects"].append(self.UUID)
        for tool, kw in (
            ("mcp__appian-dev__updateRecordType", {"uuid": self.UUID}),
            # No object name in this call at all -- only the record type's
            # uuid and a field name.
            ("mcp__appian-dev__addRecordTypeField", {"uuid": self.UUID, "fieldName": "email"}),
        ):
            d = self._write(tool, **kw)
            self.assertEqual(d["permissionDecision"], "allow",
                             "%s: %s" % (tool, d["permissionDecisionReason"]))

    def test_an_honest_task_closes_cleanly(self):
        self._take_the_task()
        self._log("mcp__appian-dev__createRecordType", name=self.OBJ)
        time.sleep(1.1)  # the write log has one-second resolution
        for phase in H.CLOSURE_PHASES:
            self._verdict(phase)
        self.assertEqual(H.closure_gate({}, self.cfg)["decision"], "approve")

    def test_a_fix_that_skips_re_verification_is_caught(self):
        # The sequence the whole freshness check exists for: review fails,
        # the agent fixes it -- more writes -- and re-runs only review.
        self._take_the_task()
        self._log("mcp__appian-dev__createRecordType", name=self.OBJ)
        time.sleep(1.1)
        for phase in H.CLOSURE_PHASES:
            self._verdict(phase)
        self.assertEqual(H.closure_gate({}, self.cfg)["decision"], "approve")

        time.sleep(1.1)
        self._log("mcp__appian-dev__updateRecordType", uuid=self.UUID)
        time.sleep(1.1)
        self._verdict("review")
        out = H.closure_gate({}, self.cfg)
        self.assertEqual(out["decision"], "block")
        self.assertIn("stale", out["reason"])

        for phase in ("implementation", "qa"):
            self._verdict(phase)
        self.assertEqual(H.closure_gate({}, self.cfg)["decision"], "approve")

    def test_the_session_reports_ready_when_all_three_links_are_there(self):
        cfg = dict(self.cfg, officialAppianSkillPath=self._fake_installed_skill())
        ctx = H.session_start({}, cfg)["additionalContext"]
        self.assertIn("all three requirements are present", ctx)
        self.assertIn("validateExpression", ctx)

    def _fake_installed_skill(self):
        d = os.path.join(self.root, "official-skill")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: appian\n---\n\n**Appian Version:** 26.7\n")
        return d


if __name__ == "__main__":
    unittest.main()
