import os, shutil, tempfile, unittest
import check_evals as C


def case(root, name, prompt="Do the thing.\n", grader="The response does the thing.\n"):
    d = os.path.join(root, "evals", name, "graders")
    os.makedirs(d)
    if prompt is not None:
        with open(os.path.join(root, "evals", name, "prompt.md"), "w", encoding="utf-8") as f:
            f.write(prompt)
    if grader is not None:
        with open(os.path.join(d, "criteria.md"), "w", encoding="utf-8") as f:
            f.write(grader)


class EvalShape(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_a_well_formed_case_passes(self):
        case(self.root, "a")
        self.assertEqual(C.check(self.root)[0], 0)

    def test_a_case_with_no_grader_fails(self):
        # A prompt with nothing scoring it is a prompt, not an eval. It would
        # run, produce output, and assert nothing -- green by construction.
        case(self.root, "a", grader=None)
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("grader" in m for m in msgs))

    def test_an_empty_prompt_fails(self):
        case(self.root, "a", prompt="   \n")
        self.assertEqual(C.check(self.root)[0], 1)

    def test_a_grader_that_only_restates_the_prompt_fails(self):
        # The theatre trap: a grader that rewards the vocabulary of the prompt
        # scores high while the task goes undone.
        case(self.root, "a", prompt="Use appian-verify to check the task.\n",
             grader="Use appian-verify to check the task.\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("restates" in m for m in msgs))

    def test_a_copy_with_the_punctuation_changed_still_fails(self):
        # Near-exact, not exact: the duplication check normalises case and
        # punctuation first, so retyping the prompt in lower case does not
        # buy a pass.
        case(self.root, "a", prompt="Use appian-verify to check the task.\n",
             grader="use appian-verify to check the task!!\n")
        self.assertEqual(C.check(self.root)[0], 1)

    def test_a_reordered_copy_warns_without_failing(self):
        # Every word of this grader comes from its prompt, so the fuzzy
        # overlap metric reads 100% -- but that metric compares SETS, and a
        # set cannot see order, frequency, negation or morphology. It has
        # never been calibrated against labelled examples, so it speaks and
        # does not break a build. Silence would be the vacuous green; a
        # failing build on an uncalibrated number would be worse.
        case(self.root, "a",
             prompt="Use appian-verify to check the task and record the evidence.\n",
             grader="Evidence record task check appian-verify use.\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(any(m.startswith(C.WARNING_PREFIX) for m in msgs))

    def test_a_case_with_no_prompt_fails(self):
        # Measured on the shipped checker: a directory holding graders/ and no
        # prompt was not read as a malformed case, it was read as not a case at
        # all -- so the run ended NOT MEASURED, which is the code a caller
        # skips, with the broken directory still in the tree.
        case(self.root, "no-prompt-here", prompt=None)
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("no-prompt-here" in m for m in msgs))

    def test_a_broken_case_does_not_hide_behind_a_good_one(self):
        # The same defect in its dangerous form, also measured: one valid case
        # was enough to carry the run to exit 0 with a broken case beside it.
        case(self.root, "broken", prompt=None)
        case(self.root, "good")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("broken" in m for m in msgs))

    def test_the_runners_output_directory_is_not_a_case(self):
        # evals/results/ is where the runner writes, not a case somebody left
        # half-written. Reporting it would teach people to scroll past this
        # check, which protects nothing.
        os.makedirs(os.path.join(self.root, "evals", "results"))
        case(self.root, "good")
        self.assertEqual(C.check(self.root)[0], 0)

    def test_a_grader_of_nothing_but_stopwords_fails(self):
        # Measured: `_significant("the response should not")` is empty, and the
        # empty set was skipped rather than failed. "not" is a stopword and it
        # is the word carrying the criterion -- so this grader says nothing a
        # judge could apply, which is a case checked and failed, not a case
        # with nothing to check.
        case(self.root, "a", grader="the response should not")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("no criterion" in m for m in msgs))

    def test_a_grader_of_nothing_but_punctuation_fails(self):
        # Same hole through the other door: "!!!" survived _significant as a
        # word, overlapped with nothing, and passed.
        case(self.root, "a", grader="!!!")
        self.assertEqual(C.check(self.root)[0], 1)

    def test_no_evals_directory_is_not_measured(self):
        self.assertEqual(C.check(self.root)[0], C.EXIT_NOT_MEASURED)

    def test_the_shipped_suite_is_well_formed(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        code, msgs = C.check(root)
        self.assertEqual(code, 0, "\n".join(msgs))

    def test_the_suite_declares_it_has_never_run(self):
        # The honesty requirement. If someone deletes the caveat from
        # evals/README.md, this fails: an unexecuted suite that stops saying so
        # reads as coverage it does not have.
        root = os.path.join(os.path.dirname(__file__), "..")
        with open(os.path.join(root, "evals", "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("never been executed", text)


if __name__ == "__main__":
    unittest.main()
