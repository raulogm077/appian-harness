"""Validates a practices-audit verdict against the plugin's own references.

A hook cannot see a subagent's transcript, so it cannot check that an auditor
loaded a skill. What it CAN check is the trail: the verdict must name the
reference sections it applied, and every one of them must resolve to a real
file and a real heading in this plugin. A fabricated citation fails here.

This does not prove the auditor read the section. It proves the section exists
and is locatable by a third party -- which is the failure mode that actually
occurs: the plausible citation that turns out not to exist.
"""
import json, os, re, sys

PHASES = ("design", "implementation", "review", "qa")
VERDICTS = ("PASS", "FAIL", "NOT_MEASURED")
CLASSES = ("BLOCKING", "DEFERRED")

REFERENCES_SUBDIR = os.path.join("skills", "appian-best-practices", "references")


def isfile_exact(path, root=None):
    """os.path.isfile, with the case of the path spelled as written.

    NTFS and APFS are case-insensitive by default and ext4 is not, so
    `practices-QA.json` satisfies `os.path.isfile(".../practices-qa.json")`
    on a laptop and not in CI -- the same evidence tree closing a task in one
    place and blocking it in the other. The documentation is unambiguous
    (the shape under evidenceDir is fixed, and a verdict named
    `practices-QA.json` is one the gate reports as missing), so the strict
    reading is the one implemented, everywhere. A harness that behaves
    differently in two places is worse than either behaviour consistently.

    `root` bounds how much of the path is held to that standard: every
    component *below* root must match on case, while root itself and
    everything above it are taken as given -- they are the project's own
    configured paths, not something an agent chose. With no root, only the
    final component is checked.
    """
    if not os.path.isfile(path):
        return False
    path = os.path.abspath(path)
    try:
        stop = os.path.abspath(root) if root else os.path.dirname(path)
        rel = os.path.relpath(path, stop)
        if rel == os.curdir or rel.startswith(os.pardir):
            raise ValueError("path is not under root")
    except ValueError:
        # Different drives on Windows, or a root that does not contain the
        # path: fall back to checking the name alone rather than giving up.
        stop, rel = os.path.dirname(path), os.path.basename(path)
    current = stop
    for part in rel.split(os.sep):
        try:
            if part not in os.listdir(current):
                return False
        except OSError:
            return False
        current = os.path.join(current, part)
    return True


def _slug(heading):
    """GitHub-style anchor for a markdown heading."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")


def anchors_of(path):
    anchors = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = re.match(r"^#{1,6}\s+(.*?)\s*$", line)
            if m:
                anchors.add(_slug(m.group(1)))
    return anchors


def load_verdict(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validate_verdict(path, plugin_root, expected_task=None, expected_phase=None):
    """Checks one verdict document.

    `expected_task` and `expected_phase` are what the caller was opening this
    path *for*. A gate always knows both -- it assembled the path from them --
    and passing them is what makes the document a claim about a particular
    piece of work rather than a claim about nothing in particular. Without
    them the only question asked of `phase` is whether it is one of four
    values, which one audit copied into four filenames answers four times.

    They stay optional because the standalone CLI use is real: the auditor
    validates its own verdict before any gate has opened it.
    """
    errors = []
    try:
        v = load_verdict(path)
    except ValueError as e:
        return ["cannot parse verdict as JSON: %s" % e]
    except OSError as e:
        return ["cannot read verdict: %s" % e]

    if not isinstance(v, dict):
        return ["verdict must be a JSON object"]

    task = v.get("task")
    if not task:
        errors.append("missing 'task'")
    elif expected_task is not None and task != expected_task:
        errors.append("verdict is for task %r but was found at the path for task %r: "
                      "an audit of one task does not certify another" % (task, expected_task))

    phase = v.get("phase")
    if phase not in PHASES:
        errors.append("'phase' is %r; must be one of %s" % (phase, ", ".join(PHASES)))
    elif expected_phase is not None and phase != expected_phase:
        errors.append("verdict declares phase %r but was found at the path for phase %r: "
                      "an audit of one phase does not certify another" % (phase, expected_phase))

    verdict = v.get("verdict")
    if verdict not in VERDICTS:
        errors.append("'verdict' is %r; must be one of %s -- there is no fourth value"
                      % (verdict, ", ".join(VERDICTS)))

    if verdict == "NOT_MEASURED":
        cls = v.get("notMeasuredClass")
        if cls not in CLASSES:
            errors.append("NOT_MEASURED needs 'notMeasuredClass' of %s" % ", ".join(CLASSES))
        elif cls == "DEFERRED":
            if not v.get("owner"):
                errors.append("a DEFERRED verdict needs an 'owner'; without one it degrades to BLOCKING")
            if not v.get("closingCondition"):
                errors.append("a DEFERRED verdict needs a 'closingCondition'")

    refs = v.get("referencesApplied")
    if not isinstance(refs, list) or not refs:
        errors.append("'referencesApplied' must be a non-empty list: an audit that applied no "
                      "reference is not an audit")
    else:
        refdir = os.path.join(plugin_root, REFERENCES_SUBDIR)
        for ref in refs:
            if not isinstance(ref, str) or "#" not in ref:
                errors.append("reference %r must be '<file>.md#<anchor>'" % (ref,))
                continue
            fname, anchor = ref.split("#", 1)
            fpath = os.path.join(refdir, fname)
            if not isfile_exact(fpath, refdir):
                errors.append("reference file %r does not exist in this plugin" % fname)
                continue
            if anchor not in anchors_of(fpath):
                errors.append("anchor %r does not exist in %s" % (anchor, fname))

    return errors


USAGE = """usage: validate_verdict.py VERDICT_JSON PLUGIN_ROOT [TASK PHASE]

TASK and PHASE are what this verdict is supposed to be about. Give them and
the document has to agree with them, which is the check the gates run: they
assembled the path from a task and a phase, so a document naming different
ones is an audit of other work sitting where this work's audit belongs.

Omit them to check the document's shape alone -- citations, required fields,
the three outcomes. That is the honest check to run before any gate has
opened the file."""


def main(argv):
    if len(argv) not in (3, 5):
        print(USAGE, file=sys.stderr)
        return 2
    expected_task, expected_phase = (argv[3], argv[4]) if len(argv) == 5 else (None, None)
    errs = validate_verdict(argv[1], argv[2], expected_task, expected_phase)
    for e in errs:
        print("ERROR %s: %s" % (argv[1], e))
    if errs:
        return 1
    print("OK %s" % argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
