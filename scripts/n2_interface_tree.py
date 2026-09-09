"""Deterministic checks over an interface's EVALUATED component tree, which
carries resolved data a linter over the source can never see.

    usage: n2_interface_tree.py TREE_JSON [--empty-path]
           n2_interface_tree.py --record POPULATED_JSON EMPTY_JSON [--out FILE]
    exit: 0 clean, 1 findings or unreadable input, 2 usage, 3 NOT MEASURED

Two jobs, and the second is why normalization lives here and nowhere else
(norm § 8.5): Appian returns a fresh `_cId` per node, re-encrypts every
`saveInto` handler with a new nonce and varies `diagnostics.durationMs`, so
two renders of an untouched screen already differ. Comparing raw renders is
a test that cannot fail.

Why the evaluated tree, and the two traps in fetching one:
docs/design-notes.md § n2_interface_tree.py · why the evaluated tree, platform traps"""
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

DESTRUCTIVE = re.compile(r"\b(delete|remove|discard|revoke|purge|erase|cancel account)\b", re.I)
TECHNICAL = re.compile(r"\[L?java|^null$|^\{.*\}$|[0-9a-f]{8}-[0-9a-f]{4}-|recordType!", re.I)
CONFIRM_KEYS = ("confirmMessage", "confirmHeader", "confirmButtonLabel")

# The categories this checker judges. Detection is by PROPERTY SIGNATURE,
# not by `#t`: the type vocabulary is open -- Appian ships components this
# list will never name, and a renamed or wrapped component silently left
# every check unrun while the run still reported OK. What a node HAS is
# what decides whether a check applies to it.
CATEGORIES = ("input", "grid", "action", "text", "coloured")


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


_GRID_KEYS = ("columns", "columnConfigs", "rowHeader", "emptyGridMessage",
              "gridSelection", "rows")
# Alternative spellings of the same accessible name. Accepting them is not
# a loosening: flagging "no label" on a component that carries one under a
# different key is a false finding, and a checker that cries wolf is
# switched off.
_LABEL_KEYS = ("label", "labelText", "accessibilityText")
_ACTION_KEYS = CONFIRM_KEYS + ("submit", "saveInto")


def categories_of(node):
    """Which categories this node belongs to, from what it carries.

    A node can be in more than one -- a coloured button is judged for
    contrast and for confirmation -- and in none, which is the honest
    answer for a layout wrapper.
    """
    if not isinstance(node, dict):
        return ()
    found = []
    type_hint = node.get("#t") if isinstance(node.get("#t"), str) else ""
    has_save = "saveInto" in node
    has_value = "value" in node or "values" in node

    if has_save and has_value:
        found.append("input")
    elif has_value and ("label" in node or "placeholder" in node) \
            and "Field" in type_hint:
        found.append("input")
    if any(k in node for k in _GRID_KEYS):
        found.append("grid")
    if (any(k in node for k in CONFIRM_KEYS)
            or (has_save and not has_value and ("label" in node
                                                or "text" in node))
            or ("Button" in type_hint or "Link" in type_hint)):
        found.append("action")
    if isinstance(node.get("text"), str) and not has_save:
        found.append("text")
    if isinstance(node.get("color"), str) and isinstance(node.get("backgroundColor"), str):
        found.append("coloured")
    return tuple(found)


def category_census(tree):
    """{category: count} over the raw tree. Coverage is not a finding, so
    it stays out of check_tree's return shape."""
    census = dict.fromkeys(CATEGORIES, 0)
    for node in _walk(tree, []):
        for category in categories_of(node):
            census[category] += 1
    return census


def check_tree(tree, empty_path=False):
    findings = []
    for n in _walk(tree, []):
        cats = categories_of(n)
        if not cats:
            continue
        t = n.get("#t", "")
        where = "%s(%s)" % (t or "node", n.get("label") or n.get("text") or "")

        if "coloured" in cats:
            fg, bg = n.get("color"), n.get("backgroundColor")
            if fg.startswith("#") and bg.startswith("#"):
                ratio = contrast_ratio(fg, bg)
                if ratio < 4.5:
                    findings.append({"check": "contrast", "where": where,
                                     "detail": "%s on %s is %.2f:1, below WCAG AA 4.5:1"
                                               % (fg, bg, ratio)})

        label = n.get("label") or n.get("text") or ""
        if "action" in cats and DESTRUCTIVE.search(str(label)):
            if not any(n.get(k) for k in CONFIRM_KEYS):
                findings.append({"check": "destructive", "where": where,
                                 "detail": "destructive control with no confirmation"})
            elif "Button" not in str(t):
                findings.append({"check": "destructive", "where": where,
                                 "detail": "confirmation set on %s; only a button honours it"
                                           % (t or "this component")})

        text = n.get("text")
        if "text" in cats and isinstance(text, str) and TECHNICAL.search(text.strip()):
            findings.append({"check": "technical-text", "where": where,
                             "detail": "technical value visible to the user: %r" % text})

        if "input" in cats and not any(n.get(k) for k in _LABEL_KEYS):
            findings.append({"check": "input-label", "where": where,
                             "detail": "input has neither label nor accessibilityText"})

        if "grid" in cats:
            if not any(n.get(k) for k in _LABEL_KEYS):
                findings.append({"check": "grid-accessibility", "where": where,
                                 "detail": "grid has no label"})
            if not n.get("rowHeader"):
                findings.append({"check": "grid-accessibility", "where": where,
                                 "detail": "grid has no rowHeader"})
            if empty_path and not n.get("emptyGridMessage"):
                findings.append({"check": "empty-state", "where": where,
                                 "detail": "no emptyGridMessage on the empty path"})

    return findings


# --- § 8.5 · normalization, defined here and nowhere else --------------

# Dropped outright: they change on every render of an untouched screen.
VOLATILE_KEYS = ("_cId", "durationMs", "requestId", "nonce")
# Kept as presence, not as content: the handler is re-encrypted per render,
# so its bytes are noise -- but whether a node HAS one is signal.
HANDLER_KEYS = ("saveInto", "link", "saveIntoValue")
# The three the normalization may never touch, whatever else it does: they
# are the payload the populated/empty inequality is measured over.
PRESERVED_KEYS = ("value", "values", "text")


def normalize_tree(node):
    """The render with its per-render noise removed, and nothing else.

    `value`, `text` and `values` are never nulled and never rewritten: the
    inequality of § 8.5 is counted over exactly those, so a normalization
    that touched them would make the guarantee vacuous.
    """
    if isinstance(node, dict):
        out = {}
        for key in sorted(node):
            if key in VOLATILE_KEYS:
                continue
            if key in HANDLER_KEYS and key not in PRESERVED_KEYS:
                out[key] = "<handler>"
                continue
            out[key] = normalize_tree(node[key])
        return out
    if isinstance(node, list):
        return [normalize_tree(v) for v in node]
    return node


def normalized_hash(tree):
    return hashlib.sha256(json.dumps(normalize_tree(tree), sort_keys=True,
                                     default=str).encode("utf-8")).hexdigest()


def _non_empty(value):
    if value is None:
        return False
    if isinstance(value, (str, list, dict)):
        return len(value) > 0
    return True


def value_nodes(tree):
    """Nodes carrying non-empty `value`, `values` or `data`. The metric of
    guarantee 3, and the one that catches an `a!forEach` that never
    iterated -- which a hash comparison cannot."""
    count = 0
    for node in _walk(tree, []):
        if any(_non_empty(node.get(k)) for k in ("value", "values", "data")):
            count += 1
    return count


def _diagnostics(tree):
    out = {"error": None, "timedOut": False, "truncated": False}
    for node in _walk(tree, []):
        diag = node.get("diagnostics")
        if isinstance(diag, dict):
            if diag.get("error"):
                out["error"] = str(diag["error"])[:400]
            out["timedOut"] = bool(out["timedOut"] or diag.get("timedOut"))
            out["truncated"] = bool(out["truncated"] or diag.get("truncated"))
        for key in ("timedOut", "truncated"):
            if node.get(key) is True:
                out[key] = True
    return out


def render_record(tree, empty_path=False):
    """Everything a consumer needs about one render, in ~500 B: the
    normalized hash, the value-node count, the diagnostics that make a
    render credit nothing, the category census and the N2 findings.

    The tree itself does not travel. A screen is 218 KB and there are
    942 KB ones (§ 8.5); what goes up is this.
    """
    diagnostics = _diagnostics(tree)
    findings = check_tree(tree, empty_path=empty_path)
    census = category_census(tree)
    return {
        "normalizedHash": normalized_hash(tree),
        "valueNodes": value_nodes(tree),
        "categories": census,
        "measured": any(census.values()),
        "findings": len(findings),
        "checks": sorted({f["check"] for f in findings}),
        "error": diagnostics["error"],
        "timedOut": diagnostics["timedOut"],
        "truncated": diagnostics["truncated"],
        "emptyPath": bool(empty_path),
    }


def render_signals(populated, empty):
    """The two guarantees and the corollary of § 8.5, over a render pair.

    1 · stability is not asserted here: it needs two renders of the SAME
        state, which is a different pair. `observe-reads` asserts it from
        two rows with the same inputs.
    2 · distinct hashes -- the corollary.
    3 · the populated has strictly more value-bearing nodes -- the
        guarantee the corollary follows from.
    """
    a = render_record(populated)
    b = render_record(empty, empty_path=True)
    credits = not (a["error"] or b["error"] or a["truncated"] or b["truncated"]
                   or a["timedOut"] or b["timedOut"])
    return {
        "populated": a,
        "empty": b,
        "guarantees": {
            "distinctHash": a["normalizedHash"] != b["normalizedHash"],
            "strictlyMoreValueNodes": a["valueNodes"] > b["valueNodes"],
            "credits": credits,
        },
    }


USAGE = """usage: n2_interface_tree.py TREE_JSON [--empty-path]
       n2_interface_tree.py --record POPULATED_JSON EMPTY_JSON [--out FILE]

TREE_JSON     a file holding the EVALUATED component tree a rendered-interface
              test returns -- the tree with data already resolved, not the
              interface's source. Any JSON shape is accepted: the checks walk
              it looking for component nodes, which are the objects carrying
              the properties each check is about.
--empty-path  say this when the render under inspection was the one against the
              identifier the project guarantees does not exist. It turns on the
              empty-state checks, which are meaningless against populated data.
--record      emit the render signals of a POPULATED/EMPTY pair as JSON: the
              normalized hashes, the value-node counts, the diagnostics and the
              two guarantees of § 8.5. The trees do not travel; this does.

The categories this checker judges, detected by what a node carries rather
than by its type name:

  %s

A tree in which none of them is present is reported NOT MEASURED, never OK:
this checker did not understand it, which is a different result from checking
it and finding nothing wrong.

Exit codes match the plugin's other checkers: 0 clean, 1 findings (or an input
that cannot be read), 2 usage, 3 NOT MEASURED -- nothing was checked.""" % (
    ", ".join(CATEGORIES),)


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _record_mode(args):
    out_path = None
    if "--out" in args:
        i = args.index("--out")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        out_path = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 2:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        signals = render_signals(_load(args[0]), _load(args[1]))
    except ValueError as e:
        print("ERROR: cannot parse a render as JSON: %s" % e)
        return 1
    except OSError as e:
        print("ERROR: cannot read a render: %s" % e)
        return 1
    signals["populated"]["path"] = args[0]
    signals["empty"]["path"] = args[1]
    text = json.dumps(signals, indent=2, sort_keys=True)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)
    if not signals["populated"]["measured"] and not signals["empty"]["measured"]:
        return EXIT_NOT_MEASURED
    guarantees = signals["guarantees"]
    if not guarantees["credits"]:
        return EXIT_NOT_MEASURED
    return 0 if guarantees["strictlyMoreValueNodes"] else 1


def main(argv):
    args = argv[1:]
    if "--record" in args:
        return _record_mode([a for a in args if a != "--record"])

    empty_path = False
    if "--empty-path" in args:
        empty_path = True
        args = [a for a in args if a != "--empty-path"]
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2

    path = args[0]
    try:
        tree = _load(path)
    except ValueError as e:
        print("ERROR %s: cannot parse the component tree as JSON: %s" % (path, e))
        return 1
    except OSError as e:
        print("ERROR %s: cannot read the component tree: %s" % (path, e))
        return 1

    findings = check_tree(tree, empty_path=empty_path)
    for f in findings:
        print("FINDING %s: %s at %s -- %s" % (path, f["check"], f["where"], f["detail"]))

    census = category_census(tree)
    unjudged = [c for c in CATEGORIES if not census[c]]
    if unjudged:
        print("NOTE %s: no node of %d categor(y/ies) was present, so their checks did "
              "not run: %s" % (path, len(unjudged), ", ".join(unjudged)))

    if not any(census.values()):
        # Findings printed above can be real and this still be unmeasured:
        # docs/design-notes.md § n2_interface_tree.py · no recognised types
        print("\nNOT MEASURED %s: no node carried a property any of these checks is "
              "about, so none of them ran. Categories: %s."
              % (path, ", ".join(CATEGORIES)))
        return EXIT_NOT_MEASURED

    if findings:
        print("\n%d finding(s)." % len(findings))
        return 1
    print("OK %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
