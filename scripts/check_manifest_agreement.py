"""Holds the two manifests that declare a version to the same answer.

`.claude-plugin/marketplace.json` sat at 0.2.1 while `.claude-plugin/plugin.json`
said 0.2.4 -- stale across three consecutive releases. Nothing broke, and that
is precisely why it survived: plugin.json wins at install time and the entry
version is silently ignored. What does read the entry is `claude plugin tag`,
probed on a throwaway repository carrying exactly this drift -- it exits 1
rather than tagging, and says so in the plugin's own terms:

    Version mismatch: plugin.json says "0.2.4" but marketplace.json
    plugins[0].version says "0.2.1". plugin.json wins at install time, so
    update the marketplace entry to "0.2.4" (or remove it) before tagging.

So the drift was one release away from blocking the thing it was invisible to.

A pass here is not a promise that `tag` will succeed. The same probe showed it
also refuses on a dirty working tree, which belongs to the release procedure
and not to this file. All this reports is that the two manifests agree.

Deliberately not a call to `claude plugin validate`: CI does not have the CLI,
and a check that only runs where the CLI happens to be installed is the same
absent-gate problem the launcher exists to prevent.

    python3 scripts/check_manifest_agreement.py [root]

Exit 0 agreement, 1 disagreement or a manifest this cannot read, 3 nothing
to compare.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402


# Python's type names are not the ones the file is written in. A reader
# staring at `[...]` in a .json is looking at an array, and telling them it is
# a "list" sends them to translate before they can act.
JSON_SHAPE = {dict: "an object", list: "an array", str: "a string",
              bool: "a boolean", type(None): "null"}


def _shape(value):
    return JSON_SHAPE.get(type(value), "a number")


def _read_manifest(path, label):
    """Return (mapping, problem); exactly one of the two is None.

    Two failure modes, not one. `json.load` raising means the file will not
    parse; a file that parses to an array is perfectly readable and still
    cannot be asked for a name. That second one used to leave here as an
    AttributeError -- in a step CONTRIBUTING places immediately before
    `claude plugin tag`, where a traceback halts a release without naming
    which of the two manifests is malformed. That is the one question this
    file exists to answer, and it already answered it for the unparseable
    case, so crashing on the other was an asymmetry rather than a boundary.
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
    # Both fields, before anything is compared. A plugin.json missing its
    # version reads as None, the entry that also omits one reads as None, and
    # the run passes having compared two absences -- agreement about nothing.
    if not name or not version:
        return 1, ["plugin.json must declare both 'name' and 'version'"]

    if not os.path.isfile(market_path):
        # A plugin distributed only through someone else's marketplace has
        # nothing here to agree with. Not a pass: nothing was compared.
        return EXIT_NOT_MEASURED, [
            "no .claude-plugin/marketplace.json; no entry was compared against "
            "plugin.json's %s %s" % (name, version)]
    market, problem = _read_manifest(market_path, "marketplace.json")
    if problem:
        return 1, [problem]

    # A missing key means no entries, which the "declares no entry" branch
    # below reports properly. A key present and holding null is a different
    # thing -- someone wrote it and got it wrong -- and `get`'s default never
    # fires for it, so it reached the loop as None and raised there.
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
        # Naming what IS declared, because the usual cause is a rename that
        # landed in one manifest only, and "no entry named X" sends the reader
        # to open the file for something this check already read.
        return 1, ["marketplace.json declares no entry named %r, so plugin.json's "
                   "version cannot be checked against anything; it declares: %s"
                   % (name, ", ".join(repr(e.get("name")) for e in declared) or "nothing")]

    for entry in entries:
        entry_version = entry.get("version")
        if entry_version is None:
            msgs.append("marketplace entry %r declares no version; plugin.json says %s"
                        % (name, version))
        elif entry_version != version:
            msgs.append("marketplace entry %r declares version %s but plugin.json says "
                        "%s; `claude plugin tag` refuses to tag a release whose "
                        "manifests disagree" % (name, entry_version, version))
    return (1 if msgs else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        print("OK both manifests declare the same name and version")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
