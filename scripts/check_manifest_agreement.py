"""Holds both manifests and the CHANGELOG heading to the same version.

    python3 scripts/check_manifest_agreement.py [root]

Exit 0 agreement, 1 disagreement or a manifest this cannot read, 3 nothing
to compare.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402


# JSON's type names, not Python's: a reader staring at `[...]` in a .json is
# looking at an array, and "list" makes them translate before they can act.
JSON_SHAPE = {dict: "an object", list: "an array", str: "a string",
              bool: "a boolean", type(None): "null"}


def _shape(value):
    return JSON_SHAPE.get(type(value), "a number")


def _read_manifest(path, label):
    """Return (mapping, problem); exactly one of the two is None.

    Two failure modes, and neither may leave here as a traceback:
    docs/design-notes.md § check_manifest_agreement.py · _read_manifest
    """
    try:
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
    except ValueError as exc:
        return None, "%s is not valid JSON: %s" % (label, exc)
    if not isinstance(loaded, dict):
        return None, ("%s must be a JSON object; its root is %s"
                      % (label, _shape(loaded)))
    return loaded, None


def check(root):
    """Return (exit_code, messages)."""
    msgs = []
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    market_path = os.path.join(root, ".claude-plugin", "marketplace.json")

    if not os.path.isfile(plugin_path):
        return 1, ["no .claude-plugin/plugin.json under %s" % root]
    plugin, problem = _read_manifest(plugin_path, "plugin.json")
    if problem:
        return 1, [problem]

    name = plugin.get("name")
    version = plugin.get("version")
    # Both fields before anything is compared -- two absences compare equal:
    # docs/design-notes.md § check_manifest_agreement.py · both fields first
    if not name or not version:
        return 1, ["plugin.json must declare both 'name' and 'version'"]

    if not os.path.isfile(market_path):
        # A plugin distributed through someone else's marketplace has
        # nothing here to agree with. Not a pass: nothing was compared.
        return EXIT_NOT_MEASURED, [
            "no .claude-plugin/marketplace.json; no entry was compared against "
            "plugin.json's %s %s" % (name, version)]
    market, problem = _read_manifest(market_path, "marketplace.json")
    if problem:
        return 1, [problem]

    # A key holding null is not a missing key; `get`'s default never fires:
    # docs/design-notes.md § check_manifest_agreement.py · plugins is null
    declared = market.get("plugins", [])
    if not isinstance(declared, list):
        return 1, ["marketplace.json 'plugins' must be an array; it is %s"
                   % _shape(declared)]
    malformed = [i for i, e in enumerate(declared) if not isinstance(e, dict)]
    if malformed:
        return 1, ["marketplace.json plugins[%d] must be an object; it is %s"
                   % (i, _shape(declared[i])) for i in malformed]

    entries = [e for e in declared if e.get("name") == name]
    if not entries:
        # Names what IS declared, because the usual cause is a rename that
        # landed in one manifest only.
        return 1, ["marketplace.json declares no entry named %r, so plugin.json's "
                   "version cannot be checked against anything; it declares: %s"
                   % (name, ", ".join(repr(e.get("name")) for e in declared) or "nothing")]

    # plugin.json wins at install time, so drift is invisible until tagging:
    # docs/design-notes.md § check_manifest_agreement.py · the drift
    for entry in entries:
        entry_version = entry.get("version")
        if entry_version is None:
            msgs.append("marketplace entry %r declares no version; plugin.json says %s"
                        % (name, version))
        elif entry_version != version:
            msgs.append("marketplace entry %r declares version %s but plugin.json says "
                        "%s; `claude plugin tag` refuses to tag a release whose "
                        "manifests disagree" % (name, entry_version, version))

    changelog = os.path.join(root, "CHANGELOG.md")
    if os.path.isfile(changelog):
        with open(changelog, encoding="utf-8") as f:
            text = f.read()
        # A boundary, not merely a prefix -- 0.5.10 must not satisfy 0.5.1 --
        # and anchored to `## ` so a version cited in prose cannot stand in.
        if not re.search(r"^##\s+%s(\s|$)" % re.escape(version), text, re.MULTILINE):
            msgs.append("CHANGELOG.md has no `## %s` entry, and the changelog is the "
                        "only announcement a behaviour change ever gets; write the "
                        "entry before releasing (CONTRIBUTING.md, Releasing, step 2)"
                        % version)
    return (1 if msgs else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        if os.path.isfile(os.path.join(root, "CHANGELOG.md")):
            print("OK the manifests agree and CHANGELOG.md carries the entry")
        else:
            print("OK both manifests declare the same name and version")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
