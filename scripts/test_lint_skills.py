import io, os, tempfile, unittest
from contextlib import redirect_stdout
from lint_skills import lint_skill, main

VALID_BODY = """
## Overview
Body.

## When to Use
Body.

## Common Rationalizations
Body.

## Red Flags
Body.

## Verification
Body.
"""

def write(dirpath, name, description, body=VALID_BODY):
    d = os.path.join(dirpath, name)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "SKILL.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\nname: %s\ndescription: %s\n---\n%s" % (name, description, body))
    return p

class TestLintSkill(unittest.TestCase):
    def test_valid_skill_has_no_errors(self):
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Implements one approved task. Use when building an Appian object.")
            self.assertEqual(lint_skill(p), [])

    def test_name_must_match_directory(self):
        with tempfile.TemporaryDirectory() as t:
            d = os.path.join(t, "appian-build"); os.makedirs(d)
            p = os.path.join(d, "SKILL.md")
            open(p, "w", encoding="utf-8").write(
                "---\nname: something-else\ndescription: Use when building.\n---\n" + VALID_BODY)
            self.assertTrue(any("name" in e for e in lint_skill(p)))

    def test_description_over_1024_chars_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Use when building. " + ("x" * 1100))
            self.assertTrue(any("1024" in e for e in lint_skill(p)))

    def test_description_without_trigger_fails(self):
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Best practices for Appian development.")
            self.assertTrue(any("trigger" in e for e in lint_skill(p)))

    def test_negated_trigger_does_not_count(self):
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Do not use when the change is cosmetic.")
            self.assertTrue(any("trigger" in e for e in lint_skill(p)))

    def test_missing_required_section_fails(self):
        body = VALID_BODY.replace("## Red Flags", "## Something Else")
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Use when building.", body)
            self.assertTrue(any("Red Flags" in e for e in lint_skill(p)))

    def test_exempt_skill_skips_section_check(self):
        body = "## Overview\nOnly this.\n"
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "using-appian-harness", "Use when starting work on an Appian project.", body)
            self.assertEqual(lint_skill(p), [])

    def test_negated_trigger_not_for_use_phrasing_fails(self):
        # "Not for use when..." puts a word between the negation and "use",
        # so it must be caught the same way "Do not use when..." is.
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Not for use when the file is a draft.")
            self.assertTrue(any("trigger" in e for e in lint_skill(p)))

    def test_incidental_negation_after_trigger_still_passes(self):
        # The negation here modifies the trigger's condition, not the trigger
        # phrase itself, and it comes after "use when" — must not be flagged.
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Use when the record type is not synced.")
            self.assertEqual(lint_skill(p), [])

    def test_negation_in_separate_sentence_still_passes(self):
        # A negation earlier in the description, but in its own sentence
        # (separated by a period) from the real trigger, must not be flagged.
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Not applicable to legacy skills. Use when onboarding a new client.")
            self.assertEqual(lint_skill(p), [])

    def test_negation_in_exclamatory_sentence_still_passes(self):
        # Same as above, but the sentence boundary is "!" rather than ".".
        with tempfile.TemporaryDirectory() as t:
            p = write(t, "appian-build", "Not for drafts! Use when publishing.")
            self.assertEqual(lint_skill(p), [])


class TestMainSkillCount(unittest.TestCase):
    def test_empty_skills_dir_is_not_measured_not_pass(self):
        # skills/ exists but has no SKILL.md files: zero validated must not
        # be reported as a pass.
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "skills"))
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main(t)
            self.assertNotEqual(rc, 0)
            self.assertIn("NOT MEASURED", out.getvalue())
            self.assertNotIn("All skills passed", out.getvalue())

    def test_passing_skills_report_count_not_blanket_claim(self):
        with tempfile.TemporaryDirectory() as t:
            write(os.path.join(t, "skills"), "appian-build", "Use when building an Appian object.")
            out = io.StringIO()
            with redirect_stdout(out):
                rc = main(t)
            self.assertEqual(rc, 0)
            self.assertIn("1 skill(s) passed.", out.getvalue())
            self.assertNotIn("All skills passed", out.getvalue())

if __name__ == "__main__":
    unittest.main()
