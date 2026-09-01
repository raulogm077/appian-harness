"""What the manifests promise, the installed tree must actually contain:
hook commands, plugin.json component paths, skills/, agents/ and commands/.
Each referent must exist case-exactly, stay in the package, and read.

    python3 scripts/check_package_integrity.py [root]

Exit 0 intact, 1 a referent is missing, 3 nothing was declared to check.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

# Forward slash only, and this placeholder only: the command string reaches
# `sh`. docs/design-notes.md § check_package_integrity.py · hook path form
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)")

# `C:` and friends, written out rather than left to os.path.isabs, which
# answers differently on Windows and POSIX.
DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")

# Fields through which plugin.json may point Claude Code somewhere other than
# the conventional directory. Declaring one and shipping nothing does not error.
COMPONENT_FIELDS = ("commands", "agents", "skills", "hooks", "mcpServers")

# The rest of the boot chain, which no manifest names. Written out, not
# derived: docs/design-notes.md § check_package_integrity.py · runtime list
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
    """The real path `relative` names under `root`, or None. Spelling only,
    case-exact against listings, never by asking the filesystem.
    docs/design-notes.md § check_package_integrity.py · case"""
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
    """Why this path can never resolve inside any install, or None. Judged
    before touching the filesystem: both faults are about the declaration
    rather than about this checkout."""
    normalized = relative.replace("\\", "/")
    if normalized.startswith("/") or DRIVE_PREFIX.match(normalized):
        # Rejected, never reinterpreted: rewriting it would conceal the very
        # defect. docs/design-notes.md § check_package_integrity.py · absolute paths
        return ("is an absolute path; a manifest path resolves against the plugin "
                "root, so this names a location on the machine it was written on "
                "and cannot survive being installed anywhere else")
    if ".." in normalized.split("/"):
        return ("climbs out of the plugin root with '..'; what it reaches is not "
                "part of what gets installed")
    return None


def _escape_reason(root, resolved):
    """Why `resolved` is not really inside `root`, or None. A correctly spelled
    name can still lead out of the package, so both ends go through realpath
    and the target has to land under the root."""
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
    """Why `relative` is not a usable referent under `root`, or None. Ordered
    by how informative each answer stops being:
    docs/design-notes.md § check_package_integrity.py · check order"""
    malformed = _declaration_problem(relative)
    if malformed:
        return malformed

    resolved = _resolve_exact(root, relative)
    if resolved is None:
        return "is not in the tree (matched case-exactly)"

    # os.listdir lists the *name*, and a dangling link has one: presence read
    # out of the listing alone counts a link to nothing as a file that is there.
    if not os.path.exists(resolved):
        return ("is a dangling link: the name is in the directory listing and "
                "resolves to nothing on disk")

    escaped = _escape_reason(root, resolved)
    if escaped:
        return escaped

    if require_file and not os.path.isfile(resolved):
        return "is not a file"
    return None


def _iter_commands(node):
    """Yield every command string anywhere in a hooks structure. Both
    spellings: `command` as a string, and `args` as an argv list."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "command" and isinstance(value, str):
                yield value
            elif key == "args" and isinstance(value, list):
                # Joined so a path split across argv elements still reads as one
                # command, and the no-placeholder notice judges the invocation.
                yield " ".join(a for a in value if isinstance(a, str))
            else:
                for found in _iter_commands(value):
                    yield found
    elif isinstance(node, list):
        for item in node:
            for found in _iter_commands(item):
                yield found


def _path_values(value):
    """The path strings in a plugin.json component field: a single path or a
    list. `hooks` and `mcpServers` also accept an inline object, which declares
    no path, so _hook_manifests reads that instead."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [v for v in value if isinstance(v, str)]
    return []


def _hook_manifests(root, plugin):
    """(label, node_or_None, error_or_None) for each hooks declaration to walk.
    plugin.json may point `hooks` at a path of its own, and only the manifest
    Claude Code actually loads is worth walking."""
    declared = plugin.get("hooks")
    sources = []

    if isinstance(declared, dict):
        # Declared inline. Nothing to resolve, but its commands still name
        # files that have to be there.
        return [("plugin.json's inline hooks block", declared, None)]

    relatives = _path_values(declared)
    if not relatives:
        # Nothing declared: Claude Code falls back to the conventional path, so
        # its absence means "ships no hooks" rather than "is broken".
        relatives = ["hooks/hooks.json"]

    for relative in relatives:
        resolved = _resolve_exact(root, relative)
        if resolved is None or not os.path.isfile(resolved):
            # A declared-but-missing path is reported by the component-path loop
            # in check(); either way there is nothing here to walk.
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
        # Shipping no hooks is legitimate, so this fires only on the
        # contradiction: docs/design-notes.md § check_package_integrity.py · orphaned hooks
        hooks_dir = os.path.join(root, "hooks")
        if os.path.isdir(hooks_dir):
            shipped = [e for e in sorted(os.listdir(hooks_dir)) if e != "__pycache__"]
            if shipped:
                msgs.append("hooks/ ships %d file(s) and no hooks manifest declares any "
                            "of them, so none is ever invoked: %s"
                            % (len(shipped), ", ".join(shipped[:4])))

    for label, declared, error in manifests:
        # Opening a manifest is not an inspection; only a referent that
        # resolved is. docs/design-notes.md § check_package_integrity.py · the tally
        if error:
            msgs.append(error)
            continue
        # Reported once per path rather than once per command: the hooks share
        # one launcher, so a single missing file would print once per hook.
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
    # named, not resolved: docs/design-notes.md § check_package_integrity.py · runtime gate
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

    # Walked, not listed: commands/<namespace>/<name>.md is how a command gets
    # a namespace. docs/design-notes.md § check_package_integrity.py · commands
    for component, noun in (("agents", "agent"), ("commands", "command")):
        directory = os.path.join(root, component)
        if not os.path.isdir(directory):
            continue
        registered = 0
        for parent, subdirs, entries in os.walk(directory):
            # Inspection is decided by the NAME, never by os.walk's verdict:
            # docs/design-notes.md § check_package_integrity.py · junctions
            named = sorted(list(entries) + [d for d in subdirs if d.endswith(".md")])
            subdirs[:] = sorted(d for d in subdirs if not d.endswith(".md"))
            prefix = os.path.relpath(parent, root).replace(os.sep, "/")
            for entry in named:
                if not entry.endswith(".md"):
                    continue
                registered += 1
                checked += 1
                relative = "%s/%s" % (prefix, entry)
                # Through _referent_problem like every other referent here, so a
                # name that resolves to nothing is reported rather than skipped.
                problem = _referent_problem(root, relative, True)
                if problem:
                    msgs.append("%s %s, so the %s it names does not register"
                                % (relative, problem, noun))
                    continue
                # Read, not parsed: bytes that do not decode are a component
                # Claude Code does not register. Caught, so CI reads a finding.
                try:
                    with open(os.path.join(parent, entry), encoding="utf-8") as f:
                        f.read()
                except (OSError, UnicodeDecodeError) as exc:
                    msgs.append("%s cannot be read as UTF-8 text (%s), so the %s it "
                                "declares does not register" % (relative, exc, noun))

        # Files present and none of them a command: the directory ships and
        # declares nothing. docs/design-notes.md § check_package_integrity.py · commands
        if component == "commands" and registered == 0:
            shipped = sorted(os.listdir(directory))
            if shipped:
                msgs.append("commands/ ships %d file(s) and none of them is a .md, so no "
                            "command registers and the directory declares nothing: %s"
                            % (len(shipped), ", ".join(shipped[:4])))

    if checked == 0 and not msgs:
        # Zero referents resolved is an uninspected package, not an intact one;
        # `and not msgs` keeps a finding from being reported as NOT MEASURED.
        return EXIT_NOT_MEASURED, ["no hooks, skills or agents were declared under %s; "
                                   "0 referents were resolved" % root]
    return (1 if msgs else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        # Says what was established and not a word more: the referents are there
        # and readable. What they mean once opened belongs to the linters.
        print("OK every declared path resolves inside the install, matched case-exactly")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
