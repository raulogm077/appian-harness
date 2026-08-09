"""Holds the README to what the repository actually contains.

Counts in prose drift. This plugin's drifted three times in one working
session — hooks, skills, test totals — and a reader caught it every time,
a check caught it never. Which is the same argument the plugin makes about
Appian evidence, turned on the plugin: a claim nobody can check is a claim
that quietly stops being true.

So anything the README asserts about its own repository becomes a fact a
machine holds:

- the number of hooks `hooks.json` declares,
- the test totals for `scripts/` and `hooks/`,
- every config key the hooks read being documented,
- every skill directory being mentioned,
- every append-only log the code writes being listed.

Deliberately narrow. It checks claims with a **mechanical referent** and
says nothing about whether the prose is any good — that needs a reader, and
pretending otherwise would be the vacuous green this plugin argues against.

    python3 scripts/check_readme_claims.py [--root .]

Exit 0 agreement, 1 disagreement (naming each), 2 usage.
"""
import glob
import json
import os
import re
import subprocess
import sys

# The README writes small numbers as words, which reads better and is
# exactly as checkable once you say so.
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

# Keys the hooks compute for themselves rather than read out of a project's
# config file. Everything else a `config.get("...")` names is a key a person
# writes, and therefore a key the README's list has to contain.
#
# Written out rather than derived from `_build_config`'s dict literal, and
# the direction of a mistake is why. Forget one here and the check reports a
# derived key as undocumented -- noise, loud, fixed in a minute. Derive the
# set instead and it silently excuses `maxAllowedObjects`, which appears in
# both places, which is the bug this list exists to have caught.
DERIVED_CONFIG_KEYS = ("activeTask", "configPath", "mcpServers", "pluginRoot", "projectRoot")


def _as_int(token):
    return WORDS.get(token.lower(), None) if not token.isdigit() else int(token)


def _ran_count(root, directory):
    """How many tests a suite actually runs. The slow launcher subprocess
    tests are skipped here — skips still count in unittest's "Ran N", so
    the total is stable either way and this keeps the check quick."""
    # The marker breaks a recursion that is easy to create and hard to see:
    # this spawns `unittest discover -s scripts`, and that discovery contains
    # this checker's own tests, one of which calls check() on the real
    # repository -- which spawns the suite again, forever. The nested run
    # sees the marker and skips that one test.
    env = dict(os.environ, APPIAN_HARNESS_SKIP_SLOW="1", PYTHONDONTWRITEBYTECODE="1",
               APPIAN_HARNESS_IN_README_CHECK="1")
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", directory],
                          capture_output=True, text=True, env=env, cwd=root)
    found = re.search(r"Ran (\d+) tests", proc.stderr)
    return int(found.group(1)) if found else None


def check(root=".", count_tests=True):
    """`count_tests=False` skips the two suite spawns.

    Only its own tests pass it: they build tiny broken trees to prove this
    checker can fail, and counting tests in a three-file fixture costs an
    interpreter start per case to learn nothing. Left on, this checker's
    own tests added seven seconds to the edit loop -- the kind of cost this
    repository now goes looking for.
    """
    readme_path = os.path.join(root, "README.md")
    if not os.path.isfile(readme_path):
        return ["no README.md at %s" % root]
    readme = open(readme_path, encoding="utf-8").read()
    source = open(os.path.join(root, "hooks", "harness_hooks.py"), encoding="utf-8").read()
    fails = []

    def claim(pattern, actual, label):
        found = re.search(pattern, readme)
        if not found:
            fails.append("%s: the README no longer states this at all, so nothing is "
                         "holding it to %r" % (label, actual))
            return
        stated = _as_int(found.group(1))
        if stated is None:
            fails.append("%s: cannot read %r as a number" % (label, found.group(1)))
        elif stated != actual:
            fails.append("%s: README says %s, tree has %s" % (label, found.group(1), actual))

    hooks = json.load(open(os.path.join(root, "hooks", "hooks.json"), encoding="utf-8"))["hooks"]
    claim(r"declaring (\w+) hooks", sum(len(v) for v in hooks.values()), "hook count")

    for directory in ("scripts", "hooks") if count_tests else ():
        # No suite, no claim to check. Spawning `unittest discover` against a
        # directory that is not there costs an interpreter start to learn
        # nothing, and would then report "could not read a test count" about a
        # suite the repository never had -- a finding that is not about the
        # README at all.
        if not os.path.isdir(os.path.join(root, directory)):
            continue
        actual = _ran_count(root, directory)
        if actual is None:
            fails.append("%s: could not read a test count from the suite" % directory)
        else:
            claim(r"(\d+) for `%s/`" % directory, actual, "%s test count" % directory)

    # Both spellings, because a key read through a helper is still a key the
    # hooks read. `maxAllowedObjects` arrives as
    # `_max_allowed_objects(project_config)`, and inside that helper the
    # parameter is called `config` -- so a pattern anchored on
    # `project_config` could not see it, and this file reported agreement
    # while one of the eight documented keys was outside its reach. It was
    # documented by luck, not by check.
    read = set(re.findall(r'\b(?:project_)?config\.get\("([a-zA-Z]+)"', source))
    for key in sorted(read - set(DERIVED_CONFIG_KEYS)):
        if key not in readme:
            fails.append("config key %r is read by the hooks and never mentioned in the "
                         "README, whose key list claims to be closed" % key)

    for skill in sorted(glob.glob(os.path.join(root, "skills", "*", "SKILL.md"))):
        name = os.path.basename(os.path.dirname(skill))
        if name not in readme:
            fails.append("skill %r exists and the README does not mention it" % name)

    for log in sorted(set(re.findall(r'"([a-z-]+\.jsonl)"', source))):
        if log not in readme:
            fails.append("the code writes %r and the README's evidence table omits it" % log)

    return fails


def main(argv):
    root = "."
    args = argv[1:]
    if args:
        if args[0] == "--root" and len(args) == 2:
            root = args[1]
        else:
            print(__doc__.strip())
            return 2
    fails = check(root)
    if fails:
        print("The README disagrees with the tree:")
        for line in fails:
            print("  - " + line)
        return 1
    print("OK README matches the tree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
