"""Static checks over SAIL source, with the rules read from the official
Appian skill at run time rather than restated here.

    usage: sail_static_check.py EXPRESSION_FILE [--skill-root DIR] [--json]
    exit: 0 clean, 1 findings or unreadable input, 2 usage, 3 NOT MEASURED

Why the rules are not written in this file: they change with every Appian
release, and a copy drifts silently. The official skill ships them --
`references/function-reference.md` names the functions that do not exist and
the ones that exist but must not be used; `references/component-reference.md`
does the same for components; `registry/components-registry.json` is the
comprehensive component list. This reads those, and when they are not
installed it says NOT MEASURED instead of passing.

What it deliberately does NOT claim: a category it cannot decide from a
static source is reported NOT MEASURED, never PASS. Null safety and
performance need evaluation; accessibility needs the evaluated tree, which
is `n2_interface_tree.py`'s job, not this one's. A checker that reports
"clean" over a category it never looked at is the vacuous pass this
plugin's exit codes exist to prevent.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

# Where `dev-mcp-skills` installs. Same order as the hook's own lookup, so a
# project that configured one path does not have to configure a second.
SKILL_SEARCH_RELPATHS = (
    os.path.join(".claude", "skills", "appian"),
    os.path.join("skills", "appian"),
)

FUNCTION_REFERENCE = os.path.join("references", "function-reference.md")
COMPONENT_REFERENCE = os.path.join("references", "component-reference.md")
COMPONENT_REGISTRY = os.path.join("registry", "components-registry.json")

# The headings the official references use for their negative lists. Matched
# on the heading text, not on a line number: the file is reorganised often
# and a line offset would rot without failing.
_BANNED_HEADING = re.compile(r"^#{2,4}\s+.*(DO NOT EXIST)\s*$", re.I | re.M)
# "Functions That Exist But Should NOT Be Used" -- and only that one. The
# neighbouring "Use with Caution" list is context-dependent advice (now(),
# loggedInUser()), not a rule a static checker can apply without crying wolf.
_DISCOURAGED_HEADING = re.compile(
    r"^#{2,4}\s+.*Should NOT Be Used\s*$", re.I | re.M)
_HEADING = re.compile(r"^#{1,6}\s", re.M)
# A bullet naming a symbol in backticks: `regexmatch()`, `a!richTextEditor`.
_BULLET_SYMBOL = re.compile(
    r"^\s*[-*]\s+((?:`[A-Za-z_][A-Za-z0-9_!]*(?:\(\))?`(?:\s*,\s*)?)+)", re.M)
_BACKTICKED = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*!?[A-Za-z0-9_]*)\(?\)?`")

# What a call looks like in SAIL source: a symbol immediately followed by an
# opening parenthesis. Comments are stripped first.
_CALL = re.compile(r"\b(a!)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_STRING = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'")
_UUID_LITERAL = re.compile(
    r"\"[_a-zA-Z0-9]*[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}[^\"]*\"")

# Every category this checker knows about, and whether it can be decided
# from a static source at all. The ones marked False are the honest gaps:
# they are reported NOT MEASURED on every run, by construction.
CATEGORIES = (
    ("banned-function", True,
     "functions the official reference says do not exist"),
    ("discouraged-function", True,
     "functions that exist but the official reference says not to use"),
    ("banned-component", True,
     "components the official reference says do not exist"),
    ("literal-uuid", True,
     "a UUID typed into the expression instead of cons! or recordType!"),
    ("unknown-symbol", True,
     "a! symbols in neither the component registry nor the function reference"),
    ("null-safety", False,
     "needs the values a rule actually receives; a static reading cannot "
     "decide whether a null reaches this branch"),
    ("performance", False,
     "needs the query plan and the data volume, neither of which is in the "
     "source"),
    ("accessibility", False,
     "needs the EVALUATED tree, where labels and contrast are resolved: "
     "that is n2_interface_tree.py, not this checker"),
    ("naming", False,
     "the conventions are the project's, not the official source's, and "
     "inventing them here would be this checker making up its own rules"),
)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def find_skill_root(explicit=None):
    """The installed official skill, or None. Explicit wins."""
    if explicit:
        return explicit if os.path.isdir(explicit) else None
    for base in (os.path.expanduser("~"), os.getcwd()):
        for rel in SKILL_SEARCH_RELPATHS:
            candidate = os.path.join(base, rel)
            if os.path.isfile(os.path.join(candidate, "SKILL.md")):
                return candidate
    return None


def _section_symbols(text, heading_re):
    """The backticked symbols listed under the first matching heading, up to
    the next heading of any level."""
    match = heading_re.search(text or "")
    if not match:
        return set()
    rest = text[match.end():]
    end = _HEADING.search(rest)
    block = rest[:end.start()] if end else rest
    symbols = set()
    for bullet in _BULLET_SYMBOL.finditer(block):
        for symbol in _BACKTICKED.findall(bullet.group(1)):
            symbols.add(symbol)
    return symbols


def load_rules(skill_root):
    """{banned, discouraged, bannedComponents, knownComponents, sources}.

    A source that is missing comes back empty AND is named in `sources` as
    absent, which is what turns its category into NOT MEASURED rather than
    into a silent pass.
    """
    rules = {"banned": set(), "discouraged": set(), "bannedComponents": set(),
             "knownComponents": set(), "knownSymbols": set(), "sources": {}}
    if not skill_root:
        return rules

    functions = _read(os.path.join(skill_root, FUNCTION_REFERENCE))
    rules["sources"][FUNCTION_REFERENCE] = functions is not None
    if functions:
        rules["banned"] = _section_symbols(functions, _BANNED_HEADING)
        rules["discouraged"] = _section_symbols(functions, _DISCOURAGED_HEADING)
        # Every symbol the reference names anywhere, as the POSITIVE list.
        # Without it `a!forEach` -- a function, not a component, so absent
        # from the registry -- would be reported unknown on every real
        # interface, and a checker that cries wolf gets switched off.
        rules["knownSymbols"] |= set(_BACKTICKED.findall(functions))

    components = _read(os.path.join(skill_root, COMPONENT_REFERENCE))
    rules["sources"][COMPONENT_REFERENCE] = components is not None
    if components:
        rules["bannedComponents"] = _section_symbols(components, _BANNED_HEADING)
        rules["knownSymbols"] |= set(_BACKTICKED.findall(components))

    registry = _read(os.path.join(skill_root, COMPONENT_REGISTRY))
    rules["sources"][COMPONENT_REGISTRY] = registry is not None
    if registry:
        try:
            parsed = json.loads(registry)
        except ValueError:
            rules["sources"][COMPONENT_REGISTRY] = False
        else:
            if isinstance(parsed, dict):
                rules["knownComponents"] = {
                    name for name, entry in parsed.items()
                    if not isinstance(entry, dict) or entry.get("exists") is not False}
    return rules


def _strip(source):
    """Source with comments and string literals blanked, so a function name
    inside a message is not reported as a call."""
    without_comments = _COMMENT.sub(" ", source)
    return _STRING.sub('""', without_comments)


def _line_of(source, index):
    return source.count("\n", 0, index) + 1


def check_source(source, rules):
    """(findings, measured_categories). Findings carry their category, so
    the coverage table below is built from the same vocabulary the checks
    use rather than from a second hand-written list."""
    findings = []
    stripped = _strip(source)

    known = rules["knownSymbols"] | rules["knownComponents"]
    for match in _CALL.finditer(stripped):
        prefix, name = match.group(1) or "", match.group(2)
        symbol = prefix + name
        line = _line_of(stripped, match.start())
        if symbol in rules["banned"]:
            findings.append({"category": "banned-function", "line": line,
                             "symbol": symbol,
                             "detail": "the official function reference lists it "
                                       "among the functions that do not exist"})
        elif symbol in rules["discouraged"]:
            findings.append({"category": "discouraged-function", "line": line,
                             "symbol": symbol,
                             "detail": "it exists, and the official function "
                                       "reference says not to use it"})
        elif symbol in rules["bannedComponents"]:
            findings.append({"category": "banned-component", "line": line,
                             "symbol": symbol,
                             "detail": "the official component reference lists it "
                                       "among the components that do not exist"})
        elif prefix and rules["knownComponents"] and symbol not in known:
            # Reported as unverified, not as absent: neither source claims
            # to name every `a!` symbol in Appian, so saying "this does not
            # exist" would be the checker claiming more than its sources
            # support. What it does say is where to go and look.
            findings.append({"category": "unknown-symbol", "line": line,
                             "symbol": symbol,
                             "detail": "not in the component registry; verify it "
                                       "against the documentation MCP before "
                                       "trusting it"})

    for match in _UUID_LITERAL.finditer(source):
        findings.append({"category": "literal-uuid",
                         "line": _line_of(source, match.start()),
                         "symbol": match.group(0)[:48],
                         "detail": "a UUID typed into the expression: use cons! or "
                                   "recordType! so it survives a deployment"})

    measured = set()
    if rules["banned"]:
        measured.add("banned-function")
    if rules["discouraged"]:
        measured.add("discouraged-function")
    if rules["bannedComponents"]:
        measured.add("banned-component")
    if rules["knownComponents"]:
        measured.add("unknown-symbol")
    # This one needs no official source: the pattern is the rule.
    measured.add("literal-uuid")
    return findings, measured


def coverage_table(measured, rules):
    """One row per category: what was measured, what was not, and why.

    § 16 Fase 3 asks for this table by name, including the categories that
    stay NOT MEASURED. A gap that is written down is a gap somebody can
    close; a gap that is silent reads as a pass.
    """
    rows = []
    for name, decidable, why in CATEGORIES:
        if not decidable:
            rows.append((name, "NOT MEASURED", why))
        elif name in measured:
            rows.append((name, "MEASURED", why))
        else:
            rows.append((name, "NOT MEASURED",
                         "%s -- the official source it reads is missing or empty"
                         % why))
    return rows


USAGE = """usage: sail_static_check.py EXPRESSION_FILE [--skill-root DIR] [--json]

EXPRESSION_FILE  a file holding SAIL source -- the expression as written, not
                 the evaluated tree. For the evaluated tree, which is where
                 labels, contrast and resolved data live, use
                 n2_interface_tree.py instead.
--skill-root     the installed official Appian skill. Without it the standard
                 user-scope location is searched. The rules this checker
                 applies are READ FROM THERE at run time and are not copied
                 into this file, because they change with every release and a
                 copy drifts silently.
--json           emit findings and the coverage table as JSON.

Every run prints a coverage table by category, including the categories that
stay NOT MEASURED: null safety and performance need evaluation, accessibility
needs the evaluated tree, and naming conventions are the project's rather than
the official source's. A category this checker cannot decide is reported NOT
MEASURED, never PASS.

Exit codes match the plugin's other checkers: 0 clean, 1 findings (or an input
that cannot be read), 2 usage, 3 NOT MEASURED -- no category could be
measured at all, which is what happens when the official skill is absent."""


def main(argv):
    args = argv[1:]
    as_json = "--json" in args
    args = [a for a in args if a != "--json"]
    skill_root = None
    if "--skill-root" in args:
        i = args.index("--skill-root")
        if i + 1 >= len(args):
            print(USAGE, file=sys.stderr)
            return 2
        skill_root = args[i + 1]
        args = args[:i] + args[i + 2:]
    if len(args) != 1:
        print(USAGE, file=sys.stderr)
        return 2

    path = args[0]
    source = _read(path)
    if source is None:
        print("ERROR %s: cannot read the SAIL source" % path)
        return 1

    root = find_skill_root(skill_root)
    rules = load_rules(root)
    findings, measured = check_source(source, rules)
    table = coverage_table(measured, rules)

    if as_json:
        print(json.dumps({"path": path, "skillRoot": root,
                          "findings": findings,
                          "coverage": [{"category": c, "status": s, "why": w}
                                       for c, s, w in table]},
                         indent=2, sort_keys=True))
    else:
        for f in findings:
            print("FINDING %s:%d: %s %s -- %s"
                  % (path, f["line"], f["category"], f["symbol"], f["detail"]))
        print("\nCoverage by category:")
        for name, status, why in table:
            print("  %-22s %-12s %s" % (name, status, why))
        if root is None:
            print("\nThe official Appian skill was not found, so every rule-based "
                  "category is unmeasured. Install it from "
                  "github.com/appian/dev-mcp-skills or pass --skill-root.")

    # In --json mode stdout carries one JSON document and nothing else: a
    # trailing human-readable line would make the output unparseable for
    # the caller that asked for JSON.
    if not measured:
        if not as_json:
            print("\nNOT MEASURED %s: no category could be decided." % path)
        return EXIT_NOT_MEASURED
    if findings:
        if not as_json:
            print("\n%d finding(s)." % len(findings))
        return 1
    if not as_json:
        print("\nOK %s (%d categor(y/ies) measured, %d NOT MEASURED)"
              % (path, len(measured), len(CATEGORIES) - len(measured)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
