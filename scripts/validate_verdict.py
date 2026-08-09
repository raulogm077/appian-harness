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


def validate_verdict(path, plugin_root):
    errors = []
    try:
        v = load_verdict(path)
    except ValueError as e:
        return ["cannot parse verdict as JSON: %s" % e]
    except OSError as e:
        return ["cannot read verdict: %s" % e]

    if not isinstance(v, dict):
        return ["verdict must be a JSON object"]

    if not v.get("task"):
        errors.append("missing 'task'")

    phase = v.get("phase")
    if phase not in PHASES:
        errors.append("'phase' is %r; must be one of %s" % (phase, ", ".join(PHASES)))

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
            if not os.path.isfile(fpath):
                errors.append("reference file %r does not exist in this plugin" % fname)
                continue
            if anchor not in anchors_of(fpath):
                errors.append("anchor %r does not exist in %s" % (anchor, fname))

    return errors


def main(argv):
    if len(argv) != 3:
        print("usage: validate_verdict.py VERDICT_JSON PLUGIN_ROOT", file=sys.stderr)
        return 2
    errs = validate_verdict(argv[1], argv[2])
    for e in errs:
        print("ERROR %s: %s" % (argv[1], e))
    if errs:
        return 1
    print("OK %s" % argv[1])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
