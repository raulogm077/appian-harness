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

So this does not inspect the command. It runs it, against a real `sh`, and
checks both answers the README promises. Two properties fall out of doing it
that way rather than by pattern:

- **A published block has to define the variables it uses.** The substitution
  below looks for `HARNESS=` and `PROJ=` and fails when either is missing --
  which is precisely the shape of the defect, whatever variable name a future
  edit reaches for.
- **The payload has to be one the gate classifies as a write.** The second
  case asserts `ask`, and a `tool_name` whose server segment does not name
  Appian answers `allow` / `not a write tool` instead. That was the older bug,
  living in `docs/troubleshooting.md`: prose promising `ask` attached to a
  payload that could never produce it.
"""
import json
import os
import re
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
README = os.path.join(PLUGIN_ROOT, "README.md")

FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
ASSIGN_RE = re.compile(r"^(HARNESS|PROJ)=")


def _posix(path):
    """A path Python can resolve from inside a shell-quoted JSON payload.

    `cwd` is read by Python, not by the shell, so on Windows it has to stay a
    native `C:/...` path. Forward slashes rather than backslashes because the
    value is about to sit inside double quotes in `sh`, where a backslash is
    an escape character and `C:\\Users` quietly becomes `C:Users`.
    """
    return path.replace("\\", "/")


def documented_blocks():
    with open(README, encoding="utf-8") as f:
        return [b for b in FENCE_RE.findall(f.read()) if "run_hook.sh" in b]


def runnable(block, harness, proj):
    """The published block with its placeholder paths pointed at real ones.

    Returns (script, defined). `defined` is what the block assigned for
    itself; a block that assigns neither is a block the reader cannot run,
    which is the whole failure being guarded against.
    """
    out, defined = [], set()
    for line in block.splitlines():
        match = ASSIGN_RE.match(line)
        if match:
            name = match.group(1)
            defined.add(name)
            out.append('%s="%s"' % (name, harness if name == "HARNESS" else proj))
        else:
            out.append(line)
    return "\n".join(out), defined


def decision(stdout):
    return json.loads(stdout)["hookSpecificOutput"]


@unittest.skipIf(SH is None, "no POSIX shell available to run the probe")
@unittest.skipIf(SKIP_SLOW, SKIP_REASON)
class TestTheReadmeProbeRuns(unittest.TestCase):
    """What the README hands a reader has to work when they paste it."""

    def setUp(self):
        blocks = documented_blocks()
        # Not `[0]`. If a second runnable probe ever appears, this test is
        # silently checking one of them and reporting on both, which is the
        # kind of partial coverage that reads as complete.
        self.assertEqual(
            1, len(blocks),
            "README.md should hold exactly one fenced block invoking "
            "run_hook.sh; found %d. Teach this test which one is the probe "
            "before adding another." % len(blocks))
        self.block = blocks[0]

    def _run(self, project_root):
        script, defined = runnable(self.block, _posix(PLUGIN_ROOT), _posix(project_root))
        self.assertEqual(
            {"HARNESS", "PROJ"}, defined,
            "the published probe must assign the paths it expands, because a "
            "reader has neither in their environment: CLAUDE_PLUGIN_ROOT is "
            "substituted inside hooks.json and is empty in a shell, and $PWD "
            "under Git Bash is an MSYS path the gate cannot resolve. Missing: "
            "%s" % sorted({"HARNESS", "PROJ"} - defined))
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
        with tempfile.TemporaryDirectory() as project:
            answer = decision(self._run(project))
            self.assertEqual("allow", answer["permissionDecision"])
            self.assertIn("not configured", answer["permissionDecisionReason"])

    def test_adopted_project_with_no_active_task_answers_ask(self):
        # The assertion that catches a payload the gate does not treat as a
        # write. WRITE_TOOL_RE requires `^mcp__...[Aa]ppian...__`, so a
        # tool_name like `mcp__x__createInterface` answers `allow` with the
        # reason `not a write tool`: still JSON, so the hook is provably
        # alive, and the wrong answer to the question the reader is asking.
        with tempfile.TemporaryDirectory() as project:
            os.makedirs(os.path.join(project, ".claude"))
            with open(os.path.join(project, ".claude", "appian-harness.json"),
                      "w", encoding="utf-8") as f:
                json.dump({"evidenceDir": "evidence"}, f)
            answer = decision(self._run(project))
            self.assertEqual(
                "ask", answer["permissionDecision"],
                "an adopted project with no active task must ask; got %r with "
                "the reason %r" % (answer["permissionDecision"],
                                   answer["permissionDecisionReason"]))


if __name__ == "__main__":
    unittest.main()
