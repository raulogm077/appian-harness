"""Validates agents/*.md the way lint_skills.py validates SKILL.md.

The three agents are as much the product as the skills, and nothing looked at
them. Their `description` decides whether they are ever dispatched -- the same
job a skill description does, judged by the same rule, which is why
`has_trigger` is imported from lint_skills rather than restated. Two copies of
one rule is the defect test_matcher_parity exists to catch, and writing it
again here would be that defect with a new name. `MAX_DESCRIPTION` and
`EXIT_NOT_MEASURED` come across for the same reason: a limit raised in one
file and not the other is two linters disagreeing about one contract.

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


def lint_agent(path, known_skills):
    errors = []
    with open(path, encoding="utf-8") as f:
        meta, body = parse_frontmatter(f.read())
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

    raw_skills = meta.get("skills", "").strip()
    if raw_skills.startswith("-"):
        # parse_frontmatter folds a key's continuation lines into one
        # space-joined string, so `skills:\n  - a\n  - b` arrives here as
        # "- a - b" and there is no reading of that which recovers two names.
        # Refusing it beats guessing: a linter that silently took the first
        # entry would report a skills list nobody wrote.
        errors.append("'skills' uses YAML block-list form; this frontmatter parser reads "
                      "the inline form only, so write it as [a, b]")
    elif raw_skills:
        for skill in [s.strip().strip("'\"[]") for s in raw_skills.strip("[]").split(",")]:
            if skill and skill not in known_skills:
                errors.append("lists skill %r, which is not a directory under skills/; the "
                              "agent would start without it and say nothing" % skill)

    tools = meta.get("tools", "").strip()
    if not tools:
        errors.append("no 'tools' line; the agent silently inherits every tool in the "
                      "session, which is never what a scoped agent wants")
    elif name in READ_ONLY_AGENTS:
        granted = [t.strip() for t in tools.split(",")]
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
