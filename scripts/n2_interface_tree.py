"""Deterministic checks over an interface's EVALUATED component tree.

Why this level exists: a rendered-interface test returns the component tree
already evaluated with resolved data -- including colours that came out of the
database and appear nowhere in the source (field experience). A linter over the
source can never see them.

Two operating notes, both field experience: the default response size cap
truncates a real screen, so raise it and trust the truncation flag rather than
the byte count; and some API surfaces fail to serialize certain component
types, so pick the surface that answers correctly, not the one that answers
first.
"""
import re

DESTRUCTIVE = re.compile(r"\b(delete|remove|discard|revoke|purge|erase|cancel account)\b", re.I)
TECHNICAL = re.compile(r"\[L?java|^null$|^\{.*\}$|[0-9a-f]{8}-[0-9a-f]{4}-|recordType!", re.I)
INPUTS = ("TextField", "ParagraphField", "IntegerField", "FloatingPointField",
          "DateField", "DropdownField", "CheckboxField", "RadioButtonField", "PickerField")
CONFIRM_KEYS = ("confirmMessage", "confirmHeader", "confirmButtonLabel")


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
