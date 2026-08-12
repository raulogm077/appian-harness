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


def scaffold(root, with_launcher=True, plugin_extra=None, hooks=MINIMAL_HOOKS):
    os.makedirs(os.path.join(root, "hooks"))
    os.makedirs(os.path.join(root, ".claude-plugin"))
    if hooks is not None:
        with open(os.path.join(root, "hooks", "hooks.json"), "w", encoding="utf-8") as f:
            json.dump(hooks, f)
    if with_launcher:
        open(os.path.join(root, "hooks", "run_hook.sh"), "w").close()
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
        # asymmetry isfile_exact exists to stop.
        scaffold(self.root, with_launcher=False)
        open(os.path.join(self.root, "hooks", "Run_Hook.sh"), "w").close()
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1, msgs)
        self.assertTrue(any("run_hook.sh" in m for m in msgs), msgs)

    def test_isfile_exact_reads_the_listing_not_the_filesystem_s_opinion(self):
        # Stated directly as well as through check(), so a regression points
        # at the function rather than at whichever caller noticed first.
        os.makedirs(os.path.join(self.root, "hooks"))
        open(os.path.join(self.root, "hooks", "Run_Hook.sh"), "w").close()
        self.assertTrue(C.isfile_exact(self.root, "hooks/Run_Hook.sh"))
        self.assertFalse(C.isfile_exact(self.root, "hooks/run_hook.sh"))
        self.assertFalse(C.isfile_exact(self.root, "Hooks/Run_Hook.sh"))


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
