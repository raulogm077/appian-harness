import json, os, re, tempfile, unittest
from validate_verdict import DEFERRABLE_CRITERIA, validate_verdict

PLUGIN_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GATES_DOC = os.path.join(PLUGIN_ROOT, "skills", "appian-best-practices", "references",
                         "10-quality-gates.md")

REFDIR = os.path.join("skills", "appian-best-practices", "references")

def make_plugin(root):
    d = os.path.join(root, REFDIR)
    os.makedirs(d)
    with open(os.path.join(d, "06-security.md"), "w", encoding="utf-8") as f:
        f.write("# Security\n\n## Record level security\nBody.\n\n## Field level security\nBody.\n")
    return root

def write_verdict(root, **over):
    v = {
        "task": "T-1",
        "phase": "implementation",
        "verdict": "PASS",
        "referencesApplied": ["06-security.md#record-level-security"],
        "findings": [],
    }
    v.update(over)
    p = os.path.join(root, "verdict.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(v, f)
    return p

class TestValidateVerdict(unittest.TestCase):
    def test_valid_verdict_has_no_errors(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self.assertEqual(validate_verdict(write_verdict(t), t), [])

    def test_unknown_reference_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, referencesApplied=["99-invented.md#whatever"])
            self.assertTrue(any("99-invented.md" in e for e in validate_verdict(p, t)))

    def test_unknown_anchor_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, referencesApplied=["06-security.md#no-such-heading"])
            self.assertTrue(any("anchor" in e for e in validate_verdict(p, t)))

    def test_empty_references_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, referencesApplied=[])
            self.assertTrue(any("referencesApplied" in e for e in validate_verdict(p, t)))

    def test_fourth_verdict_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, verdict="N/A")
            self.assertTrue(any("verdict" in e for e in validate_verdict(p, t)))

    def test_not_measured_needs_a_class(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, verdict="NOT_MEASURED")
            self.assertTrue(any("notMeasuredClass" in e for e in validate_verdict(p, t)))

    def test_deferred_without_owner_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, verdict="NOT_MEASURED", notMeasuredClass="DEFERRED")
            self.assertTrue(any("owner" in e for e in validate_verdict(p, t)))

    def test_deferred_with_owner_and_condition_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, verdict="NOT_MEASURED", notMeasuredClass="DEFERRED",
                              owner="a person", closingCondition="when the site ships",
                              deferredCriterion=DEFERRABLE_CRITERIA[0])
            self.assertEqual(validate_verdict(p, t), [])

    def test_unknown_phase_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, phase="whatever")
            self.assertTrue(any("phase" in e for e in validate_verdict(p, t)))

    def test_malformed_json_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = os.path.join(t, "verdict.json")
            open(p, "w", encoding="utf-8").write("{not json")
            self.assertTrue(any("parse" in e.lower() for e in validate_verdict(p, t)))


class TestVerdictAgreesWithWhereItWasFound(unittest.TestCase):
    """A verdict is a claim about one task and one phase. Checking only that
    `phase` is *one of* four values lets a single audit be copied into all
    four filenames, which is indistinguishable from four independent ones --
    and that makes the four-phase guarantee decorative. So the caller says
    what it is opening, and the document has to agree with it."""

    def test_verdict_for_another_task_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, task="TASK-999")
            errs = validate_verdict(p, t, expected_task="TASK-3", expected_phase="implementation")
            self.assertTrue(any("TASK-999" in e and "TASK-3" in e for e in errs))

    def test_verdict_for_another_phase_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, phase="qa")
            errs = validate_verdict(p, t, expected_task="T-1", expected_phase="design")
            self.assertTrue(any("qa" in e and "design" in e for e in errs))

    def test_agreeing_verdict_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, task="TASK-3", phase="review")
            self.assertEqual(
                validate_verdict(p, t, expected_task="TASK-3", expected_phase="review"), [])

    def test_expectations_are_optional_so_the_cli_still_works_standalone(self):
        # `validate_verdict.py VERDICT PLUGIN_ROOT` is what the auditor runs
        # on itself, before it knows which gate will open the file.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            self.assertEqual(validate_verdict(write_verdict(t), t), [])

    def test_a_phase_outside_the_four_is_still_rejected_without_expectations(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, phase="whatever")
            self.assertTrue(any("phase" in e for e in validate_verdict(p, t)))


class TestDeferralNamesACriterion(unittest.TestCase):
    """The document calls the deferrable list closed and says an agent
    "cannot declare a criterion deferrable in order to unblock itself".
    While the schema had no field naming *which* criterion was deferred,
    that was unenforceable by construction: DEFERRED was an unconditional
    unlock and `owner: "me" / closingCondition: "eventually"` opened a gate.
    """

    def _deferred(self, root, **over):
        base = dict(verdict="NOT_MEASURED", notMeasuredClass="DEFERRED",
                    owner="the accessibility lead",
                    closingCondition="before the site is released",
                    deferredCriterion=DEFERRABLE_CRITERIA[0])
        base.update(over)
        return write_verdict(root, **base)

    def test_deferral_without_a_named_criterion_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._deferred(t, deferredCriterion=None)
            self.assertTrue(any("deferredCriterion" in e for e in validate_verdict(p, t)))

    def test_criterion_outside_the_closed_list_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._deferred(t, deferredCriterion="the-bit-i-did-not-do")
            errs = validate_verdict(p, t)
            self.assertTrue(any("the-bit-i-did-not-do" in e for e in errs))

    def test_every_listed_criterion_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for criterion in DEFERRABLE_CRITERIA:
                self.assertEqual(validate_verdict(self._deferred(t, deferredCriterion=criterion), t),
                                 [], criterion)

    def test_a_blocking_verdict_needs_no_criterion(self):
        # BLOCKING is not a deferral and names nothing: it is the harness
        # saying it could have measured this and did not.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, verdict="NOT_MEASURED", notMeasuredClass="BLOCKING")
            self.assertEqual(validate_verdict(p, t), [])

    def test_a_deferral_without_an_owner_is_rejected_not_degraded(self):
        # The document used to say an ownerless deferral "degrades to
        # blocking". Nothing degraded it; it was refused. The message must
        # describe what the code does.
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._deferred(t, owner=None)
            errs = validate_verdict(p, t)
            self.assertTrue(any("owner" in e for e in errs))
            self.assertFalse(any("degrade" in e.lower() for e in errs))


class TestTheClosedListLivesInOnePlace(unittest.TestCase):
    """A list hand-copied into three files is the shape of defect this
    plugin keeps finding in itself. The constant is the source of truth and
    the document points at it; this is the drift detector that makes that
    claim mean something."""

    @staticmethod
    def ids_in_the_document():
        with open(GATES_DOC, encoding="utf-8") as f:
            lines = f.read().splitlines()
        start = next(i for i, l in enumerate(lines) if "Only these criteria may be deferred" in l)
        ids = []
        for line in lines[start + 1:]:
            m = re.match(r"^-\s+`([a-z0-9-]+)`", line)
            if m:
                ids.append(m.group(1))
            elif ids and line.strip():
                break
        return ids

    def test_the_document_and_the_constant_name_the_same_criteria(self):
        self.assertEqual(self.ids_in_the_document(), list(DEFERRABLE_CRITERIA))

    def test_the_document_actually_lists_something(self):
        # A parser that silently finds nothing would make the test above
        # pass against an empty constant.
        self.assertTrue(self.ids_in_the_document())


class TestFindingsAreNotAFreeTextHatch(unittest.TestCase):
    """`findings[]` went entirely unvalidated, so the per-gate "N/A: didn't
    get to it" the three-outcomes section exists to close survived inside
    it. N/A is legal at finding level -- unlike at verdict level -- but the
    document requires a justification about the OBJECT, never about the
    process, the schedule or the time available."""

    def _with_finding(self, root, finding):
        return write_verdict(root, findings=[finding])

    def test_na_justified_by_the_object_is_accepted(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._with_finding(t, {
                "criterion": "field-level security",
                "verdict": "N/A",
                "evidence": "the record type exposes no field carrying protected data",
                "reference": "06-security.md#record-level-security"})
            self.assertEqual(validate_verdict(p, t), [])

    def test_na_justified_by_the_process_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            for excuse in ("N/A: didn't get to it",
                           "no time left in the sprint",
                           "will check after the deadline",
                           "skipped for now"):
                p = self._with_finding(t, {
                    "criterion": "field-level security",
                    "verdict": "N/A",
                    "evidence": excuse,
                    "reference": "06-security.md#record-level-security"})
                self.assertTrue(any("N/A" in e for e in validate_verdict(p, t)), excuse)

    def test_bare_na_is_not_a_justification(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._with_finding(t, {"criterion": "field-level security",
                                       "verdict": "N/A", "evidence": "N/A"})
            self.assertTrue(any("N/A" in e for e in validate_verdict(p, t)))

    def test_a_finding_needs_a_criterion_and_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._with_finding(t, {"verdict": "PASS"})
            errs = validate_verdict(p, t)
            self.assertTrue(any("criterion" in e for e in errs))
            self.assertTrue(any("evidence" in e for e in errs))

    def test_a_finding_verdict_outside_the_four_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = self._with_finding(t, {"criterion": "c", "verdict": "probably fine",
                                       "evidence": "looked at the source"})
            self.assertTrue(any("probably fine" in e for e in validate_verdict(p, t)))

    def test_findings_must_be_a_list(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, findings={"criterion": "c"})
            self.assertTrue(any("findings" in e for e in validate_verdict(p, t)))


class TestCaseSensitiveLookup(unittest.TestCase):
    """The documentation says a citation names a file in references/. On a
    case-insensitive filesystem `06-SECURITY.md` resolves and on a
    case-sensitive one it does not, so the same verdict passes on a laptop
    and fails in CI. Match the documentation everywhere."""

    def test_reference_file_with_the_wrong_case_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            make_plugin(t)
            p = write_verdict(t, referencesApplied=["06-SECURITY.md#record-level-security"])
            self.assertTrue(any("06-SECURITY.md" in e for e in validate_verdict(p, t)))

if __name__ == "__main__":
    unittest.main()
