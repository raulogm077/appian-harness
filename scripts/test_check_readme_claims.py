"""The checker that keeps the README honest has to be honest itself.

A checker that cannot fail is a checker nobody should trust, so these
mostly build small broken trees and confirm it says so.
"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_readme_claims import check, _as_int

REAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestNumberWords(unittest.TestCase):
    def test_words_and_digits_both_read(self):
        self.assertEqual(_as_int("six"), 6)
        self.assertEqual(_as_int("Six"), 6)
        self.assertEqual(_as_int("6"), 6)

    def test_a_non_number_reads_as_none_rather_than_crashing(self):
        self.assertIsNone(_as_int("several"))


@unittest.skipIf(os.environ.get("APPIAN_HARNESS_IN_README_CHECK") == "1",
                 "nested inside check() itself -- would recurse forever")
@unittest.skipIf(os.environ.get("APPIAN_HARNESS_SKIP_SLOW") == "1",
                 "APPIAN_HARNESS_SKIP_SLOW=1: spawns both suites. Unset before a release.")
class TestAgainstTheRealRepository(unittest.TestCase):
    """Runs both suites as subprocesses, so it costs ~40s and sits behind
    the same opt-out as the launcher tests. Same reasoning: default on, so
    it cannot rot; explicit to skip, so the edit-loop stays at a second."""

    def test_this_repository_agrees_with_its_own_readme(self):
        # The check that actually earns its keep. If this fails, the README
        # is making a claim the tree does not support.
        self.assertEqual(check(REAL_ROOT), [])


class TestItCanActuallyFail(unittest.TestCase):
    def _tree(self, root, readme):
        os.makedirs(os.path.join(root, "hooks"))
        os.makedirs(os.path.join(root, "skills", "a-skill"))
        with open(os.path.join(root, "hooks", "hooks.json"), "w", encoding="utf-8") as f:
            f.write('{"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}}')
        with open(os.path.join(root, "hooks", "harness_hooks.py"), "w", encoding="utf-8") as f:
            f.write('project_config.get("someKey", 1)\nX = "some-log.jsonl"\n')
        with open(os.path.join(root, "skills", "a-skill", "SKILL.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: a-skill\n---\n")
        with open(os.path.join(root, "README.md"), "w", encoding="utf-8") as f:
            f.write(readme)

    def test_a_wrong_hook_count_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring four hooks\nsomeKey a-skill some-log.jsonl\n")
            self.assertTrue(any("hook count" in f for f in check(t, count_tests=False)))

    def test_an_undocumented_config_key_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\na-skill some-log.jsonl\n")
            self.assertTrue(any("someKey" in f for f in check(t, count_tests=False)))

    def test_an_unmentioned_skill_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey some-log.jsonl\n")
            self.assertTrue(any("a-skill" in f for f in check(t, count_tests=False)))

    def test_an_undocumented_log_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill\n")
            self.assertTrue(any("some-log.jsonl" in f for f in check(t, count_tests=False)))

    def test_a_claim_deleted_from_the_readme_is_reported(self):
        # Silence must not read as agreement -- the same argument the
        # plugin makes about NOT MEASURED.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "someKey a-skill some-log.jsonl\n")
            self.assertTrue(any("no longer states this" in f for f in check(t, count_tests=False)))

    def test_a_missing_readme_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertTrue(check(t, count_tests=False))


if __name__ == "__main__":
    unittest.main()
