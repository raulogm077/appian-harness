import os, shutil, tempfile, unittest
import check_evals as C


def case(root, name, prompt="Do the thing.\n", grader="The response does the thing.\n"):
    d = os.path.join(root, "evals", name, "graders")
    os.makedirs(d)
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
