"""The v07 verdict contract: the object x gate matrix (norm § 9.2), the three
gate classes (§ 9.3) and the re-emission cap (§ 9.4).

The 0.6 shape checks live in test_validate_verdict.py and stay there: § 15
keeps the old phases valid, so both contracts are in force at once and the
two files say which is which.
"""
import json, os, re, tempfile, unittest

from validate_verdict import (
    CARDINAL, CLASS_BY_GATE, CONTEXTUAL, GATES, GUARANTEE_RESIDUE_IDS,
    NATURE_BY_GATE, NATURE_FULL_JUDGEMENT, NATURE_IMPORTED,
    NATURE_JUDGED_ON_EVIDENCE, NEVER_GRADED_DOWN, PENDING_JUDGEMENT_IDS,
    PHASES_LEGACY, PHASES_V07, RECOMMENDED, earlier_versions, gate_class,
    validate_verdict,
)

REFDIR = os.path.join("skills", "appian-best-practices", "references")
PLUGIN_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GATES_DOC = os.path.join(PLUGIN_ROOT, REFDIR, "10-quality-gates.md")


def make_plugin(root):
    d = os.path.join(root, REFDIR)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "06-security.md"), "w", encoding="utf-8") as f:
        f.write("# Security\n\n## Record level security\nBody.\n")
    return root


REF = "06-security.md#record-level-security"


def cell(obj, gate, verdict="PASS", **over):
    """One well-formed cell, with whatever a PASS of its nature needs."""
    c = {"object": obj, "gate": gate, "nature": NATURE_BY_GATE[gate],
         "verdict": verdict}
    if NATURE_BY_GATE[gate] == NATURE_IMPORTED:
        c["toolUseId"] = "tu-%s-%d" % (obj, gate)
        c["result"] = "ok"
    elif NATURE_BY_GATE[gate] == NATURE_JUDGED_ON_EVIDENCE:
        c["citesRow"] = "tu-%s-%d" % (obj, gate)
    if verdict != "PASS":
        c.update({"evidence": "what was looked at", "impact": "what it costs",
                  "remedy": "what to do"})
        if NATURE_BY_GATE[gate] != NATURE_IMPORTED:
            c["reference"] = REF
    c.update(over)
    return c


def full_matrix(*objects):
    return [cell(o, g) for o in objects for g in GATES]


def certify(root, name="practices-certify.json", **over):
    v = {
        "task": "T-1",
        "instanceId": "inst-1",
        "phase": "certify",
        "verdict": "PASS",
        "objects": ["GDE_INT_Dashboard"],
        "matrix": full_matrix("GDE_INT_Dashboard"),
        "referencesApplied": [REF],
        "findings": [],
    }
    v.update(over)
    path = os.path.join(root, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(v, f)
    return path


def ledger(evidence_dir, rows):
    os.makedirs(evidence_dir, exist_ok=True)
    with open(os.path.join(evidence_dir, "checks.jsonl"), "w",
              encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def rows_for(objects, instance="inst-1", guarantee="structure"):
    return [{"toolUseId": "tu-%s-%d" % (o, g), "instanceId": instance,
             "result": "ok", "guaranteeClass": guarantee, "object": o}
            for o in objects for g in GATES]


class TestCoverageIsTheGuarantee(unittest.TestCase):
    """Full coverage -- one entry per object per gate -- is not traded for
    tokens. What 0.7 changed is what a cell IS, not how many there are."""

    def test_a_complete_matrix_validates(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self.assertEqual(validate_verdict(certify(t), t), [])

    def test_a_missing_cell_is_reported_with_its_gate(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("GDE_INT_Dashboard") if c["gate"] != 5]
            errs = validate_verdict(certify(t, matrix=m), t)
            self.assertTrue(any("incomplete" in e and "gate 5" in e for e in errs), errs)

    def test_a_duplicated_cell_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("GDE_INT_Dashboard")
            m.append(cell("GDE_INT_Dashboard", 4))
            errs = validate_verdict(certify(t, matrix=m), t)
            self.assertTrue(any("repeats object" in e for e in errs), errs)

    def test_several_objects_each_owe_seven_gates(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            objs = ["A", "B"]
            good = certify(t, objects=objs, matrix=full_matrix(*objs))
            self.assertEqual(validate_verdict(good, t), [])
            half = certify(t, objects=objs, matrix=full_matrix("A"))
            self.assertTrue(any("incomplete" in e for e in validate_verdict(half, t)))

    def test_a_cell_about_an_undeclared_object_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("GDE_INT_Dashboard") + [cell("Other", 1)]
            errs = validate_verdict(certify(t, matrix=m), t)
            self.assertTrue(any("not in 'objects'" in e for e in errs), errs)

    def test_a_certify_without_a_matrix_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(certify(t, matrix=[]), t)
            self.assertTrue(any("non-empty 'matrix'" in e for e in errs), errs)

    def test_design_and_risk_owe_no_matrix(self):
        # The matrix is certify's question ("contract, doctrine and evidence
        # per cell?"). design asks whether it is a good solution and risk
        # asks how it fails; neither is answered cell by cell.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for phase in ("design", "risk"):
                path = os.path.join(t, "v.json")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"task": "T-1", "phase": phase, "verdict": "PASS",
                               "referencesApplied": [REF], "findings": []}, f)
                self.assertEqual(validate_verdict(path, t), [], phase)


class TestWhoAnswersAGateIsNotTheAuditorsToChoose(unittest.TestCase):
    def test_every_gate_has_the_nature_the_norm_gives_it(self):
        self.assertEqual(NATURE_BY_GATE[1], NATURE_IMPORTED)
        self.assertEqual(NATURE_BY_GATE[2], NATURE_IMPORTED)
        self.assertEqual(NATURE_BY_GATE[3], NATURE_JUDGED_ON_EVIDENCE)
        self.assertEqual(NATURE_BY_GATE[5], NATURE_JUDGED_ON_EVIDENCE)
        for gate in (4, 6, 7):
            self.assertEqual(NATURE_BY_GATE[gate], NATURE_FULL_JUDGEMENT)

    def test_declaring_another_nature_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("GDE_INT_Dashboard")
            for c in m:
                if c["gate"] == 1:
                    c["nature"] = NATURE_FULL_JUDGEMENT
            errs = validate_verdict(certify(t, matrix=m), t)
            self.assertTrue(any("not the auditor's to choose" in e for e in errs), errs)

    def test_a_case_created_in_scope_turns_gate_two_into_judgement(self):
        # The one leg of the floor whose evidence the interested party
        # fabricates: the question moves to where there is judgement, and it
        # costs zero new calls.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 2]
            m.append({"object": "D", "gate": 2, "caseCreatedInScope": True,
                      "nature": NATURE_JUDGED_ON_EVIDENCE, "verdict": "PASS",
                      "citesRow": "tu-D-2"})
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"], matrix=m), t), [])

    def test_without_that_flag_gate_two_is_still_imported(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 2]
            m.append({"object": "D", "gate": 2,
                      "nature": NATURE_JUDGED_ON_EVIDENCE, "verdict": "PASS",
                      "citesRow": "tu-D-2"})
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("not the auditor's to choose" in e for e in errs), errs)


class TestAnImportedCellIsCopiedNotJudged(unittest.TestCase):
    """`validate_verdict.py` checks that the row exists, is this instance's
    and bought more than a green signal. The auditor does not judge it."""

    def test_an_imported_cell_without_a_tool_use_id_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("D")
            for c in m:
                if c["gate"] == 1:
                    del c["toolUseId"]
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("needs the 'toolUseId'" in e for e in errs), errs)

    def test_an_imported_cell_without_the_rows_result_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("D")
            for c in m:
                if c["gate"] == 2:
                    del c["result"]
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("needs the 'result'" in e for e in errs), errs)

    def test_a_row_that_is_in_no_ledger_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            ev = os.path.join(t, "evidence")
            ledger(ev, rows_for(["D"])[1:])   # the first row is missing
            errs = validate_verdict(certify(t, objects=["D"],
                                            matrix=full_matrix("D")), t,
                                    evidence_dir=ev, instance_id="inst-1")
            self.assertTrue(any("in no checks.jsonl row" in e for e in errs), errs)

    def test_a_row_of_another_instance_does_not_accredit_this_one(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            ev = os.path.join(t, "evidence")
            ledger(ev, rows_for(["D"], instance="inst-OTHER"))
            errs = validate_verdict(certify(t, objects=["D"],
                                            matrix=full_matrix("D")), t,
                                    evidence_dir=ev, instance_id="inst-1")
            self.assertTrue(any("in no checks.jsonl row" in e for e in errs), errs)

    def test_a_green_signal_only_row_cannot_carry_a_gate(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            ev = os.path.join(t, "evidence")
            ledger(ev, rows_for(["D"], guarantee="green-signal-only"))
            errs = validate_verdict(certify(t, objects=["D"],
                                            matrix=full_matrix("D")), t,
                                    evidence_dir=ev, instance_id="inst-1")
            self.assertTrue(any("green-signal-only" in e for e in errs), errs)

    def test_a_resolving_ledger_leaves_the_matrix_clean(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            ev = os.path.join(t, "evidence")
            ledger(ev, rows_for(["D"]))
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"],
                                         matrix=full_matrix("D")), t,
                                 evidence_dir=ev, instance_id="inst-1"), [])

    def test_with_no_ledger_the_cells_are_checked_for_shape_alone(self):
        # The CLI can run before any gate opened the file. Shape-only is
        # honest; inventing a resolution failure there is not.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self.assertEqual(validate_verdict(certify(t), t,
                                              evidence_dir=os.path.join(t, "nope"),
                                              instance_id="inst-1"), [])


class TestJudgementOverEvidenceMustCiteTheRow(unittest.TestCase):
    def test_a_pass_with_no_row_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("D")
            for c in m:
                if c["gate"] == 3:
                    del c["citesRow"]
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("cannot be PASS" in e for e in errs), errs)

    def test_with_no_row_not_measured_is_the_honest_answer(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 5]
            m.append({"object": "D", "gate": 5,
                      "nature": NATURE_JUDGED_ON_EVIDENCE,
                      "verdict": "NOT_MEASURED", "evidence": "no row measured it",
                      "impact": "performance is unknown", "remedy": "measure it",
                      "reference": REF})
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"], matrix=m,
                                         verdict="NOT_MEASURED",
                                         notMeasuredClass="BLOCKING"), t), [])


class TestCellsAreProportional(unittest.TestCase):
    """A PASS is one line. The development -- evidence, impact, remedy,
    citation -- is owed by the cells somebody is going to read."""

    def test_a_pass_needs_no_development(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for c in full_matrix("D"):
                self.assertNotIn("impact", c)
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"],
                                         matrix=full_matrix("D")), t), [])

    def test_a_fail_owes_evidence_impact_and_remedy(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 6]
            m.append({"object": "D", "gate": 6, "nature": NATURE_FULL_JUDGEMENT,
                      "verdict": "FAIL", "evidence": "e", "reference": REF})
            errs = validate_verdict(certify(t, objects=["D"], matrix=m,
                                            verdict="FAIL"), t)
            self.assertTrue(any("'impact'" in e for e in errs), errs)
            self.assertTrue(any("'remedy'" in e for e in errs), errs)

    def test_a_judged_fail_owes_the_doctrine_it_applied(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 4]
            m.append({"object": "D", "gate": 4, "nature": NATURE_FULL_JUDGEMENT,
                      "verdict": "FAIL", "evidence": "e", "impact": "i",
                      "remedy": "r"})
            errs = validate_verdict(certify(t, objects=["D"], matrix=m,
                                            verdict="FAIL"), t)
            self.assertTrue(any("owes a 'reference'" in e for e in errs), errs)

    def test_a_citation_that_does_not_resolve_fails_here_too(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 4]
            m.append({"object": "D", "gate": 4, "nature": NATURE_FULL_JUDGEMENT,
                      "verdict": "FAIL", "evidence": "e", "impact": "i",
                      "remedy": "r", "reference": "06-security.md#invented"})
            errs = validate_verdict(certify(t, objects=["D"], matrix=m,
                                            verdict="FAIL"), t)
            self.assertTrue(any("anchor" in e for e in errs), errs)

    def test_an_imported_fail_owes_no_reference(self):
        # It was not judged: the row that accredits it is the citation.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 1]
            m.append({"object": "D", "gate": 1, "nature": NATURE_IMPORTED,
                      "verdict": "FAIL", "toolUseId": "tu-D-1", "result": "failed",
                      "evidence": "the row says it failed", "impact": "i",
                      "remedy": "r"})
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"], matrix=m,
                                         verdict="FAIL"), t), [])

    def test_na_justified_by_the_schedule_is_refused_in_a_cell_too(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 7]
            m.append({"object": "D", "gate": 7, "nature": NATURE_FULL_JUDGEMENT,
                      "verdict": "N/A", "evidence": "N/A: no time this sprint",
                      "impact": "i", "remedy": "r", "reference": REF})
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("about the object" in e for e in errs), errs)

    def test_a_bare_na_is_not_a_justification_in_a_cell(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 7]
            m.append({"object": "D", "gate": 7, "nature": NATURE_FULL_JUDGEMENT,
                      "verdict": "N/A", "evidence": "N/A", "impact": "i",
                      "remedy": "r", "reference": REF})
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("beyond the words 'N/A'" in e for e in errs), errs)


class TestTheHeaderIsDerivedNotSummarised(unittest.TestCase):
    def _with_gate_six(self, root, outcome):
        m = [c for c in full_matrix("D") if c["gate"] != 6]
        m.append({"object": "D", "gate": 6, "nature": NATURE_FULL_JUDGEMENT,
                  "verdict": outcome, "evidence": "e", "impact": "i",
                  "remedy": "r", "reference": REF})
        return m

    def test_a_pass_over_a_failing_cell_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(
                certify(t, objects=["D"], matrix=self._with_gate_six(t, "FAIL"),
                        verdict="PASS"), t)
            self.assertTrue(any("derived from the cells" in e for e in errs), errs)

    def test_a_pass_over_a_not_measured_cell_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(
                certify(t, objects=["D"],
                        matrix=self._with_gate_six(t, "NOT_MEASURED"),
                        verdict="PASS"), t)
            self.assertTrue(any("derived from the cells" in e for e in errs), errs)

    def test_fail_outranks_not_measured(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = self._with_gate_six(t, "FAIL")
            for c in m:
                if c["gate"] == 4:
                    c.update({"verdict": "NOT_MEASURED", "evidence": "e",
                              "impact": "i", "remedy": "r", "reference": REF})
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"], matrix=m,
                                         verdict="FAIL"), t), [])

    def test_na_cells_do_not_stop_a_pass(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = [c for c in full_matrix("D") if c["gate"] != 7]
            m.append({"object": "D", "gate": 7, "nature": NATURE_FULL_JUDGEMENT,
                      "verdict": "N/A",
                      "evidence": "the object reaches no external system",
                      "impact": "none", "remedy": "none", "reference": REF})
            self.assertEqual(
                validate_verdict(certify(t, objects=["D"], matrix=m), t), [])


class TestTheSevenGatesDoNotBlockAlike(unittest.TestCase):
    """Class and nature are independent axes (§ 9.3): gate 1 is CARDINAL and
    its cell is imported, and there is no tension in that."""

    def test_the_classes_are_the_ones_the_norm_names(self):
        self.assertEqual(CLASS_BY_GATE[1], CARDINAL)
        self.assertEqual(CLASS_BY_GATE[3], CARDINAL)
        for gate in (2, 4, 7):
            self.assertEqual(CLASS_BY_GATE[gate], RECOMMENDED)
        for gate in (5, 6):
            self.assertEqual(CLASS_BY_GATE[gate], CONTEXTUAL)

    def test_there_is_no_fourth_class_and_no_gate_without_one(self):
        self.assertEqual(sorted(CLASS_BY_GATE), list(GATES))
        self.assertEqual(set(CLASS_BY_GATE.values()),
                         {CARDINAL, RECOMMENDED, CONTEXTUAL})

    def test_a_never_graded_down_finding_is_cardinal_wherever_it_lands(self):
        # Maintainability is CONTEXTUAL, but a non-idempotent write found
        # there is still blocking: the doctrine never grades those down.
        self.assertEqual(gate_class({"gate": 6}), CONTEXTUAL)
        self.assertEqual(
            gate_class({"gate": 6, "neverGradedDown": "non-idempotent-write"}),
            CARDINAL)

    def test_an_invented_never_graded_down_id_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            m = full_matrix("D")
            for c in m:
                if c["gate"] == 6:
                    c["neverGradedDown"] = "whatever-i-decide"
            errs = validate_verdict(certify(t, objects=["D"], matrix=m), t)
            self.assertTrue(any("neverGradedDown" in e for e in errs), errs)

    def test_the_document_and_the_constants_name_the_same_classes(self):
        # The doctrine is readable without MCP and the code is what runs;
        # a second copy that drifts is worse than either.
        with open(GATES_DOC, encoding="utf-8") as f:
            doc = f.read()
        # Named one by one rather than asserting over the whole document: a
        # failure here should say which class is missing, not print 20 KB.
        missing = [k for k in (CARDINAL, RECOMMENDED, CONTEXTUAL) if k not in doc]
        self.assertEqual(missing, [], "10-quality-gates.md names no %s"
                         % ", ".join(missing))
        for gate, klass in sorted(CLASS_BY_GATE.items()):
            row = re.search(r"^\|\s*%d\s*\..*$" % gate, doc, re.M)
            self.assertIsNotNone(row, "gate %d has no row in the class table" % gate)
            self.assertIn(klass, row.group(0),
                          "gate %d is %s in the code and the document disagrees"
                          % (gate, klass))

    def test_the_three_never_graded_down_are_in_the_document(self):
        with open(os.path.join(PLUGIN_ROOT, "skills", "appian-best-practices",
                               "SKILL.md"), encoding="utf-8") as f:
            skill = f.read()
        for phrase in ("invalid reference", "authorization gap",
                       "non-idempotent write"):
            self.assertIn(phrase, skill)
        self.assertEqual(len(NEVER_GRADED_DOWN), 3)


class TestTheReissueCapIsEnforcement(unittest.TestCase):
    """§ 9.4: the one anti-waste magnitude that goes from auditable to
    impossible. A comparison of sets over files on disk, not a declaration."""

    def _emit(self, root, number, finding_ids):
        return certify(root, name="practices-certify.%03d.json" % number,
                       findings=[{"id": i, "criterion": "c", "verdict": "FAIL",
                                  "evidence": "e"} for i in finding_ids])

    def test_a_third_verdict_with_no_new_finding_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self._emit(t, 1, ["f-1"])
            self._emit(t, 2, ["f-1", "f-2"])
            third = self._emit(t, 3, ["f-1", "f-2"])
            errs = validate_verdict(third, t)
            self.assertTrue(any("raises no finding" in e for e in errs), errs)

    def test_a_third_verdict_that_raises_something_new_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self._emit(t, 1, ["f-1"])
            self._emit(t, 2, ["f-2"])
            third = self._emit(t, 3, ["f-1", "f-3"])
            self.assertEqual([e for e in validate_verdict(third, t)
                              if "raises no finding" in e], [])

    def test_the_second_verdict_is_never_refused_by_the_cap(self):
        # Two emissions is one remediation cycle, which the norm allows.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self._emit(t, 1, ["f-1"])
            second = self._emit(t, 2, ["f-1"])
            self.assertEqual([e for e in validate_verdict(second, t)
                              if "raises no finding" in e], [])

    def test_a_fourth_verdict_is_held_to_the_same_rule(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for n in (1, 2, 3):
                self._emit(t, n, ["f-1"])
            fourth = self._emit(t, 4, ["f-1"])
            self.assertTrue(any("raises no finding" in e
                                for e in validate_verdict(fourth, t)))

    def test_an_unversioned_verdict_is_not_compared(self):
        # A fixed name has no corpus: the second emission overwrote the
        # first, so there is nothing on disk to compare against.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self.assertEqual(validate_verdict(certify(t), t), [])

    def test_the_comparison_reads_files_not_declarations(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self._emit(t, 1, ["f-1"])
            self._emit(t, 2, ["f-1"])
            self.assertEqual(len(earlier_versions(
                os.path.join(t, "practices-certify.003.json"))), 2)
            # Deleting one changes the answer, because the answer is the disk.
            os.remove(os.path.join(t, "practices-certify.002.json"))
            self.assertEqual(len(earlier_versions(
                os.path.join(t, "practices-certify.003.json"))), 1)

    def test_versions_of_one_phase_do_not_count_for_another(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for n in (1, 2):
                certify(t, name="practices-risk.%03d.json" % n)
            self.assertEqual(earlier_versions(
                os.path.join(t, "practices-certify.003.json")), [])


class TestFindingIdsMakeTheCapPossible(unittest.TestCase):
    def test_a_v07_finding_without_an_id_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            path = certify(t, findings=[{"criterion": "c", "verdict": "FAIL",
                                         "evidence": "e"}])
            errs = validate_verdict(path, t)
            self.assertTrue(any("needs a non-empty 'id'" in e for e in errs), errs)

    def test_two_findings_may_not_share_an_id(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            path = certify(t, findings=[
                {"id": "f-1", "criterion": "a", "verdict": "FAIL", "evidence": "e"},
                {"id": "f-1", "criterion": "b", "verdict": "FAIL", "evidence": "e"}])
            errs = validate_verdict(path, t)
            self.assertTrue(any("reuses finding id" in e for e in errs), errs)

    def test_a_legacy_phase_owes_no_ids(self):
        # § 15: a 0.6 verdict stays valid, or a scope opened under the old
        # rules cannot close by any route.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            path = os.path.join(t, "v.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"task": "T", "phase": "review", "verdict": "PASS",
                           "referencesApplied": [REF],
                           "findings": [{"criterion": "c", "verdict": "PASS",
                                         "evidence": "e"}]}, f)
            self.assertEqual(validate_verdict(path, t), [])


class TestTheClosedListLivesOutsideTheAgent(unittest.TestCase):
    """§ 9.5: two classes that do not mix, because they lead to different
    terminal states."""

    def _requires_human(self, root, criterion, phase="certify", **over):
        v = {"task": "T", "instanceId": "inst-1", "phase": phase,
             "verdict": "NOT_MEASURED", "notMeasuredClass": "REQUIRES_HUMAN",
             "owner": "the scope's owner",
             "closingCondition": "a person looks at the screen",
             "deferredCriterion": criterion,
             "referencesApplied": [REF], "findings": [],
             "objects": ["D"], "matrix": full_matrix("D")}
        # A NOT_MEASURED header needs a cell to derive from.
        for c in v["matrix"]:
            if c["gate"] == 4:
                c.update({"verdict": "NOT_MEASURED", "evidence": "e",
                          "impact": "i", "remedy": "r", "reference": REF})
        v.update(over)
        path = os.path.join(root, "v.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(v, f)
        return path

    def test_a_pending_judgement_id_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for criterion in PENDING_JUDGEMENT_IDS:
                self.assertEqual(
                    validate_verdict(self._requires_human(t, criterion), t),
                    [], criterion)

    def test_a_residue_id_used_as_a_deferral_is_refused_with_the_remedy(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for criterion in GUARANTEE_RESIDUE_IDS:
                errs = validate_verdict(self._requires_human(t, criterion), t)
                self.assertTrue(any("deferred-debt.jsonl" in e for e in errs),
                                (criterion, errs))
                self.assertTrue(any("Nothing failed" in e for e in errs),
                                (criterion, errs))

    def test_an_invented_id_is_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(self._requires_human(t, "i-decided-this"), t)
            self.assertTrue(any("not on the closed list" in e for e in errs), errs)

    def test_a_visual_judgement_is_not_valid_in_design(self):
        # design is meant to precede every write: there is no rendered
        # screen to judge yet.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(
                self._requires_human(t, "visual-judgement-on-rendered-screen",
                                     phase="design", objects=None, matrix=None), t)
            self.assertTrue(any("not valid in phase 'design'" in e for e in errs), errs)

    def test_an_instrument_limit_is_valid_in_design(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(
                self._requires_human(t, "instrument-limit-known", phase="design",
                                     objects=None, matrix=None), t)
            self.assertEqual(errs, [])

    def test_an_ownerless_deferral_is_rejected_not_rewritten(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(
                self._requires_human(t, PENDING_JUDGEMENT_IDS[0], owner=None), t)
            self.assertTrue(any("needs an 'owner'" in e for e in errs), errs)

    def test_a_deferral_without_a_closing_condition_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            errs = validate_verdict(
                self._requires_human(t, PENDING_JUDGEMENT_IDS[0],
                                     closingCondition=None), t)
            self.assertTrue(any("'closingCondition'" in e for e in errs), errs)

    def test_the_two_classes_share_no_id(self):
        self.assertEqual(set(PENDING_JUDGEMENT_IDS) & set(GUARANTEE_RESIDUE_IDS),
                         set())

    def test_the_document_names_both_lists_and_neither_drifts(self):
        # Same drift detector the 0.6 deferrable list already has: the
        # constants are the original and the document is the readable copy.
        with open(GATES_DOC, encoding="utf-8") as f:
            doc = f.read()
        for name in PENDING_JUDGEMENT_IDS + GUARANTEE_RESIDUE_IDS:
            self.assertIn("`%s`" % name, doc,
                          "%r is in the code and in no document" % name)
        # And nothing the document invents beyond them, inside that section.
        section = doc.split("What a NOT MEASURED means when a person still has to look", 1)[1]
        section = section.split("## The seven gates", 1)[0]
        named = set(re.findall(r"`([a-z][a-z0-9-]{6,})`", section))
        self.assertEqual(named - set(PENDING_JUDGEMENT_IDS)
                         - set(GUARANTEE_RESIDUE_IDS) - {"deferred-debt.jsonl"},
                         set())


class TestTheV07PhasesAndTheLegacyOnes(unittest.TestCase):
    def test_the_three_v07_phases_are_the_ones_the_norm_names(self):
        self.assertEqual(PHASES_V07, ("design", "certify", "risk"))

    def test_the_legacy_phases_survive_for_migration(self):
        self.assertEqual(sorted(PHASES_LEGACY),
                         ["implementation", "qa", "review"])

    def test_a_phase_outside_both_sets_is_still_refused(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            path = os.path.join(t, "v.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"task": "T", "phase": "verify", "verdict": "PASS",
                           "referencesApplied": [REF], "findings": []}, f)
            errs = validate_verdict(path, t)
            self.assertTrue(any("'phase' is 'verify'" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
