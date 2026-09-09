"""The acid case of § 17.2, reproduced from recorded shapes.

Defined by PROPERTIES, not by an object: a `micro` -- one object, one
intention, a small change -- over the worst interface a project has:
reachable from a published site, served only by REST, with charts, and
carrying the `testInterface` 500 of serialization.

It must close as `micro`, **without escalating** and **without repeating a
single check**. What makes that possible, and what this file holds to:

  * exposure through a site modulates the LANE, never the size (§ 5.5);
  * a failure of the instrument NEVER changes the `kind` (§ 8.7);
  * the failure is first told apart from a regression the write itself
    introduced (§ 8.7 step 1-bis);
  * the search for alternative evidence runs PER GUARANTEE CLASS, so
    behaviour can be covered by the REST test-case run while accessibility
    -- which needs a tree that will not render -- stays NOT MEASURED.

The close is now the FULL one, reviewer included: the `certify` is the single
judge's, and it arrives with Phase 4. Exposure bought this scope a reviewer and
not a size, so the verdict is one object's matrix -- and the two halves of the
case meet in it: gate 2 is accredited by the REST replay, gate 4 is
NOT_MEASURED because accessibility needs a tree that will not render, and the
scope still closes as `micro`.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import harness_hooks as hh  # noqa: E402
from harness_hooks import (closure_gate, log_write, observe_reads, scope_gate,
                           state_gate)
from test_certify import REF, certify_cells, write_certify
from test_grant import GRANT, signed_cfg
from test_state_gate import projection, read_scope, write_scope

DASHBOARD = "_uuid-dashboard"
# The environment's own words, from the 500 recorded in this project.
SERIALIZATION_500 = ("API error (HTTP 500): Failed to serialize test result")


def _entry(tool, tool_input, response, tool_use_id):
    return {"tool_name": tool, "tool_input": tool_input,
            "tool_use_id": tool_use_id, "tool_response": response}


def _rest_run(uuid, tool_use_id="tu-rest"):
    """The alternative surface § 17.2 names: the 500 is the servlet's, and
    the REST path for running an interface's test cases exists and is
    documented. It arrives as a Bash call, which is why `observe-reads`
    recognises it -- without that, this case has no behavioural alternative
    at all and would close pending human on a class that WAS measured."""
    return _entry("Bash",
                  {"command": "curl -s -u $APPIAN_USER:$APPIAN_KEY "
                              "https://indra-spain.appiancloud.com/suite/rest/a/"
                              "lcp-api/latest/interfaces/%s/test-cases/run" % uuid},
                  json.dumps({"testCases": [{"name": "carga inicial",
                                             "passed": True},
                                            {"name": "sin resultados",
                                             "passed": True}]}),
                  tool_use_id)


class AcidCase(unittest.TestCase):

    def scope(self, root):
        """A micro over one object, published in a site. The exposure is a
        property of the object, not a field of the scope: nothing in the
        contract says `site`, and that is the point -- there is no lever
        here for exposure to pull on the size."""
        grant = dict(GRANT, objects=[DASHBOARD])
        return signed_cfg(root, kind="micro",
                          intent="cambiar el label de la columna de tarifa",
                          allowedObjects=[DASHBOARD], grant=grant)

    def write(self, c, tool_use_id="tu-w1", expression='a!textField(label: "Tarifa")'):
        out = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                          "session_id": "s-acid", "tool_use_id": tool_use_id,
                          "tool_input": {"uuid": DASHBOARD,
                                         "expression": expression}}, c)
        self.assertEqual(out["permissionDecision"], "allow",
                         out.get("permissionDecisionReason"))
        log_write({"tool_name": "mcp__appian-dev__updateInterface",
                   "tool_use_id": tool_use_id,
                   "tool_input": {"uuid": DASHBOARD, "expression": expression},
                   "tool_response": json.dumps({"uuid": DASHBOARD,
                                                "versionId": 12})}, c)
        return c

    def observe(self, c, batch):
        c = dict(c, activeTask=read_scope(c))
        observe_reads({"tool_calls": batch}, c)
        return c

    def certify(self, c):
        """The reviewer's half, which Phase 3 left to Phase 4.

        Exposure through a published site bought this scope a reviewer, not
        a size (§ 5.5), and the whole verdict is ONE object's matrix. Its
        shape is what the case is really about: gate 2 is accredited by the
        REST replay -- the alternative surface, because the 500 is the
        servlet's -- while gate 4 stays NOT_MEASURED, because accessibility
        needs a tree that will not render and no instrument can produce it.
        `validateDesignObject` accredits nothing: it is green on anything
        that parses, and the validator refuses it for that reason.
        """
        scope = read_scope(c)
        cells = certify_cells([DASHBOARD], "tu-get",
                              gate2={"toolUseId": "tu-rest"},
                              gate4={"verdict": "NOT_MEASURED",
                                     "evidence": "the render is the 500 of "
                                                 "serialization; no tree exists to "
                                                 "judge the screen on",
                                     "impact": "the screen's accessibility and its "
                                               "states are unjudged",
                                     "remedy": "a person opens the screen in the site",
                                     "reference": REF})
        return write_certify(
            c, scope, objects=[DASHBOARD], verdict="NOT_MEASURED",
            notMeasuredClass="REQUIRES_HUMAN", owner="the scope's owner",
            closingCondition="somebody opens GDE_INT_Dashboard in the site and "
                             "says whether it reads correctly",
            deferredCriterion="visual-judgement-on-rendered-screen",
            matrix=cells)

    def close(self, c):
        scope = read_scope(c)
        scope["request"] = "close"
        c = write_scope(c, scope)
        state_gate({"tool_name": "Write",
                    "tool_input": {"file_path": c["activeTaskFile"]}}, c)
        c = dict(c, activeTask=read_scope(c))
        return c, closure_gate({}, c)

    def floor_batch(self, c):
        """What a screen that WILL NOT RENDER can still be measured with:
        validate, the re-read, the failed render itself -- which is the
        corroboration § 8.7 step 1 demands -- and the REST replay."""
        return [
            _entry("mcp__appian-dev__validateDesignObject", {"uuid": DASHBOARD},
                   {"valid": True}, "tu-val"),
            _entry("mcp__appian-dev__getInterface", {"uuid": DASHBOARD},
                   {"name": "GDE_INT_Dashboard", "expression": "a!x()"},
                   "tu-get"),
            _entry("mcp__appian-dev__testInterface",
                   {"uuid": DASHBOARD, "testInputs": {"id": 1}},
                   SERIALIZATION_500, "tu-render"),
            _rest_run(DASHBOARD),
        ]

    def family_evidence(self, c):
        """§ 8.7 step 1-bis, third way: the same failure on another object
        of the same family. It is what tells a limit of the environment
        from a regression this very write introduced."""
        return self.observe(c, [
            _entry("mcp__appian-dev__testInterface",
                   {"uuid": "_uuid-otro-dashboard", "testInputs": {}},
                   SERIALIZATION_500, "tu-familia")])


class TestTheAcidCaseClosesAsMicro(AcidCase):

    def test_it_closes_without_escalating_and_without_repeating_a_check(self):
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            self.certify(c)

            report = hh.floor_report(c, read_scope(c))
            # Nothing is BLOCKING: there is no leg the person could go and
            # pay, because the instrument that would pay it is down.
            self.assertEqual(report["missing"], [], report["missing"])
            self.assertEqual(report["blocking"], [], report["blocking"])

            c, out = self.close(c)
            self.assertEqual(out["decision"], "approve", out)

            final = read_scope(c)
            # The size did not move. That is the whole claim of § 8.7.
            self.assertEqual(final["kind"], "micro")
            self.assertEqual(final["status"], "closed-pending-human")
            self.assertEqual(projection(c)["scope"]["kind"], "micro")

    def test_it_buys_exactly_one_judge_and_no_chain(self):
        # § 5.4: the reviewer lane costs ONE certify over the object. No
        # design (a micro never pays it), no risk (the scope is not high),
        # and no second opinion voting against the first.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            self.certify(c)
            c, out = self.close(c)
            self.assertEqual(out["decision"], "approve", out)
            scope_dir = os.path.join(c["evidenceDir"], read_scope(c)["id"])
            verdicts = sorted(f for f in os.listdir(scope_dir)
                              if f.startswith("practices-"))
            # The design verdict is the fixture's, and a micro's close never
            # asks for it: what this scope BOUGHT is the one certify -- one
            # emission (§ 9.4's version) plus the copy § 11.1 keeps for
            # readers, and nothing else.
            self.assertEqual([f for f in verdicts if "certify" in f],
                             ["practices-certify.001.json",
                              "practices-certify.json"])
            self.assertEqual([f for f in verdicts if "risk" in f], [])

    def test_the_instrument_failure_did_not_buy_a_second_judge(self):
        # A failure of the instrument changes neither the kind (§ 8.7) nor
        # the number of judges: the gap is carried as a pending judgement,
        # not escalated into more ceremony.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            self.certify(c)
            c, _out = self.close(c)
            dispatched = [r for r in hh._read_jsonl(
                os.path.join(c["evidenceDir"], "gate-decisions.jsonl"))
                if r.get("event") == "judge-dispatched"]
            self.assertEqual(dispatched, [])
            self.assertEqual(read_scope(c)["kind"], "micro")

    def test_no_check_is_issued_twice(self):
        # § 17.3's "comprobaciones repetidas: 0". Every credited row has its
        # own tool_use_id, and no (object, action, inputs) triple appears
        # more than once for this instance.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            rows = hh.read_checks(c, read_scope(c)["instanceId"])
            seen = [(r.get("object"), r.get("action"), r.get("inputsDigest"))
                    for r in rows]
            self.assertEqual(len(seen), len(set(seen)), seen)
            self.assertEqual(len({r["toolUseId"] for r in rows}), len(rows))

    def test_a_second_close_demands_nothing_new(self):
        # Nothing that could change the result changed, so the floor asks
        # for nothing the first pass already settled.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            scope = read_scope(c)
            first = hh.floor_report(c, scope)
            second = hh.floor_report(c, scope)
            self.assertEqual(first["missing"], second["missing"])
            self.assertEqual(first["notMeasured"], second["notMeasured"])


class TestWhatMustNotEscalateIt(AcidCase):

    def test_being_published_in_a_site_does_not_escalate_the_size(self):
        # § 5.5: exposure modulates the lane, not the size. There is no
        # lever in the contract for it to pull on, and this asserts the
        # absence rather than trusting it.
        self.assertNotIn("site", hh._DESIGN_DEMANDING_ACTIONS.pattern.lower())
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            self.assertEqual(
                hh.task_min_kind("mcp__appian-dev__updateInterface",
                                 {"uuid": DASHBOARD, "expression": "a!x()"}),
                "micro")

    def test_the_known_render_failure_does_not_escalate_the_size(self):
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            c, _out = self.close(c)
            self.assertEqual(read_scope(c)["kind"], "micro")


class TestWhatTheCaseStillOwes(AcidCase):
    """The half that must NOT be manufactured into a pass."""

    def test_behaviour_is_covered_by_the_rest_replay(self):
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            classes = [g["class"] for g in hh.floor_report(c, read_scope(c))["notMeasured"]]
            self.assertNotIn("behavioural", classes)

    def test_accessibility_stays_not_measured_with_an_owner_and_a_condition(self):
        # Running the test cases answers for behaviour and produces NO
        # tree, so it cannot answer for accessibility. Treating the two
        # classes together would call the floor met when it is met in part.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            gaps = [g for g in hh.floor_report(c, read_scope(c))["notMeasured"]
                    if g["class"] == "accessibility"]
            self.assertEqual(len(gaps), 1)
            self.assertTrue(gaps[0]["owner"])
            self.assertTrue(gaps[0]["condition"])

    def test_the_gap_reaches_disk_with_its_owner(self):
        # A warning that must survive nobody being in front of the screen
        # belongs on disk, not in a systemMessage.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c))
            self.certify(c)
            c, _out = self.close(c)
            debts = hh._read_jsonl(os.path.join(c["evidenceDir"],
                                                "deferred-debt.jsonl"))
            gaps = [d for d in debts
                    if d.get("kind") == "NOT_MEASURED / REQUIRES_HUMAN"]
            self.assertTrue(gaps)
            self.assertTrue(all(d.get("owner") and d.get("condition")
                                for d in gaps))

    def test_without_the_rest_replay_behaviour_is_owed_too(self):
        # The negative control: if the alternative surface is not used, the
        # class it would have covered is NOT MEASURED as well. Nothing here
        # passes by absence of measurement.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.family_evidence(c)
            c = self.observe(c, self.floor_batch(c)[:3])
            classes = [g["class"] for g in hh.floor_report(c, read_scope(c))["notMeasured"]]
            self.assertIn("behavioural", classes)
            self.assertIn("accessibility", classes)


class TestTheInstrumentIsNotConfusedWithARegression(AcidCase):

    def test_an_unexplained_failure_does_not_pass_as_an_environment_limit(self):
        # Without any of the three ways of § 8.7 step 1-bis, the scope
        # still closes pending human -- but on a different gap, named for
        # what it is: nobody can tell the two apart.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.write(c)
            c = self.observe(c, self.floor_batch(c))
            classes = [g["class"] for g in hh.floor_report(c, read_scope(c))["notMeasured"]]
            self.assertIn("instrument-undistinguished", classes)

    def test_a_screen_that_rendered_before_the_write_is_a_regression(self):
        # An instrument that measured and stopped measuring after a write
        # of the agent's is a change of the OBJECT, and that blocks: it is
        # the one case where there is something to fix.
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.observe(c, [
                _entry("mcp__appian-dev__testInterface",
                       {"uuid": DASHBOARD, "testInputs": {"id": 1}},
                       {"#t": "Form", "contents": [
                           {"#t": "TextField", "label": "Tarifa",
                            "value": "12", "saveInto": "enc:1"}]},
                       "tu-antes")])
            c = self.write(c)
            c = self.observe(c, self.floor_batch(c))
            report = hh.floor_report(c, read_scope(c))
            self.assertTrue(report["blocking"])
            self.assertIn("not a limit of the environment", report["blocking"][0])

    def test_a_regression_blocks_the_close_instead_of_deferring_it(self):
        with tempfile.TemporaryDirectory() as root:
            c = self.scope(root)
            c = self.observe(c, [
                _entry("mcp__appian-dev__testInterface",
                       {"uuid": DASHBOARD, "testInputs": {"id": 1}},
                       {"#t": "Form", "contents": [
                           {"#t": "TextField", "label": "Tarifa",
                            "value": "12", "saveInto": "enc:1"}]},
                       "tu-antes")])
            c = self.write(c)
            c = self.observe(c, self.floor_batch(c))
            _c, out = self.close(c)
            self.assertEqual(out["decision"], "block")


if __name__ == "__main__":
    unittest.main()
