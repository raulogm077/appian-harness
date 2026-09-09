"""Validates a practices-audit verdict against the plugin's own references.

Checks required fields, the three outcomes, and that every citation resolves
to a real file and heading in this plugin.
docs/design-notes.md § validate_verdict.py · what a citation check proves.

    usage: validate_verdict.py VERDICT_JSON PLUGIN_ROOT [TASK PHASE]
    exit: 0 valid, 1 errors printed, 2 usage"""
import json, os, re, sys, time

# `risk` asks how the thing fails, not whether it meets its contract:
# docs/design-notes.md § validate_verdict.py · the risk phase
PHASES_V07 = ("design", "certify", "risk")

# Norm § 15 keeps these accepted and obsolete. Removing them turns the
# verdicts of a 0.6 scope from insufficient into invalid, and a scope opened
# under the old rules then cannot close by any route.
PHASES_LEGACY = ("implementation", "review", "qa")
PHASES = PHASES_V07 + PHASES_LEGACY

VERDICTS = ("PASS", "FAIL", "NOT_MEASURED")

# `REQUIRES_HUMAN` is the v07 spelling (§ 9.5); the two before it belong to
# the 0.6 vocabulary and stay for the same reason PHASES_LEGACY does.
CLASS_REQUIRES_HUMAN = "REQUIRES_HUMAN"
CLASSES = ("BLOCKING", "DEFERRED", CLASS_REQUIRES_HUMAN)

# --- § 9.2 · the matrix: three natures of cell ------------------------
# What each cell IS, decided by who can answer it. Nature and class are
# independent axes: nature says who determines a FAIL, class says what
# happens to it.
NATURE_IMPORTED = "imported"
NATURE_JUDGED_ON_EVIDENCE = "judged-on-evidence"
NATURE_FULL_JUDGEMENT = "full-judgement"
NATURES = (NATURE_IMPORTED, NATURE_JUDGED_ON_EVIDENCE, NATURE_FULL_JUDGEMENT)

GATES = (1, 2, 3, 4, 5, 6, 7)
GATE_NAMES = {
    1: "platform correctness", 2: "functional behavior", 3: "security",
    4: "SAIL interfaces", 5: "performance", 6: "maintainability",
    7: "operations",
}
NATURE_BY_GATE = {
    1: NATURE_IMPORTED, 2: NATURE_IMPORTED,
    3: NATURE_JUDGED_ON_EVIDENCE, 5: NATURE_JUDGED_ON_EVIDENCE,
    4: NATURE_FULL_JUDGEMENT, 6: NATURE_FULL_JUDGEMENT,
    7: NATURE_FULL_JUDGEMENT,
}

# --- § 9.3 · the seven gates do not block alike -----------------------
CARDINAL = "CARDINAL"
RECOMMENDED = "RECOMMENDED"
CONTEXTUAL = "CONTEXTUAL"
GATE_CLASSES = (CARDINAL, RECOMMENDED, CONTEXTUAL)
CLASS_BY_GATE = {
    1: CARDINAL, 3: CARDINAL,
    2: RECOMMENDED, 4: RECOMMENDED, 7: RECOMMENDED,
    5: CONTEXTUAL, 6: CONTEXTUAL,
}

# The three the doctrine never grades down, whatever gate they land on
# (`appian-best-practices/SKILL.md`, "What is never graded down"). A cell or
# finding that names one is CARDINAL regardless of CLASS_BY_GATE.
NEVER_GRADED_DOWN = ("invalid-reference", "authorization-gap",
                     "non-idempotent-write")

# A read whose class is this proves the call returned green and nothing
# else, so it cannot accredit an imported cell (§ 8.4, § 9.2).
GREEN_SIGNAL_ONLY = "green-signal-only"

# --- § 9.5 · the closed list, split into two classes ------------------
# (a) Pending judgement: verdict entries the auditor writes. They close the
#     scope `closed-pending-human`.
PENDING_JUDGEMENT_IDS = ("visual-judgement-on-rendered-screen",
                         "instrument-limit-known")

# `design` is meant to precede every write, so there is no rendered screen
# to judge yet.
PENDING_IDS_INVALID_IN = {"visual-judgement-on-rendered-screen": ("design",)}

# (b) Guarantee-class residue: NOT verdict entries. The hook and the floor
#     write them to deferred-debt.jsonl and the scope closes `closed`.
#     Using one as a deferral is rejected, with the remedy named.
GUARANTEE_RESIDUE_IDS = ("branch-not-exercisable-without-writing-data",
                         "type-has-no-floor", "manual-step-not-tooled",
                         "external-effect-not-exercised")

# § 9.4: the third verdict of a phase is refused unless it carries a finding
# id absent from every earlier one. Versioned so there is something to
# compare against -- with a fixed name the second emission overwrites the
# first and the comparison has no corpus.
REISSUE_CAP = 3
_VERSIONED_RE = re.compile(r"^practices-([a-z]+)\.(\d{3})\.json$")

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


def validate_verdict(path, plugin_root, expected_task=None, expected_phase=None,
                     evidence_dir=None, instance_id=None):
    """Checks one verdict document. Gates pass the task and phase they
    assembled the path from; the CLI may omit both.
    docs/design-notes.md § validate_verdict.py · expected task and phase

    `evidence_dir` and `instance_id` are what an imported cell is resolved
    against (§ 9.2). Without them the matrix is checked for shape and the
    cited rows are not opened, which is the honest thing the CLI can do.
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
        elif cls == CLASS_REQUIRES_HUMAN:
            errors.extend(_requires_human_errors(v, phase))
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

    errors.extend(_findings_errors(v.get("findings"), phase))

    if phase == "certify":
        errors.extend(matrix_errors(v, plugin_root, evidence_dir, instance_id))
        errors.extend(header_agrees_with_matrix(v))
    errors.extend(reissue_errors(path, v))

    return errors


def _requires_human_errors(v, phase):
    """§ 9.5: the closed list lives outside the agent, and its two classes
    do not mix -- they lead to different terminal states (§ 10.1).

    Class (a) is a verdict entry and closes `closed-pending-human`. Class
    (b) is a row of deferred-debt.jsonl that the hook and the floor write,
    and the scope closes `closed`. Using a (b) id as a deferral is refused,
    with the remedy named: a declared ceiling per type is not a gate that
    failed, and treating it as one would send every integration, every
    manual type and every expressionless user filter to `pending-human` --
    blinding the very magnitude the exit gate uses.
    """
    errors = []
    if not v.get("owner"):
        errors.append("a REQUIRES_HUMAN verdict needs an 'owner'; without one it is "
                      "rejected, and the gate it was meant to open stays shut")
    if not v.get("closingCondition"):
        errors.append("a REQUIRES_HUMAN verdict needs a 'closingCondition'")
    criterion = v.get("deferredCriterion")
    if not criterion:
        errors.append("a REQUIRES_HUMAN verdict needs a 'deferredCriterion' off the "
                      "closed list of § 9.5 (a): %s" % ", ".join(PENDING_JUDGEMENT_IDS))
    elif criterion in GUARANTEE_RESIDUE_IDS:
        errors.append("'deferredCriterion' is %r, which is a guarantee-class residue, "
                      "not a pending judgement (§ 9.5 b). Nothing failed: that is a row "
                      "of deferred-debt.jsonl written by the hook and the floor, and the "
                      "scope closes `closed`. It is not a verdict entry and it does not "
                      "hold a close open" % criterion)
    elif criterion not in PENDING_JUDGEMENT_IDS:
        errors.append("'deferredCriterion' is %r, which is not on the closed list of "
                      "§ 9.5 (a): %s. The list lives in the plugin, not in the task"
                      % (criterion, ", ".join(PENDING_JUDGEMENT_IDS)))
    elif phase in PENDING_IDS_INVALID_IN.get(criterion, ()):
        errors.append("%r is not valid in phase %r: %s"
                      % (criterion, phase,
                         "design is meant to precede every write, so there is no "
                         "rendered screen to judge yet"))
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


def _findings_errors(findings, phase=None):
    """Checks the shape of `findings[]`, where `N/A` is legal but needs a
    justification about the object.
    docs/design-notes.md § validate_verdict.py · validating findings

    Under the v07 phases every finding also carries an `id`. That is what
    the re-emission cap compares (§ 9.4): without ids the third verdict has
    nothing to be measured against and the cap silently stops existing.
    """
    errors = []
    if findings is None:
        return errors
    if not isinstance(findings, list):
        return ["'findings' must be a list of finding objects"]

    ids = {}
    for i, f in enumerate(findings):
        where = "findings[%d]" % i
        if not isinstance(f, dict):
            errors.append("%s must be an object" % where)
            continue

        if phase in PHASES_V07:
            fid = f.get("id")
            if not (isinstance(fid, str) and fid.strip()):
                errors.append("%s needs a non-empty 'id': the re-emission cap of § 9.4 "
                              "compares finding ids across versions, and a finding "
                              "without one cannot be told apart from a restatement"
                              % where)
            elif fid in ids:
                errors.append("%s reuses finding id %r, already used at %s: two "
                              "different findings under one id read as one"
                              % (where, fid, ids[fid]))
            else:
                ids[fid] = where

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


def _nonempty(value):
    return isinstance(value, str) and value.strip()


def _checks_index(evidence_dir, instance_id):
    """`checks.jsonl` by toolUseId, for this instance only.

    Returns None when the ledger cannot be read at all, which is how the CLI
    (no evidenceDir) says "shape only" rather than "no row resolves". An
    empty dict means the ledger is there and holds nothing for us, and that
    IS a finding: docs/design-notes.md § validate_verdict.py · imported cells
    """
    if not evidence_dir:
        return None
    path = os.path.join(evidence_dir, "checks.jsonl")
    if not os.path.isfile(path):
        return None
    index = {}
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(row, dict):
                    continue
                if instance_id is not None \
                        and row.get("instanceId") != instance_id:
                    continue
                key = row.get("toolUseId")
                if _nonempty(key):
                    index[key] = row
    except OSError:
        return None
    return index


def _cited_row_errors(where, tool_use_id, index, instance_id):
    """Whether the row a cell points at exists, is this instance's, and
    bought more than a green signal (§ 9.2)."""
    if index is None:
        return []          # shape-only mode: nothing to resolve against
    row = index.get(tool_use_id)
    if row is None:
        return ["%s cites toolUseId %r, which is in no checks.jsonl row of this "
                "instance. A cell is accredited by a read the hook saw, not by a "
                "reference anyone can type" % (where, tool_use_id)]
    if instance_id is not None and row.get("instanceId") != instance_id:
        return ["%s cites a row of instance %r, not of this scope's %r"
                % (where, row.get("instanceId"), instance_id)]
    if row.get("guaranteeClass") == GREEN_SIGNAL_ONLY:
        return ["%s is accredited by a row whose guaranteeClass is %r: it proves the "
                "call returned green and nothing else, so it cannot carry a gate "
                "(§ 8.4)" % (where, GREEN_SIGNAL_ONLY)]
    return []


def _cell_nature(cell):
    """The nature this gate imposes, with the one exception of § 9.2: a
    gate-2 cell whose test case was created inside the scope stops being
    imported, because its evidence was fabricated by the interested party."""
    gate = cell.get("gate")
    if gate == 2 and cell.get("caseCreatedInScope") is True:
        return NATURE_JUDGED_ON_EVIDENCE
    return NATURE_BY_GATE.get(gate)


def gate_class(cell):
    """CARDINAL / RECOMMENDED / CONTEXTUAL for one cell (§ 9.3). A cell that
    names one of the three never-graded-down ids is CARDINAL wherever it
    landed; otherwise the gate decides."""
    if cell.get("neverGradedDown") in NEVER_GRADED_DOWN:
        return CARDINAL
    return CLASS_BY_GATE.get(cell.get("gate"))


def _proportional_errors(where, cell, refdir):
    """§ 9.2's proportional cell: a PASS is one line, and the full
    development is owed by the outcomes somebody is going to read."""
    errors = []
    outcome = cell.get("verdict")
    if outcome == "PASS":
        return errors
    for field in ("evidence", "impact", "remedy"):
        if not _nonempty(cell.get(field)):
            errors.append("%s is %s and needs a non-empty %r: a PASS is written in one "
                          "line, and the development is reserved for the cells someone "
                          "reads" % (where, outcome, field))
    if outcome == "N/A":
        justification = _strip_na(cell.get("evidence") or "")
        if not justification:
            errors.append("%s is N/A with no justification beyond the words 'N/A'" % where)
        elif PROCESS_EXCUSE.search(justification):
            errors.append("%s is N/A justified by the process, the schedule or the time "
                          "available, which is NOT_MEASURED, not N/A. N/A is a statement "
                          "about the object" % where)
    # "and a reference when it applies": it applies wherever the auditor
    # judged rather than imported, because that judgement cites doctrine.
    if _cell_nature(cell) != NATURE_IMPORTED:
        ref = cell.get("reference")
        if not _nonempty(ref):
            errors.append("%s is %s on a cell the auditor judged, so it owes a "
                          "'reference' naming the doctrine it applied" % (where, outcome))
        else:
            errors.extend(_reference_errors(ref, refdir, where))
    return errors


def _reference_errors(ref, refdir, where):
    """One `<file>.md#<anchor>` citation, resolved against references/."""
    if "#" not in ref:
        return ["%s reference %r must be '<file>.md#<anchor>'" % (where, ref)]
    fname, anchor = ref.split("#", 1)
    if not _is_citable_filename(fname):
        return ["%s reference %r must name a .md file directly inside references/"
                % (where, fname)]
    fpath = os.path.join(refdir, fname)
    if not isfile_exact(fpath, refdir):
        return ["%s reference file %r does not exist in this plugin" % (where, fname)]
    if anchor not in anchors_of(fpath):
        return ["%s anchor %r does not exist in %s" % (where, anchor, fname)]
    return []


def matrix_errors(v, plugin_root, evidence_dir=None, instance_id=None):
    """The object x gate matrix of § 9.2, for a `certify`.

    Full coverage is the guarantee and is not traded for tokens: one entry
    per object per gate, no gap and no duplicate. What changed in 0.7 is
    what each cell IS -- who can answer it -- not how many there are.
    """
    errors = []
    objects = v.get("objects")
    if not isinstance(objects, list) or not objects \
            or not all(_nonempty(o) for o in objects):
        return ["a certify verdict needs a non-empty 'objects' list naming the objects "
                "it covers: the matrix is object x gate, and without the objects there "
                "is nothing to be complete about"]

    matrix = v.get("matrix")
    if not isinstance(matrix, list) or not matrix:
        return ["a certify verdict needs a non-empty 'matrix': one entry per object per "
                "gate (§ 9.2). Cells are not dropped to save tokens -- a PASS costs one "
                "line"]

    refdir = os.path.join(plugin_root, REFERENCES_SUBDIR)
    index = _checks_index(evidence_dir, instance_id)
    seen = {}
    for i, cell in enumerate(matrix):
        where = "matrix[%d]" % i
        if not isinstance(cell, dict):
            errors.append("%s must be an object" % where)
            continue
        obj, gate = cell.get("object"), cell.get("gate")
        if obj not in objects:
            errors.append("%s is about %r, which is not in 'objects'" % (where, obj))
            continue
        if gate not in GATES:
            errors.append("%s has gate %r; the gates are 1-7" % (where, gate))
            continue
        if (obj, gate) in seen:
            errors.append("%s repeats object %r gate %d, already at matrix[%d]"
                          % (where, obj, gate, seen[(obj, gate)]))
            continue
        seen[(obj, gate)] = i

        outcome = cell.get("verdict")
        if outcome not in FINDING_VERDICTS:
            errors.append("%s has verdict %r; a cell is one of %s"
                          % (where, outcome, ", ".join(FINDING_VERDICTS)))
            continue

        expected = _cell_nature(cell)
        if cell.get("nature") != expected:
            errors.append("%s declares nature %r but gate %d (%s) is %r: who answers a "
                          "gate is not the auditor's to choose"
                          % (where, cell.get("nature"), gate, GATE_NAMES[gate], expected))

        if expected == NATURE_IMPORTED:
            # The auditor does not judge these: it copies the row that
            # accredits them, and the validator resolves the reference.
            tool_use_id = cell.get("toolUseId")
            if not _nonempty(tool_use_id):
                errors.append("%s is an imported cell and needs the 'toolUseId' of the "
                              "checks.jsonl row that accredits it (§ 9.2)" % where)
            else:
                errors.extend(_cited_row_errors(where, tool_use_id, index, instance_id))
                if not _nonempty(cell.get("result")):
                    errors.append("%s is an imported cell and needs the 'result' of that "
                                  "row alongside its toolUseId" % where)
        elif expected == NATURE_JUDGED_ON_EVIDENCE:
            # Judgement over a measurement somebody else took: it must cite
            # the row it is judging, and without one it cannot be a PASS.
            cites = cell.get("citesRow")
            if not _nonempty(cites):
                if outcome == "PASS":
                    errors.append("%s judges evidence and cites no row, so it cannot be "
                                  "PASS: with no row it is NOT_MEASURED (§ 9.2)" % where)
                elif outcome == "NOT_MEASURED":
                    pass
                elif outcome != "N/A":
                    errors.append("%s judges evidence and needs 'citesRow' naming the "
                                  "row it judged" % where)
            else:
                errors.extend(_cited_row_errors(where, cites, index, instance_id))

        if cell.get("neverGradedDown") is not None \
                and cell.get("neverGradedDown") not in NEVER_GRADED_DOWN:
            errors.append("%s names neverGradedDown %r, which is not one of %s"
                          % (where, cell.get("neverGradedDown"),
                             ", ".join(NEVER_GRADED_DOWN)))

        errors.extend(_proportional_errors(where, cell, refdir))

    missing = [(o, g) for o in objects for g in GATES if (o, g) not in seen]
    if missing:
        errors.append("the matrix is incomplete: %s. Full coverage is the guarantee -- "
                      "a gate nobody wrote down is not a gate that passed"
                      % ", ".join("%s gate %d (%s)" % (o, g, GATE_NAMES[g])
                                  for o, g in missing[:10]))
    return errors


def header_agrees_with_matrix(v):
    """The top-level verdict is derived, not summarised.

    An auditor that writes PASS over a failing cell has graded its own work.
    Class does not enter here on purpose (§ 9.3): what a CONTEXTUAL FAIL
    buys is decided at the gate, not by hiding the FAIL.
    """
    cells = [c for c in (v.get("matrix") or []) if isinstance(c, dict)]
    if not cells:
        return []
    outcomes = [c.get("verdict") for c in cells]
    if "FAIL" in outcomes:
        expected = "FAIL"
    elif "NOT_MEASURED" in outcomes:
        expected = "NOT_MEASURED"
    else:
        expected = "PASS"
    if v.get("verdict") != expected:
        return ["the verdict says %r while its matrix says %r (%d FAIL, %d NOT_MEASURED): "
                "the top-level outcome is derived from the cells, never summarised over "
                "them" % (v.get("verdict"), expected, outcomes.count("FAIL"),
                          outcomes.count("NOT_MEASURED"))]
    return []


def _finding_ids(path):
    """The `findings[].id` set of one verdict on disk. Unreadable counts as
    empty: a file nobody can parse contributes no ids to compare against."""
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return set()
    if not isinstance(doc, dict):
        return set()
    return set(f["id"] for f in (doc.get("findings") or [])
               if isinstance(f, dict) and _nonempty(f.get("id")))


def earlier_versions(path):
    """Every `practices-<phase>.NNN.json` before this one, in order.

    Set comparison over files on disk rather than over anything the verdict
    declares: § 9.4 asks what is there, not what it says about itself.
    """
    match = _VERSIONED_RE.match(os.path.basename(path))
    if not match:
        return []
    phase, number = match.group(1), int(match.group(2))
    directory = os.path.dirname(path) or os.curdir
    earlier = []
    for index in range(1, number):
        sibling = os.path.join(directory, "practices-%s.%03d.json" % (phase, index))
        if os.path.isfile(sibling):
            earlier.append(sibling)
    return earlier


def reissue_errors(path, v):
    """§ 9.4: the third verdict of a phase is refused unless it brings a
    finding nobody had raised.

    This is the one anti-waste magnitude that goes from auditable to
    impossible, and it is enforcement rather than a number in a report: the
    7 re-emissions asked for by hand were the most expensive defect of the
    session that motivated the redesign.
    """
    match = _VERSIONED_RE.match(os.path.basename(path))
    if not match:
        return []
    number = int(match.group(2))
    if number < REISSUE_CAP:
        return []
    earlier = earlier_versions(path)
    if not earlier:
        return []
    already = set()
    for sibling in earlier:
        already |= _finding_ids(sibling)
    mine = set(f["id"] for f in (v.get("findings") or [])
               if isinstance(f, dict) and _nonempty(f.get("id")))
    new = mine - already
    if new:
        return []
    return ["this is emission #%d of practices-%s and it raises no finding the %d "
            "earlier one(s) did not already carry. A cycle is every finding applied "
            "in one batch and a single re-certify (§ 9.4); re-running the judge to "
            "get a different answer is not a cycle. Apply the open findings, or "
            "close with the debt recorded" % (number, match.group(1), len(earlier))]


USAGE = """usage: validate_verdict.py VERDICT_JSON PLUGIN_ROOT [TASK PHASE]

TASK and PHASE are what this verdict is supposed to be about. Give them and
the document has to agree with them, which is the check the gates run: they
assembled the path from a task and a phase, so a document naming different
ones is an audit of other work sitting where this work's audit belongs.

Omit them to check the document's shape alone -- citations, required fields,
the three outcomes. That is the honest check to run before any gate has
opened the file.

The imported cells of a `certify` matrix are resolved against
`checks.jsonl` when it can be found: the verdict's own `instanceId` selects
the rows, and the ledger is looked for in the parent of the verdict's
directory, which is where `<evidenceDir>/<task>/` puts it. Run from
somewhere else and those cells are checked for shape alone -- which the
output says, rather than passing them in silence."""


def _implied_evidence_dir(path):
    """`<evidenceDir>` inferred from `<evidenceDir>/<task>/practices-*.json`.

    The ledger is per evidenceDir, not per scope (§ 11.1). Returned only
    when the file is actually there, so the caller can tell "no ledger" from
    "a ledger with no matching row".
    """
    parent = os.path.dirname(os.path.dirname(os.path.abspath(path)))
    return parent if os.path.isfile(os.path.join(parent, "checks.jsonl")) else None


def main(argv):
    if len(argv) not in (3, 5):
        print(USAGE, file=sys.stderr)
        return 2
    expected_task, expected_phase = (argv[3], argv[4]) if len(argv) == 5 else (None, None)
    try:
        instance_id = load_verdict(argv[1]).get("instanceId")
    except (OSError, ValueError, AttributeError):
        instance_id = None
    errs = validate_verdict(argv[1], argv[2], expected_task, expected_phase,
                            evidence_dir=_implied_evidence_dir(argv[1]),
                            instance_id=instance_id)
    for e in errs:
        print("ERROR %s: %s" % (argv[1], e))
    if errs:
        return 1
    print("OK %s" % argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
