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
- every skills/<dir> holds a SKILL.md, and every .md under agents/ and
  commands/ leads to a file that is inside the package and decodes as text,
- a commands/ that ships files registers at least one of them as a command.

That last one is the only rule here about something being ABSENT, and it is
narrow on purpose: shipping no commands at all is a normal thing for a plugin
to do, so the finding is not "commands/ is missing" but "commands/ is there,
holds files, and Claude Code takes nothing out of it".

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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

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

# The rest of the boot chain. hooks.json names run_hook.sh and stops; what
# run_hook.sh starts, and what that in turn imports, no manifest mentions --
# so a package can lose either one and every declared path still resolves.
#
# Written out rather than derived, and the direction of a mistake is why --
# the argument check_readme_claims already makes for DERIVED_CONFIG_KEYS.
# Deriving would mean being right about two more languages: shell, for the
# `$PLUGIN_ROOT/...` that run_hook.sh names, and Python imports, for what
# harness_hooks.py pulls out of scripts/. Wrong about either and the miss is
# silent, which is precisely the failure this entry list exists to end. A
# stale entry here fails loudly on the next run and is fixed in a minute.
#
# These are THIS package's files. Like lint_skills.SECTION_EXEMPT, the dict is
# meant to be edited by whoever adopts the file, not inherited unread.
REQUIRED_AT_RUNTIME = {
    "hooks/harness_hooks.py":
        "the program every hook command starts. run_hook.sh probes an interpreter "
        "and execs it against this path; with the file gone Python exits with "
        "`can't open file` and writes nothing to stdout, so the scope gate returns "
        "no decision and the write it was gating proceeds",
    "scripts/validate_verdict.py":
        "imported at module level by hooks/harness_hooks.py, so losing it is not a "
        "degraded closure gate -- it is an ImportError before any subcommand runs, "
        "which takes down all six hooks at once and just as quietly",
}


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


# There were two wrappers here, `isfile_exact` and `exists_exact`, returning
# `_referent_problem(...) is None`. Both are gone, and the reason is worth the
# four lines it takes to say.
#
# `check()` never called them -- it calls `_referent_problem` directly, because
# it wants the reason and not the bool. So they were public surface with one
# caller between them, that caller being their own test. And `isfile_exact` is
# already the name of a *different* function, in `validate_verdict.py`, with the
# arguments the other way round: `isfile_exact(path, root=None)` against
# `isfile_exact(root, relative)`. Two strings in, a bool out, both times --
# so importing the wrong one does not fail, it answers wrongly and says nothing.
# The one the rest of this repository means by that name is the other one:
# `hooks/harness_hooks.py` imports it to decide whether a verdict file exists,
# which is the gate that closes a task.
#
# A name collision costs nothing until somebody reaches for it. Deleting the
# unused half was cheaper than making the two halves agree.


def _iter_commands(node):
    """Yield every command string anywhere in a hooks structure.

    Both spellings. A hook may carry its command as a string under `command`
    or as an argv list under `args`, and reading only the first meant an
    exec-form hook contributed no referents *and* no warning: the recursion
    descended into the list, every element was a bare str, and a str node
    yields nothing. A typo in the path of an exec-form hook was invisible --
    not even the "names no path under ${CLAUDE_PLUGIN_ROOT}" notice fired,
    because no command string was ever seen to notice it about.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            elif key == "args" and isinstance(value, list):
                # Joined rather than yielded one by one so a path split across
                # argv elements still reads as one command to the caller, and
                # so the no-placeholder notice judges the whole invocation.
                yield " ".join(a for a in value if isinstance(a, str))
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

    named_a_plugin_path = False
    manifests = _hook_manifests(root, plugin)
    if not manifests:
        # Nothing declared any hooks. That is legitimate -- plenty of plugins
        # ship none -- so it is only a finding when the package contradicts
        # itself: hooks/ full of code and no manifest naming any of it. A
        # plugin with no hooks has no hooks/ directory; one with the launcher,
        # the program and no hooks.json installs, looks healthy and invokes
        # none of it, which is this file's own subject pointed one level up.
        #
        # Found by deleting hooks/hooks.json from a copy of this repository
        # and watching check() return (0, []) -- the six hooks left the
        # package and the checker whose docstring is about hooks that never
        # run said nothing. What did fail the build was check_readme_claims,
        # by raising FileNotFoundError, because the README happens to say
        # "six hooks": coverage that exists by accident of the prose and
        # arrives as a traceback rather than a finding.
        #
        # Deliberately not keyed on plugin.json's `hooks` field: this repo
        # does not declare one, hooks are discovered at the conventional
        # path, so a rule about the declaration would be a no-op on the very
        # tree the gap was measured in.
        hooks_dir = os.path.join(root, "hooks")
        if os.path.isdir(hooks_dir):
            shipped = [e for e in sorted(os.listdir(hooks_dir)) if e != "__pycache__"]
            if shipped:
                msgs.append("hooks/ ships %d file(s) and no hooks manifest declares any "
                            "of them, so none is ever invoked: %s"
                            % (len(shipped), ", ".join(shipped[:4])))

    for label, declared, error in manifests:
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
            named_a_plugin_path = True
            problem = _referent_problem(root, relative, True)
            if problem:
                msgs.append("%s invokes %s, which %s" % (label, relative, problem))

    # Gated on a hook command having *named* a path under the plugin root --
    # named, not resolved. Naming one is what makes this a package that runs
    # hooks, and it stays true when the file it names is the missing one, so a
    # tree that lost both run_hook.sh and the program behind it reports both.
    #
    # Not gated on "a manifest was walked", which was the first shape and the
    # wrong one: `{"hooks": {}}` walks a manifest and declares nothing, and
    # the gate would have turned that from NOT MEASURED into a finding about
    # files a package with no hooks has no reason to carry.
    if named_a_plugin_path:
        for relative in sorted(REQUIRED_AT_RUNTIME):
            checked += 1
            problem = _referent_problem(root, relative, True)
            if problem:
                msgs.append("%s %s -- and it is %s"
                            % (relative, problem, REQUIRED_AT_RUNTIME[relative]))

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

    # commands/ joins agents/ here, and before this loop existed nothing looked
    # at it at all: lint_skills walks skills/, lint_agents walks agents/, and
    # the one component a user invokes by name had no reader in any of the nine
    # CI steps. What this closes is the file being there, leading somewhere
    # inside the package, and decoding. It does NOT close "the README promises
    # /appian-init and no such file exists": that is a claim about prose, it
    # belongs to check_readme_claims, and the boundary is the same one drawn
    # for the hooks manifest above -- a package that ships no commands
    # legitimately has no commands/ directory at all.
    #
    # Walked rather than listed, because commands/<namespace>/<name>.md is how
    # a command gets a namespace. A top-level-only scan reads a package whose
    # commands all live one level down as a package with none, which would
    # make the "registers nothing" finding below fire on a perfectly good tree.
    for component, noun in (("agents", "agent"), ("commands", "command")):
        directory = os.path.join(root, component)
        if not os.path.isdir(directory):
            continue
        registered = 0
        for parent, subdirs, entries in os.walk(directory):
            # What gets inspected is decided by the NAME, never by os.walk's
            # verdict on it. A dangling junction keeps its directory attribute
            # after the target is gone, so Windows hands `appian-init.md` back
            # in `subdirs` and a loop over `entries` alone never sees it --
            # measured here, and it is the same blind spot in a new place: the
            # name is in the listing, ends in .md, and resolves to nothing.
            # Judged, then not descended into, since whatever sits under a
            # name that cannot itself register is not registering either.
            named = sorted(list(entries) + [d for d in subdirs if d.endswith(".md")])
            subdirs[:] = sorted(d for d in subdirs if not d.endswith(".md"))
            prefix = os.path.relpath(parent, root).replace(os.sep, "/")
            for entry in named:
                if not entry.endswith(".md"):
                    continue
                registered += 1
                checked += 1
                relative = "%s/%s" % (prefix, entry)
                # Through _referent_problem like every other referent in this
                # file, rather than the `os.path.isfile(...) or continue` this
                # loop used to open with. That guard answered False for a
                # dangling link and moved on in silence -- a name in the
                # listing, ending in .md, resolving to nothing -- which is the
                # precise defect a reviewer had already found in exists_exact
                # and which these two directories reintroduced by being added
                # after the fix.
                problem = _referent_problem(root, relative, True)
                if problem:
                    msgs.append("%s %s, so the %s it names does not register"
                                % (relative, problem, noun))
                    continue
                # Read, not parsed. What the frontmatter says is lint_agents.py's
                # subject; what this file establishes is that the bytes are there
                # and decode -- a file Claude Code cannot read is one it does not
                # register, silently, exactly like a hook command it cannot find.
                #
                # Caught rather than allowed to propagate: a traceback out of a
                # checker is a broken checker to whoever reads the CI log, and this
                # is a finding about the package, which is what the run is for.
                try:
                    with open(os.path.join(parent, entry), encoding="utf-8") as f:
                        f.read()
                except (OSError, UnicodeDecodeError) as exc:
                    msgs.append("%s cannot be read as UTF-8 text (%s), so the %s it "
                                "declares does not register" % (relative, exc, noun))

        # A directory that is scanned for commands and yields none. Files are
        # there, so this is not the legitimate absence above; none of them is
        # a command, so the directory ships and declares nothing -- the same
        # contradiction as a skills/<dir> with no SKILL.md, and the same one
        # the hooks rule makes about code no manifest invokes.
        #
        # A name ending in .md that turned out to be dangling still counts as
        # registered for this purpose. It has already been reported precisely,
        # one line up, and adding "and nothing registers" on top would be the
        # same file reported twice under two descriptions.
        #
        # Asked of commands/ only, and not for lack of symmetry: lint_agents
        # already answers it for agents/, exiting 3 over an agents/ that holds
        # no .md file. Restating it here would be a second checker with an
        # opinion about the same tree, which is how this file's agent
        # frontmatter rule and lint_agents' drifted apart the first time.
        if component == "commands" and registered == 0:
            shipped = sorted(os.listdir(directory))
            if shipped:
                msgs.append("commands/ ships %d file(s) and none of them is a .md, so no "
                            "command registers and the directory declares nothing: %s"
                            % (len(shipped), ", ".join(shipped[:4])))

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
