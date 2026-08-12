import io, os, shutil, tempfile, unittest
from contextlib import redirect_stdout

import lint_agents as L

GOOD = ("---\n"
        "name: appian-reviewer\n"
        "description: Reviews one Appian change from a clean context. Use when a "
        "change creates an object or writes data.\n"
        "model: inherit\n"
        "color: red\n"
        "skills: [appian-best-practices]\n"
        "tools: Read, Grep, Glob, Skill\n"
        "---\n\nbody\n")


class AgentFrontmatter(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "agents"))
        os.makedirs(os.path.join(self.root, "skills", "appian-best-practices"))
        open(os.path.join(self.root, "skills", "appian-best-practices", "SKILL.md"),
             "w").close()
        self.addCleanup(shutil.rmtree, self.root, True)

    def write(self, filename, text):
        path = os.path.join(self.root, "agents", filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_a_well_formed_agent_passes(self):
        path = self.write("appian-reviewer.md", GOOD)
        self.assertEqual(L.lint_agent(path, {"appian-best-practices"}), [])

    def test_name_must_match_the_filename(self):
        path = self.write("other.md", GOOD)
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("filename" in e for e in errs))

    def test_a_description_without_a_trigger_is_rejected(self):
        # Same rule as skills, imported rather than restated: an agent whose
        # description only says what it is never gets dispatched.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("Use when a change creates an object or writes data.",
                                       "It is a reviewer."))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("trigger" in e for e in errs))

    def test_a_skill_that_does_not_exist_is_rejected(self):
        path = self.write("appian-reviewer.md",
                          GOOD.replace("[appian-best-practices]", "[nope]"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("nope" in e for e in errs))

    def test_a_yaml_block_list_of_skills_is_read_not_refused(self):
        # A block sequence is valid YAML. It is read from the raw frontmatter
        # lines rather than from parse_frontmatter's space-joined fold, which
        # would deliver "- a - b" and recover neither name.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("skills: [appian-best-practices]",
                                       "skills:\n  - appian-best-practices"))
        self.assertEqual(L.lint_agent(path, {"appian-best-practices"}), [])

    def test_a_bad_entry_in_a_block_list_of_skills_is_still_caught(self):
        # The half of the block-list reader that matters: reading it must not
        # mean waving it through, and the second entry is the one a fold
        # would have destroyed.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("skills: [appian-best-practices]",
                                       "skills:\n  - appian-best-practices\n  - nope"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        # The quotes are the assertion. A folded read reports the whole
        # sequence as one name -- "'- appian-best-practices - nope'" -- which
        # contains "nope" and would pass a looser check while naming a skill
        # nobody wrote and blaming a good entry alongside the bad one.
        self.assertEqual(len(errs), 1, errs)
        self.assertTrue(any("'nope'" in e for e in errs))

    def test_missing_tools_is_rejected(self):
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill\n", ""))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("tools" in e for e in errs))

    def test_an_agent_granted_write_tools_must_say_why(self):
        # appian-reviewer is Read/Grep/Glob on purpose: a reviewer that can
        # edit the thing it reviews is not an independent reviewer. Granting
        # Write silently would dissolve that separation.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill",
                                       "tools: Read, Write, Edit"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("Write" in e for e in errs))

    def test_a_read_only_agent_may_not_declare_every_tool(self):
        # The same separation, dissolved by a shorter edit. `tools: *` grants
        # Write without spelling it, so a check that only reads the named
        # tools would wave it through -- one character standing in for the
        # whole list the rule above exists to police.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill", "tools: *"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("Write" in e for e in errs))

    def test_a_flow_list_of_tools_does_not_hide_write(self):
        # The defect an independent review found: `tools: [Write]` is valid
        # YAML, and splitting it on commas yields the single token "[Write]",
        # which is not the string "Write". The read-only rule was satisfied
        # by two square brackets -- the same hole as `tools: *`, in the
        # spelling that looks most like a list.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill", "tools: [Write]"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("Write" in e for e in errs))

    def test_a_multi_entry_flow_list_of_tools_does_not_hide_write(self):
        # Where the brackets land on the first and last entries only, so a
        # reader that strips them from the whole string still has to split
        # correctly to see the middle.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill",
                                       "tools: [Read, Write, Glob]"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("Write" in e for e in errs))

    def test_a_block_list_of_tools_does_not_hide_write(self):
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill\n",
                                       "tools:\n  - Read\n  - Write\n"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("Write" in e for e in errs))

    def test_a_trailing_comment_does_not_hide_write(self):
        # The third spelling in the same family: YAML allows a comment after
        # a scalar, so "Write # temporary" is a grant of Write, and a reader
        # that keeps the comment compares against a token that is not the
        # string "Write". A temporary grant is exactly the one that gets
        # written this way and then stays.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill",
                                       "tools: Read, Write # temporary, remove me"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("Write" in e for e in errs))

    def test_a_commented_skill_resolves_without_its_comment(self):
        # The same strip, in the direction that produces a false alarm rather
        # than a miss: the comment must not become part of the skill name.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("skills: [appian-best-practices]",
                                       "skills:\n  - appian-best-practices # the doctrine"))
        self.assertEqual(L.lint_agent(path, {"appian-best-practices"}), [])

    def test_a_block_list_of_tools_counts_as_a_tools_line(self):
        # The other direction, and the one a stricter reader gets wrong: a
        # legitimate block list must satisfy the tools requirement rather
        # than read as an agent that declared none. appian-verifier is not
        # read-only, so Write here is exactly what it ships with.
        path = self.write("appian-verifier.md",
                          GOOD.replace("name: appian-reviewer", "name: appian-verifier")
                              .replace("tools: Read, Grep, Glob, Skill\n",
                                       "tools:\n  - Read\n  - Write\n  - Bash\n"))
        self.assertEqual(L.lint_agent(path, {"appian-best-practices"}), [])

    def test_zero_agents_is_not_measured(self):
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, True)
        os.makedirs(os.path.join(empty, "agents"))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = L.main(empty)
        self.assertEqual(rc, L.EXIT_NOT_MEASURED)
        self.assertIn("NOT MEASURED", out.getvalue())

    def test_the_shipped_agents_pass(self):
        out = io.StringIO()
        with redirect_stdout(out):
            rc = L.main(os.path.join(os.path.dirname(__file__), ".."))
        self.assertEqual(rc, 0, out.getvalue())


class SharedRule(unittest.TestCase):
    def test_the_trigger_rule_is_the_skill_linter_s_own(self):
        # Not a second copy. lint_skills.has_trigger is the single definition;
        # a divergence here is the failure test_matcher_parity exists to stop.
        import lint_skills
        self.assertIs(L.has_trigger, lint_skills.has_trigger)

    def test_the_shared_constants_are_the_skill_linter_s_own(self):
        # Same argument, and the one the first draft of this module got
        # wrong: it imported has_trigger and then wrote `MAX_DESCRIPTION =
        # 1024` again. A limit raised in one file and not the other is two
        # linters disagreeing about the same contract.
        import lint_skills
        self.assertIs(L.parse_frontmatter, lint_skills.parse_frontmatter)
        self.assertEqual(L.MAX_DESCRIPTION, lint_skills.MAX_DESCRIPTION)
        self.assertEqual(L.EXIT_NOT_MEASURED, lint_skills.EXIT_NOT_MEASURED)


if __name__ == "__main__":
    unittest.main()
