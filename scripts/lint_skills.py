"""Validates SKILL.md files against the appian-harness authoring contract.

    python3 scripts/lint_skills.py [root]

Exit 0 pass, 1 findings, 3 nothing was checked.
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Imported and re-exported -- lint_agents holds this import:
# docs/design-notes.md § lint_skills.py · shared exit code
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

MAX_DESCRIPTION = 1024

REQUIRED_SECTIONS = [
    "## Overview",
    "## When to Use",
    "## Common Rationalizations",
    "## Red Flags",
    "## Verification",
]

# Both the imperative and the third-person phrasings count as saying WHEN a
# skill fires: docs/design-notes.md § lint_skills.py · trigger phrasings
TRIGGER = re.compile(
    r"\buse (this )?when\b|\buse (before|after|during)\b"
    r"|\bused when\b|\bused (before|after|during)\b",
    re.I,
)
# A negation in the same sentence marks an exclusion, and need not sit next
# to the verb: docs/design-notes.md § lint_skills.py · negation window
TRIGGER_NEGATED = re.compile(r"\b(do not|don't|never|avoid|not)\b[^.!?]{0,30}\bused?\b", re.I)

# Deliberately naive -- a mis-split yields a sentence with no trigger, which
# the next one covers. docs/design-notes.md § lint_skills.py · sentence split
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def has_trigger(description):
    """True when SOME sentence says when the skill fires.

    Per sentence, so a trigger followed by an exclusion still passes:
    docs/design-notes.md § lint_skills.py · per-sentence judgement
    """
    for sentence in SENTENCE_SPLIT.split(description):
        if TRIGGER.search(sentence) and not TRIGGER_NEGATED.search(sentence):
            return True
    return False

# name -> documented reason. Exemptions live here so a skill cannot bypass
# the validator: docs/design-notes.md § lint_skills.py · SECTION_EXEMPT
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
    # Zero skills is not a pass; exit 3 keeps "nothing was checked" apart
    # from a failure. docs/design-notes.md § lint_skills.py · exit 3
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
