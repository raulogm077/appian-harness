import json, os, tempfile, unittest
from validate_verdict import validate_verdict

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
                              owner="a person", closingCondition="when the site ships")
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
