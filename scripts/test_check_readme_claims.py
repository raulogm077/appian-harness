"""The checker that keeps the README honest has to be honest itself.

A checker that cannot fail is a checker nobody should trust, so these
mostly build small broken trees and confirm it says so.
"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_readme_claims import check, _as_int, _markdown_files

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


def claims(modules=0, cases=0, routing=0, safety=0, agents=0, references=0, skills=1):
    """The counting sentences a fixture README states about its own tree.

    Defaulted to what the three-file tree below actually contains -- no
    scripts/, agents/, evals/ or references/, and the one skill `_tree`
    creates -- so a test that breaks one claim reports that one finding
    instead of seven, and each fixture stays as small as the thing its test
    is about. A test that needs a claim to be wrong passes the wrong number
    in rather than pasting a second contradicting sentence after it, which
    would fire the same check twice with different answers.
    """
    return ("%d modules, %d eval cases -- %d routing, %d safety, %d judging agents, "
            "%d domain references, %d skills\n"
            % (modules, cases, routing, safety, agents, references, skills))


class TreeFixture:
    """The three-file broken tree the failure tests are built on.

    A mixin rather than a base class with tests in it: several classes below
    need the same fixture and none of them needs to re-run another's cases.
    """

    def _tree(self, root, readme, counts=None):
        os.makedirs(os.path.join(root, "hooks"))
        os.makedirs(os.path.join(root, "skills", "a-skill"))
        with open(os.path.join(root, "hooks", "hooks.json"), "w", encoding="utf-8") as f:
            f.write('{"hooks": {"Stop": [{"hooks": [{"type": "command"}]}]}}')
        with open(os.path.join(root, "hooks", "harness_hooks.py"), "w", encoding="utf-8") as f:
            f.write('project_config.get("someKey", 1)\nX = "some-log.jsonl"\n')
        with open(os.path.join(root, "skills", "a-skill", "SKILL.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: a-skill\n---\n")
        self._write(root, "README.md", (claims() if counts is None else counts) + readme)

    def _write(self, root, relative, text):
        path = os.path.join(root, *relative.split("/"))
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


class TestItCanActuallyFail(TreeFixture, unittest.TestCase):
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


class TestAMissingFileIsAFindingAndNotATraceback(TreeFixture, unittest.TestCase):
    """A checker that raises has reported nothing.

    Whoever reads the CI log sees a stack trace out of `check_readme_claims`
    and concludes the checker is broken, when what happened is that the
    package lost a file -- which is the finding, and the one thing the run
    existed to produce. It also collapses the 0/1/3 vocabulary every caller
    here is written against into an unhandled exception, which is neither.

    Measured, not imagined: deleting hooks/hooks.json from a copy of this
    repository made this file raise FileNotFoundError on the json.load that
    counts hooks, and that traceback -- not a finding -- was what failed the
    build. check_package_integrity.py says so in its own comment.
    """

    def test_a_missing_hooks_manifest_is_a_finding(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            os.remove(os.path.join(t, "hooks", "hooks.json"))
            fails = check(t, count_tests=False)
            self.assertTrue(any("hooks.json" in f for f in fails), fails)

    def test_an_unparseable_hooks_manifest_is_a_finding(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "hooks/hooks.json", "{not json,")
            fails = check(t, count_tests=False)
            self.assertTrue(any("hooks.json" in f for f in fails), fails)

    def test_a_hooks_manifest_of_the_wrong_shape_is_a_finding(self):
        # Decodes as JSON and cannot be counted. `sum(len(v) for v in ...)`
        # raises AttributeError here, which is the same traceback wearing a
        # different exception type.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "hooks/hooks.json", '{"hooks": ["Stop"]}')
            fails = check(t, count_tests=False)
            self.assertTrue(any("hooks.json" in f for f in fails), fails)

    def test_a_missing_hook_program_is_a_finding(self):
        # The config keys and the log names are both read out of this file, so
        # losing it silently unheld two of the checks rather than one.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            os.remove(os.path.join(t, "hooks", "harness_hooks.py"))
            fails = check(t, count_tests=False)
            self.assertTrue(any("harness_hooks.py" in f for f in fails), fails)

    def test_an_undecodable_readme_is_a_finding(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            with open(os.path.join(t, "README.md"), "wb") as f:
                f.write(b"declaring one hooks \xff\xfe not utf-8\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("README.md" in f for f in fails), fails)


class TestTheCountsTheReadmeTableStates(TreeFixture, unittest.TestCase):
    """The claims that were prose and nothing else until now.

    "Ten modules", "Seven skills", "Eleven domain references", "Three judging
    agents", "Six eval cases -- three routing, three safety". All true when
    written, none of them held by anything: adding an eleventh module left CI
    green while the README listed ten of eleven. They arrived in the release
    that codified "a claim in prose brings the check that holds it", which is
    the whole reason they are worth the fixtures below.
    """

    def test_a_wrong_module_count_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\nthing.py\n")
            self._write(t, "scripts/thing.py", "")
            fails = check(t, count_tests=False)
            self.assertTrue(any("module count" in f for f in fails), fails)

    def test_a_module_the_prose_never_names_is_reported(self):
        # The count is right and the list is not. Ten modules of which one is
        # not the module named passes any tally and still sends a reader to a
        # file that is not there.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n",
                       counts=claims(modules=1))
            self._write(t, "scripts/thing.py", "")
            fails = check(t, count_tests=False)
            self.assertTrue(any("thing.py" in f for f in fails), fails)
            self.assertFalse([f for f in fails if "module count" in f], fails)

    def test_a_test_module_is_not_one_of_the_modules(self):
        # The README's list is of the programs, not of their suites -- whose
        # totals it states separately, in tests rather than in files.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "scripts/test_thing.py", "")
            fails = check(t, count_tests=False)
            self.assertFalse([f for f in fails if "module" in f], fails)

    def test_a_counting_word_ending_another_word_is_not_a_count(self):
        # "standalone modules" ends in "one". Without a boundary on the left
        # of the number, that reads as a claim of one module and fails a tree
        # that has none -- a finding invented out of ordinary prose, in a
        # file whose whole worth is that its findings are real. No sentence
        # in the README does this today; the sections about to be written
        # into docs/ are where connective prose like it lands.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n"
                          "the standalone modules are documented elsewhere\n")
            fails = check(t, count_tests=False)
            self.assertFalse([f for f in fails if "module count" in f], fails)

    def test_a_wrong_skill_count_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "skills/b-skill/SKILL.md", "---\nname: b-skill\n---\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("skill count" in f for f in fails), fails)

    def test_a_wrong_agent_count_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\nan-agent\n")
            self._write(t, "agents/an-agent.md", "---\nname: an-agent\n---\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("agent count" in f for f in fails), fails)

    def test_an_agent_the_prose_never_names_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n",
                       counts=claims(agents=1))
            self._write(t, "agents/an-agent.md", "---\nname: an-agent\n---\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("an-agent" in f for f in fails), fails)
            self.assertFalse([f for f in fails if "agent count" in f], fails)

    def test_a_wrong_domain_reference_count_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "skills/appian-best-practices/references/01-x.md", "x\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("domain reference count" in f for f in fails), fails)

    def test_a_wrong_eval_case_count_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "evals/routing-a/prompt.md", "go\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("eval case count" in f for f in fails), fails)

    def test_the_routing_and_safety_split_is_held_apart(self):
        # Six cases split three and three is three claims, not one: swapping a
        # safety case for a routing case keeps the total at six while the
        # sentence describing the suite stops being true.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n",
                       counts=claims(cases=2, routing=2, safety=0))
            self._write(t, "evals/routing-a/prompt.md", "go\n")
            self._write(t, "evals/safety-b/prompt.md", "go\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("routing" in f for f in fails), fails)
            self.assertTrue(any("safety" in f for f in fails), fails)
            self.assertFalse([f for f in fails if "eval case count" in f], fails)

    def test_the_runners_own_notion_of_a_case_is_the_one_used(self):
        # `results/` is where the eval runner writes its scores and dot- and
        # dunder-prefixed directories are tool artefacts. check_evals.py owns
        # that list; a second copy of it here would be free to disagree with
        # the file that decides what actually runs.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "evals/results/scores.json", "{}")
            self._write(t, "evals/__pycache__/x.pyc", "")
            fails = check(t, count_tests=False)
            self.assertFalse([f for f in fails if "eval case" in f], fails)


class TestTheClaimsMayLiveInMoreThanOneFile(TreeFixture, unittest.TestCase):
    """README.md is where these claims are today, not where they belong.

    A README that has to state every count is a README nobody finishes, so
    the sections move into docs/. A checker that only ever opens README.md
    would report every moved claim as deleted -- which is the correct answer
    to a deletion and the wrong one to a move, and the two are worth telling
    apart because only one of them is a defect.
    """

    def test_a_claim_moved_into_docs_is_still_checked(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "someKey a-skill some-log.jsonl\n")
            self._write(t, "docs/hooks.md", "declaring one hooks\n")
            fails = check(t, count_tests=False)
            self.assertFalse([f for f in fails if "hook count" in f], fails)

    def test_a_claim_wrong_in_docs_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "someKey a-skill some-log.jsonl\n")
            self._write(t, "docs/hooks.md", "declaring four hooks\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("hook count" in f for f in fails), fails)
            self.assertTrue(any("docs/hooks.md" in f for f in fails), fails)

    def test_a_second_stale_copy_of_a_claim_is_reported(self):
        # The README already states the domain-reference count twice, in the
        # table and again four sections down. Holding only the first match
        # would leave the second free to go stale, which is this file's own
        # subject with the search narrowed to one hit.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self._write(t, "docs/hooks.md", "declaring four hooks\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("hook count" in f for f in fails), fails)

    def test_a_name_mentioned_only_in_docs_counts_as_mentioned(self):
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsome-log.jsonl\n")
            self._write(t, "docs/config.md", "someKey and a-skill are documented here\n")
            fails = check(t, count_tests=False)
            self.assertEqual(fails, [])

    def test_no_docs_directory_is_not_a_finding(self):
        # docs/ does not exist in this repository today, and a checker that
        # required it would fail the build for the shape the tree already has.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
            self.assertEqual(check(t, count_tests=False), [])

    def test_a_claim_in_no_document_at_all_is_still_a_finding(self):
        # The half of this checker worth having. Silence must not read as
        # agreement just because the search got wider.
        with tempfile.TemporaryDirectory() as t:
            self._tree(t, "someKey a-skill some-log.jsonl\n")
            self._write(t, "docs/unrelated.md", "prose about something else\n")
            fails = check(t, count_tests=False)
            self.assertTrue(any("no longer states this" in f for f in fails), fails)


class TestEveryRelativeLinkResolves(TreeFixture, unittest.TestCase):
    """A link is the shortest checkable claim a document can make.

    "It is over there" -- and moving a section is exactly what breaks it.
    Splitting the README into docs/ took `](CHANGELOG.md)` with it, a link
    that resolved from the root and does not resolve from `docs/`, and it was
    found by a person reading. Everything else in this file exists because
    that kind of coverage lasts until the day nobody remembers to look.
    """

    def _link_fails(self, root, documents):
        self._tree(root, "declaring one hooks\nsomeKey a-skill some-log.jsonl\n")
        for relative, text in sorted(documents.items()):
            self._write(root, relative, text)
        return [f for f in check(root, count_tests=False) if "links to" in f]

    def test_a_link_to_a_missing_file_names_both_ends(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "see [the other one](missing.md)\n"})
            self.assertTrue(any("docs/a.md" in f and "missing.md" in f for f in fails), fails)

    def test_a_link_from_docs_up_to_the_root_resolves(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "see [the changelog](../CHANGELOG.md)\n",
                                         "CHANGELOG.md": "# Changelog\n"})
            self.assertEqual(fails, [])

    def test_a_link_is_resolved_against_its_own_file_and_not_the_root(self):
        # The defect itself. `](CHANGELOG.md)` in a document that used to be
        # part of the README resolves to docs/CHANGELOG.md once it moves, and
        # a checker resolving from the root would call it fine.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "see [the changelog](CHANGELOG.md)\n",
                                         "CHANGELOG.md": "# Changelog\n"})
            self.assertTrue(any("docs/a.md" in f for f in fails), fails)

    def test_a_link_between_two_documents_in_docs_resolves(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "see [b](b.md)\n", "docs/b.md": "# B\n"})
            self.assertEqual(fails, [])

    def test_links_with_a_scheme_are_left_alone(self):
        # Not this file's business, and a checker that reached for the network
        # would turn every offline run into a failure about connectivity.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[docs](https://example.com/x.md)\n"
                                                      "[plain](http://example.com/y.md)\n"
                                                      "[write](mailto:someone@example.com)\n"})
            self.assertEqual(fails, [])

    def test_a_windows_drive_letter_is_a_path_and_not_a_scheme(self):
        # `C:/Users/...` is one character short of reading as a URI scheme,
        # and it is the exact shape of a link that works on the machine it
        # was written on and nowhere else.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[here](C:/Users/someone/README.md)\n"})
            self.assertTrue(any("docs/a.md" in f for f in fails), fails)

    def test_a_link_that_climbs_out_of_the_repository_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[out](../../elsewhere.md)\n"})
            self.assertTrue(any("elsewhere.md" in f for f in fails), fails)

    def test_a_link_differing_only_in_case_is_reported(self):
        # NTFS and APFS say this file is there; ext4 and GitHub say it is not.
        # A checker that inherits the filesystem's opinion passes on the
        # machine where the mistake is invisible -- check_package_integrity's
        # argument, and the reason its resolver is the one used here.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[b](B.md)\n", "docs/b.md": "# B\n"})
            self.assertTrue(any("B.md" in f for f in fails), fails)

    def test_a_title_after_the_target_is_not_part_of_the_path(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": '[b](b.md "the second one")\n',
                                         "docs/b.md": "# B\n"})
            self.assertEqual(fails, [])

    def test_a_target_in_angle_brackets_is_unwrapped(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[b](<b.md>)\n", "docs/b.md": "# B\n"})
            self.assertEqual(fails, [])

    def test_a_link_with_no_target_at_all_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[b]()\n"})
            self.assertTrue(any("docs/a.md" in f for f in fails), fails)

    def test_a_fragment_naming_no_heading_in_the_target_is_reported(self):
        # The half the split creates: the file still exists, the section in
        # it does not, and the link lands silently at the top of the page.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[gates](b.md#the-gates)\n",
                                         "docs/b.md": "# B\n\n## Something else\n"})
            self.assertTrue(any("the-gates" in f for f in fails), fails)

    def test_a_fragment_matching_a_heading_resolves(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[gates](b.md#the-gates)\n",
                                         "docs/b.md": "# B\n\n## The gates\n"})
            self.assertEqual(fails, [])

    def test_punctuation_in_a_heading_does_not_decide_the_match(self):
        # Renderers disagree about what a slug does with a code span:
        # `## The `hooks.json` file` is "the-hooksjson-file" on GitHub and
        # "the-hooks-json-file" under a naive implementation. Comparing on
        # letters and digits alone accepts both, which is the point -- this
        # check answers "is that heading in this document", and a checker
        # that guessed one renderer's punctuation rule would invent findings
        # about links that work.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[cfg](b.md#the-hooksjson-file)\n",
                                         "docs/b.md": "# B\n\n## The `hooks.json` file\n"})
            self.assertEqual(fails, [])

    def test_an_anchor_with_no_file_is_checked_against_its_own_document(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "# A\n\n## Here\n\n[up](#here)\n"
                                                      "[nowhere](#not-here)\n"})
            self.assertTrue(any("not-here" in f for f in fails), fails)
            self.assertFalse([f for f in fails if "#here" in f], fails)

    def test_a_repeated_heading_can_be_linked_by_its_numbered_slug(self):
        # A changelog has "### Fixed" once per release, and the second one is
        # reachable as `#fixed-1`. Generated the way a renderer generates
        # them, so the suffix that exists resolves and the one that does not
        # is still a finding.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[second](b.md#fixed-1)\n",
                                         "docs/b.md": "## Fixed\n\n## Fixed\n"})
            self.assertEqual(fails, [])

    def test_a_numbered_slug_past_the_last_copy_is_reported(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[fourth](b.md#fixed-3)\n",
                                         "docs/b.md": "## Fixed\n\n## Fixed\n"})
            self.assertTrue(any("fixed-3" in f for f in fails), fails)

    def test_a_fragment_on_something_that_is_not_markdown_is_left_alone(self):
        # `#L42` on a source file is a line anchor the renderer invents;
        # there is no heading to look for and no way to be right about it.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[line](../hooks/harness_hooks.py#L42)\n"})
            self.assertEqual(fails, [])

    def test_a_link_to_a_directory_resolves(self):
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"docs/a.md": "[the skills](../skills)\n"})
            self.assertEqual(fails, [])

    def test_documents_outside_the_claim_set_have_their_links_checked(self):
        # The two sets are deliberately different sizes. CONTRIBUTING.md,
        # SECURITY.md, the skills and the eval cases state no count this file
        # holds, and every one of them can carry a link that rots.
        with tempfile.TemporaryDirectory() as t:
            fails = self._link_fails(t, {"CONTRIBUTING.md": "[security](SECURITY.md)\n"})
            self.assertTrue(any("CONTRIBUTING.md" in f for f in fails), fails)

    def test_the_real_repository_has_no_broken_link(self):
        # Cheap enough to run unconditionally -- it reads files and spawns
        # nothing, unlike the suite-counting test this one sits next to.
        self.assertEqual([f for f in check(REAL_ROOT, count_tests=False) if "links to" in f], [])

    def test_the_real_repository_is_actually_being_walked(self):
        # The test above is the one that earns its keep, and it would pass
        # just as happily if the walk returned nothing at all -- zero
        # documents inspected reported as agreement, which is the vacuous
        # green this plugin spends a README arguing against. So the corners
        # are pinned: a root document, a docs/ page, a skill and an eval
        # case are four different depths, and .pytest_cache ships a
        # README.md that no one in this repository wrote.
        found = [label for label, _ in _markdown_files(REAL_ROOT)]
        self.assertIn("README.md", found)
        self.assertIn("CHANGELOG.md", found)
        self.assertTrue([f for f in found if f.startswith("docs/")], found)
        self.assertTrue([f for f in found if f.startswith("skills/")], found)
        self.assertTrue([f for f in found if f.startswith("evals/")], found)
        self.assertFalse([f for f in found if f.startswith(".")], found)


if __name__ == "__main__":
    unittest.main()
