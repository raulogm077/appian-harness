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


class TempTree(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)


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

    def test_an_agent_frontmatter_naming_a_missing_skill_fails(self):
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "agents"))
        with open(os.path.join(self.root, "agents", "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: a\ndescription: Use when x.\nskills: [nope]\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("nope" in m for m in msgs), msgs)

    def test_a_block_style_skills_list_is_read_too(self):
        # YAML accepts both spellings, and the checker that only knows the
        # inline one reports agreement about a list it never read -- the
        # silent pass this repository treats as worse than a loud failure.
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "agents"))
        with open(os.path.join(self.root, "agents", "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: a\ndescription: Use when x.\nskills:\n"
                    "  - nope\n  - alsonope\ntools: Read\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("nope" in m for m in msgs), msgs)
        self.assertTrue(any("alsonope" in m for m in msgs), msgs)

    def test_an_agent_naming_a_skill_that_exists_passes(self):
        scaffold(self.root)
        os.makedirs(os.path.join(self.root, "skills", "real"))
        open(os.path.join(self.root, "skills", "real", "SKILL.md"), "w").close()
        os.makedirs(os.path.join(self.root, "agents"))
        with open(os.path.join(self.root, "agents", "a.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: a\ndescription: Use when x.\nskills: [real]\n---\nbody\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 0, msgs)


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
