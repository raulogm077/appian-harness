"""One assignment, or the constant is not shared -- it is merely agreed with.

`assertEqual(module.EXIT_NOT_MEASURED, 3)` over six modules passes just as
happily when all six type the number out themselves. So the assertion that
carries the weight here is about the source text rather than the imported
value: exactly one file in the tree assigns the number, the rest import it.
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exit_codes  # noqa: E402

REAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The assignment, not the import. `from exit_codes import EXIT_NOT_MEASURED`
# has the name on the wrong side of the `=` and does not match; a re-typed
# `EXIT_NOT_MEASURED = 3` does. Indentation is allowed for so a copy hidden
# inside a function or a class body is not a way through.
ASSIGNMENT = re.compile(r"^[ \t]*EXIT_NOT_MEASURED\s*=\s*[0-9]", re.M)

# Every module that reports the third outcome. Written out rather than
# discovered, for the reason check_package_integrity gives about
# REQUIRED_AT_RUNTIME: a stale entry here fails loudly on the next run, while
# a discovery rule that quietly matched nothing would pass over a checker that
# had dropped the name entirely.
#
# lint_agents is on the list although it assigns nothing -- it takes
# `EXIT_NOT_MEASURED` from lint_skills, which re-exports it from here, and
# that two-step is precisely the thing worth holding to an assertion.
REPORTERS = (
    "lint_skills",
    "lint_agents",
    "n2_interface_tree",
    "n3_process_layout",
    "check_evals",
    "check_manifest_agreement",
    "check_package_integrity",
)


def python_sources(root):
    """(path relative to root, text) for every .py in the tree.

    Read inside a `with` rather than in the comprehension that consumes this,
    which is not fussiness: an unclosed handle per file turns a green run into
    a page of ResourceWarnings, and a CI log people learn to scroll past is
    the same protection-that-is-not-read this plugin argues about elsewhere.
    """
    for parent, subdirs, entries in os.walk(root):
        subdirs[:] = [d for d in subdirs if d not in ("__pycache__", ".git")]
        for entry in sorted(entries):
            if not entry.endswith(".py"):
                continue
            path = os.path.join(parent, entry)
            with open(path, encoding="utf-8") as f:
                yield os.path.relpath(path, root).replace(os.sep, "/"), f.read()


class TheConstant(unittest.TestCase):
    def test_the_value_is_the_one_the_documentation_states(self):
        # The literal is spelled out here on purpose, and it is the only place
        # in the tests it appears. CONTRIBUTING.md says `EXIT_NOT_MEASURED = 3`
        # and the README twice states the 0/1/2/3 scale; prose is not
        # importable, so nothing else in this repository can notice the day the
        # constant and the sentences describing it stop agreeing.
        self.assertEqual(exit_codes.EXIT_NOT_MEASURED, 3)

    def test_exactly_one_file_assigns_it(self):
        # Six files each typing `EXIT_NOT_MEASURED = 3` all agree, every test
        # is green, and one of them changing its mind stays green -- the same
        # shape as the matcher written three times that
        # hooks/test_matcher_parity.py exists to catch.
        assigning = sorted(relative for relative, text in python_sources(REAL_ROOT)
                           if ASSIGNMENT.search(text))
        self.assertEqual(assigning, ["scripts/exit_codes.py"], assigning)

    def test_every_checker_that_reports_it_gets_it_from_here(self):
        # Guards the re-export as much as the value: lint_agents imports the
        # name from lint_skills, so lint_skills dropping it in favour of a
        # bare `exit_codes.EXIT_NOT_MEASURED` at each use site would break a
        # second linter without touching its file.
        for name in REPORTERS:
            module = __import__(name)
            self.assertTrue(hasattr(module, "EXIT_NOT_MEASURED"),
                            "%s no longer exposes EXIT_NOT_MEASURED" % name)
            self.assertEqual(module.EXIT_NOT_MEASURED,
                             exit_codes.EXIT_NOT_MEASURED, name)


if __name__ == "__main__":
    unittest.main()
