"""Validates SKILL.md files against the appian-harness authoring contract.

Exemptions live HERE, not in skill frontmatter, so a skill cannot bypass the
validator by editing its own file. Every entry needs a documented reason.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Imported rather than restated, and re-exported rather than used through the
# module name: lint_agents.py does `from lint_skills import EXIT_NOT_MEASURED`
# alongside MAX_DESCRIPTION and has_trigger, and that import is what a test
# holds. The comment this line replaced claimed the value was "shared with
# n2_interface_tree and n3_process_layout" while all three typed it out
# separately -- shared by assertion, not by construction.
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

MAX_DESCRIPTION = 1024

REQUIRED_SECTIONS = [
    "## Overview",
    "## When to Use",
    "## Common Rationalizations",
    "## Red Flags",
    "## Verification",
]

# A description must say WHEN the skill fires, not only what it is. Both the
# imperative house style ("Use when...") and the third-person form
# `plugin-dev:skill-development` prescribes ("This skill should be used
# when...") count: rejecting the latter would refuse a skill written exactly
# as the official guidance recommends. `plugin-dev:skill-reviewer` found the
# phrasing choice itself does not affect triggering quality — only the
# specificity of the stated conditions does — so both forms are accepted on
# equal footing rather than one being treated as a fallback.
TRIGGER = re.compile(
    r"\buse (this )?when\b|\buse (before|after|during)\b"
    r"|\bused when\b|\bused (before|after|during)\b",
    re.I,
)
# "Do not use when...", "Not for use when...", "should not be used when...",
# etc. describe an exclusion, not a trigger. The negation word can be a few
# words away from "use"/"used" ("Not for use when...") rather than directly
# adjacent to it ("Do not use when..."), so this matches a negation word
# followed, within the same sentence, by "use" or "used".
#
# This is applied per sentence, by has_trigger below, and that is the whole
# point of it. Applied to the description as a whole it rejected
# "Use when X. Do not use when Y." -- a description with a perfectly good
# trigger and an exclusion after it, which is the commonest real shape there
# is. An earlier comment here claimed sentence punctuation protected that
# case; it does not. What it protects is a negation placed BEFORE the
# trigger ("Not applicable to legacy skills. Use when...") which the
# `[^.!?]` cannot reach across. A negation AFTER the trigger sits in its own
# later sentence and matched perfectly well.
TRIGGER_NEGATED = re.compile(r"\b(do not|don't|never|avoid|not)\b[^.!?]{0,30}\bused?\b", re.I)

# Splitting on sentence-ending punctuation followed by whitespace. A
# description is one or two sentences of prose, so this does not need to
# survive "e.g." or an abbreviation mid-clause -- and if it mis-split one,
# the result is a sentence with no trigger, which the next sentence covers.
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def has_trigger(description):
    """True when SOME sentence says when the skill fires.

    Per sentence rather than per description: a trigger and an exclusion are
    two different statements, and a skill that states both is better
    documented than one that states only the trigger. Judging them together
    means the better description is the one that gets rejected.

    The exclusion sentence still cannot serve as the trigger on its own --
    it is skipped, not accepted -- so a description carrying only
    "Do not use when..." fails exactly as before.
    """
    for sentence in SENTENCE_SPLIT.split(description):
        if TRIGGER.search(sentence) and not TRIGGER_NEGATED.search(sentence):
            return True
    return False

# name -> documented reason. Empty on purpose: every skill this plugin ships
# carries the required sections, so nothing is exempt. The mechanism stays
# because a router skill -- one that only lists other skills, with no
# procedure to rationalize about -- would legitimately need it. It held one
# entry for "using-appian-harness", a skill that does not exist here; a live
# exemption for a phantom would silently exempt whatever took that name
# later, which is not what a file whose exemptions are meant to be
# unbypassable should do.
SECTION_EXEMPT = {}


def parse_frontmatter(text):
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    key = None
    for line in parts[1].splitlines():
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            key = m.group(1)
            meta[key] = m.group(2).strip()
        elif key and line.strip():
            meta[key] = (meta[key] + " " + line.strip()).strip()
    return meta, parts[2]


def lint_skill(path):
    errors = []
    with open(path, encoding="utf-8") as f:
        text = f.read()
    meta, body = parse_frontmatter(text)
    directory = os.path.basename(os.path.dirname(path))

    name = meta.get("name", "")
    if not name:
        errors.append("missing 'name' in frontmatter")
    elif name != directory:
        errors.append("'name' is %r but the directory is %r; they must match" % (name, directory))
    if name and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name):
        errors.append("'name' must be kebab-case")

    desc = meta.get("description", "")
    if not desc:
        errors.append("missing 'description' in frontmatter")
    else:
        if len(desc) > MAX_DESCRIPTION:
            errors.append("description is %d chars; the limit is %d" % (len(desc), MAX_DESCRIPTION))
        if not has_trigger(desc):
            errors.append("description has no trigger phrase (needs 'use when' / 'use before' in "
                          "a sentence that is not itself an exclusion; a negated form does not count)")

    if name not in SECTION_EXEMPT:
        for section in REQUIRED_SECTIONS:
            if not re.search(r"^%s\s*$" % re.escape(section), body, re.M):
                errors.append("missing required section %r" % section)

    return errors


def main(root):
    checked = 0
    failed = 0
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        print("ERROR: no skills/ directory under %s" % root)
        return 1
    for entry in sorted(os.listdir(skills_dir)):
        path = os.path.join(skills_dir, entry, "SKILL.md")
        if not os.path.isfile(path):
            continue
        checked += 1
        errs = lint_skill(path)
        for e in errs:
            print("ERROR %s: %s" % (path, e))
        if errs:
            failed += 1
        else:
            print("OK    %s" % path)
    # Zero skills checked is NOT a pass: "All skills passed" would be
    # trivially true of nothing. This harness exists to keep "verified" from
    # being confused with "not measured", so say NOT MEASURED explicitly and
    # fail the run -- with exit 3, which every checker in this plugin now
    # uses for that condition, kept distinct from 1 so "nothing was checked"
    # and "something was checked and failed" stop being one signal.
    if checked == 0:
        print("\nNOT MEASURED: skills/ exists but contains no SKILL.md files; 0 skills were validated.")
        return EXIT_NOT_MEASURED
    if failed:
        print("\n%d skill(s) failed." % failed)
        return 1
    print("\n%d skill(s) passed." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..")))
