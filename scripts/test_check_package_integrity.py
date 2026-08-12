"""A checker for missing files has to be able to miss one.

Every case here builds a tree with exactly one referent broken and confirms
the checker names it -- plus the one case that matters most, which points at
the real repository and would catch the defect the other 321 tests cannot
see: they import harness_hooks.py, and importing a module says nothing about
whether Claude Code can find the file hooks.json told it to run.

The case-sensitivity case is the odd one. It runs on Windows, where the
filesystem itself disagrees with the assertion, which is the entire point:
if isfile_exact ever degrades to os.path.isfile, that test goes green in CI
and red here, and the plugin quietly becomes author-machine-only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_package_integrity as C

REAL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MINIMAL_HOOKS = {
    "hooks": {"SessionStart": [{"hooks": [
        {"type": "command",
         "command": 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/run_hook.sh" '
                    '"${CLAUDE_PLUGIN_ROOT}" session-start'}]}]}}


def scaffold(root, with_launcher=True, plugin_extra=None, hooks=MINIMAL_HOOKS,
             with_boot_chain=True):
    os.makedirs(os.path.join(root, "hooks"))
    os.makedirs(os.path.join(root, ".claude-plugin"))
    if hooks is not None:
        with open(os.path.join(root, "hooks", "hooks.json"), "w", encoding="utf-8") as f:
            json.dump(hooks, f)
    if with_launcher:
        open(os.path.join(root, "hooks", "run_hook.sh"), "w").close()
    if with_boot_chain:
        # A tree that declares a hook is not complete at run_hook.sh: the
        # launcher execs a program and that program imports another, and
        # neither is named by any manifest. The fixture grew these when the
        # checker learned to require them -- what "a complete tree" means
        # changed, so the tree that stands for one had to change with it.
        os.makedirs(os.path.join(root, "scripts"))
        open(os.path.join(root, "hooks", "harness_hooks.py"), "w").close()
        open(os.path.join(root, "scripts", "validate_verdict.py"), "w").close()
    manifest = {"name": "p", "version": "1.0.0"}
    manifest.update(plugin_extra or {})
    with open(os.path.join(root, ".claude-plugin", "plugin.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f)


def link_dir(link, target):
    """Point `link` at directory `target`, however this platform will allow.

    A symlink first, then a Windows junction. The fallback is what makes the
    dangling and escaping cases testable *here*: os.symlink needs a privilege
    this account does not have, and `mklink /J` needs none, and both produce
    the condition under test -- a name that appears in a directory listing
    whether or not anything is on the other end of it.

    Falling back rather than skipping is deliberate. These are precisely the
    cases an author cannot reason about from their own machine, which is how
    they survived review in the first place; a test that quietly skips on the
    developer's platform and runs only in CI is the absent gate again.
    """
    try:
        os.symlink(target, link, target_is_directory=True)
        return True
    except (AttributeError, NotImplementedError, OSError):
        pass
    if os.name != "nt":
        return False
    return subprocess.call(["cmd", "/c", "mklink", "/J", link, target],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0


class TempTree(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def elsewhere(self):
        """A directory outside self.root, cleaned up separately."""
        outside = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, outside, True)
        return outside


class ReferencedFilesExist(TempTree):
    def test_a_complete_tree_passes(self):
        scaffold(self.root)
        self.assertEqual(C.check(self.root)[0], 0)

    def test_a_hook_command_pointing_at_a_missing_file_fails(self):
        # The failure this exists for: hooks.json ships, the file it invokes
        # does not, and the hook simply never runs -- silently.
        scaffold(self.root, with_launcher=False)
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("run_hook.sh" in m for m in msgs), msgs)

    def test_a_command_naming_no_plugin_root_path_fails(self):
        # ${CLAUDE_PLUGIN_ROOT} is the only thing Claude Code substitutes.
        # `sh hooks/run_hook.sh` resolves against the session's cwd, which is
        # the author's checkout while they are testing and somebody else's
        # project every time after that.
        scaffold(self.root, hooks={"hooks": {"Stop": [{"hooks": [
            {"type": "command", "command": "sh hooks/run_hook.sh"}]}]}})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("CLAUDE_PLUGIN_ROOT" in m for m in msgs), msgs)

    def test_a_hooks_json_that_is_not_json_fails(self):
        scaffold(self.root)
        with open(os.path.join(self.root, "hooks", "hooks.json"), "w",
                  encoding="utf-8") as f:
            f.write("{not json")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("valid JSON" in m for m in msgs), msgs)

    def test_a_manifest_declaring_no_hooks_is_not_measured(self):
        # Having opened a file is not having checked anything. A hooks.json
        # that declares nothing resolves no referent, and answering "OK every
        # declared path resolves" to that is true and worthless.
        scaffold(self.root, with_launcher=False, hooks={"hooks": {}})
        self.assertEqual(C.check(self.root)[0], C.EXIT_NOT_MEASURED)

    def test_no_hooks_json_is_not_measured(self):
        os.makedirs(os.path.join(self.root, ".claude-plugin"))
        with open(os.path.join(self.root, ".claude-plugin", "plugin.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"name": "p", "version": "1.0.0"}, f)
        self.assertEqual(C.check(self.root)[0], C.EXIT_NOT_MEASURED)


class CaseSensitivity(TempTree):
    def test_a_case_mismatch_fails_on_every_platform(self):
        # NTFS and APFS resolve Run_Hook.sh to run_hook.sh; ext4 does not. A
        # plugin that installs on a laptop and dies on Linux is the exact
        # asymmetry the case-exact resolution exists to stop.
        scaffold(self.root, with_launcher=False)
        open(os.path.join(self.root, "hooks", "Run_Hook.sh"), "w").close()
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("run_hook.sh" in m for m in msgs), msgs)

    def test_resolution_reads_the_listing_not_the_filesystem_s_opinion(self):
        # Stated directly as well as through check(), so a regression points
        # at the function rather than at whichever caller noticed first. Aimed
        # at `_referent_problem` because that is what check() calls: a test
        # that exercises a wrapper nothing else uses proves the wrapper, and
        # the shipped path is free to rot underneath it.
        os.makedirs(os.path.join(self.root, "hooks"))
        open(os.path.join(self.root, "hooks", "Run_Hook.sh"), "w").close()
        self.assertIsNone(C._referent_problem(self.root, "hooks/Run_Hook.sh", True))
        self.assertIsNotNone(C._referent_problem(self.root, "hooks/run_hook.sh", True))
        self.assertIsNotNone(C._referent_problem(self.root, "Hooks/Run_Hook.sh", True))


class ComponentsResolve(TempTree):
    def test_a_skill_directory_without_SKILL_md_fails(self):
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "skills", "ghost"))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("ghost" in m for m in msgs), msgs)

    def test_an_agent_file_that_does_not_decode_is_reported(self):
        # The whole of what this file asks of an agent now: that the bytes are
        # there and are text. Whether the frontmatter inside means anything is
        # lint_agents.py's question, and asking it in two places is how the
        # two answers drifted apart the first time.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "agents"))
        with open(os.path.join(self.root, "agents", "a.md"), "wb") as f:
            f.write(b"---\nname: a\ndescription: \xff\xfe not utf-8\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("cannot be read as UTF-8" in m for m in msgs), msgs)

    def test_a_readable_agent_naming_anything_at_all_passes(self):
        # Including a skill that does not exist: that is a real defect and it
        # is lint_agents.py's to report, not this file's to report twice.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "agents"))
        with open(os.path.join(self.root, "agents", "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: a\ndescription: Use when x.\nskills: [nope]\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 0, msgs)


class TheBootChain(TempTree):
    """hooks.json names the launcher and stops. The chain does not."""

    def test_the_program_the_launcher_starts_must_be_in_the_tree(self):
        # Measured on a copy of this repository: delete hooks/harness_hooks.py
        # and check() returned (0, []). run_hook.sh execs an interpreter
        # against that path, Python exits `can't open file` writing nothing to
        # stdout, and a scope gate that emits no decision does not gate.
        scaffold(self.root)
        os.remove(os.path.join(self.root, "hooks", "harness_hooks.py"))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("harness_hooks.py" in m for m in msgs), msgs)

    def test_what_that_program_imports_must_be_in_the_tree_too(self):
        # The fourth link, and the worst of them: harness_hooks.py imports
        # validate_verdict at module level, so its absence is not a degraded
        # closure gate, it is an ImportError before any subcommand runs --
        # all six hooks down at once.
        scaffold(self.root)
        os.remove(os.path.join(self.root, "scripts", "validate_verdict.py"))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("validate_verdict.py" in m for m in msgs), msgs)

    def test_a_package_declaring_no_hook_path_is_not_asked_for_the_chain(self):
        # The gate. These files belong to a package that runs hooks through
        # the plugin root; requiring them of one that does not would be this
        # checker inventing a defect. `{"hooks": {}}` still reads NOT MEASURED.
        scaffold(self.root, with_launcher=False, hooks={"hooks": {}},
                 with_boot_chain=False)
        self.assertEqual(C.check(self.root)[0], C.EXIT_NOT_MEASURED)

    def test_a_tree_missing_both_the_launcher_and_the_program_reports_both(self):
        # Gated on a plugin-root path being *named*, not resolved, which is
        # what keeps the second finding from hiding behind the first.
        scaffold(self.root, with_launcher=False, with_boot_chain=False)
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("run_hook.sh" in m for m in msgs), msgs)
        self.assertTrue(any("harness_hooks.py" in m for m in msgs), msgs)


class ExecFormHooks(TempTree):
    def test_a_typo_in_an_exec_form_hook_is_seen(self):
        # Reading only `command` meant an argv-form hook produced no referent
        # AND no warning: the recursion reached the list, every element was a
        # bare str, and a str node yields nothing. check() returned (0, []).
        scaffold(self.root, hooks={"hooks": {"Stop": [{"hooks": [
            {"type": "command",
             "args": ["sh", "${CLAUDE_PLUGIN_ROOT}/hooks/TYPO.sh", "x"]}]}]}})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("TYPO.sh" in m for m in msgs), msgs)

    def test_an_exec_form_hook_naming_a_real_file_passes(self):
        scaffold(self.root, hooks={"hooks": {"Stop": [{"hooks": [
            {"type": "command",
             "args": ["sh", "${CLAUDE_PLUGIN_ROOT}/hooks/run_hook.sh", "x"]}]}]}})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 0, msgs)


class Commands(TempTree):
    """The component a user invokes by name, and the one with no other reader.

    lint_skills walks skills/ and lint_agents walks agents/; nothing in the
    nine CI steps had ever opened commands/. The half of that gap which is a
    claim about prose -- the README promising `/appian-init` when no such file
    exists -- is check_readme_claims', not this file's. What is here is what
    the physical inventory can contradict on its own.

    The remaining half, plugin.json pointing `commands` at a path that is not
    there, needs nothing new: `commands` is one of COMPONENT_FIELDS and
    ManifestDeclaredPaths.test_a_component_path_plugin_json_declares_must_exist
    is already written on exactly that fixture.
    """

    def test_a_command_file_that_does_not_decode_is_reported(self):
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "commands"))
        with open(os.path.join(self.root, "commands", "appian-init.md"), "wb") as f:
            f.write(b"---\nname: appian-init\ndesc: \xff\xfe\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("commands/appian-init.md" in m for m in msgs), msgs)

    def test_a_directory_shipping_no_md_at_all_registers_no_command(self):
        # The shape the readability loop could not see: it selected `.md`
        # files and there were none, so a commands/ holding a renamed or
        # half-converted file contributed nothing to check and nothing to
        # report. A directory Claude Code scans and takes zero commands out of
        # is the same package-looks-healthy-and-does-nothing failure this file
        # opens by describing, one component along.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "commands"))
        open(os.path.join(self.root, "commands", "appian-init.txt"), "w").close()
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("no command registers" in m for m in msgs), msgs)
        self.assertTrue(any("appian-init.txt" in m for m in msgs), msgs)

    def test_a_package_shipping_no_commands_directory_is_not_a_finding(self):
        # The boundary, and the reason the rule above is not "commands/ must
        # exist": a plugin with no commands is a normal plugin, and unlike
        # hooks/ it leaves no orphaned code behind to contradict it. Absence
        # is only a defect against something that promised otherwise, and the
        # promise lives in prose.
        scaffold(self.root)
        self.assertFalse(os.path.exists(os.path.join(self.root, "commands")))
        self.assertEqual(C.check(self.root)[0], 0)

    def test_an_empty_commands_directory_is_not_a_finding(self):
        # Nothing shipped, nothing contradicted -- the same guard the hooks/
        # rule carries. An empty directory does not survive git anyway; what
        # would reach an install is the case above, where files are there and
        # none of them is a command.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "commands"))
        self.assertEqual(C.check(self.root)[0], 0)

    def test_a_namespaced_command_counts_as_registered(self):
        # commands/<namespace>/<name>.md is how a command gets a namespace,
        # so a package whose commands all live one level down registers plenty
        # of them. A top-level-only scan would have called that empty and
        # invented a finding, which is worse than the silence it replaced.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "commands", "appian"))
        with open(os.path.join(self.root, "commands", "appian", "init.md"), "w",
                  encoding="utf-8") as f:
            f.write("---\nname: init\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 0, msgs)

    def test_a_namespaced_command_file_is_read_like_any_other(self):
        # The other side of the recursion: counting a nested file as a
        # registered command while never opening it would trade one blind spot
        # for a narrower one.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "commands", "appian"))
        with open(os.path.join(self.root, "commands", "appian", "init.md"), "wb") as f:
            f.write(b"---\nname: init\ndesc: \xff\xfe\n---\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("commands/appian/init.md" in m for m in msgs), msgs)

    def test_a_command_file_that_leads_nowhere_is_reported(self):
        # `os.path.isfile` answers False for a dangling link and the loop used
        # to read that as "not a command file" and move on -- silence over a
        # name that is in the listing, ends in .md, and resolves to nothing.
        # Every other referent in this file goes through _referent_problem;
        # these two directories were the exception, for no reason but that
        # they were added last.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "commands"))
        if not link_dir(os.path.join(self.root, "commands", "appian-init.md"),
                        os.path.join(self.root, "no-such-target")):
            self.skipTest("this platform allows neither symlink nor junction")
        self.assertIn("appian-init.md", os.listdir(os.path.join(self.root, "commands")))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("dangling" in m for m in msgs), msgs)


class WhereTheNameActuallyLeads(TempTree):
    """A name in a listing is evidence of spelling and of nothing else."""

    def test_a_dangling_referent_is_not_a_present_one(self):
        # The defect a reviewer found: exists_exact never asked the
        # filesystem anything. os.listdir reports the name of a link whose
        # target does not exist, so a declared component directory that
        # pointed at nothing counted as present, raised the tally, emitted no
        # finding, and the checker could exit 0 over it.
        scaffold(self.root, plugin_extra={"skills": "./components"})
        if not link_dir(os.path.join(self.root, "components"),
                        os.path.join(self.root, "no-such-target")):
            self.skipTest("this platform allows neither symlink nor junction")
        self.assertIn("components", os.listdir(self.root))
        self.assertFalse(os.path.exists(os.path.join(self.root, "components")))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("dangling" in m for m in msgs), msgs)

    def test_a_referent_leading_outside_the_plugin_root_fails(self):
        # Spelled right, exists, and still not part of the package: an
        # install copies the tree, not whatever the tree points at. The
        # launcher is really there, so every check but containment passes.
        outside = self.elsewhere()
        open(os.path.join(outside, "run_hook.sh"), "w").close()
        with open(os.path.join(outside, "hooks.json"), "w", encoding="utf-8") as f:
            json.dump(MINIMAL_HOOKS, f)
        os.makedirs(os.path.join(self.root, ".claude-plugin"))
        with open(os.path.join(self.root, ".claude-plugin", "plugin.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"name": "p", "version": "1.0.0"}, f)
        if not link_dir(os.path.join(self.root, "hooks"), outside):
            self.skipTest("this platform allows neither symlink nor junction")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "hooks", "run_hook.sh")))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("outside the plugin root" in m for m in msgs), msgs)


class MalformedDeclarations(TempTree):
    def test_an_absolute_path_is_rejected_not_reinterpreted(self):
        # Silently dropping the leading slash would look up hooks/hooks.json
        # under the root, find it, and report OK about a declaration that on
        # a real install points at the filesystem root.
        scaffold(self.root, plugin_extra={"hooks": "/hooks/hooks.json"})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("absolute path" in m for m in msgs), msgs)

    def test_a_windows_drive_letter_is_rejected_too(self):
        scaffold(self.root, plugin_extra={"commands": "C:/cmds"})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("absolute path" in m for m in msgs), msgs)

    def test_a_declaration_climbing_out_with_dotdot_is_rejected(self):
        scaffold(self.root, plugin_extra={"commands": "../cmds"})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("climbs out" in m for m in msgs), msgs)


class ManifestDeclaredPaths(TempTree):
    def test_a_component_path_plugin_json_declares_must_exist(self):
        # plugin.json may point Claude Code somewhere other than the
        # conventional directory. Point it at nothing and the components do
        # not fail to load -- as far as the session is concerned they were
        # never declared, which looks exactly like not having written them.
        scaffold(self.root, plugin_extra={"commands": "./cmds"})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("cmds" in m for m in msgs), msgs)

    def test_hook_code_with_nothing_declaring_it_fails(self):
        # Measured against a copy of this repository: delete hooks/hooks.json
        # and check() returned (0, []). Six hooks left the package and the
        # checker whose whole subject is hooks that never run said nothing.
        scaffold(self.root)
        os.remove(os.path.join(self.root, "hooks", "hooks.json"))
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("no hooks manifest declares" in m for m in msgs), msgs)

    def test_a_plugin_that_ships_no_hooks_at_all_is_not_a_failure(self):
        # The other half, and the reason the rule is not "hooks.json must
        # exist": shipping no hooks is a normal thing for a plugin to do. The
        # contradiction is code with nothing invoking it, not absence.
        os.makedirs(os.path.join(self.root, ".claude-plugin"))
        with open(os.path.join(self.root, ".claude-plugin", "plugin.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"name": "p", "version": "1.0.0"}, f)
        os.makedirs(os.path.join(self.root, "skills", "real"))
        open(os.path.join(self.root, "skills", "real", "SKILL.md"), "w").close()
        code, msgs = C.check(self.root)
        self.assertEqual(code, 0, msgs)

    def test_a_declared_hooks_manifest_that_is_absent_is_reported(self):
        # Already true before this test existed -- `hooks` is one of
        # COMPONENT_FIELDS, so the declared path goes through the same loop
        # as every other declared path. Pinned here because "it happens to
        # work" and "it is held to working" are different states.
        scaffold(self.root, hooks=None, plugin_extra={"hooks": "./gone.json"})
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("gone.json" in m for m in msgs), msgs)

    def test_a_declared_hooks_manifest_is_the_one_that_gets_walked(self):
        # Checking hooks/hooks.json by convention while plugin.json points at
        # another file would validate a manifest Claude Code never loads.
        scaffold(self.root, hooks=None, plugin_extra={"hooks": "./elsewhere.json"})
        with open(os.path.join(self.root, "elsewhere.json"), "w", encoding="utf-8") as f:
            json.dump({"hooks": {"Stop": [{"hooks": [
                {"type": "command",
                 "command": 'sh "${CLAUDE_PLUGIN_ROOT}/hooks/absent.sh"'}]}]}}, f)
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("absent.sh" in m for m in msgs), msgs)


class ThisRepository(unittest.TestCase):
    def test_the_shipped_tree_is_intact(self):
        code, msgs = C.check(REAL_ROOT)
        self.assertEqual(code, 0, "\n".join(msgs))


if __name__ == "__main__":
    unittest.main()
