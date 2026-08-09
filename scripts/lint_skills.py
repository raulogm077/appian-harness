"""Validates SKILL.md files against the appian-harness authoring contract.

Exemptions live HERE, not in skill frontmatter, so a skill cannot bypass the
validator by editing its own file. Every entry needs a documented reason.
"""
import os, re, sys

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
# followed, within the same sentence, by "use" or "used" — but a
# sentence-ending punctuation mark between them breaks the match, so a
# negation earlier in the description that isn't about the trigger clause
# ("Not applicable to legacy skills. Use when...") is left alone.
TRIGGER_NEGATED = re.compile(r"\b(do not|don't|never|avoid|not)\b[^.!?]{0,30}\bused?\b", re.I)

# name -> documented reason
SECTION_EXEMPT = {
    "using-appian-harness": "Router skill: it lists other skills, it has no procedure to rationalize about.",
}


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
        if TRIGGER_NEGATED.search(desc) or not TRIGGER.search(desc):
            errors.append("description has no trigger phrase (needs 'use when' / 'use before'; a negated form does not count)")

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
    # fail the run.
    if checked == 0:
        print("\nNOT MEASURED: skills/ exists but contains no SKILL.md files; 0 skills were validated.")
        return 1
    if failed:
        print("\n%d skill(s) failed." % failed)
        return 1
    print("\n%d skill(s) passed." % checked)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..")))
