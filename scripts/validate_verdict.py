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

# `N/A` is legal for one finding and never for the whole verdict: it is the
# decision that a gate never came into play for this object, made before the
# three outcomes become relevant (10-quality-gates.md#how-its-recorded).
FINDING_VERDICTS = VERDICTS + ("N/A",)

# THE closed list of deferrable criteria. It lives here, in code, in one
# place -- `10-quality-gates.md` and the auditor point at these ids rather
# than restating them, and a test parses the document's copy and asserts it
# matches this tuple, because a list hand-copied into three files is exactly
# the drift this plugin keeps finding in itself.
#
# What makes the list mean anything is that a DEFERRED verdict must name
# which entry it is invoking. Without that field the closed list was
# unenforceable by construction: nothing in the document said which
# criterion was being deferred, so "an agent cannot declare a criterion
# deferrable in order to unblock itself" was a sentence with no mechanism
# under it, and DEFERRED was an unconditional unlock.
DEFERRABLE_CRITERIA = (
    "screen-reader-testing",
    "design-guidance-warnings",
    "row-and-field-level-security-with-a-real-user",
    "contrast-against-theme-supplied-colors",
    "process-model-connection-routing",
)

# A tripwire, not a semantic judgement. The document requires an `N/A` to be
# justified by what the OBJECT does or does not expose, "never a
# justification about the process, the schedule or the time available" --
# and that distinction cannot be decided by a regular expression. What this
# can do is catch the handful of phrasings the excuse actually arrives in,
# which is enough to stop it passing *silently*. A false positive costs one
# rewording; the false negative it replaces cost a gate.
PROCESS_EXCUSE = re.compile(
    r"\b(did\s?n[o']?t\s+(get|have)|didnt\s+(get|have)"
    r"|no\s+time|out\s+of\s+time|not\s+enough\s+time|lack\s+of\s+time|time\s+constraints?"
    r"|deadline|schedule|sprint|later\s+(sprint|release|task|phase|on)"
    r"|too\s+busy|skipp?ed|todo|to\s+be\s+done|will\s+(do|check|verify|revisit)"
    r"|next\s+time|for\s+now|ran\s+out)\b",
    re.I,
)

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
            # Rejected, not degraded. The document used to describe an
            # ownerless deferral as degrading to BLOCKING, and this message
            # repeated the claim -- but nothing degrades anything: the
            # verdict is refused and the gate stays shut. Rewriting an
            # agent's document into a class it did not write would be worse
            # than refusing it, because the record would then say something
            # nobody claimed. So the behaviour stays and the words changed.
            if not v.get("owner"):
                errors.append("a DEFERRED verdict needs an 'owner'; without one it is rejected, "
                              "and the gate it was meant to open stays shut")
            if not v.get("closingCondition"):
                errors.append("a DEFERRED verdict needs a 'closingCondition'")
            criterion = v.get("deferredCriterion")
            if not criterion:
                errors.append("a DEFERRED verdict needs a 'deferredCriterion' naming which "
                              "criterion off the plugin's closed list is being deferred; one of: "
                              "%s" % ", ".join(DEFERRABLE_CRITERIA))
            elif criterion not in DEFERRABLE_CRITERIA:
                errors.append("'deferredCriterion' is %r, which is not on the plugin's closed "
                              "list: %s. The list lives in the plugin, not in the task -- a "
                              "criterion cannot be declared deferrable in order to unblock a "
                              "task" % (criterion, ", ".join(DEFERRABLE_CRITERIA)))

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

    errors.extend(_findings_errors(v.get("findings")))

    return errors


def _strip_na(text):
    """Removes leading 'N/A' tokens and their punctuation.

    `"evidence": "N/A"` restates the verdict instead of justifying it, and
    the document is explicit that a bare N/A does not count. What is left
    after this is the part that was supposed to be about the object."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"^\s*(n\s*/\s*a|not\s+applicable)\s*[:.,;-]*\s*", "", text, flags=re.I)
    return text.strip()


def _findings_errors(findings):
    """Checks the shape of `findings[]`.

    This went entirely unvalidated, which left the per-gate "N/A: didn't get
    to it" alive inside the one field nobody looked at -- the exact hatch
    the three-outcomes section exists to close. Unlike the top-level
    verdict, `N/A` IS legal here: it is the decision that a gate never
    applied to this object. What it needs is a justification about the
    object, and that is what gets checked.
    """
    errors = []
    if findings is None:
        return errors
    if not isinstance(findings, list):
        return ["'findings' must be a list of finding objects"]

    for i, f in enumerate(findings):
        where = "findings[%d]" % i
        if not isinstance(f, dict):
            errors.append("%s must be an object" % where)
            continue

        if not (isinstance(f.get("criterion"), str) and f["criterion"].strip()):
            errors.append("%s needs a non-empty 'criterion' naming what was checked" % where)

        fv = f.get("verdict")
        if fv not in FINDING_VERDICTS:
            errors.append("%s has verdict %r; a finding is one of %s"
                          % (where, fv, ", ".join(FINDING_VERDICTS)))

        evidence = f.get("evidence")
        if not (isinstance(evidence, str) and evidence.strip()):
            errors.append("%s needs non-empty 'evidence' saying what was looked at" % where)
        elif fv == "N/A":
            justification = _strip_na(evidence)
            if not justification:
                errors.append("%s is N/A with no justification beyond the words 'N/A'. N/A needs "
                              "a concrete reason about the OBJECT -- what it does not expose, "
                              "touch or need" % where)
            elif PROCESS_EXCUSE.search(justification):
                errors.append("%s is N/A justified by the process, the schedule or the time "
                              "available (%r), which the gates do not accept as N/A under any "
                              "name: that is NOT_MEASURED / BLOCKING. N/A is a statement about "
                              "the object" % (where, evidence))

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
