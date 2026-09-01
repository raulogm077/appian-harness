"""Validates a practices-audit verdict against the plugin's own references.

Checks required fields, the three outcomes, and that every citation resolves
to a real file and heading in this plugin.
docs/design-notes.md § validate_verdict.py · what a citation check proves.

    usage: validate_verdict.py VERDICT_JSON PLUGIN_ROOT [TASK PHASE]
    exit: 0 valid, 1 errors printed, 2 usage"""
import json, os, re, sys, time

# `risk` asks how the thing fails, not whether it meets its contract:
# docs/design-notes.md § validate_verdict.py · the risk phase
PHASES = ("design", "implementation", "review", "qa", "risk")
VERDICTS = ("PASS", "FAIL", "NOT_MEASURED")
CLASSES = ("BLOCKING", "DEFERRED")

# Legal for one finding, never for the whole verdict:
# docs/design-notes.md § validate_verdict.py · N/A at finding level
FINDING_VERDICTS = VERDICTS + ("N/A",)

# The closed list, and a DEFERRED verdict must name which entry it invokes:
# docs/design-notes.md § validate_verdict.py · the closed list
DEFERRABLE_CRITERIA = (
    "screen-reader-testing",
    "design-guidance-warnings",
    "row-and-field-level-security-with-a-real-user",
    "contrast-against-theme-supplied-colors",
    "process-model-connection-routing",
)

# A tripwire on the phrasings the excuse arrives in, not a semantic judgement:
# docs/design-notes.md § validate_verdict.py · the process-excuse tripwire
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
    """Case-exact os.path.isfile below `root`; outside `root`, False.
    docs/design-notes.md § validate_verdict.py · case-exact paths, paths outside root"""
    if not os.path.isfile(path):
        return False
    path = os.path.abspath(path)
    if root:
        stop = os.path.abspath(root)
        try:
            rel = os.path.relpath(path, stop)
        except ValueError:
            return False  # different drives: it cannot be under root
        if rel == os.curdir or rel == os.pardir or rel.startswith(os.pardir + os.sep):
            return False
    else:
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


def _is_citable_filename(fname):
    """A `.md` file directly inside `references/`, nothing that leaves it.
    docs/design-notes.md § validate_verdict.py · citable filenames"""
    if not fname or os.path.isabs(fname) or not fname.lower().endswith(".md"):
        return False
    parts = fname.replace("\\", "/").split("/")
    if len(parts) != 1:
        return False
    return parts[0] not in (os.curdir, os.pardir)


def _slug(heading):
    """The anchor for a markdown heading, as THIS validator derives it.
    Deliberately NOT GitHub's slug rule, which keeps runs of separators:
    docs/design-notes.md § validate_verdict.py · the slug rule"""
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
    """Checks one verdict document. Gates pass the task and phase they
    assembled the path from; the CLI may omit both.
    docs/design-notes.md § validate_verdict.py · expected task and phase"""
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
            # An ownerless deferral is refused, not rewritten into another class:
            # docs/design-notes.md § validate_verdict.py · DEFERRED is rejected
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

    # Shape, not presence: absent is a legal mtime fallback, malformed is not.
    # docs/design-notes.md § validate_verdict.py · recordedAt
    recorded = v.get("recordedAt")
    if recorded is not None:
        ok = isinstance(recorded, str)
        if ok:
            try:
                time.strptime(recorded.strip(), "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                ok = False
        if not ok:
            errors.append("'recordedAt' must be UTC in exactly 'YYYY-MM-DDThh:mm:ssZ', not %r. "
                          "Any other spelling is ignored and the closure gate silently falls "
                          "back to the file's modification time" % (recorded,))

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
            # Shape first, so a file that exists out of bounds is not reported
            # as missing. docs/design-notes.md § validate_verdict.py · citable filenames
            if not _is_citable_filename(fname):
                errors.append("reference %r must name a .md file directly inside references/ -- "
                              "no absolute path, no '..', no subdirectory. A citation names "
                              "this plugin's doctrine, not an arbitrary file" % fname)
                continue
            fpath = os.path.join(refdir, fname)
            if not isfile_exact(fpath, refdir):
                errors.append("reference file %r does not exist in this plugin" % fname)
                continue
            if anchor not in anchors_of(fpath):
                errors.append("anchor %r does not exist in %s" % (anchor, fname))

    errors.extend(_findings_errors(v.get("findings")))

    return errors


def _strip_na(text):
    """Removes leading 'N/A' tokens and their punctuation, so what is left is
    the part that was supposed to be about the object.
    docs/design-notes.md § validate_verdict.py · bare N/A in evidence"""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"^\s*(n\s*/\s*a|not\s+applicable)\s*[:.,;-]*\s*", "", text, flags=re.I)
    return text.strip()


def _findings_errors(findings):
    """Checks the shape of `findings[]`, where `N/A` is legal but needs a
    justification about the object.
    docs/design-notes.md § validate_verdict.py · validating findings"""
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
