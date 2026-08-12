"""The probe the README tells a reader to run, actually run.

`0.5.0` published a liveness check on the way in -- the command that answers
"are my gates alive?" -- and nobody had ever executed it. It expanded
`$CLAUDE_PLUGIN_ROOT`, which Claude Code substitutes inside `hooks.json` and
which is empty in a reader's shell, so the whole thing was `sh
/hooks/run_hook.sh` and exited 127. It also passed `cwd` as `$PWD`, which Git
Bash renders `/c/...` and the gate cannot resolve, so on Windows it would have
answered "not configured" for every project including a governed one.

466 tests passed while that shipped, because not one of them ran a command out
of the documentation. A lint was the first idea and the corpus refused it:
`${CLAUDE_PLUGIN_ROOT}` appears legitimately in eight places across `skills/`
and `agents/`, where the surrounding text already says to resolve it by hand,
and once in `docs/troubleshooting.md` where the recipe assigns it. A rule that
flagged those is a rule people learn to scroll past, which is the argument
`ci.yml` makes against restating checks.

So this does not inspect the command. It runs it, against a real `sh`, in both
documents that publish one, and checks both answers the prose promises. Four
defects fall out of executing rather than pattern-matching, and each was
confirmed by putting it back and watching this go red:

- **A published block has to spell out the paths it expands.** The
  substitution looks for `HARNESS=`, `PROJ=` or the `/abs/path/to/...`
  placeholders and fails naming whichever never resolved -- the shape of the
  `0.5.0` bug, whatever variable a later edit reaches for.
- **The payload has to be one the gate classifies as a write.** A `tool_name`
  whose server segment does not name Appian answers `allow` / `not a write
  tool`, so the `ask` case fails on it. That was the older bug in
  `docs/troubleshooting.md`: prose promising `ask` attached to a payload that
  could never produce it.
- **The launcher has to be named absolutely.** That same block invoked
  `hooks/run_hook.sh` relative, which resolves only from inside the checkout
  -- not where a reader stands when they have a project to ask about, and the
  surrounding text never told them to move.
- **Both paths have to be quoted.** Unquoted, the probe splits on the first
  space. This one is why the fixtures below build directories whose names
  contain spaces instead of accepting whatever `tempfile` hands over: it
  failed on the author's checkout, under `Proyecto Claude Code Cowork`, and
  would have passed on a GitHub runner forever.
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

# One shell-finder, not two. `test_run_hook_launcher` already had to work out
# where Git for Windows hides `sh.exe`, and a second copy of that knowledge is
# a second thing to drift -- the same reason `EXIT_NOT_MEASURED` lives in one
# module and is asserted by a tree scan rather than by six equal constants.
from test_run_hook_launcher import SH, SKIP_REASON, SKIP_SLOW

HOOKS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HOOKS)

# Both documents, because the payload bug lived in the one the README copied
# from. Two copies of a probe are two things that drift, and a regression test
# covering one of them is the half-coverage this plugin keeps arguing against.
PROBE_DOCS = ("README.md", os.path.join("docs", "troubleshooting.md"))

FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
ASSIGN_RE = re.compile(r"^(HARNESS|PROJ)=")

# Not every block invoking the launcher is a probe, and running the rest would
# make this cry wolf. `docs/troubleshooting.md` also holds a 26-line recipe
# that builds a project first, and a one-liner continuing it that reads
# `$PAYLOAD` from the block above; `SECURITY.md` quotes the hooks.json command
# line with a literal `<subcommand>`, to describe it rather than to be run.
# A probe is the block that asks the gate one question and carries its own
# payload -- so: a tool_name, and no state built on the way.
def _is_probe(block):
    return ("run_hook.sh" in block
            and '"tool_name"' in block
            and "mkdir" not in block)


def _posix(path):
    """A path Python can resolve from inside a shell-quoted JSON payload.

    `cwd` is read by Python, not by the shell, so on Windows it has to stay a
    native `C:/...` path. Forward slashes rather than backslashes because the
    value is about to sit inside double quotes in `sh`, where a backslash is
    an escape character and `C:\\Users` quietly becomes `C:Users`.
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
    `resolved` says which paths the block made substitutable. A block that
    resolves neither is a block the reader cannot run, which is the whole
    failure being guarded against.
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


# Both sides of every probe are given a directory whose name contains a space,
# on purpose. The unquoted form in `docs/troubleshooting.md` failed here and
# would have passed on CI forever: a GitHub runner checks out to
# `/home/runner/work/appian-harness/appian-harness`, and the defect only
# appears when a path has a space in it. `C:/Users/you/My Documents/…` is an
# ordinary place to keep a checkout, so the test supplies what the runner
# cannot.
SPACED_HARNESS = "a harness with spaces"
SPACED_PROJECT = "a project with spaces"


def spaced_copy_of_the_plugin(tmp):
    """The launcher and what it imports, under a path containing a space.

    `run_hook.sh` launches `$PLUGIN_ROOT/hooks/harness_hooks.py`, which imports
    `validate_verdict` out of `scripts/`, and the program reads its version
    from `.claude-plugin/`. Those three, and no more: copying is what makes
    the harness side of the quoting testable on a runner whose own checkout
    path is well behaved.
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
        # One per document, asserted rather than assumed. A third appearing
        # means somebody added a probe this test is silently not running,
        # which is the partial coverage that reads as complete.
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
        # No `cwd=`: a probe that only runs from one directory is a probe that
        # fails for the reader standing in their own project, and nothing in
        # the surrounding prose tells them to move.
        proc = subprocess.run([SH, "-c", script], capture_output=True,
                              text=True, timeout=180)
        self.assertEqual(
            0, proc.returncode,
            "the documented probe did not run: exit %d\nstdout: %s\nstderr: %s"
            % (proc.returncode, proc.stdout.strip(), proc.stderr.strip()))
        return proc.stdout

    def test_unconfigured_project_answers_allow_and_says_why(self):
        # Path 1 in the README: the plugin is installed and this project never
        # asked to be governed. The gate has to say so rather than stay quiet,
        # because "allow" with no reason is indistinguishable from a hook that
        # never ran -- which is the question the probe exists to settle.
        for doc, block in self.probes:
            with self.subTest(doc=doc), tempfile.TemporaryDirectory() as tmp:
                project = os.path.join(tmp, SPACED_PROJECT)
                os.makedirs(project)
                answer = decision(self._run(block, spaced_copy_of_the_plugin(tmp), project))
                self.assertEqual("allow", answer["permissionDecision"])
                self.assertIn("not configured", answer["permissionDecisionReason"])

    def test_adopted_project_with_no_active_task_answers_ask(self):
        # The assertion that catches a payload the gate does not treat as a
        # write. WRITE_TOOL_RE requires `^mcp__...[Aa]ppian...__`, so a
        # tool_name like `mcp__x__createInterface` answers `allow` with the
        # reason `not a write tool`: still JSON, so the hook is provably
        # alive, and the wrong answer to the question the reader is asking.
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
    continues it in the next, which reads `$PAYLOAD` from the first. They are
    one script split by a paragraph, so they are run as one.
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

    It promised two answers and, followed exactly, produced neither: the
    payload was one the gate does not treat as a write, and the fixture was
    missing the skill-load record the gate opens before any write. Both were
    invisible to every reader for four releases and to 468 tests, for the same
    reason as the one-liner -- nobody ran it.
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
            # skills/appian-best-practices/, which the launcher itself does
            # not need -- but the gate resolves them before it will accept a
            # verdict, so the copy needs them too.
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
            # references the verdict cites, so it refuses to accept a verdict
            # it cannot check. That is the documented trap, and it is only
            # reachable once everything before it is satisfied -- which makes
            # this assertion a check on the whole fixture, not just the tail.
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
