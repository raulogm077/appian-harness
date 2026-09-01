"""Validates agents/*.md frontmatter: name, description, skills, tools.

    python3 scripts/lint_agents.py [root]

Exit 0 pass, 1 findings, 3 nothing was checked.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# One definition of the description rule and of the exit-code vocabulary:
# docs/design-notes.md § lint_agents.py · shared rules
from lint_skills import (EXIT_NOT_MEASURED, MAX_DESCRIPTION,  # noqa: E402
                         has_trigger, parse_frontmatter)

# Agents whose independence depends on not being able to write, mapped to the
# reason: docs/design-notes.md § lint_agents.py · READ_ONLY_AGENTS
READ_ONLY_AGENTS = {
    "appian-reviewer": "a reviewer that can edit what it reviews is not an "
                       "independent reviewer",
}

# A whitelist, not the write tools negated -- Bash, Task and MCP write tools
# cannot be enumerated: docs/design-notes.md § lint_agents.py · READ_ONLY_TOOLS
READ_ONLY_TOOLS = frozenset(("Read", "Grep", "Glob", "Skill"))

# A key at the start of a line ends the previous key's declaration.
TOP_LEVEL_KEY = re.compile(r"^[A-Za-z0-9_-]+:")

# `  - Read` -- one entry of a YAML block sequence.
BLOCK_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")

# A YAML comment, whole-line or trailing.
COMMENT = re.compile(r"(?m)(?:^|\s)#.*$")

# A tool name, or `*`. Greedy about `_` and `-` so an MCP name arrives whole:
# docs/design-notes.md § lint_agents.py · TOOL_TOKEN
TOOL_TOKEN = re.compile(r"\*|[A-Za-z_][A-Za-z0-9_-]*")

# Everything a `tools:` declaration can be made of while naming no tool.
PUNCTUATION_ONLY = re.compile(r"[\s\-\[\],>|]")


def declaration_regions(text, key):
    """The raw block of every declaration of `key`, punctuation and all.

    Every declaration, not the first, because YAML resolves a duplicate key
    to the last: docs/design-notes.md § lint_agents.py · declarations
    """
    if not text.startswith("---"):
        return []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return []

    lines = parts[1].splitlines()
    prefix = key + ":"
    regions = []
    index = 0
    while index < len(lines):
        if not lines[index].startswith(prefix):
            index += 1
            continue
        region = [lines[index][len(prefix):]]
        index += 1
        while index < len(lines) and not TOP_LEVEL_KEY.match(lines[index]):
            region.append(lines[index])
            index += 1
        regions.append("\n".join(region))
    return regions


def frontmatter_list(text, key):
    """The names `key` lists, in every YAML spelling. Always a list.

    For `skills:` only -- docs/design-notes.md § lint_agents.py · skills vs tools;
    not a YAML parser -- docs/design-notes.md § lint_agents.py · not a YAML parser
    """
    values = []
    for region in declaration_regions(text, key):
        lines = [COMMENT.sub("", line) for line in region.split("\n")]
        # Two shapes collected separately, then both split on commas: that
        # reads a wrapped flow sequence and an interrupted block sequence.
        scalar = []
        items = []
        for position, line in enumerate(lines):
            item = BLOCK_ITEM.match(line) if position else None
            if item:
                items.append(item.group(1))
            elif line.strip():
                scalar.append(line.strip())
        for chunk in [" ".join(scalar)] + items:
            for piece in chunk.strip("[] ").split(","):
                piece = piece.strip().strip("'\"").strip("[] ")
                if piece:
                    values.append(piece)
    return values


def disallowed_tools(text):
    """Every name in a `tools:` declaration that a read-only agent may not hold.

    A raw search: docs/design-notes.md § lint_agents.py · read-only whitelist
    Comments stripped: docs/design-notes.md § lint_agents.py · comments in tools
    """
    found = []
    for region in declaration_regions(text, "tools"):
        for token in TOOL_TOKEN.findall(COMMENT.sub("", region)):
            if token not in READ_ONLY_TOOLS and token not in found:
                found.append(token)
    return found


def declares_tools(text):
    """True when a `tools:` declaration names anything at all.

    Emptiness is judged after stripping comments and punctuation:
    docs/design-notes.md § lint_agents.py · empty tools line
    """
    for region in declaration_regions(text, "tools"):
        if PUNCTUATION_ONLY.sub("", COMMENT.sub("", region)):
            return True
    return False


def lint_agent(path, known_skills):
    try:
        # utf-8-sig, not utf-8: a BOM hides the frontmatter and every field
        # reads as missing. docs/design-notes.md § lint_agents.py · utf-8-sig
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        # A traceback collapses the 0/1/3 vocabulary into "it crashed":
        # docs/design-notes.md § lint_agents.py · checkers do not raise
        return ["cannot be read as UTF-8 text (%s), so nothing in it was "
                "validated" % exc]

    errors = []
    meta, body = parse_frontmatter(text)
    stem = os.path.splitext(os.path.basename(path))[0]

    name = meta.get("name", "")
    if not name:
        errors.append("missing 'name' in frontmatter")
    elif name != stem:
        errors.append("'name' is %r but the filename is %r; they must match or the "
                      "agent is addressable under a name that does not exist"
                      % (name, stem))
    if name and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        errors.append("'name' must be kebab-case")

    desc = meta.get("description", "")
    if not desc:
        errors.append("missing 'description' in frontmatter")
    else:
        if len(desc) > MAX_DESCRIPTION:
            errors.append("description is %d chars; the limit is %d"
                          % (len(desc), MAX_DESCRIPTION))
        if not has_trigger(desc):
            errors.append("description has no trigger phrase, so nothing says when this "
                          "agent should be dispatched (needs 'use when' / 'use before' "
                          "in a sentence that is not itself an exclusion)")

    for skill in frontmatter_list(text, "skills"):
        if skill not in known_skills:
            errors.append("lists skill %r, which is not a directory under skills/; the "
                          "agent would start without it and say nothing" % skill)

    if not declares_tools(text):
        errors.append("no 'tools' line; the agent silently inherits every tool in the "
                      "session, which is never what a scoped agent wants")
    elif name in READ_ONLY_AGENTS:
        disallowed = disallowed_tools(text)
        if disallowed:
            # Names the route out and its price, not only what is wrong:
            # docs/design-notes.md § lint_agents.py · READ_ONLY_AGENTS
            errors.append("its 'tools' declaration names %s, and a read-only agent may "
                          "hold only %s (%s). If one of those names is genuinely "
                          "read-only, add it to READ_ONLY_TOOLS with the reason written "
                          "down rather than widening the set here"
                          % (", ".join(disallowed), ", ".join(sorted(READ_ONLY_TOOLS)),
                             READ_ONLY_AGENTS[name]))

    if not body.strip():
        errors.append("has frontmatter and no body")
    return errors


def stale_read_only_entries(shipped):
    """Keys of READ_ONLY_AGENTS that name no agent in the tree.

    A rename removes the restriction in silence:
    docs/design-notes.md § lint_agents.py · stale read-only entries
    """
    return [name for name in sorted(READ_ONLY_AGENTS) if name not in shipped]


def main(root):
    agents_dir = os.path.join(root, "agents")
    if not os.path.isdir(agents_dir):
        # Not exit 1: nothing was inspected, which the third code keeps
        # apart from a failure. docs/design-notes.md § lint_agents.py · exit 3
        print("NOT MEASURED: no agents/ directory under %s; 0 agents were validated."
              % root)
        return EXIT_NOT_MEASURED

    known_skills = set()
    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        known_skills = set(e for e in os.listdir(skills_dir)
                           if os.path.isdir(os.path.join(skills_dir, e)))

    checked = failed = 0
    shipped = set()
    for entry in sorted(os.listdir(agents_dir)):
        if not entry.endswith(".md"):
            continue
        path = os.path.join(agents_dir, entry)
        checked += 1
        shipped.add(os.path.splitext(entry)[0])
        errs = lint_agent(path, known_skills)
        for e in errs:
            print("ERROR %s: %s" % (path, e))
        if errs:
            failed += 1
        else:
            print("OK    %s" % path)

    # Zero agents is not a pass, and the stale-entry check is skipped rather
    # than fired: docs/design-notes.md § lint_agents.py · exit 3
    if checked == 0:
        print("\nNOT MEASURED: agents/ exists but contains no .md files; 0 agents "
              "were validated.")
        return EXIT_NOT_MEASURED

    stale = stale_read_only_entries(shipped)
    for name in stale:
        print("ERROR %s: READ_ONLY_AGENTS restricts %r, which is no agent in this tree; "
              "the restriction applies to nothing and says nothing, which is how a "
              "rename silently removes it" % (agents_dir, name))

    if failed or stale:
        print("\n%d agent(s) failed, %d stale read-only entr%s."
              % (failed, len(stale), "y" if len(stale) == 1 else "ies"))
        return 1
    print("\n%d agent(s) passed." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
