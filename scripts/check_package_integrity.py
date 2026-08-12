"""What the manifests promise, the installed tree must actually contain.

Every test in this repository imports `harness_hooks.py` directly. That proves
the program is correct and proves nothing about whether Claude Code can start
it: hooks.json names a path, and a hook whose command cannot be found does not
ask and does not block -- it does not run. The plugin installs, looks healthy,
and enforces nothing, which is the failure `run_hook.sh` was written to prevent
one layer further in, and which no amount of unit testing the module can see.

So this walks the declarations and checks the referents:

- every path a hook command names exists, matched case-exactly, in the
  manifest Claude Code would actually load -- which is the one plugin.json
  points at, not the conventional one, when those differ,
- every component directory plugin.json declares exists,
- every skills/<dir> holds a SKILL.md and every agents/<file>.md is readable.

The inventory is physical on purpose: does the referent exist, is it spelled
the way the declaration spells it, does it lead anywhere, is where it leads
still inside the package. What a file *means* once opened belongs to the
linters -- `lint_agents.py` owns the frontmatter of an agent, including which
skills it may name. This file held that rule too for a while, and the two
copies had already drifted into disagreeing about block-style YAML before
anyone noticed, which is the defect `test_matcher_parity` exists to catch
wearing a different hat.

    python3 scripts/check_package_integrity.py [root]

Exit 0 intact, 1 a referent is missing, 3 nothing was declared to check.
"""
import json
import os
import re
import sys

EXIT_NOT_MEASURED = 3

# ${CLAUDE_PLUGIN_ROOT}/a/b -- the only path form a hook command may use,
# because it is the only one Claude Code substitutes. A bare relative path in a
# hook command resolves against the session's cwd, not the install, which works
# on the author's machine and nowhere else.
#
# Forward slash only, and not because Windows is being ignored: these strings
# are handed to `sh`, where a backslash is an escape character rather than a
# separator. A command written with backslashes is broken on every platform,
# and matching it here would report it as fine.
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")

# `C:` and friends. Written out rather than left to os.path.isabs, which
# answers differently on Windows and POSIX and has changed its mind about
# `\foo` across releases -- a checker whose entire premise is giving the same
# answer on every platform cannot ask a question that does not.
DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")

# Fields through which plugin.json may point Claude Code at somewhere other
# than the conventional directory. Declaring one and shipping nothing at it
# does not error at load time: the components are simply not there, which from
# inside a session is indistinguishable from never having written them.
COMPONENT_FIELDS = ("commands", "agents", "skills", "hooks", "mcpServers")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _resolve_exact(root, relative):
    """The real path `relative` names under `root`, or None if it is absent.

    Every component is matched against the directory listing instead of being
    handed to the filesystem, because NTFS and APFS are case-insensitive and
    ext4 is not: `Run_Hook.sh` satisfies os.path.isfile() on the author's
    laptop and is simply not there in CI. A checker that inherits the
    filesystem's opinion passes on the machine where the mistake is invisible
    and fails on the machine where it bites, which is the asymmetry rather
    than a check of it.

    Spelling only. Whether the name leads anywhere, and whether where it
    leads is still inside the package, are separate questions that
    _referent_problem asks after this one -- a listing is evidence that a
    name was written correctly and evidence of nothing else.
    """
    parts = [p for p in relative.replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        return None
    here = root
    for part in parts:
        try:
            entries = os.listdir(here)
        except OSError:
            return None
        if part not in entries:
            return None
        here = os.path.join(here, part)
    return here


def _declaration_problem(relative):
    """Why this path can never resolve inside any install, or None.

    Judged before touching the filesystem, because both of these are wrong
    about the *declaration* rather than about this particular checkout, and
    would otherwise be reported as though a file were merely missing.
    """
    normalized = relative.replace("\\", "/")
    if normalized.startswith("/") or DRIVE_PREFIX.match(normalized):
        # Rejected rather than reinterpreted, and the choice is not obvious,
        # so: `/hooks/hooks.json` gets split into components today and looked
        # up under the plugin root, which quietly turns a broken declaration
        # into a working one and reports OK. Whether Claude Code accepts an
        # absolute path here is a question whose two answers both end in
        # "say something" -- if it does, the path leaves the install and the
        # containment rule below refuses it; if it does not, the declaration
        # is malformed. Neither answer ends in silently rewriting it, which
        # would have this file conceal the exact class of defect it exists
        # to find.
        return ("is an absolute path; a manifest path resolves against the plugin "
                "root, so this names a location on the machine it was written on "
                "and cannot survive being installed anywhere else")
    if ".." in normalized.split("/"):
        return ("climbs out of the plugin root with '..'; what it reaches is not "
                "part of what gets installed")
    return None


def _escape_reason(root, resolved):
    """Why `resolved` is not really inside `root`, or None.

    Spelling a name correctly says nothing about where it leads. A
    `hooks/run_hook.sh` that is a link to somewhere else on the author's disk
    satisfies every check above and ships as a package whose launcher is not
    in it -- so both ends are put through realpath and the target has to land
    under the root.
    """
    real_root = os.path.realpath(root)
    real_target = os.path.realpath(resolved)
    if real_target == real_root:
        return None
    try:
        inside = os.path.commonpath([real_root, real_target]) == real_root
    except ValueError:
        # Different drives on Windows: not comparable, therefore not inside.
        inside = False
    if inside:
        return None
    return ("resolves to %s, outside the plugin root; an installed package cannot "
            "depend on a target that does not travel with it" % real_target)


def _referent_problem(root, relative, require_file):
    """Why `relative` is not a usable referent under `root`, or None.

    The order is the order the answers stop being informative in: a
    malformed declaration first, then spelling, then whether the name leads
    anywhere, then whether where it leads is still in the package, then what
    kind of thing it is. Escape is reported before file-ness because "points
    outside the install" is the useful half of "points outside the install at
    something that is not a file".
    """
    malformed = _declaration_problem(relative)
    if malformed:
        return malformed

    resolved = _resolve_exact(root, relative)
    if resolved is None:
        return "is not in the tree (matched case-exactly)"

    # os.listdir lists the *name*, and a dangling link has one. Reading
    # presence out of the listing alone -- which is what this file did until
    # a reviewer pointed at it -- counts a link to nothing as a file that is
    # there, increments the tally, emits no finding and can exit 0.
    if not os.path.exists(resolved):
        return ("is a dangling link: the name is in the directory listing and "
                "resolves to nothing on disk")

    escaped = _escape_reason(root, resolved)
    if escaped:
        return escaped

    if require_file and not os.path.isfile(resolved):
        return "is not a file"
    return None


def isfile_exact(root, relative):
    """os.path.isfile, but case-sensitive and install-contained everywhere."""
    return _referent_problem(root, relative, True) is None


def exists_exact(root, relative):
    """As isfile_exact, for a referent that may legitimately be a directory."""
    return _referent_problem(root, relative, False) is None


def _iter_commands(node):
    """Yield every command string anywhere in a hooks structure."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            else:
                for found in _iter_commands(value):
                    yield found
    elif isinstance(node, list):
        for item in node:
            for found in _iter_commands(item):
                yield found


def _path_values(value):
    """The path strings in a plugin.json component field.

    Every one of these fields accepts a single path or a list of them, and
    `hooks` and `mcpServers` additionally accept the configuration inline as
    an object. An object declares no path, so it contributes nothing here --
    _hook_manifests reads it instead.
    """
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _hook_manifests(root, plugin):
    """(label, node_or_None, error_or_None) for each hooks declaration to walk.

    Which file to open is not a detail. plugin.json may point `hooks` at a
    path of its own, and walking hooks/hooks.json regardless would validate a
    manifest Claude Code never loads while the one it does load goes unread --
    a green run about the wrong file.
    """
    declared = plugin.get("hooks")
    sources = []

    if isinstance(declared, dict):
        # Declared inline. Nothing to resolve, but its commands still name
        # files that have to be there.
        return [("plugin.json's inline hooks block", declared, None)]

    relatives = _path_values(declared)
    if not relatives:
        # Nothing declared: Claude Code falls back to the conventional path,
        # so that is the one whose absence means "this plugin ships no hooks"
        # rather than "this plugin is broken".
        relatives = ["hooks/hooks.json"]

    for relative in relatives:
        resolved = _resolve_exact(root, relative)
        if resolved is None or not os.path.isfile(resolved):
            # A declared-but-missing path is reported by the component-path
            # loop in check(); the conventional one being absent is not a
            # finding at all. Either way there is nothing here to walk.
            continue
        try:
            sources.append((relative, _load(resolved), None))
        except ValueError as exc:
            sources.append((relative, None, "%s is not valid JSON: %s" % (relative, exc)))
    return sources


def check(root):
    """Return (exit_code, messages)."""
    msgs = []
    checked = 0

    plugin = {}
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    if os.path.isfile(plugin_path):
        try:
            plugin = _load(plugin_path)
        except ValueError as exc:
            return 1, [".claude-plugin/plugin.json is not valid JSON: %s" % exc]
        if not isinstance(plugin, dict):
            return 1, [".claude-plugin/plugin.json is not an object"]

    for field in COMPONENT_FIELDS:
        for relative in _path_values(plugin.get(field)):
            checked += 1
            problem = _referent_problem(root, relative, False)
            if problem:
                msgs.append("plugin.json declares %s at %s, which %s"
                            % (field, relative, problem))

    for label, declared, error in _hook_manifests(root, plugin):
        # Opening a manifest is deliberately NOT counted as an inspection --
        # only a referent that actually resolved is. A hooks.json declaring
        # `{"hooks": {}}` would otherwise buy a clean "OK every declared path
        # resolves" for having been opened and found to declare nothing, which
        # is the vacuous green this plugin spends a README arguing against.
        # The `and not msgs` guard on the tally below is what keeps findings
        # from being swallowed by the same zero.
        if error:
            msgs.append(error)
            continue
        # Collected first and reported once per path rather than once per
        # command. All six hooks in this plugin go through the same launcher,
        # so a single missing file printed six identical times reads as six
        # problems and buries whatever else the run found.
        referents = []
        for command in _iter_commands(declared):
            referenced = PLUGIN_PATH.findall(command)
            if not referenced:
                msgs.append("%s declares a hook command naming no path under "
                            "${CLAUDE_PLUGIN_ROOT}, so whatever it invokes is looked up "
                            "on PATH or against the session's cwd rather than the "
                            "install: %r" % (label, command))
                continue
            for relative in referenced:
                if relative not in referents:
                    referents.append(relative)

        for relative in referents:
            checked += 1
            problem = _referent_problem(root, relative, True)
            if problem:
                msgs.append("%s invokes %s, which %s" % (label, relative, problem))

    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        for entry in sorted(os.listdir(skills_dir)):
            if not os.path.isdir(os.path.join(skills_dir, entry)):
                continue
            checked += 1
            problem = _referent_problem(root, "skills/%s/SKILL.md" % entry, True)
            if problem:
                msgs.append("skills/%s/SKILL.md %s, so the directory ships and declares "
                            "nothing" % (entry, problem))

    agents_dir = os.path.join(root, "agents")
    if os.path.isdir(agents_dir):
        for entry in sorted(os.listdir(agents_dir)):
            path = os.path.join(agents_dir, entry)
            if not entry.endswith(".md") or not os.path.isfile(path):
                continue
            checked += 1
            # Read, not parsed. What the frontmatter says is lint_agents.py's
            # subject; what this file establishes is that the bytes are there
            # and decode -- an agent Claude Code cannot read is one it does not
            # register, silently, exactly like a hook command it cannot find.
            #
            # Caught rather than allowed to propagate: a traceback out of a
            # checker is a broken checker to whoever reads the CI log, and this
            # is a finding about the package, which is what the run is for.
            try:
                with open(path, encoding="utf-8") as f:
                    f.read()
            except (OSError, UnicodeDecodeError) as exc:
                msgs.append("agents/%s cannot be read as UTF-8 text (%s), so the agent it "
                            "declares does not register" % (entry, exc))

    if checked == 0 and not msgs:
        # Zero referents resolved is not an intact package, it is an
        # uninspected one, and the two must not share an exit code.
        #
        # `and not msgs` is not belt-and-braces. NOT MEASURED outranking a
        # finding is the worst answer this file can give: it reports "nothing
        # was checked" about a defect it has already found and is holding in
        # its hand, and exit 3 is the code a caller is most likely to wave
        # through. Findings win.
        return EXIT_NOT_MEASURED, ["no hooks, skills or agents were declared under %s; "
                                   "0 referents were resolved" % root]
    return (1 if msgs else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        # Says what was established and not a word more. "every skill and
        # agent resolves" was true when this file read agent frontmatter; it
        # now checks that the files are there and readable, and a success line
        # that keeps claiming the larger thing is the drift this repository
        # has a checker for.
        print("OK every declared path resolves inside the install, matched case-exactly")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
