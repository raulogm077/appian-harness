"""The liveness probe the documentation publishes, actually executed.

Invariant: a probe printed in README.md or docs/troubleshooting.md runs as
pasted, under a real `sh`, and answers what the prose promises. Background:
docs/design-notes.md § test_documented_probe.py · executed, not linted.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

# One shell-finder, not two: `test_run_hook_launcher` already locates where
# Git for Windows hides `sh.exe`, and a second copy would drift.
from test_run_hook_launcher import SH, SKIP_REASON, SKIP_SLOW

HOOKS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HOOKS)

# Both documents publish a probe and both are exercised: covering one of two
# copies is the half-coverage that reads as complete.
PROBE_DOCS = ("README.md", os.path.join("docs", "troubleshooting.md"))

FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
ASSIGN_RE = re.compile(r"^(HARNESS|PROJ)=")

# Not every block invoking the launcher is a probe: docs/troubleshooting.md
# also holds a recipe that builds a project first plus a one-liner continuing
# it from `$PAYLOAD`, and SECURITY.md quotes the hooks.json command line to
# describe it. A probe asks one question and carries its own payload -- so: a
# tool_name, and no state built on the way.
def _is_probe(block):
    return ("run_hook.sh" in block
            and '"tool_name"' in block
            and "mkdir" not in block)


def _posix(path):
    """A path Python can resolve from inside a shell-quoted JSON payload.

    `cwd` is read by Python, not by the shell, so on Windows it stays a native
    `C:/...` path -- forward slashes because inside double quotes in `sh` a
    backslash escapes and `C:\\Users` quietly becomes `C:Users`.
    """
    return path.replace("\\", "/")


def documented_probes():
    """Every liveness probe a reader could paste, keyed by the document."""
    found = []
    for relative in PROBE_DOCS:
        with open(os.path.join(PLUGIN_ROOT, relative), encoding="utf-8") as f:
            for block in FENCE_RE.findall(f.read()):
                if _is_probe(block):
                    found.append((relative.replace("\\", "/"), block))
    return found


def runnable(block, harness, proj):
    """The published block with its placeholder paths pointed at real ones.

    Two styles, because the two documents use two: the README assigns
    `HARNESS=` and `PROJ=` on their own lines, and `docs/troubleshooting.md`
    writes `/abs/path/to/...` inline. Returns (script, resolved), where
    `resolved` names the paths the block made substitutable; a block that
    resolves neither is a block the reader cannot run.
    """
    out, resolved = [], set()
    for line in block.splitlines():
        match = ASSIGN_RE.match(line)
        if match:
            name = match.group(1)
            resolved.add(name)
            out.append('%s="%s"' % (name, harness if name == "HARNESS" else proj))
            continue
        # Longest first: `/abs/path/to/appian-harness` contains no other
        # placeholder, but a shorter pattern replaced first would leave the
        # tail of a longer one behind.
        for placeholder, value, name in (
            ("/abs/path/to/appian-harness", harness, "HARNESS"),
            ("/abs/path/to/scratch-project", proj, "PROJ"),
            ("/abs/path/to/your-project", proj, "PROJ"),
            ("/abs/path/to/project", proj, "PROJ"),
        ):
            if placeholder in line:
                line = line.replace(placeholder, value)
                resolved.add(name)
        out.append(line)
    return "\n".join(out), resolved


def decision(stdout):
    return json.loads(stdout)["hookSpecificOutput"]


# Both sides of every probe get a directory whose name contains a space, on
# purpose: a GitHub runner checks out to a space-free path, so an unquoted
# probe passes there forever. See docs/design-notes.md
# § test_documented_probe.py · spaces in paths.
SPACED_HARNESS = "a harness with spaces"
SPACED_PROJECT = "a project with spaces"


def spaced_copy_of_the_plugin(tmp):
    """The launcher and what it imports, under a path containing a space.

    `run_hook.sh` launches `$PLUGIN_ROOT/hooks/harness_hooks.py`, which imports
    `validate_verdict` out of `scripts/`, and the program reads its version
    from `.claude-plugin/`. Those three parts and no more.
    """
    root = os.path.join(tmp, SPACED_HARNESS)
    os.makedirs(root)
    skip_caches = shutil.ignore_patterns("__pycache__")
    for part in ("hooks", "scripts", ".claude-plugin"):
        shutil.copytree(os.path.join(PLUGIN_ROOT, part),
                        os.path.join(root, part), ignore=skip_caches)
    return root


@unittest.skipIf(SH is None, "no POSIX shell available to run the probe")
@unittest.skipIf(SKIP_SLOW, SKIP_REASON)
class TestTheReadmeProbeRuns(unittest.TestCase):
    """What the README hands a reader has to work when they paste it."""

    def setUp(self):
        self.probes = documented_probes()
        # One per document, asserted rather than assumed: a third means
        # somebody added a probe this test is silently not running.
        self.assertEqual(
            [doc for doc, _ in self.probes],
            ["README.md", "docs/troubleshooting.md"],
            "expected exactly one liveness probe in each document; found %r. "
            "Teach this test about the new one before adding it."
            % [doc for doc, _ in self.probes])

    def _run(self, block, harness_root, project_root):
        script, resolved = runnable(block, _posix(harness_root), _posix(project_root))
        self.assertEqual(
            {"HARNESS", "PROJ"}, resolved,
            "a published probe must spell out both paths it needs, because "
            "the reader has neither: CLAUDE_PLUGIN_ROOT is substituted inside "
            "hooks.json and is empty in a shell, and $PWD under Git Bash is "
            "an MSYS path the gate cannot resolve. Unresolved: %s"
            % sorted({"HARNESS", "PROJ"} - resolved))
        # No `cwd=`: a probe that only runs from one directory fails the
        # reader standing in their own project, and the prose never says move.
        proc = subprocess.run([SH, "-c", script], capture_output=True,
                              text=True, timeout=180)
        self.assertEqual(
            0, proc.returncode,
            "the documented probe did not run: exit %d\nstdout: %s\nstderr: %s"
            % (proc.returncode, proc.stdout.strip(), proc.stderr.strip()))
        return proc.stdout

    def test_unconfigured_project_answers_allow_and_says_why(self):
        # Plugin installed, project never governed. The gate has to say so:
        # "allow" with no reason is indistinguishable from a hook that never
        # ran, which is the question the probe exists to settle.
        for doc, block in self.probes:
            with self.subTest(doc=doc), tempfile.TemporaryDirectory() as tmp:
                project = os.path.join(tmp, SPACED_PROJECT)
                os.makedirs(project)
                answer = decision(self._run(block, spaced_copy_of_the_plugin(tmp), project))
                self.assertEqual("allow", answer["permissionDecision"])
                self.assertIn("not configured", answer["permissionDecisionReason"])

    def test_adopted_project_with_no_active_task_answers_ask(self):
        # Catches a payload the gate does not treat as a write:
        # WRITE_TOOL_RE requires `^mcp__...[Aa]ppian...__`, so a tool_name
        # like `mcp__x__createInterface` answers `allow` / `not a write tool`
        # -- still JSON, so the hook looks alive, and still the wrong answer.
        for doc, block in self.probes:
            with self.subTest(doc=doc), tempfile.TemporaryDirectory() as tmp:
                project = os.path.join(tmp, SPACED_PROJECT)
                os.makedirs(os.path.join(project, ".claude"))
                with open(os.path.join(project, ".claude", "appian-harness.json"),
                          "w", encoding="utf-8") as f:
                    json.dump({"evidenceDir": "evidence"}, f)
                answer = decision(self._run(block, spaced_copy_of_the_plugin(tmp), project))
                self.assertEqual(
                    "ask", answer["permissionDecision"],
                    "an adopted project with no active task must ask; got %r "
                    "with the reason %r" % (answer["permissionDecision"],
                                            answer["permissionDecisionReason"]))


def recipe_blocks():
    """The two-block recipe that drives the gate all the way to `allow`.

    `docs/troubleshooting.md` builds a scratch project in one block and
    continues it in the next, which reads `$PAYLOAD` from the first: one
    script split by a paragraph, so they are run as one.
    """
    with open(os.path.join(PLUGIN_ROOT, "docs", "troubleshooting.md"),
              encoding="utf-8") as f:
        blocks = FENCE_RE.findall(f.read())
    build = [b for b in blocks if "mkdir" in b and "run_hook.sh" in b]
    finish = [b for b in blocks if "CLAUDE_PLUGIN_ROOT=" in b and "$PAYLOAD" in b]
    return build, finish


@unittest.skipIf(SH is None, "no POSIX shell available to run the recipe")
@unittest.skipIf(SKIP_SLOW, SKIP_REASON)
class TestTheFullChainRecipeRuns(unittest.TestCase):
    """The recipe for seeing the whole chain has to produce the chain.

    Followed exactly, it reaches `ask` then `allow`: the payload has to be one
    the gate treats as a write, and the fixture has to carry the skill-load
    record the gate opens before any write.
    """

    def test_the_recipe_reaches_ask_then_allow(self):
        build, finish = recipe_blocks()
        self.assertEqual((1, 1), (len(build), len(finish)),
                         "expected one build block and one continuation in "
                         "docs/troubleshooting.md; found %d and %d"
                         % (len(build), len(finish)))
        with tempfile.TemporaryDirectory() as tmp:
            project = os.path.join(tmp, SPACED_PROJECT)
            harness = spaced_copy_of_the_plugin(tmp)
            # The references the verdict cites live under
            # skills/appian-best-practices/: the launcher does not need them,
            # but the gate resolves them before accepting a verdict.
            shutil.copytree(os.path.join(PLUGIN_ROOT, "skills"),
                            os.path.join(harness, "skills"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            script, resolved = runnable(build[0] + "\n" + finish[0],
                                        _posix(harness), _posix(project))
            self.assertEqual({"HARNESS", "PROJ"}, resolved)
            proc = subprocess.run([SH, "-c", script], capture_output=True,
                                  text=True, timeout=180)
            self.assertEqual(0, proc.returncode,
                             "the recipe did not run: %s" % proc.stderr.strip())
            answers = [json.loads(line)["hookSpecificOutput"]
                       for line in proc.stdout.strip().splitlines() if line.strip()]
            self.assertEqual(2, len(answers),
                             "the recipe probes twice; got %d answer(s): %s"
                             % (len(answers), proc.stdout.strip()))

            # Without CLAUDE_PLUGIN_ROOT the gate cannot resolve the
            # references the verdict cites, so it refuses a verdict it cannot
            # check -- the documented trap, reachable only once everything
            # before it is satisfied, so this checks the whole fixture.
            self.assertEqual("ask", answers[0]["permissionDecision"])
            self.assertIn("no pluginRoot configured",
                          answers[0]["permissionDecisionReason"])

            self.assertEqual("allow", answers[1]["permissionDecision"],
                             "the recipe promises the whole chain clears; got "
                             "%r" % answers[1]["permissionDecisionReason"])
            self.assertIn("scope and design audit check out",
                          answers[1]["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
