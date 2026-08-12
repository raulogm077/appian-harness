"""Validates agents/*.md the way lint_skills.py validates SKILL.md.

The three agents are as much the product as the skills, and nothing looked at
them. Their `description` decides whether they are ever dispatched -- the same
job a skill description does, judged by the same rule, which is why
`has_trigger` is imported from lint_skills rather than restated. Two copies of
one rule is the defect test_matcher_parity exists to catch, and writing it
again here would be that defect with a new name. `MAX_DESCRIPTION` and
`EXIT_NOT_MEASURED` come across for the same reason: a limit raised in one
file and not the other is two linters disagreeing about one contract.

This file owns what an agent's frontmatter MEANS -- `name`, `description`,
`skills`, `tools`. `check_package_integrity.py` owns the physical inventory:
that declared paths exist, that each skills/<dir> holds a SKILL.md, that the
agent files are readable. It does not interpret frontmatter, so the list
reader that used to live in both lives here.

What is checked beyond the shared rule:

- `name` matches the filename, or the agent is addressable under a name that
  does not exist,
- every skill in `skills:` resolves to a real directory under skills/,
- `tools` is declared, because an agent with no tools line silently inherits
  everything,
- a read-only reviewing agent may not quietly gain write tools: appian-reviewer
  is Read/Grep/Glob because a reviewer that can edit what it reviews is not an
  independent reviewer, and that separation should not dissolve in a diff
  nobody reads.

    python3 scripts/lint_agents.py [root]

Exit 0 pass, 1 findings, 3 nothing was checked.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lint_skills import (EXIT_NOT_MEASURED, MAX_DESCRIPTION,  # noqa: E402
                         has_trigger, parse_frontmatter)

# Agents whose independence depends on not being able to write, mapped to the
# reason. An entry here is a claim the README makes about the verification
# pyramid; removing one is a design decision, not a lint fix.
READ_ONLY_AGENTS = {
    "appian-reviewer": "a reviewer that can edit what it reviews is not an "
                       "independent reviewer",
}
WRITE_TOOLS = ("Write", "Edit", "MultiEdit", "NotebookEdit")

# `  - Read` — one entry of a YAML block sequence.
BLOCK_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")

# ` # anything` — a YAML trailing comment. Stripped because leaving it on
# turns "Write # temporary" into a token that is not the string "Write", and
# the read-only rule compares strings: the same bypass `tools: [Write]` was,
# in the spelling that announces itself. No skill or tool name contains `#`,
# so cutting at the first one costs nothing.
TRAILING_COMMENT = re.compile(r"\s+#.*$")


def frontmatter_list(text, key):
    """The values `key` lists, in every YAML spelling, or None if absent.

    `parse_frontmatter` folds a key's continuation lines into one space-joined
    string, which is right for a description that wraps and wrong for a list:
    a block sequence arrives as "- a - b" and no reading of that recovers two
    names. So lists are read from the raw frontmatter lines instead.

    Reading only the inline form is worse than it looks. `tools: [Write]` is
    valid YAML and a comma-split of it yields the single token "[Write]",
    which is not the string "Write" -- so a read-only agent handed write
    access passes the check written to stop exactly that. The reported
    agreement is about a list that was never read, which is the silent pass
    this plugin exists to argue against.

    None rather than [] when the key is absent: "declared nothing" and "did
    not declare" are different findings, and the tools rule needs to tell
    them apart.

    Not a YAML parser, and the limits are worth naming: a quoted entry
    containing a comma (`skills: ["a,b"]`) is split in two, and a nested
    sequence is not understood. Both fail loudly toward a name that does not
    resolve, so they produce a confusing finding rather than a silent pass --
    which is why they are documented instead of half-fixed. Trailing comments
    are stripped rather than tolerated, because that one failed the other
    way.
    """
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    lines = parts[1].splitlines()
    declaration = re.compile(r"^%s:\s*(.*)$" % re.escape(key))
    for index, line in enumerate(lines):
        match = declaration.match(line)
        if not match:
            continue
        inline = TRAILING_COMMENT.sub("", match.group(1)).strip()
        if inline:
            return [v for v in (item.strip().strip("'\"")
                                for item in inline.strip("[]").split(",")) if v]
        found = []
        for following in lines[index + 1:]:
            item = BLOCK_ITEM.match(following)
            if not item:
                break
            entry = TRAILING_COMMENT.sub("", item.group(1)).strip().strip("'\"")
            if entry:
                found.append(entry)
        return found
    return None


def lint_agent(path, known_skills):
    errors = []
    with open(path, encoding="utf-8") as f:
        text = f.read()
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

    for skill in frontmatter_list(text, "skills") or []:
        if skill not in known_skills:
            errors.append("lists skill %r, which is not a directory under skills/; the "
                          "agent would start without it and say nothing" % skill)

    granted = frontmatter_list(text, "tools")
    if not granted:
        errors.append("no 'tools' line; the agent silently inherits every tool in the "
                      "session, which is never what a scoped agent wants")
    elif name in READ_ONLY_AGENTS:
        if "*" in granted:
            # `tools: *` grants Write and Edit without naming either, so a
            # check that only reads the named tools waves through in one
            # character exactly what the loop below exists to stop.
            errors.append("declares 'tools: *', which grants Write and Edit without naming "
                          "them, but %s" % READ_ONLY_AGENTS[name])
        for tool in WRITE_TOOLS:
            if tool in granted:
                errors.append("is granted %s, but %s" % (tool, READ_ONLY_AGENTS[name]))

    if not body.strip():
        errors.append("has frontmatter and no body")
    return errors


def main(root):
    agents_dir = os.path.join(root, "agents")
    if not os.path.isdir(agents_dir):
        print("ERROR: no agents/ directory under %s" % root)
        return 1

    known_skills = set()
    skills_dir = os.path.join(root, "skills")
    if os.path.isdir(skills_dir):
        known_skills = set(e for e in os.listdir(skills_dir)
                           if os.path.isdir(os.path.join(skills_dir, e)))

    checked = failed = 0
    for entry in sorted(os.listdir(agents_dir)):
        if not entry.endswith(".md"):
            continue
        path = os.path.join(agents_dir, entry)
        checked += 1
        errs = lint_agent(path, known_skills)
        for e in errs:
            print("ERROR %s: %s" % (path, e))
        if errs:
            failed += 1
        else:
            print("OK    %s" % path)

    # Zero agents checked is not a pass, for the reason lint_skills.main
    # gives at length: "all agents passed" is trivially true of nothing.
    if checked == 0:
        print("\nNOT MEASURED: agents/ exists but contains no .md files; 0 agents "
              "were validated.")
        return EXIT_NOT_MEASURED
    if failed:
        print("\n%d agent(s) failed." % failed)
        return 1
    print("\n%d agent(s) passed." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
