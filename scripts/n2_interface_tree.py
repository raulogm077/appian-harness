"""Deterministic checks over an interface's EVALUATED component tree, which
carries resolved data a linter over the source can never see.

    usage: n2_interface_tree.py TREE_JSON [--empty-path]
    exit: 0 clean, 1 findings or unreadable input, 2 usage, 3 NOT MEASURED

Why the evaluated tree, and the two traps in fetching one:
docs/design-notes.md § n2_interface_tree.py · why the evaluated tree, platform traps"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

DESTRUCTIVE = re.compile(r"\b(delete|remove|discard|revoke|purge|erase|cancel account)\b", re.I)
TECHNICAL = re.compile(r"\[L?java|^null$|^\{.*\}$|[0-9a-f]{8}-[0-9a-f]{4}-|recordType!", re.I)
INPUTS = ("TextField", "ParagraphField", "IntegerField", "FloatingPointField",
          "DateField", "DropdownField", "CheckboxField", "RadioButtonField", "PickerField")
CONFIRM_KEYS = ("confirmMessage", "confirmHeader", "confirmButtonLabel")

# The `#t` values this checker judges, and USAGE is built from it:
# docs/design-notes.md § n2_interface_tree.py · the checked-type vocabulary
CHECKED_TYPES = INPUTS + ("Grid", "Button", "DynamicLink", "Text")


def _srgb(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hexcolor):
    h = hexcolor.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _srgb(r) + 0.7152 * _srgb(g) + 0.0722 * _srgb(b)


def contrast_ratio(fg, bg):
    a, b = _luminance(fg), _luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


def _walk(node, out):
    if isinstance(node, dict):
        out.append(node)
        for v in node.values():
            _walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk(v, out)
    return out


def type_census(tree):
    """(recognised, unrecognised) `#t` values in this tree, both sorted.
    Coverage is not a finding, so it stays out of check_tree's return shape:
    docs/design-notes.md § n2_interface_tree.py · type_census"""
    recognised, unrecognised = set(), set()
    for n in _walk(tree, []):
        t = n.get("#t")
        if not isinstance(t, str) or not t:
            continue
        (recognised if t in CHECKED_TYPES else unrecognised).add(t)
    return sorted(recognised), sorted(unrecognised)


def check_tree(tree, empty_path=False):
    findings = []
    for n in _walk(tree, []):
        t = n.get("#t", "")
        where = "%s(%s)" % (t, n.get("label") or n.get("text") or "")

        fg, bg = n.get("color"), n.get("backgroundColor")
        if isinstance(fg, str) and fg.startswith("#") and isinstance(bg, str) and bg.startswith("#"):
            ratio = contrast_ratio(fg, bg)
            if ratio < 4.5:
                findings.append({"check": "contrast", "where": where,
                                 "detail": "%s on %s is %.2f:1, below WCAG AA 4.5:1" % (fg, bg, ratio)})

        label = n.get("label") or n.get("text") or ""
        if DESTRUCTIVE.search(str(label)):
            if not any(n.get(k) for k in CONFIRM_KEYS):
                findings.append({"check": "destructive", "where": where,
                                 "detail": "destructive control with no confirmation"})
            elif t != "Button":
                findings.append({"check": "destructive", "where": where,
                                 "detail": "confirmation set on %s; only a button honours it" % t})

        text = n.get("text")
        if isinstance(text, str) and TECHNICAL.search(text.strip()):
            findings.append({"check": "technical-text", "where": where,
                             "detail": "technical value visible to the user: %r" % text})

        if t in INPUTS and not n.get("label") and not n.get("accessibilityText"):
            findings.append({"check": "input-label", "where": where,
                             "detail": "input has neither label nor accessibilityText"})

        if t == "Grid":
            if not n.get("label"):
                findings.append({"check": "grid-accessibility", "where": where,
                                 "detail": "grid has no label"})
            if not n.get("rowHeader"):
                findings.append({"check": "grid-accessibility", "where": where,
                                 "detail": "grid has no rowHeader"})
            if empty_path and not n.get("emptyGridMessage"):
                findings.append({"check": "empty-state", "where": where,
                                 "detail": "no emptyGridMessage on the empty path"})

    return findings


USAGE = """usage: n2_interface_tree.py TREE_JSON [--empty-path]

TREE_JSON     a file holding the EVALUATED component tree a rendered-interface
              test returns -- the tree with data already resolved, not the
              interface's source. Any JSON shape is accepted: the checks walk
              it looking for component nodes, which are the objects carrying a
              "#t" type key.
--empty-path  say this when the render under inspection was the one against the
              identifier the project guarantees does not exist. It turns on the
              empty-state checks, which are meaningless against populated data.

The component types this checker knows how to judge:

  %s

A tree containing none of them is reported NOT MEASURED, never OK: this
checker did not understand it, which is a different result from checking it
and finding nothing wrong. Types outside the list are named in the output so
the gap is visible rather than assumed to be empty.

Exit codes match the plugin's other checkers: 0 clean, 1 findings (or an input
that cannot be read), 2 usage, 3 NOT MEASURED -- nothing was checked.""" % (
    ", ".join(CHECKED_TYPES),)


def main(argv):
    args = argv[1:]
    empty_path = False
    if "--empty-path" in args:
        empty_path = True
        args = [a for a in args if a != "--empty-path"]
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2

    path = args[0]
    try:
        with open(path, encoding="utf-8") as f:
            tree = json.load(f)
    except ValueError as e:
        print("ERROR %s: cannot parse the component tree as JSON: %s" % (path, e))
        return 1
    except OSError as e:
        print("ERROR %s: cannot read the component tree: %s" % (path, e))
        return 1

    findings = check_tree(tree, empty_path=empty_path)
    for f in findings:
        print("FINDING %s: %s at %s -- %s" % (path, f["check"], f["where"], f["detail"]))

    recognised, unrecognised = type_census(tree)
    if unrecognised:
        print("NOTE %s: %d component type(s) this checker does not judge: %s"
              % (path, len(unrecognised), ", ".join(unrecognised)))

    if not recognised:
        # Findings printed above can be real and this still be unmeasured:
        # docs/design-notes.md § n2_interface_tree.py · no recognised types
        print("\nNOT MEASURED %s: no component node of a type this checker judges was found, so "
              "none of the type-keyed checks ran. Known types: %s."
              % (path, ", ".join(CHECKED_TYPES)))
        return EXIT_NOT_MEASURED

    if findings:
        print("\n%d finding(s)." % len(findings))
        return 1
    print("OK %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
