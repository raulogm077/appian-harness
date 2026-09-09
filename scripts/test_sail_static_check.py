"""The static SAIL checker: what it can decide from the official sources,
and -- the half that matters more -- what it refuses to claim.

No PASS may be obtained by absence of measurement. A category this checker
cannot decide is reported NOT MEASURED on every run, and a run with the
official skill absent measures nothing at all rather than coming back clean.
"""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import sail_static_check as ssc

# A miniature of the official sources, in their real shape: the headings and
# the backticked-bullet form this checker parses.
FUNCTION_REFERENCE = """# Appian Function Reference

## Critical Validation Rule

### Functions That DO NOT Exist

- `regexmatch()`, `regex()` - SAIL has no regex support; use `split()`
- `a!dateTimeValue()` - Use `dateTime()` instead

### Functions That Exist But Should NOT Be Used

- `apply()` - Always use `a!forEach()` instead
- `isnull()` - Use `a!isNullOrEmpty()` instead

### Functions to Use with Caution

- `now()`, `today()` - Non-deterministic. Safe for audit fields.

## Complete Function Reference

- `a!localVariables()` - Declares local variables
- `a!forEach()` - Iterates
"""

COMPONENT_REFERENCE = """# SAIL Component Reference

## Critical Validation Rule

### Components That DO NOT Exist

- `a!richTextEditor` - NO rich text editor exists. Use `a!paragraphField`
"""

REGISTRY = {"a!formLayout": {"exists": True}, "a!textField": {"exists": True},
            "a!paragraphField": {"exists": True}}


def make_skill(root, functions=FUNCTION_REFERENCE, components=COMPONENT_REFERENCE,
               registry=REGISTRY):
    skill = os.path.join(root, "skills", "appian")
    os.makedirs(os.path.join(skill, "references"), exist_ok=True)
    os.makedirs(os.path.join(skill, "registry"), exist_ok=True)
    with open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write("# Appian\n\n**Appian Version:** 26.8\n")
    if functions is not None:
        with open(os.path.join(skill, ssc.FUNCTION_REFERENCE), "w",
                  encoding="utf-8") as f:
            f.write(functions)
    if components is not None:
        with open(os.path.join(skill, ssc.COMPONENT_REFERENCE), "w",
                  encoding="utf-8") as f:
            f.write(components)
    if registry is not None:
        with open(os.path.join(skill, ssc.COMPONENT_REGISTRY), "w",
                  encoding="utf-8") as f:
            json.dump(registry, f)
    return skill


class TestTheRulesComeFromTheOfficialSource(unittest.TestCase):
    """They are not restated in this repository: they change with every
    Appian release, and a copy drifts silently."""

    def test_the_negative_lists_are_read_from_the_reference_files(self):
        with tempfile.TemporaryDirectory() as root:
            rules = ssc.load_rules(make_skill(root))
            self.assertEqual(rules["banned"],
                             {"regexmatch", "regex", "a!dateTimeValue"})
            self.assertEqual(rules["discouraged"], {"apply", "isnull"})
            self.assertEqual(rules["bannedComponents"], {"a!richTextEditor"})

    def test_the_use_with_caution_list_is_not_treated_as_a_rule(self):
        # `now()` and `today()` are context-dependent advice, not a rule a
        # static checker can apply. Flagging them would be crying wolf, and
        # a checker that cries wolf gets switched off.
        with tempfile.TemporaryDirectory() as root:
            rules = ssc.load_rules(make_skill(root))
            self.assertNotIn("now", rules["discouraged"])
            self.assertNotIn("today", rules["discouraged"])

    def test_a_source_that_grows_a_rule_is_picked_up_without_a_code_change(self):
        extended = FUNCTION_REFERENCE.replace(
            "- `a!dateTimeValue()` - Use `dateTime()` instead",
            "- `a!dateTimeValue()` - Use `dateTime()` instead\n"
            "- `a!brandNewMistake()` - Added by a later release")
        with tempfile.TemporaryDirectory() as root:
            rules = ssc.load_rules(make_skill(root, functions=extended))
            self.assertIn("a!brandNewMistake", rules["banned"])


class TestWhatItDecides(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.rules = ssc.load_rules(make_skill(self._tmp.name))

    def categories(self, source):
        findings, _ = ssc.check_source(source, self.rules)
        return [f["category"] for f in findings]

    def test_a_function_that_does_not_exist_is_caught(self):
        self.assertIn("banned-function",
                      self.categories('regexmatch("a", "b")'))

    def test_a_discouraged_function_is_caught_and_named_differently(self):
        self.assertIn("discouraged-function", self.categories("isnull(x)"))

    def test_a_component_that_does_not_exist_is_caught(self):
        self.assertIn("banned-component",
                      self.categories('a!richTextEditor(value: "x")'))

    def test_a_literal_uuid_is_caught(self):
        self.assertIn("literal-uuid", self.categories(
            'a!textField(value: "e8f2b1a0-1234-4abc-9def-0123456789ab")'))

    def test_a_symbol_in_no_source_is_reported_as_unverified(self):
        cats = self.categories('a!fancyWidget(label: "x")')
        self.assertIn("unknown-symbol", cats)

    def test_a_real_function_absent_from_the_registry_is_not_flagged(self):
        # `a!forEach` is a function, so it is not in the component registry.
        # Reporting it would make the checker useless on every real screen.
        self.assertEqual(self.categories(
            'a!localVariables(local!x: 1, a!forEach(items: {1}, '
            'expression: a!textField(label: "x")))'), [])

    def test_a_name_inside_a_string_is_not_a_call(self):
        self.assertEqual(self.categories('a!textField(label: "regexmatch(")'), [])

    def test_a_name_inside_a_comment_is_not_a_call(self):
        self.assertEqual(self.categories('/* do not use regexmatch() */ '
                                         'a!textField(label: "x")'), [])

    def test_findings_carry_the_line_they_are_on(self):
        findings, _ = ssc.check_source('a!textField(label: "x")\n'
                                       'regexmatch("a", "b")', self.rules)
        self.assertEqual(findings[0]["line"], 2)


class TestNoPassByAbsenceOfMeasurement(unittest.TestCase):
    """The half that matters more. A category this checker cannot decide is
    NOT MEASURED on every run, and it says so."""

    def test_the_undecidable_categories_are_always_not_measured(self):
        with tempfile.TemporaryDirectory() as root:
            rules = ssc.load_rules(make_skill(root))
            _findings, measured = ssc.check_source('a!textField(label: "x")',
                                                   rules)
            table = dict((name, status)
                         for name, status, _why in ssc.coverage_table(measured,
                                                                      rules))
            for category in ("null-safety", "performance", "accessibility",
                             "naming"):
                self.assertEqual(table[category], "NOT MEASURED", category)

    def test_every_category_has_a_reason_written_down(self):
        # A gap that is written down is a gap somebody can close; a silent
        # gap reads as a pass.
        with tempfile.TemporaryDirectory() as root:
            rules = ssc.load_rules(make_skill(root))
            _f, measured = ssc.check_source("", rules)
            for _name, _status, why in ssc.coverage_table(measured, rules):
                self.assertTrue(why and len(why) > 20)

    def test_a_missing_source_turns_its_category_not_measured(self):
        with tempfile.TemporaryDirectory() as root:
            rules = ssc.load_rules(make_skill(root, components=None))
            _f, measured = ssc.check_source('a!richTextEditor()', rules)
            table = dict((n, s) for n, s, _ in ssc.coverage_table(measured, rules))
            self.assertEqual(table["banned-component"], "NOT MEASURED")
            self.assertEqual(table["banned-function"], "MEASURED")

    def test_without_the_official_skill_nothing_rule_based_is_measured(self):
        rules = ssc.load_rules(None)
        _f, measured = ssc.check_source('regexmatch("a")', rules)
        self.assertEqual(measured, {"literal-uuid"})
        table = dict((n, s) for n, s, _ in ssc.coverage_table(measured, rules))
        self.assertEqual(table["banned-function"], "NOT MEASURED")


class TestCLI(unittest.TestCase):

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = ssc.main(["sail_static_check.py"] + args)
        return code, out.getvalue(), err.getvalue()

    def source_file(self, root, text):
        p = os.path.join(root, "expr.sail")
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_a_clean_expression_exits_zero_and_prints_the_table(self):
        with tempfile.TemporaryDirectory() as root:
            skill = make_skill(root)
            p = self.source_file(root, 'a!textField(label: "x")')
            code, out, _ = self.run_main([p, "--skill-root", skill])
            self.assertEqual(code, 0)
            self.assertIn("Coverage by category", out)
            self.assertIn("NOT MEASURED", out)   # the undecidable ones
            self.assertIn("OK", out)

    def test_findings_exit_one_and_are_printed_with_their_category(self):
        with tempfile.TemporaryDirectory() as root:
            skill = make_skill(root)
            p = self.source_file(root, 'regexmatch("a", "b")')
            code, out, _ = self.run_main([p, "--skill-root", skill])
            self.assertEqual(code, 1)
            self.assertIn("banned-function", out)

    def test_the_json_shape_carries_findings_and_coverage(self):
        with tempfile.TemporaryDirectory() as root:
            skill = make_skill(root)
            p = self.source_file(root, 'isnull(x)')
            _code, out, _ = self.run_main([p, "--skill-root", skill, "--json"])
            payload = json.loads(out)
            self.assertEqual(payload["findings"][0]["category"],
                             "discouraged-function")
            self.assertEqual(len(payload["coverage"]), len(ssc.CATEGORIES))

    def test_no_argument_is_a_usage_error_on_stderr(self):
        code, _out, err = self.run_main([])
        self.assertEqual(code, 2)
        self.assertIn("usage", err)

    def test_an_unreadable_source_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as root:
            code, out, _ = self.run_main([os.path.join(root, "nope.sail")])
            self.assertEqual(code, 1)
            self.assertIn("ERROR", out)

    def test_a_skill_root_that_is_not_a_skill_says_so(self):
        with tempfile.TemporaryDirectory() as root:
            p = self.source_file(root, 'a!textField(label: "x")')
            _code, out, _ = self.run_main([p, "--skill-root",
                                           os.path.join(root, "absent")])
            self.assertIn("official Appian skill was not found", out)


class TestAgainstTheInstalledSkill(unittest.TestCase):
    """The parser has to survive the real file, not only the miniature: the
    official reference writes its bullets as `regexmatch()` -- parentheses
    INSIDE the backticks -- and a pattern that missed that came back with an
    empty rule set, which reads exactly like a clean run."""

    def setUp(self):
        self.root = ssc.find_skill_root()
        if not self.root:
            self.skipTest("the official Appian skill is not installed here")

    def test_the_real_reference_yields_a_non_empty_rule_set(self):
        rules = ssc.load_rules(self.root)
        self.assertTrue(rules["banned"], "no banned function was parsed")
        self.assertTrue(rules["discouraged"])
        self.assertTrue(rules["bannedComponents"])
        self.assertGreater(len(rules["knownComponents"]), 50)

    def test_a_realistic_screen_produces_no_false_positive(self):
        rules = ssc.load_rules(self.root)
        findings, _ = ssc.check_source(
            'a!localVariables(\n'
            '  local!rows: a!queryRecordType(recordType: recordType!Candidato,\n'
            '    fields: {}, pagingInfo: a!pagingInfo(1, 50)),\n'
            '  a!formLayout(titleBar: a!headerTemplateSimple(title: "Alta"),\n'
            '    contents: a!forEach(items: local!rows.data,\n'
            '      expression: a!textField(label: "Nombre", value: fv!item))))',
            rules)
        self.assertEqual(findings, [], findings)


if __name__ == "__main__":
    unittest.main()
