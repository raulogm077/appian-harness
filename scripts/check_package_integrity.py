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
- every skills/<dir> holds a SKILL.md and every agents/<file>.md is readable,
- every skill an agent's frontmatter lists resolves to a real skill.

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

    A `..` component finds no match in any listing and so reads as missing.
    That is the intended answer: a plugin path that climbs out of its own
    install has nothing to do with what was installed.
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


def isfile_exact(root, relative):
    """os.path.isfile, but case-sensitive on every platform."""
    resolved = _resolve_exact(root, relative)
    return resolved is not None and os.path.isfile(resolved)


def exists_exact(root, relative):
    """As isfile_exact, for a referent that may legitimately be a directory."""
    return _resolve_exact(root, relative) is not None


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


def _frontmatter_skills(text):
    """The skills an agent's frontmatter lists, in either YAML spelling.

    Both `skills: [a, b]` and a block sequence under `skills:` are valid, and
    a reader that knows only the inline form reports agreement about a list it
    never read. That is the silent pass this plugin exists to argue against,
    so both are parsed rather than one being assumed.
    """
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []

    lines = parts[1].splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^skills:\s*(.*)$", line)
        if not match:
            continue
        inline = match.group(1).strip()
        if inline:
            return [s.strip().strip("'\"") for s in inline.strip("[]").split(",")
                    if s.strip().strip("'\"")]
        found = []
        for following in lines[index + 1:]:
            item = re.match(r"^\s*-\s*(.+?)\s*$", following)
            if not item:
                break
            found.append(item.group(1).strip("'\""))
        return found
    return []


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
            if not exists_exact(root, relative):
                msgs.append("plugin.json declares %s at %s, which is not in the tree "
                            "(matched case-exactly); the components it names are absent "
                            "from the session rather than reported missing"
                            % (field, relative))

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
            if not isfile_exact(root, relative):
                msgs.append("%s invokes %s, which is not in the tree (matched "
                            "case-exactly)" % (label, relative))

    skills_dir = os.path.join(root, "skills")
    known_skills = set()
    if os.path.isdir(skills_dir):
        for entry in sorted(os.listdir(skills_dir)):
            if not os.path.isdir(os.path.join(skills_dir, entry)):
                continue
            checked += 1
            # Recorded as known even when its SKILL.md is missing. The defect
            # is reported once, here, where it can be fixed; letting it also
            # surface as "an agent lists a skill that does not exist" would
            # report one mistake twice and send the reader to the wrong file.
            known_skills.add(entry)
            if not isfile_exact(root, "skills/%s/SKILL.md" % entry):
                msgs.append("skills/%s has no SKILL.md, so the directory ships and "
                            "declares nothing" % entry)

    agents_dir = os.path.join(root, "agents")
    if os.path.isdir(agents_dir):
        for entry in sorted(os.listdir(agents_dir)):
            path = os.path.join(agents_dir, entry)
            if not entry.endswith(".md") or not os.path.isfile(path):
                continue
            checked += 1
            with open(path, encoding="utf-8") as f:
                text = f.read()
            for skill in _frontmatter_skills(text):
                if skill not in known_skills:
                    msgs.append("agents/%s lists skill %r, which is not a directory under "
                                "skills/; the agent would start without it and say nothing"
                                % (entry, skill))

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
        print("OK every declared path, skill and agent resolves in the tree")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
