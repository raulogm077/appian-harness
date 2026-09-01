"""Holds README.md and docs/*.md to what the repository actually contains:
the counts the prose states, the config keys the hooks read, the skills,
modules, agents and logs it names, and every relative link the package ships.

    python3 scripts/check_readme_claims.py [--root .]

Exit 0 agreement, 1 disagreement (naming each), 2 usage.
"""
import glob
import json
import os
import posixpath
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_evals import _is_case_dir  # noqa: E402
from check_package_integrity import DRIVE_PREFIX, _resolve_exact  # noqa: E402

# `](target)`: every inline link and every image. Reference-style definitions
# are not read. docs/design-notes.md § check_readme_claims.py · link pattern
LINK = re.compile(r"\]\(([^)]*)\)")

# A URI scheme, and therefore not a path in this repository. Two characters
# minimum before the colon, which keeps `C:/Users/...` from reading as one.
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")

# The prose writes small numbers as words, which are as checkable as digits.
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

# A counting word or a number and nothing else; the `\b` on the left is
# load-bearing. docs/design-notes.md § check_readme_claims.py · NUMBER
NUMBER = r"\b(?i:(%s|\d+))" % "|".join(WORDS)

# Keys the hooks compute for themselves rather than read out of a project's
# config. Written out, not derived: docs/design-notes.md § check_readme_claims.py · derived keys
DERIVED_CONFIG_KEYS = ("activeTask", "configPath", "mcpServers", "pluginRoot", "projectRoot")


def _as_int(token):
    return WORDS.get(token.lower(), None) if not token.isdigit() else int(token)


def _read_text(path, label):
    """(text, None) or (None, why it could not be read). Never raises: every
    read in this file goes through here.
    docs/design-notes.md § check_readme_claims.py · reads never raise"""
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read(), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, "%s cannot be read (%s)" % (label, exc)


def _documents(root):
    """(label, text) for every document a claim may live in, and read problems.
    README.md plus docs/*.md; docs/ being absent is not a finding. Labels are
    slash-separated so a message names the same file on either platform."""
    problems = []
    found = []
    paths = []

    readme = os.path.join(root, "README.md")
    if os.path.isfile(readme):
        paths.append(("README.md", readme))
    else:
        problems.append("no README.md at %s" % root)

    docs = os.path.join(root, "docs")
    if os.path.isdir(docs):
        for path in sorted(glob.glob(os.path.join(docs, "*.md"))):
            paths.append(("docs/" + os.path.basename(path), path))

    for label, path in paths:
        text, problem = _read_text(path, label)
        if problem:
            problems.append("%s, so every claim it carries is unheld" % problem)
        else:
            found.append((label, text))
    return found, problems


def _hook_count(text):
    """How many hook entries hooks.json declares, or None if it cannot say.
    The shape is checked rather than trusted: an array under `hooks` decodes
    as valid JSON and would turn the sum below into an AttributeError."""
    try:
        parsed = json.loads(text)
    except ValueError:
        return None
    declared = parsed.get("hooks") if isinstance(parsed, dict) else None
    if not isinstance(declared, dict) or not all(isinstance(v, list)
                                                 for v in declared.values()):
        return None
    return sum(len(v) for v in declared.values())


def _eval_cases(root):
    """The eval case directories, by the runner's own definition of one.
    `_is_case_dir` is imported rather than reimplemented so the two cannot
    drift: docs/design-notes.md § check_readme_claims.py · borrowed definitions"""
    evals = os.path.join(root, "evals")
    if not os.path.isdir(evals):
        return []
    return sorted(entry for entry in os.listdir(evals)
                  if os.path.isdir(os.path.join(evals, entry)) and _is_case_dir(entry))


def _markdown_files(root):
    """(label, path) for every markdown document the package ships. Wider than
    the set `_documents` reads, and dot-directories and __pycache__ are tool
    state: docs/design-notes.md § check_readme_claims.py · two document sets"""
    found = []
    for here, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for name in sorted(files):
            if name.endswith(".md"):
                path = os.path.join(here, name)
                found.append((os.path.relpath(path, root).replace(os.sep, "/"), path))
    return found


def _fragment_key(text):
    """A heading or a fragment reduced to what every renderer agrees on:
    letters and digits, looser than any real slug rule.
    docs/design-notes.md § check_readme_claims.py · fragment keys"""
    return "".join(c for c in text.lower() if c.isalnum())


def _anchor_keys(text):
    """Every fragment a document's headings can be linked by. Repeats are
    numbered the way renderers number them: a second `## Fixed` is reachable
    as `#fixed-1`, a third as `#fixed-2`."""
    keys = set()
    seen = {}
    for heading in re.findall(r"(?m)^#{1,6}[ \t]+(.+?)[ \t]*#*$", text):
        key = _fragment_key(heading)
        if not key:
            continue
        count = seen.get(key, 0)
        seen[key] = count + 1
        keys.add(key if count == 0 else "%s%d" % (key, count))
    return keys


def _link_target(raw):
    """(path, fragment) for a link target, either of them possibly None. Both
    forms markdown allows for a title are handled, `path "Title"` and `<path
    with spaces>`, so a title is not reported as part of the path."""
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1:target.index(">")]
    elif target.split():
        target = target.split()[0]
    else:
        target = ""
    path, _, fragment = target.partition("#")
    return (path or None), (fragment or None)


def _link_problems(root):
    """Every relative link in the package that resolves to nothing -- the
    shortest checkable claim a document makes, and the one a move breaks."""
    problems = []
    texts = {}
    for label, path in _markdown_files(root):
        text, problem = _read_text(path, label)
        if problem:
            problems.append("%s, so the links in it were not checked" % problem)
        else:
            texts[label] = text

    anchors = {}
    for label in sorted(texts):
        # posixpath and not os.path: labels are slash-separated whatever the
        # platform, and os.path.join would produce `docs\..\CHANGELOG.md`.
        here = posixpath.dirname(label)
        for match in LINK.finditer(texts[label]):
            raw = match.group(1).strip()
            if SCHEME.match(raw) or raw.startswith("//"):
                continue
            relative, fragment = _link_target(raw)
            shown = (relative or "") + ("#" + fragment if fragment else "")

            if relative is None and fragment is None:
                problems.append("%s links to nothing: the target between the parentheses "
                                "is empty" % label)
                continue

            if relative is None:
                target = label
            else:
                if relative.startswith("/") or DRIVE_PREFIX.match(relative):
                    problems.append("%s links to %s, which is an absolute path: it names "
                                    "the root of the site or of the disk it was written "
                                    "on, never the root of the repository"
                                    % (label, shown))
                    continue
                target = posixpath.normpath(posixpath.join(here, relative))
                if target == ".." or target.startswith("../"):
                    problems.append("%s links to %s, which climbs out of the repository; "
                                    "what it reaches does not travel with the checkout"
                                    % (label, shown))
                    continue
                # Case-exact through check_package_integrity's resolver rather
                # than the filesystem, which disagrees across platforms.
                if _resolve_exact(root, target) is None:
                    problems.append("%s links to %s, which is not in the tree (matched "
                                    "case-exactly). A link resolves against the file that "
                                    "holds it, not against the repository root"
                                    % (label, shown))
                    continue

            if not fragment or target not in texts:
                # Nothing to look a heading up in: `#L42` is a line anchor the
                # renderer invents, and a directory has no headings at all.
                continue
            if target not in anchors:
                anchors[target] = _anchor_keys(texts[target])
            if _fragment_key(fragment) not in anchors[target]:
                problems.append("%s links to %s, and %s has no heading that answers to "
                                "'#%s'. The file is there and the section is not, so the "
                                "link lands silently at the top of the page"
                                % (label, shown, target, fragment))
    return problems


def _ran_count(root, directory):
    """How many tests a suite actually runs. The slow launcher subprocess
    tests are skipped here -- skips still count in unittest's "Ran N", so the
    total is stable either way and this keeps the check quick."""
    # The marker breaks a recursion: this spawns the scripts suite, which holds
    # a test that calls check() on the real repository, which spawns it again.
    env = dict(os.environ, APPIAN_HARNESS_SKIP_SLOW="1", PYTHONDONTWRITEBYTECODE="1",
               APPIAN_HARNESS_IN_README_CHECK="1")
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", directory],
                          capture_output=True, text=True, env=env, cwd=root)
    found = re.search(r"Ran (\d+) tests", proc.stderr)
    return int(found.group(1)) if found else None


def check(root=".", count_tests=True):
    """`count_tests=False` skips the two suite spawns; only this file's own
    tests pass it, since counting tests in a fixture tree learns nothing.
    docs/design-notes.md § check_readme_claims.py · count_tests"""
    documents, fails = _documents(root)
    if not documents:
        # Nothing to read. Reporting every claim as missing from a file that is
        # not there says one fact many times over and buries it.
        return fails
    # Joined for the "is this name mentioned anywhere" checks, which ask
    # about presence and not about which document holds it.
    prose = "\n".join(text for _, text in documents)

    def claim(pattern, actual, label):
        # Every occurrence in every document, not the first one found: a
        # duplicate that has gone stale is the defect this file exists for.
        stated_anywhere = False
        for name, text in documents:
            for found in re.finditer(pattern, text):
                stated_anywhere = True
                stated = _as_int(found.group(1))
                if stated is None:
                    fails.append("%s: cannot read %r in %s as a number"
                                 % (label, found.group(1), name))
                elif stated != actual:
                    fails.append("%s: %s says %s, tree has %s"
                                 % (label, name, found.group(1), actual))
        if not stated_anywhere:
            fails.append("%s: the prose no longer states this at all -- not in %s -- so "
                         "nothing is holding it to %r"
                         % (label, ", ".join(name for name, _ in documents), actual))

    source, problem = _read_text(os.path.join(root, "hooks", "harness_hooks.py"),
                                 "hooks/harness_hooks.py")
    if problem:
        # Both the config-key list and the evidence table derive from this
        # file, so losing it leaves two checks holding nothing rather than one.
        fails.append("%s, so neither the config-key list nor the evidence table has "
                     "anything holding it" % problem)
        source = ""

    hooks_text, problem = _read_text(os.path.join(root, "hooks", "hooks.json"),
                                     "hooks/hooks.json")
    declared = None if problem else _hook_count(hooks_text)
    if declared is None:
        fails.append("%s, so the hook count the prose states is holding nothing"
                     % (problem or "hooks/hooks.json has no countable hooks block in it"))
    else:
        claim(r"declaring (\w+) hooks", declared, "hook count")

    for directory in ("scripts", "hooks") if count_tests else ():
        # No suite, no claim to check: spawning `unittest discover` against a
        # directory that is not there reports a finding about the wrong subject.
        if not os.path.isdir(os.path.join(root, directory)):
            continue
        actual = _ran_count(root, directory)
        if actual is None:
            fails.append("%s: could not read a test count from the suite" % directory)
        else:
            claim(r"(\d+) for `%s/`" % directory, actual, "%s test count" % directory)

    # Counted against the tree with no "does the directory exist" guard, so a
    # missing directory reads as a count of none. Test files are not modules.
    modules = sorted(os.path.basename(path)
                     for path in glob.glob(os.path.join(root, "scripts", "*.py"))
                     if not os.path.basename(path).startswith("test_"))
    claim(NUMBER + r" modules", len(modules), "scripts module count")

    skills = sorted(os.path.basename(os.path.dirname(path))
                    for path in glob.glob(os.path.join(root, "skills", "*", "SKILL.md")))
    claim(NUMBER + r" skills", len(skills), "skill count")

    # This one path rather than skills/*/references/*.md: the sentence being
    # held is about appian-best-practices' references specifically.
    references = glob.glob(os.path.join(root, "skills", "appian-best-practices",
                                        "references", "*.md"))
    claim(NUMBER + r" domain references", len(references), "domain reference count")

    # "judging agents", never "agents" on its own: a looser pattern reaches
    # prose about how the agents are used and calls it a wrong count.
    agents = sorted(os.path.basename(path)[:-len(".md")]
                    for path in glob.glob(os.path.join(root, "agents", "*.md")))
    claim(NUMBER + r" judging agents", len(agents), "agent count")

    cases = _eval_cases(root)
    claim(NUMBER + r" eval cases", len(cases), "eval case count")
    # Three claims and not one: swapping one kind of case for the other keeps
    # the total right while the sentence describing the split stops being true.
    claim(NUMBER + r" routing, \w+ safety",
          len([c for c in cases if c.startswith("routing-")]), "routing eval count")
    claim(r"\w+ routing, " + NUMBER + r" safety",
          len([c for c in cases if c.startswith("safety-")]), "safety eval count")

    # Both spellings, because a key read through a helper is still a key the
    # hooks read: docs/design-notes.md § check_readme_claims.py · config key pattern
    read = set(re.findall(r'\b(?:project_)?config\.get\("([a-zA-Z]+)"', source))
    for key in sorted(read - set(DERIVED_CONFIG_KEYS)):
        if key not in prose:
            fails.append("config key %r is read by the hooks and named in no document, "
                         "though the key list claims to be closed" % key)

    for name in skills:
        if name not in prose:
            fails.append("skill %r exists and no document mentions it" % name)

    # The counts above say how many; these say which. A table that enumerates
    # can be wrong in two ways, and one number covers only one of them.
    for module in modules:
        if module not in prose:
            fails.append("scripts/%s exists and no document names it, though the module "
                         "list names them one by one" % module)

    for agent in agents:
        if agent not in prose:
            fails.append("agent %r exists and no document names it" % agent)

    for log in sorted(set(re.findall(r'"([a-z-]+\.jsonl)"', source))):
        if log not in prose:
            fails.append("the code writes %r and the evidence table omits it" % log)

    fails.extend(_link_problems(root))
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
        # Names the set that was read, not one file: a line naming README.md
        # alone would be the drift this file exists to catch, one level up.
        print("The prose disagrees with the tree:")
        for line in fails:
            print("  - " + line)
        return 1
    print("OK README.md and docs/ match the tree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
