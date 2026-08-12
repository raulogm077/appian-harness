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

# Every one of these is valid YAML, and every one grants Write to an agent
# in READ_ONLY_AGENTS. They are here as a corpus rather than as a dozen
# hand-written tests for the reason test_matcher_parity gives about the tool
# catalogue: the last several defects in this file were each one more
# spelling, found by measuring against a list and not by reasoning about the
# parser. A reader who adds a spelling adds a row.
#
# The first six were caught by successive patches to a parser. The rest were
# not, and are why the rule stopped going through a parser at all.
GRANTS_WRITE = (
    ("inline plain", "tools: Read, Write\n"),
    ("inline flow, one entry", "tools: [Write]\n"),
    ("inline flow, several", "tools: [Read, Write, Glob]\n"),
    ("wildcard", "tools: *\n"),
    ("trailing comment", "tools: Read, Write # temporary\n"),
    ("block sequence", "tools:\n  - Read\n  - Write\n"),
    ("quoted scalar", 'tools: "Read, Write"\n'),
    # A comment line inside a block sequence: an item-by-item reader stops
    # here and everything below it disappears.
    ("block sequence, comment line", "tools:\n  - Read\n  # - Grep\n  - Write\n"),
    ("block sequence, blank line", "tools:\n  - Read\n\n  - Write\n"),
    ("flow sequence across lines", "tools: [Read,\n        Write]\n"),
    ("nested sequence", "tools:\n  - [Read, Write]\n"),
    # YAML resolves a duplicate key to the last one, so a reader that
    # returns at the first match reads the declaration the loader throws
    # away.
    ("duplicate key", "tools: Read\ntools: Read, Write\n"),
    ("folded block scalar", "tools: >\n  Read,\n  Write\n"),
    ("literal block scalar", "tools: |\n  Read, Write\n"),
    # Not a spelling -- a different forbidden tool, and the only row that
    # grants one without also granting Write. Without it every row could be
    # satisfied by a rule that knows the word "Write" and nothing else, and
    # the corpus would be blind to an Edit-only grant.
    ("edit alone", "tools: [Read, Edit]\n"),
)

# Tools that let an agent change what it is reviewing, one per row, each in
# the plainest possible spelling. The corpus above varies the punctuation and
# holds the tool fixed; this one varies the tool and holds the punctuation
# fixed, because those are two different failures and only the first was ever
# measured.
#
# `Bash` is here because it is the one that got through: a reviewer holding
# it writes any file in the repository with a redirection, and it is not a
# write tool by name. The rest are the next ones along the same line -- and
# the MCP rows are the argument for a whitelist all by themselves, since no
# two servers spell their write tools alike.
WRITE_CAPABLE = (
    "Write", "Edit", "MultiEdit", "NotebookEdit", "Bash", "BashOutput",
    "Task", "Agent", "SlashCommand", "WebFetch", "Artifact", "TaskUpdate",
    "mcp__appian-dev__createRecordType",
    "mcp__appian-dev__deleteRecordType",
    "mcp__appian-dev__updateObjectSecurity",
    "mcp__claude_ai_Supabase__execute_sql",
    # The row that separates a whitelist from a longer blacklist. Every
    # other name here exists today, so a rule that enumerated all of them
    # would still pass this corpus while failing on the first tool anyone
    # ships next week. `Frobnicate` is nobody's tool, and a whitelist has to
    # refuse it for the same reason it refuses Bash: not because it is
    # known to write, but because it is not known to be safe.
    "Frobnicate",
)

# The two spellings a genuinely read-only agent uses. A prohibition that
# fails closed is only useful if it is quiet about these.
READ_ONLY_SPELLINGS = (
    ("inline", "tools: Read, Grep, Glob, Skill\n"),
    ("block sequence", "tools:\n  - Read\n  - Grep\n  - Glob\n  - Skill\n"),
    # A documented tools line. Under the blacklist this was safe by
    # accident; under a whitelist the comment's words are candidate tool
    # names, so refusing it would make every commented declaration a false
    # alarm and the rule the first thing anyone deletes.
    ("inline with a comment", "tools: Read, Grep, Glob, Skill # nothing that writes\n"),
)


def agent_with_tools(tools_block):
    """A well-formed appian-reviewer whose only variable is its tools line."""
    return ("---\n"
            "name: appian-reviewer\n"
            "description: Reviews one change. Use when a change creates an object.\n"
            "model: inherit\n"
            + tools_block +
            "skills: [appian-best-practices]\n"
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
        # The same separation, dissolved by a shorter edit: `*` grants every
        # tool without naming one.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("tools: Read, Grep, Glob, Skill", "tools: *"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("*" in e for e in errs), errs)

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

    def test_a_comment_between_skills_does_not_lose_the_one_after_it(self):
        # The class the whitelist argument missed: not a name read wrongly,
        # a name not read at all. An item-by-item reader stops at the comment
        # and never sees `nope`, so the one key where a bad read is supposed
        # to be noisy goes silent too.
        path = self.write("appian-reviewer.md",
                          GOOD.replace("skills: [appian-best-practices]",
                                       "skills:\n  - appian-best-practices\n"
                                       "  # - retired-skill\n  - nope"))
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("'nope'" in e for e in errs), errs)

    def test_a_non_utf8_agent_is_a_finding_not_a_traceback(self):
        # A checker that raises is a broken checker to whoever reads the CI
        # log, and it takes the other agents' results down with it: the run
        # reports nothing about the files it never got to.
        path = os.path.join(self.root, "agents", "appian-reviewer.md")
        with open(path, "wb") as f:
            f.write(b"---\nname: appian-reviewer\ndescription: \xff\xfe Use when.\n"
                    b"---\n\nbody\n")
        errs = L.lint_agent(path, {"appian-best-practices"})
        self.assertTrue(any("UTF-8" in e for e in errs), errs)

    def test_a_non_utf8_agent_does_not_stop_the_run(self):
        self.write("appian-verifier.md",
                   GOOD.replace("name: appian-reviewer", "name: appian-verifier"))
        with open(os.path.join(self.root, "agents", "appian-reviewer.md"), "wb") as f:
            f.write(b"\xff\xfe not text at all")
        out = io.StringIO()
        with redirect_stdout(out):
            rc = L.main(self.root)
        self.assertEqual(rc, 1)
        self.assertIn("UTF-8", out.getvalue())
        # The other agent was still reached and still reported.
        self.assertIn("appian-verifier.md", out.getvalue())

    def test_a_bom_is_not_four_findings_about_a_well_formed_agent(self):
        # An editor that writes a BOM makes the first character something
        # other than `-`, so the frontmatter is not recognised and every
        # field reads as missing: four findings, none of them the problem,
        # about a file that is correct.
        path = os.path.join(self.root, "agents", "appian-reviewer.md")
        with open(path, "w", encoding="utf-8-sig") as f:
            f.write(GOOD)
        self.assertEqual(L.lint_agent(path, {"appian-best-practices"}), [])

    def test_a_renamed_read_only_agent_does_not_silently_lose_its_restriction(self):
        # Rename the file and its `name:` together and every per-file check
        # still passes -- name matches filename, tools are declared -- while
        # READ_ONLY_AGENTS now restricts nothing. Nothing printed, because a
        # rule that matches no agent has no agent to complain about, and the
        # protection is gone in the direction that does not announce itself.
        self.write("appian-independent-reviewer.md",
                   GOOD.replace("name: appian-reviewer",
                                "name: appian-independent-reviewer")
                       .replace("tools: Read, Grep, Glob, Skill", "tools: *"))
        out = io.StringIO()
        with redirect_stdout(out):
            rc = L.main(self.root)
        self.assertEqual(rc, 1)
        self.assertIn("appian-reviewer", out.getvalue())

    def test_the_shipped_tree_has_no_stale_read_only_entries(self):
        # Stated against the real tree as well as the fixture: the fixture
        # proves the check works and says nothing about whether this
        # plugin's own entries still name agents it ships.
        shipped = set()
        agents_dir = os.path.join(os.path.dirname(__file__), "..", "agents")
        for entry in os.listdir(agents_dir):
            if entry.endswith(".md"):
                shipped.add(os.path.splitext(entry)[0])
        self.assertEqual(L.stale_read_only_entries(shipped), [])

    def test_a_missing_agents_directory_is_not_measured(self):
        # 3, not 1. Nothing was inspected, which is not the same as
        # something having been inspected and failed -- the distinction the
        # third exit code exists for, and which every checker here spells
        # the same way.
        empty = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, empty, True)
        out = io.StringIO()
        with redirect_stdout(out):
            rc = L.main(empty)
        self.assertEqual(rc, L.EXIT_NOT_MEASURED)
        self.assertIn("NOT MEASURED", out.getvalue())

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


class EverySpellingThatGrantsWrite(unittest.TestCase):
    """The prohibition is measured against the corpus, not against intent."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "agents"))
        self.addCleanup(shutil.rmtree, self.root, True)

    def lint(self, tools_block):
        path = os.path.join(self.root, "agents", "appian-reviewer.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(agent_with_tools(tools_block))
        return L.lint_agent(path, {"appian-best-practices"})

    def test_every_spelling_that_grants_write_is_caught(self):
        # The failure this replaces: three separate patches, each closing one
        # spelling, each leaving the rule enforced by a parser that the next
        # spelling walked around. Every miss here is silent, because the rule
        # asks whether the string "Write" is present and a misparse produces
        # a token that is not it.
        for label, block in GRANTS_WRITE:
            with self.subTest(spelling=label):
                # Asserted on the finding existing, not on its wording. Every
                # row but one grants Write specifically, so a substring
                # assertion would have passed on a rule that knows that one
                # word and nothing else -- and the corpus exists precisely to
                # stop the rule being narrower than the thing it forbids.
                self.assertNotEqual(self.lint(block), [], label)

    def test_the_word_write_outside_the_tools_declaration_is_not_a_grant(self):
        # The region bound, stated rather than assumed. A description that
        # says the agent never writes data contains the forbidden word; a
        # search over the whole frontmatter would refuse the agent for
        # documenting the very property being enforced.
        path = os.path.join(self.root, "agents", "appian-reviewer.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(agent_with_tools("tools: Read, Grep, Glob, Skill\n")
                    .replace("Reviews one change.",
                             "Reviews one change and never issues a Write or an Edit."))
        self.assertEqual(L.lint_agent(path, {"appian-best-practices"}), [])

    def test_the_legitimate_read_only_spellings_stay_clean(self):
        # Without this the test above passes on a rule that fails everything.
        for label, block in READ_ONLY_SPELLINGS:
            with self.subTest(spelling=label):
                self.assertEqual(self.lint(block), [], label)

    def test_every_write_capable_tool_is_refused(self):
        # The defect a review found after three rounds of spelling patches:
        # `tools: Read, Grep, Glob, Skill, Bash` passed. The rule enumerated
        # four forbidden names, and a blacklist only ever protects against
        # what its author imagined. This is the corpus that would have said
        # so, and it is why the rule is a whitelist now.
        for tool in WRITE_CAPABLE:
            with self.subTest(tool=tool):
                errs = self.lint("tools: Read, Grep, %s\n" % tool)
                self.assertTrue(any(tool in e for e in errs), "%s: %r" % (tool, errs))

    def test_an_mcp_write_tool_is_not_invisible_to_the_harvester(self):
        # Stated on its own because the obvious harvester misses it, and
        # missing it is silent. `\b[A-Z][A-Za-z]*\b` was proposed for this
        # job: built-in tool names are capitalised, but there is no `\b[A-Z]`
        # anywhere in `mcp__appian-dev__createRecordType` -- the capital R is
        # between two word characters, so no boundary precedes it. That
        # pattern harvests Read and Grep from the line and reports an agent
        # holding every Appian write tool as clean.
        errs = self.lint("tools: Read, Grep, mcp__appian-dev__createRecordType\n")
        self.assertTrue(any("createRecordType" in e for e in errs), errs)

    def test_the_finding_says_what_to_do_about_it(self):
        # A finding that only says "not permitted" leaves two routes, and the
        # one taken under time pressure is deleting the tool that was needed.
        errs = self.lint("tools: Read, Grep, Frobnicate\n")
        self.assertTrue(any("READ_ONLY_TOOLS" in e and "reason" in e for e in errs), errs)

    def test_the_corpus_covers_more_than_one_shape(self):
        # The parity file's own guard, for the same reason: the assertions
        # above are trivially true of a corpus that shrank.
        self.assertGreater(len(GRANTS_WRITE), 12)
        self.assertGreater(len(WRITE_CAPABLE), 12)
        self.assertTrue(any("\n" in block for _, block in GRANTS_WRITE))
        # A whitelist that refuses everything would satisfy both loops, and a
        # blacklist long enough to name every tool that exists today would
        # satisfy them until next week. One row is an MCP name, one is a tool
        # nobody has written.
        self.assertTrue(any(t.startswith("mcp__") for t in WRITE_CAPABLE))
        self.assertIn("Frobnicate", WRITE_CAPABLE)


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

    def test_frontmatter_list_always_returns_a_list(self):
        # It used to return None for an absent key and [] for an empty one,
        # defended in a docstring, and no caller ever told them apart.
        self.assertEqual(L.frontmatter_list(GOOD, "nothing-declares-this"), [])
        self.assertEqual(L.frontmatter_list("no frontmatter here", "skills"), [])


if __name__ == "__main__":
    unittest.main()
