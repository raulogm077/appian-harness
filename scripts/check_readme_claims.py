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
- the size of every directory the prose enumerates — modules, skills, domain
  references, judging agents, and eval cases split into routing and safety,
- every config key the hooks read being documented,
- every skill, module and agent being named,
- every append-only log the code writes being listed,
- every relative link resolving, section included.

Read across a **set** of documents, not one file: `README.md`, plus every
`docs/*.md` when that directory exists. A README that states every count is
a README nobody finishes, so those sections move out of it — and a checker
that only ever opened README.md would then report every moved claim as
deleted, which is the right answer to a deletion and the wrong one to a
move. A claim in none of them is still a failure; that half is the point.

And the shortest claim any document makes is a link: **it is over there**.
Every relative link in every markdown file the package ships has to resolve
to something that exists, spelled the way the link spells it, resolved
against the file holding the link — which is the defect the split actually
caused, `](CHANGELOG.md)` travelling into `docs/` where it means something
else. Where a link names a section, the section has to be in the target.

That is a **second, wider set** than the claims above, and the two must not
be merged: the link set includes `CHANGELOG.md`, whose `0.4.0` entry says
`Ten modules` about a release where ten was right, and reading history as a
claim about today would fail the build for being accurate.

Deliberately narrow. It checks claims with a **mechanical referent** and
says nothing about whether the prose is any good — that needs a reader, and
pretending otherwise would be the vacuous green this plugin argues against.

Nothing here exits 3, and the omission is deliberate rather than inherited.
Its siblings need NOT MEASURED because a tree can declare nothing for them
to inspect; this file counts every fact against the tree whether or not the
directory is there, so an `agents/` that has gone missing reports "the prose
says three, the tree has none" instead of counting nothing and calling it
agreement. Every referent it cannot read becomes a finding for the same
reason: silence is the one answer it must never give.

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

# `](target)`, which is every inline link and every image. Reference-style
# definitions (`[label]: target`) are not read, and the repository has none --
# if one appears, this stays quiet about it rather than guessing.
#
# Inline code is not special-cased either: a link written inside backticks as
# an example gets resolved like any other. That is a deliberate limit rather
# than an oversight -- telling them apart needs a markdown parser, this
# repository has none, and the alternative to being occasionally too strict
# would be a rule that also skips real links which happen to sit near code.
LINK = re.compile(r"\]\(([^)]*)\)")

# A URI scheme, and therefore not a path in this repository: http, https,
# mailto, and anything else somebody writes. Two characters minimum before
# the colon, which is what keeps `C:/Users/...` out of it -- a drive letter
# would otherwise read as a scheme and a link that only works on the machine
# it was written on would be waved through as somebody else's problem.
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]+:")

# The README writes small numbers as words, which reads better and is
# exactly as checkable once you say so.
WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
         "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}

# A counting word or a number, and nothing else, for the claims added below.
#
# The older patterns capture with `(\w+)` and get away with it because each
# anchors on a phrase that occurs once. The new ones cannot: `(\w+) skills`
# also matches "The skills orchestrate" four sections down, and `(\w+) agents`
# matches "two agents", "three agents" and "the agents" in three more places.
# Loose, every one of those reads as a count this file then declares
# unreadable -- a checker inventing findings about sentences that were never
# claims. Digits stay in: the test totals are written as digits.
#
# The `\b` is the whole of the left anchor and it is not decoration. The noun
# anchors the right side; with nothing on the left, "standalone modules" ends
# in "one" and reads as a claim of one module, so a sentence that was never a
# count becomes a finding against a tree that has eleven. The older `(\w+)`
# patterns need no such guard -- each is anchored by a literal ("declaring ",
# "for `") that a word cannot run into.
NUMBER = r"\b(?i:(%s|\d+))" % "|".join(WORDS)

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


def _read_text(path, label):
    """(text, None) or (None, why it could not be read). Never raises.

    Every read in this file goes through here, and the reason is the one
    check_package_integrity.py wrote down when it wrapped its own: a
    traceback out of a checker reads in a CI log as "the checker is broken",
    not as "the package has a problem" -- which is the finding, and the whole
    output the run existed to produce. It also collapses the 0/1/2 vocabulary
    every caller here is written against into an unhandled exception, which
    is none of the three.

    Measured rather than imagined. Deleting hooks/hooks.json from a copy of
    this repository made check() raise FileNotFoundError on the json.load
    that counted hooks, and that traceback -- not a finding -- was what
    failed the build; check_package_integrity.py cites it by name in the
    comment about its own missing-manifest case.

    UnicodeDecodeError joins OSError because a file that does not decode is
    a file Claude Code does not read either, and the two arrive here as the
    same fact: there is no text, so whatever it was holding is unheld.
    """
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read(), None
    except (OSError, UnicodeDecodeError) as exc:
        return None, "%s cannot be read (%s)" % (label, exc)


def _documents(root):
    """(label, text) for every document a claim may live in, and read problems.

    README.md plus docs/*.md. docs/ being absent is not a finding -- it is
    absent in this repository today, and a checker that required it would
    fail the build for the shape the tree already has.

    Labels are relative and slash-separated so a message names the same file
    on Windows and Linux, which is where these runs are compared.
    """
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

    The shape is checked rather than trusted. `{"hooks": []}` decodes as
    valid JSON and turns the sum below into an AttributeError -- the same
    crash as a missing file wearing a different exception type, and worth
    exactly as little to whoever is reading the log.
    """
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

    `_is_case_dir` is imported from check_evals rather than reimplemented
    here, private name and all: it encodes that `results/` is where the
    runner writes scores and that dot- and dunder-prefixed directories are
    tool artefacts. A second copy of that list would be free to drift from
    the file that decides what actually runs, and this checker would then
    hold the README to a count of cases nobody executes -- the same argument
    check_evals makes for borrowing lint_skills' frontmatter parser instead
    of writing a second one.
    """
    evals = os.path.join(root, "evals")
    if not os.path.isdir(evals):
        return []
    return sorted(entry for entry in os.listdir(evals)
                  if os.path.isdir(os.path.join(evals, entry)) and _is_case_dir(entry))


def _markdown_files(root):
    """(label, path) for every markdown document the package ships.

    Wider than the set `_documents` reads, on purpose, and the two must not
    be merged. That one answers "where may a claim about the tree live", and
    widening it would read CHANGELOG.md -- whose 0.4.0 entry says `Ten
    modules` about a release where ten was right, and would fail a build for
    describing history accurately. This one answers "whose links have to
    resolve", and every document in the package has that duty, including the
    skills and the eval cases, which state no count at all.

    Dot-directories and __pycache__ are tool state rather than authored
    documents: .pytest_cache ships a README.md nobody wrote.
    """
    found = []
    for here, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        for name in sorted(files):
            if name.endswith(".md"):
                path = os.path.join(here, name)
                found.append((os.path.relpath(path, root).replace(os.sep, "/"), path))
    return found


def _fragment_key(text):
    """A heading or a fragment reduced to what every renderer agrees on.

    Letters and digits, nothing else, so `The \\`hooks.json\\` file` and the
    anchor `#the-hooksjson-file` meet. Deliberately looser than any real slug
    rule, and this repository is the reason there is no strict one to borrow:
    `validate_verdict._slug` exists, and its own docstring records that it is
    NOT GitHub's rule -- GitHub keeps runs of separators, so `a / b` anchors
    as `a--b` there and `a-b` here, and twenty-one of this plugin's reference
    headings differ between the two.

    That function is right for what it does, which is a different question
    from this one. It defines what an agent must WRITE into a verdict, so one
    exact rule is the contract. A markdown link is read by whatever renders
    the page, so the authority is the renderer -- and picking either rule
    here would report links written for the other as broken. Both survive
    dropping the punctuation, which is why it is dropped.
    """
    return "".join(c for c in text.lower() if c.isalnum())


def _anchor_keys(text):
    """Every fragment a document's headings can be linked by.

    Repeats are numbered the way renderers number them: a second `## Fixed`
    is reachable as `#fixed-1`, a third as `#fixed-2`. CHANGELOG.md has four
    such headings per release, so without this the only honest options would
    be reporting a working link as broken or not checking fragments at all.
    """
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
    """(path, fragment) for a link target, either of them possibly None.

    Both forms markdown allows for a title are handled -- `path "Title"` and
    `<path with spaces>` -- because the alternative is reporting a link with
    a title as a path that contains one, which is a finding about this
    parser rather than about the document.
    """
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
    """Every relative link in the package that resolves to nothing.

    A link is the shortest checkable claim a document can make -- "it is over
    there" -- and moving a section is what breaks it. Splitting the README
    carried `](CHANGELOG.md)` into docs/, where it no longer resolves, and a
    person reading found it. This is that reader, minus the remembering.
    """
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
        # platform, and a link is written the same way on both. Joining with
        # os.path would produce `docs\..\CHANGELOG.md` on Windows and compare
        # it against slash-separated labels.
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
                # Matched case-exactly through check_package_integrity's own
                # resolver rather than handed to the filesystem. NTFS and APFS
                # say `Troubleshooting.md` is there and ext4 and GitHub say it
                # is not, so asking the filesystem passes on the machine where
                # the mistake is invisible and fails where a reader meets it.
                if _resolve_exact(root, target) is None:
                    problems.append("%s links to %s, which is not in the tree (matched "
                                    "case-exactly). A link resolves against the file that "
                                    "holds it, not against the repository root"
                                    % (label, shown))
                    continue

            if not fragment or target not in texts:
                # Nothing to look a heading up in. `#L42` on a source file is
                # a line anchor the renderer invents, and a directory has no
                # headings at all -- neither is a claim this can judge.
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
    documents, fails = _documents(root)
    if not documents:
        # Nothing to read. Reporting a dozen claims as missing from a file
        # that is not there says one fact twelve times and buries it.
        return fails
    # Joined for the "is this name mentioned anywhere" checks, which ask
    # about presence and not about which document holds it.
    prose = "\n".join(text for _, text in documents)

    def claim(pattern, actual, label):
        # Every occurrence in every document, not the first one found. The
        # README already states the domain-reference count twice -- in the
        # table and again four sections down -- and re.search held only the
        # first, so the second was as unchecked as if it were in another
        # file. Which, once these sections move into docs/, some of them will
        # be. A duplicate that has gone stale is exactly the defect this file
        # exists for, and stopping at the first match is how it survives.
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
        # Both the config-key list and the evidence table are derived from
        # this file, so losing it leaves two checks holding nothing rather
        # than one, and neither of them would have said so.
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

    # The "What is in the box" table states a size for every directory it
    # lists, and until now not one of those numbers was held by anything --
    # in the very release that codified "an assertion in prose brings the
    # check that sustains it". Add an eleventh module and CI stays green
    # while the table lists ten of eleven.
    #
    # Counted against the tree with no "does the directory exist" guard, on
    # purpose. A missing agents/ makes the count 0 and the finding reads "the
    # prose says three, the tree has none", which is true and useful; guarded,
    # the claim would go unchecked precisely when it had become most wrong.
    #
    # Test files are not modules here. The README lists the programs, and
    # states their suites' totals separately, as tests rather than as files.
    modules = sorted(os.path.basename(path)
                     for path in glob.glob(os.path.join(root, "scripts", "*.py"))
                     if not os.path.basename(path).startswith("test_"))
    claim(NUMBER + r" modules", len(modules), "scripts module count")

    skills = sorted(os.path.basename(os.path.dirname(path))
                    for path in glob.glob(os.path.join(root, "skills", "*", "SKILL.md")))
    claim(NUMBER + r" skills", len(skills), "skill count")

    # This one path rather than skills/*/references/*.md: the sentence being
    # held is about appian-best-practices' references specifically, so a
    # second skill growing a references/ of its own would turn a true
    # sentence into a failure and teach whoever hits it to loosen the check.
    references = glob.glob(os.path.join(root, "skills", "appian-best-practices",
                                        "references", "*.md"))
    claim(NUMBER + r" domain references", len(references), "domain reference count")

    # "judging agents", never "agents" on its own. The README says "three
    # agents do the judging" one section later and "two agents" in the
    # paragraph about review, both of them prose about how the agents are
    # used rather than a count of what ships -- and a pattern loose enough to
    # reach the table row reaches those too and calls one of them wrong.
    agents = sorted(os.path.basename(path)[:-len(".md")]
                    for path in glob.glob(os.path.join(root, "agents", "*.md")))
    claim(NUMBER + r" judging agents", len(agents), "agent count")

    cases = _eval_cases(root)
    claim(NUMBER + r" eval cases", len(cases), "eval case count")
    # Three claims and not one. Swapping a safety case for a routing case
    # keeps the total at six while the sentence describing the suite stops
    # being true, and the split is the half that says what the suite covers.
    claim(NUMBER + r" routing, \w+ safety",
          len([c for c in cases if c.startswith("routing-")]), "routing eval count")
    claim(r"\w+ routing, " + NUMBER + r" safety",
          len([c for c in cases if c.startswith("safety-")]), "safety eval count")

    # Both spellings, because a key read through a helper is still a key the
    # hooks read. `maxAllowedObjects` arrives as
    # `_max_allowed_objects(project_config)`, and inside that helper the
    # parameter is called `config` -- so a pattern anchored on
    # `project_config` could not see it, and this file reported agreement
    # while one of the eight documented keys was outside its reach. It was
    # documented by luck, not by check.
    read = set(re.findall(r'\b(?:project_)?config\.get\("([a-zA-Z]+)"', source))
    for key in sorted(read - set(DERIVED_CONFIG_KEYS)):
        if key not in prose:
            fails.append("config key %r is read by the hooks and named in no document, "
                         "though the key list claims to be closed" % key)

    for name in skills:
        if name not in prose:
            fails.append("skill %r exists and no document mentions it" % name)

    # The counts above say how many; these say which. A table that
    # enumerates can be wrong in two ways, and one number covers only one of
    # them -- ten modules of which one is not the module listed passes any
    # count and is still a table that sends a reader to a file that is not
    # there.
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
        # "The README disagrees" until the claims could live in docs/ too.
        # A success line that keeps naming one file when the check reads
        # several is the same drift this file exists to catch, one level up.
        print("The prose disagrees with the tree:")
        for line in fails:
            print("  - " + line)
        return 1
    print("OK README.md and docs/ match the tree")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
