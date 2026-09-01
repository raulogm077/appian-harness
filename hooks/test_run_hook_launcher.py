"""The launcher answers when the program cannot start.

A hook whose command cannot be found does not ask and does not block: it does
not run, and the plugin looks healthy while enforcing nothing. These run the
real `run_hook.sh` through a real `sh`, with the interpreter search starved.
"""
import json, os, shutil, subprocess, sys, tempfile, unittest

HOOKS = os.path.dirname(os.path.abspath(__file__))
PLUGIN_ROOT = os.path.dirname(HOOKS)
SCRIPT = os.path.join(HOOKS, "run_hook.sh")


def _find_shell():
    """A POSIX shell, including where Git for Windows actually puts one.

    `shutil.which("sh")` is not enough on Windows, for the reason
    `run_hook.sh` is written around: Git for Windows puts git.exe on PATH via
    `Git\\cmd` and leaves sh.exe in `Git\\bin` and `Git\\usr\\bin`, neither
    usually on PATH. Giving up there would skip precisely on the platform
    whose failure mode this launcher exists to survive.
    """
    found = shutil.which("sh") or shutil.which("bash")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Git\bin\sh.exe",
        r"C:\Program Files\Git\usr\bin\sh.exe",
        r"C:\Program Files (x86)\Git\bin\sh.exe",
        "/bin/sh",
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


SH = _find_shell()

# Measured on Windows: ~3.8s per starved invocation and ~8.5s with an
# interpreter, nearly all of it Git Bash and Python startup. Across the cases
# below that is minutes -- right for CI, too slow for the edit loop. So the
# default is to run them and the fast loop is an explicit opt-out:
#
#     APPIAN_HARNESS_SKIP_SLOW=1 python -m unittest discover -s hooks
#
# CI never sets it.
SKIP_SLOW = os.environ.get("APPIAN_HARNESS_SKIP_SLOW") == "1"
SKIP_REASON = ("APPIAN_HARNESS_SKIP_SLOW=1: launcher subprocess tests skipped. "
               "Unset it before trusting a release.")

SUBCOMMANDS = ("session-start", "scope-gate", "closure-gate", "log-write",
               "log-evidence-write", "failure-notice")


def run(subcommand, project_root, starve=False, payload=None, extra_env=None):
    """Invoke the launcher exactly as hooks.json does.

    `starve` empties PATH so no python3/python/py can be found, which is the
    degraded branch. On Windows the shell itself lives on PATH, so the
    directory holding `sh` is kept -- otherwise the test would measure the
    shell failing to start rather than the script's answer.
    """
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = project_root
    if starve:
        keep = os.path.dirname(SH) if os.name == "nt" else ""
        env["PATH"] = keep
        env.pop("PYTHONHOME", None)
    if extra_env:
        env.update(extra_env)
    body = json.dumps(payload if payload is not None else {"cwd": project_root})
    # 180s, not 60s: a Git Bash spawn plus an interpreter probe is seconds on
    # an idle Windows box and considerably more when the machine is busy. A
    # timeout that fires under load measures the machine, not the launcher.
    proc = subprocess.run([SH, SCRIPT, PLUGIN_ROOT, subcommand],
                          input=body, capture_output=True, text=True, env=env, timeout=180)
    return proc


def configured(root):
    os.makedirs(os.path.join(root, ".claude"), exist_ok=True)
    with open(os.path.join(root, ".claude", "appian-harness.json"), "w",
              encoding="utf-8") as f:
        json.dump({"evidenceDir": "evidence"}, f)


@unittest.skipIf(SH is None, "no POSIX shell available to run the launcher")
@unittest.skipIf(SKIP_SLOW, SKIP_REASON)
class TestLauncherWithNoInterpreter(unittest.TestCase):
    """Rule 3 still holds in the degraded branch, and so does fail-closed."""

    def test_every_subcommand_still_emits_valid_json(self):
        # A hook that prints nothing, or prints something unparseable, is a
        # hook that silently did not run.
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            for sub in SUBCOMMANDS:
                p = run(sub, t, starve=True)
                self.assertEqual(p.returncode, 0, "%s exited %d" % (sub, p.returncode))
                try:
                    json.loads(p.stdout)
                except ValueError:
                    self.fail("%s emitted unparseable output: %r" % (sub, p.stdout))

    def test_an_unconfigured_project_is_never_obstructed(self):
        # The plugin installed in a project that does not use it must not
        # get in the way, interpreter or no interpreter.
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(
                json.loads(run("scope-gate", t, starve=True).stdout)
                ["hookSpecificOutput"]["permissionDecision"], "allow")
            self.assertEqual(json.loads(run("closure-gate", t, starve=True).stdout),
                             {"decision": "approve"})
            self.assertEqual(json.loads(run("session-start", t, starve=True).stdout), {})

    def test_a_configured_project_is_told_the_gate_did_not_run(self):
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            out = json.loads(run("scope-gate", t, starve=True).stdout)["hookSpecificOutput"]
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("Python 3", out["permissionDecisionReason"])

    def test_the_requirements_check_refuses_to_go_quiet(self):
        # Silence here would read as "all three links are present", which
        # is the false reassurance it exists to prevent.
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            ctx = json.loads(run("session-start", t, starve=True).stdout)
            self.assertIn("additionalContext", ctx["hookSpecificOutput"])

    def test_the_first_stop_blocks_and_a_repeat_stop_approves_loudly(self):
        # A Stop hook has only approve and block. Blocking forever is the
        # deadlock that gets a guardrail switched off, so it mirrors the
        # Python path: block once, then approve saying nothing was checked.
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            first = json.loads(run("closure-gate", t, starve=True).stdout)
            self.assertEqual(first["decision"], "block")
            repeat = json.loads(run("closure-gate", t, starve=True,
                                    payload={"cwd": t, "stop_hook_active": True}).stdout)
            self.assertEqual(repeat["decision"], "approve")
            self.assertIn("UNMEASURED", repeat["systemMessage"])

    def test_an_unknown_subcommand_is_inert_rather_than_noisy(self):
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            p = run("no-such-subcommand", t, starve=True)
            self.assertEqual(p.returncode, 0)
            self.assertEqual(json.loads(p.stdout), {})


@unittest.skipIf(SH is None, "no POSIX shell available to run the launcher")
@unittest.skipIf(SKIP_SLOW, SKIP_REASON)
class TestLauncherWithAnInterpreter(unittest.TestCase):
    """With Python present the launcher must get out of the way entirely."""

    def test_it_reaches_the_python_gate_and_returns_its_decision(self):
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            out = json.loads(run("scope-gate", t, payload={
                "cwd": t, "tool_name": "mcp__appian-dev__createRecordType",
                "tool_input": {"name": "A"}}).stdout)["hookSpecificOutput"]
            # No active task in this project, so the real gate asks -- and
            # the wording is the Python path's, not the launcher's fallback.
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertNotIn("Python 3", out["permissionDecisionReason"])
            self.assertIn("no active task", out["permissionDecisionReason"])

    def test_a_read_still_passes_straight_through_the_real_gate(self):
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            out = json.loads(run("scope-gate", t, payload={
                "cwd": t, "tool_name": "mcp__appian-dev__getRecordType",
                "tool_input": {"name": "A"}}).stdout)["hookSpecificOutput"]
            self.assertEqual(out["permissionDecision"], "allow")
            self.assertEqual(out["permissionDecisionReason"], "not a write tool")

    def test_it_does_not_write_bytecode_into_the_installed_plugin(self):
        # A plugin that grows __pycache__ stops being comparable with
        # `git ls-files`, which is how anyone checks what they are running.
        before = set()
        for base, dirs, _ in os.walk(PLUGIN_ROOT):
            before.update(os.path.join(base, d) for d in dirs if d == "__pycache__")
        with tempfile.TemporaryDirectory() as t:
            configured(t)
            run("scope-gate", t)
        after = set()
        for base, dirs, _ in os.walk(PLUGIN_ROOT):
            after.update(os.path.join(base, d) for d in dirs if d == "__pycache__")
        self.assertEqual(after - before, set())

    def test_an_unconfigured_project_is_allowed_through_the_python_path_too(self):
        with tempfile.TemporaryDirectory() as t:
            out = json.loads(run("scope-gate", t).stdout)["hookSpecificOutput"]
            self.assertEqual(out["permissionDecision"], "allow")
            self.assertIn("not configured", out["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
