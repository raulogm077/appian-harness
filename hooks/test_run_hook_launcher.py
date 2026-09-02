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
               "state-gate", "failure-notice")


def run(subcommand, project_root, starve=False, payload=None, extra_env=None):
    """Invoke the launcher exactly as hooks.json does.

    `starve` empties PATH so no python3/python/py can be found, which is the
    degraded branch. On Windows the shell itself lives on PATH, so the
    directory holding `sh` is kept -- otherwise the test would measure the
    shell failing to start rather than the script's answer.
    """
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = project_root
    # Hermetic by default: the launcher caches its interpreter probe under
    # XDG_CACHE_HOME, and tests must not write into the user's real cache.
    env["XDG_CACHE_HOME"] = os.path.join(project_root, "xdg-cache")
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


@unittest.skipIf(SH is None, "no POSIX shell available to run the launcher")
@unittest.skipIf(SKIP_SLOW, SKIP_REASON)
class TestTheInterpreterCache(unittest.TestCase):
    """The probe is paid once per user, not once per gated call.

    The cache may only ever run the three literal candidates, so a tampered
    entry is a miss, never a command; and a resolution that no longer holds
    re-probes instead of failing."""

    def _fake_bin(self, root):
        """A logging `python3` that satisfies the probe and says when it ran."""
        bindir = os.path.join(root, "fakebin")
        os.makedirs(bindir, exist_ok=True)
        log = os.path.join(root, "fake-python.log")
        path = os.path.join(bindir, "python3")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write("#!/bin/sh" + chr(10) + 'printf %s'
                    + chr(92) + chr(92) + "n " + '"$*" >> "'
                    + log.replace(os.sep, "/") + '"' + chr(10) + "exit 0" + chr(10))
        os.chmod(path, 0o755)
        return bindir, log

    def _env(self, bindir):
        # OS unset takes the POSIX probe order, so the fake python3 is the
        # first candidate on every platform this test runs on.
        return {"OS": "", "PATH": bindir + os.pathsep + os.environ.get("PATH", "")}

    def _cache_file(self, project_root):
        return os.path.join(project_root, "xdg-cache", "appian-harness",
                            "interpreter.v1")

    def _log_lines(self, log):
        if not os.path.isfile(log):
            return []
        with open(log, encoding="utf-8") as f:
            return [l for l in f.read().splitlines() if l.strip()]

    def test_the_second_run_skips_the_probe(self):
        with tempfile.TemporaryDirectory() as t:
            bindir, log = self._fake_bin(t)
            run("scope-gate", t, extra_env=self._env(bindir))
            first = self._log_lines(log)
            run("scope-gate", t, extra_env=self._env(bindir))
            second = self._log_lines(log)
            probes = [l for l in second if "-c" in l.split()]
            self.assertEqual(len(first), 2, first)   # probe + real run
            self.assertEqual(len(second), 3, second) # + real run only
            self.assertEqual(len(probes), 1, second) # no second probe

    def test_a_stale_resolution_reprobes_and_heals_the_cache(self):
        with tempfile.TemporaryDirectory() as t:
            bindir, log = self._fake_bin(t)
            cache = self._cache_file(t)
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8", newline="") as f:
                f.write("python3" + chr(10) + "/nonexistent/python3" + chr(10))
            p = run("scope-gate", t, extra_env=self._env(bindir))
            self.assertEqual(p.returncode, 0)
            probes = [l for l in self._log_lines(log) if "-c" in l.split()]
            self.assertEqual(len(probes), 1)  # it re-probed
            with open(cache, encoding="utf-8") as f:
                healed = f.read().splitlines()
            self.assertEqual(healed[0], "python3")
            self.assertNotEqual(healed[1], "/nonexistent/python3")

    def test_a_tampered_cache_is_a_miss_never_a_command(self):
        with tempfile.TemporaryDirectory() as t:
            marker = os.path.join(t, "evil-ran")
            evil = os.path.join(t, "evil")
            with open(evil, "w", encoding="utf-8", newline="") as f:
                f.write("#!/bin/sh" + chr(10) + 'touch "'
                        + marker.replace(os.sep, "/") + '"' + chr(10))
            os.chmod(evil, 0o755)
            cache = self._cache_file(t)
            os.makedirs(os.path.dirname(cache), exist_ok=True)
            with open(cache, "w", encoding="utf-8", newline="") as f:
                f.write(evil.replace(os.sep, "/") + chr(10)
                        + evil.replace(os.sep, "/") + chr(10))
            p = run("scope-gate", t)
            self.assertEqual(p.returncode, 0)
            json.loads(p.stdout)  # the real probe still answered
            self.assertFalse(os.path.exists(marker),
                             "a tampered cache entry was executed")

    def test_an_unwritable_cache_location_is_harmless(self):
        with tempfile.TemporaryDirectory() as t:
            blocker = os.path.join(t, "not-a-dir")
            with open(blocker, "w", encoding="utf-8") as f:
                f.write("file, so mkdir -p under it fails")
            p = run("scope-gate", t,
                    extra_env={"XDG_CACHE_HOME": os.path.join(blocker, "xdg")})
            self.assertEqual(p.returncode, 0)
            json.loads(p.stdout)


if __name__ == "__main__":
    unittest.main()
