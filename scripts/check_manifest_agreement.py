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

Exit 0 agreement, 1 disagreement, 3 nothing to compare.
"""
import json
import os
import sys

EXIT_NOT_MEASURED = 3


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check(root):
    """Return (exit_code, messages)."""
    msgs = []
    plugin_path = os.path.join(root, ".claude-plugin", "plugin.json")
    market_path = os.path.join(root, ".claude-plugin", "marketplace.json")

    if not os.path.isfile(plugin_path):
        return 1, ["no .claude-plugin/plugin.json under %s" % root]
    try:
        plugin = _load(plugin_path)
    except ValueError as exc:
        return 1, ["plugin.json is not valid JSON: %s" % exc]

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
    try:
        market = _load(market_path)
    except ValueError as exc:
        return 1, ["marketplace.json is not valid JSON: %s" % exc]

    declared = market.get("plugins", [])
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
