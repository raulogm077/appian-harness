import os, tempfile, unittest
from lint_skills import lint_skill

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

if __name__ == "__main__":
    unittest.main()
