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
`skills`, `tools`. `check_package_integrity.py` owns the physical inventory,
and does not interpret frontmatter.

## The read-only rule, and why it is shaped the way it is

`appian-reviewer` holds Read/Grep/Glob because a reviewer that can edit what
it reviews is not an independent reviewer. Enforcing that took four attempts,
and all four failures were the same mistake at different altitudes: asking
what is FORBIDDEN, which only ever protects against what its author thought
of.

  1. A parser plus a list of four write tools. `tools: [Write]` walked past
     it -- comma-splitting the folded value yields "[Write]", not "Write".
  2. Patch the brackets. `tools: Read, Write # temporary` walked past it.
  3. Patch the comment. Six more YAML spellings walked past it: a comment
     line or a blank line inside a block sequence, a flow sequence wrapped
     across lines, a nested sequence, a duplicate key, a block scalar.
  4. Stop parsing -- search the raw declaration for the forbidden words. Then
     `tools: Read, Grep, Glob, Skill, Bash` walked past it, because `Bash`
     writes any file in the repository with a redirection and was not one of
     the four words. `Task` and every MCP write tool were open too.

So both halves are inverted now. The region is read RAW, which no spelling
can hide inside, and what may be in it is a WHITELIST -- `READ_ONLY_TOOLS`.
Any other name is a finding, including the ones nobody has invented yet. A
blacklist fails open on everything its author did not enumerate; a whitelist
fails closed on everything it does not permit, and that is the only direction
a prohibition may be wrong in.

`skills:` is deliberately NOT read this way. It is a whitelist already --
each name has to resolve against skills/ -- so a spelling this file misreads
produces a name that does not resolve and gets printed. Under `tools:` the
same misreading produced a token that is not a forbidden word, which is a
clean pass on an agent holding write access. Same misparse, noisy under one
key and silent under the other. That asymmetry is the reason two keys in one
frontmatter are read two different ways, and anyone tempted to unify them
should re-read this paragraph first.

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
# pyramid; removing one is a design decision, not a lint fix. main() checks
# every key still names a shipped agent -- see the comment there for the
# silent failure that guards against.
READ_ONLY_AGENTS = {
    "appian-reviewer": "a reviewer that can edit what it reviews is not an "
                       "independent reviewer",
}

# Everything such an agent may hold. Adding a name here widens what a
# reviewer can do to the thing it is reviewing, so it is a design decision
# with an argument attached, not a way to make a red build go green.
#
# Note what is absent and why the list is not "the write tools, negated":
# `Bash` writes any file with a redirection, `Task` delegates to an agent
# that can write, `WebFetch` reaches the network, and every MCP server spells
# its write tools differently -- `mcp__appian-dev__createRecordType` and
# another server's equivalent share no substring worth matching on. None of
# those can be enumerated. What a reviewer needs can.
READ_ONLY_TOOLS = frozenset(("Read", "Grep", "Glob", "Skill"))

# A key at the start of a line ends the previous key's declaration. Anything
# indented, blank, or commented belongs to the key above it.
TOP_LEVEL_KEY = re.compile(r"^[A-Za-z0-9_-]+:")

# `  - Read` -- one entry of a YAML block sequence.
BLOCK_ITEM = re.compile(r"^\s*-\s*(.+?)\s*$")

# A YAML comment, whole-line or trailing.
COMMENT = re.compile(r"(?m)(?:^|\s)#.*$")

# A tool name, or the `*` that stands for all of them. Deliberately greedy
# about `_` and `-` so an MCP name arrives whole:
# `mcp__appian-dev__createRecordType` is one token that is not on the
# whitelist, rather than several fragments that individually look harmless.
#
# Not `\b[A-Z][A-Za-z]*\b`, which is the obvious spelling and was proposed
# for this: built-in tool names are capitalised, but MCP tool names are not,
# and there is no `\b[A-Z]` anywhere in `mcp__appian-dev__createRecordType`
# -- the capital R sits between two word characters, so no boundary
# precedes it. That pattern harvests `Read` and `Grep` from the line and
# nothing else, and reports an agent granted every Appian write tool as
# clean. Measured, not reasoned about.
TOOL_TOKEN = re.compile(r"\*|[A-Za-z_][A-Za-z0-9_-]*")

# Whitespace, list punctuation and block-scalar indicators: everything a
# `tools:` declaration can be made of while naming no tool at all.
PUNCTUATION_ONLY = re.compile(r"[\s\-\[\],>|]")


def declaration_regions(text, key):
    """The raw block of every declaration of `key`, punctuation and all.

    A region runs from the `key:` line to the next top-level key, so it holds
    the inline value AND every continuation line -- block sequence entries,
    the tail of a flow sequence that wrapped, comment lines, blank lines, the
    body of a block scalar. Whatever the spelling, the names it grants are in
    here somewhere.

    Every declaration, not the first: YAML resolves a duplicate key to the
    last one, so a reader that returns at the first match reads a declaration
    the loader discards. `tools: Read` followed by `tools: Read, Write` is a
    grant of Write that stopping early reports as read-only.
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

    For `skills:` only -- see the module docstring on why the tools rule does
    not go through here. Names are resolved against a whitelist, so a
    spelling this does not understand yields a name that does not resolve and
    gets printed.

    Not a YAML parser: a quoted entry containing a comma (`["a,b"]`) is split
    in two, and an anchor or alias is taken literally. Both surface as a
    complaint about a name nobody wrote, which is a bad message rather than a
    missed finding.
    """
    values = []
    for region in declaration_regions(text, key):
        lines = [COMMENT.sub("", line) for line in region.split("\n")]
        # A flow sequence may wrap across lines and a block sequence may be
        # interrupted by a comment or a blank line. Collecting the two shapes
        # separately, then splitting both on commas, reads all of them: the
        # scalar half rejoins a wrapped `[a,\n b]`, and the item half no
        # longer stops at the first line that is not an entry -- stopping
        # there dropped every name after a comment silently, which under a
        # whitelist is the one failure that does not print anything.
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

    A search over the raw region rather than a check on parsed names: a
    prohibition is not enforced by parsing, because every spelling a parser
    fails to understand becomes a token that does not match, and a token that
    does not match is a silent pass. The region is read whole and each
    word-like token in it is tested against `READ_ONLY_TOOLS`.

    Comments ARE stripped here, and the reasoning is the reverse of what it
    was under the blacklist this replaced. There, dropping a comment risked
    dropping a grant. Under a whitelist a comment's words are not grants and
    keeping them makes every documented tools line a false alarm -- `tools:
    Read # nothing that writes` would be refused for the word "nothing". What
    survives the strip is the declaration itself, which is exactly what the
    loader sees.
    """
    found = []
    for region in declaration_regions(text, "tools"):
        for token in TOOL_TOKEN.findall(COMMENT.sub("", region)):
            if token not in READ_ONLY_TOOLS and token not in found:
                found.append(token)
    return found


def declares_tools(text):
    """True when a `tools:` declaration names anything at all.

    An agent with no tools line inherits every tool in the session. So does
    one whose tools line is punctuation and comments, which is why emptiness
    is judged after stripping both rather than by the presence of the key.
    """
    for region in declaration_regions(text, "tools"):
        if PUNCTUATION_ONLY.sub("", COMMENT.sub("", region)):
            return True
    return False


def lint_agent(path, known_skills):
    try:
        # utf-8-sig, not utf-8: an editor that writes a BOM produces a file
        # whose first character is not `-`, so the frontmatter is not
        # recognised and every field reads as missing. Four findings about
        # a well-formed agent, none of them the actual problem.
        with open(path, encoding="utf-8-sig") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        # Caught rather than allowed to propagate, for the reason
        # check_package_integrity gives: a traceback out of a checker is a
        # broken checker to whoever reads the CI log, it takes the other
        # agents' results down with it, and it collapses the 0/1/3 vocabulary
        # the whole design rests on into "it crashed".
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
            # Says what to do, not only what is wrong. A finding that reads
            # "not permitted" leaves the reader two options, and the one they
            # reach for under time pressure is deleting the tool they needed.
            # Naming the route also names its price: the entry has to carry a
            # reason, because a set that grows without an argument is the
            # blacklist this replaced wearing the other polarity.
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

    The failure this exists for is silent in the worst direction. Rename
    `agents/appian-reviewer.md` and its `name:` together and every per-file
    check still passes -- name matches filename, tools are declared -- while
    the restriction simply stops applying to anything. Nothing prints,
    because a rule that matches no agent has no agent to complain about.

    lint_skills diagnoses the same phantom-entry hazard for SECTION_EXEMPT,
    but that one over-permits LOUDLY: a stale exemption skips a section check
    on a skill that is right there in the output. A stale restriction
    under-protects in silence, which is the worse of the two directions, so
    it is checked rather than commented about.

    What this cannot see: an agent that SHOULD be read-only and was never
    added here. `appian-second-reviewer.md` with `tools: *` passes, and no
    fact about the tree distinguishes it from an agent legitimately allowed
    to write. That is a judgement about intent; this is a check about names.
    """
    return [name for name in sorted(READ_ONLY_AGENTS) if name not in shipped]


def main(root):
    agents_dir = os.path.join(root, "agents")
    if not os.path.isdir(agents_dir):
        # Not exit 1. No agents/ means nothing was inspected, which is the
        # condition every checker in this plugin spells 3 -- reporting it as
        # a finding says something was checked and failed, and the whole
        # point of the third code is that those two stop being one signal.
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

    # Zero agents checked is not a pass, for the reason lint_skills.main
    # gives at length: "all agents passed" is trivially true of nothing. The
    # stale-entry check is skipped in that case rather than firing: against a
    # tree with no agents at all it would report every guarded name as
    # missing, which is true of the tree and says nothing about the rule.
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
