"""The checker that catches manifest drift has to be able to catch it.

Mostly small broken pairs of manifests, confirming it says so. The one test
that earns its keep is the last: it runs against this repository, where the
drift it describes actually happened.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_manifest_agreement as C  # noqa: E402


def write_pair(root, plugin_version, entry_version, plugin_name="p", entry_name="p"):
    d = os.path.join(root, ".claude-plugin")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "plugin.json"), "w", encoding="utf-8") as f:
        json.dump({"name": plugin_name, "version": plugin_version}, f)
    with open(os.path.join(d, "marketplace.json"), "w", encoding="utf-8") as f:
        json.dump({"name": "m", "plugins": [{"name": entry_name, "version": entry_version,
                                             "source": "./"}]}, f)


def write_raw(root, filename, text):
    d = os.path.join(root, ".claude-plugin")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, filename), "w", encoding="utf-8") as f:
        f.write(text)


class VersionAgreement(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_matching_versions_pass(self):
        write_pair(self.root, "0.2.4", "0.2.4")
        self.assertEqual(C.check(self.root)[0], 0)

    def test_the_drift_that_actually_happened_is_caught(self):
        # marketplace.json sat at 0.2.1 while plugin.json had moved on to 0.2.4.
        write_pair(self.root, "0.2.4", "0.2.1")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("0.2.1" in m and "0.2.4" in m for m in msgs))

    def test_name_disagreement_is_caught(self):
        write_pair(self.root, "0.2.4", "0.2.4", plugin_name="a", entry_name="b")
        self.assertEqual(C.check(self.root)[0], 1)

    def test_no_marketplace_is_not_measured(self):
        # A plugin can ship through someone else's marketplace and carry none
        # of its own. That is not a failure, and it is not an agreement either.
        d = os.path.join(self.root, ".claude-plugin")
        os.makedirs(d)
        with open(os.path.join(d, "plugin.json"), "w", encoding="utf-8") as f:
            json.dump({"name": "p", "version": "1.0.0"}, f)
        self.assertEqual(C.check(self.root)[0], C.EXIT_NOT_MEASURED)

    def test_missing_plugin_json_is_a_failure(self):
        self.assertEqual(C.check(self.root)[0], 1)

    def test_this_repository_agrees(self):
        root = os.path.join(os.path.dirname(__file__), "..")
        self.assertEqual(C.check(root)[0], 0)


class SilenceIsNotAgreement(unittest.TestCase):
    """The two ways this could report agreement while comparing nothing.

    Each is a branch the checker already handles; neither was exercised, and
    an unexercised branch in a checker is the same unverified claim the plugin
    spends a README arguing against.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_an_entry_with_no_version_at_all_is_caught(self):
        # The vacuous green this guards: written as
        # `if entry_version and entry_version != version`, a marketplace entry
        # that simply omits the field agrees with every release forever.
        write_raw(self.root, "plugin.json", '{"name": "p", "version": "1.0.0"}')
        write_raw(self.root, "marketplace.json",
                  '{"name": "m", "plugins": [{"name": "p", "source": "./"}]}')
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("no version" in m for m in msgs))

    def test_a_plugin_json_missing_its_version_is_caught(self):
        # Without the name/version guard both sides read as None, None == None,
        # and the run passes having compared two absences.
        write_raw(self.root, "plugin.json", '{"name": "p"}')
        write_raw(self.root, "marketplace.json",
                  '{"name": "m", "plugins": [{"name": "p", "source": "./"}]}')
        self.assertEqual(C.check(self.root)[0], 1)


class ReportedRatherThanRaised(unittest.TestCase):
    """A manifest can parse cleanly and still be unusable.

    CI runs this checker, and CONTRIBUTING puts it at step 3 of the release,
    immediately before `claude plugin tag`. A traceback there halts a release
    without naming which of the two manifests is malformed -- the one question
    this file can answer. It already answered it for a file that will not
    parse; these are the same case one layer in, where the JSON is valid and
    the shape is not.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def test_unparseable_json_is_reported_rather_than_raised(self):
        # A traceback out of CI names a line of this file; a message names the
        # manifest that is broken. Only one of those tells the reader what to fix.
        write_raw(self.root, "plugin.json", '{"name": "p", "version": "1.0.0"}')
        write_raw(self.root, "marketplace.json", "{not json at all")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("marketplace.json" in m for m in msgs))

    def test_a_manifest_whose_root_is_an_array_is_reported(self):
        # `[]` parses. Asking it for a name raised AttributeError.
        write_raw(self.root, "plugin.json", "[]")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("plugin.json" in m and "array" in m for m in msgs))

    def test_a_plugins_key_holding_null_is_reported(self):
        # `get("plugins", [])` never returns its default here: the key is
        # present, so None came back and the comprehension raised on it.
        write_raw(self.root, "plugin.json", '{"name": "p", "version": "1.0.0"}')
        write_raw(self.root, "marketplace.json", '{"name": "m", "plugins": null}')
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("plugins" in m and "null" in m for m in msgs))

    def test_a_null_entry_inside_plugins_is_reported_with_its_index(self):
        # The index matters: "one of your entries is wrong" in a marketplace
        # listing several plugins is a message that still requires a search.
        write_raw(self.root, "plugin.json", '{"name": "p", "version": "1.0.0"}')
        write_raw(self.root, "marketplace.json", '{"name": "m", "plugins": [null]}')
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("plugins[0]" in m and "null" in m for m in msgs))


class ChangelogCarriesTheRelease(unittest.TestCase):
    """Step 2 of the release procedure, as a check instead of a sentence.

    CONTRIBUTING said "add the CHANGELOG entry" and nothing verified it -- the
    only step of the four with no gate behind it, in a repository whose
    changelog opens by saying it is the only announcement a gate that stops
    firing ever gets. These hold the new rule: a CHANGELOG.md that exists must
    carry a heading for the version the manifests declare.
    """

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root, True)

    def changelog(self, text):
        with open(os.path.join(self.root, "CHANGELOG.md"), "w",
                  encoding="utf-8") as f:
            f.write(text)

    def test_an_entry_for_the_released_version_passes(self):
        write_pair(self.root, "0.6.0", "0.6.0")
        self.changelog("# Changelog\n\n## 0.6.0 — 2026-08-12\n\nWords.\n")
        self.assertEqual(C.check(self.root)[0], 0)

    def test_a_bump_with_no_entry_is_caught_and_names_the_step(self):
        # The drift this exists for: both manifests moved, the changelog did
        # not, and the release ships behaviour nobody was told about.
        write_pair(self.root, "0.6.0", "0.6.0")
        self.changelog("# Changelog\n\n## 0.5.3 — 2026-08-12\n\nWords.\n")
        code, msgs = C.check(self.root)
        self.assertEqual(code, 1)
        self.assertTrue(any("## 0.6.0" in m and "CONTRIBUTING" in m for m in msgs))

    def test_a_longer_version_is_not_mistaken_for_its_prefix(self):
        # `0.5.10` contains `0.5.1`. An unanchored search would let the entry
        # for the newer release vouch for the older one forever.
        write_pair(self.root, "0.5.1", "0.5.1")
        self.changelog("# Changelog\n\n## 0.5.10 — 2027-01-01\n\nWords.\n")
        self.assertEqual(C.check(self.root)[0], 1)

    def test_a_version_mentioned_in_prose_is_not_an_entry(self):
        # Every entry here cites earlier releases in its body. A paragraph
        # saying "0.6.0 fixed this" is not the heading a reader scans for.
        write_pair(self.root, "0.6.0", "0.6.0")
        self.changelog("# Changelog\n\n## 0.5.3\n\nAnd 0.6.0 will fix it.\n")
        self.assertEqual(C.check(self.root)[0], 1)

    def test_no_changelog_at_all_is_not_this_checkers_finding(self):
        # Deliberate division of labour: the shipped documents link to
        # CHANGELOG.md, so its absence breaks the cross-document link check in
        # check_readme_claims.py. Reporting it here too is the restated-check
        # drift ci.yml argues against -- and every earlier test in this file
        # builds a root with no changelog, which is also why this branch stays
        # quiet rather than NOT_MEASURED.
        write_pair(self.root, "0.6.0", "0.6.0")
        self.assertEqual(C.check(self.root)[0], 0)


if __name__ == "__main__":
    unittest.main()
