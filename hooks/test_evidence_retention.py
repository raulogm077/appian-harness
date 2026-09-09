"""§ 11: the ceiling on evidence, applied at the one moment nothing will
read a closed instance's rows again.

Without it the evidence grows for ever -- a real project reached 43 MB in
398 files, with five renders of the same screen inside a single scope -- and
evidence nobody can open is evidence nobody reads.
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
import harness_hooks as hh  # noqa: E402


TREE = {"#t": "Form", "_cId": "abc",
        "contents": [{"#t": "TextField", "label": "Name", "value": "Ana",
                      "saveInto": "enc:1"}]}


class RetentionCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = self._tmp.name
        self.evidence = os.path.join(self.root, "evidence")
        self.scope_dir = os.path.join(self.evidence, "S-1")
        os.makedirs(self.scope_dir)
        self.scope = {"id": "S-1", "instanceId": "inst-1"}
        self.config = {"projectRoot": self.root, "evidenceDir": self.evidence}

    def render(self, name, tree=None):
        path = os.path.join(self.scope_dir, name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(tree or TREE, f)
        return path

    def ledger(self, name, rows):
        for row in rows:
            hh._append_jsonl(os.path.join(self.evidence, name), row)


class TestRenderRetention(RetentionCase):

    def test_the_last_render_of_each_path_survives(self):
        for name in hh.KEPT_RENDERS:
            self.render(name)
        self.render("render-poblado-intermedio.json")
        hh.close_out_evidence(self.config, self.scope)
        left = set(os.listdir(self.scope_dir))
        for name in hh.KEPT_RENDERS:
            self.assertIn(name, left)
        self.assertNotIn("render-poblado-intermedio.json", left)

    def test_an_intermediate_leaves_its_normalized_hash_behind(self):
        # "De los intermedios queda su hash normalizado en
        # render-signals.json al cerrar": the file goes, the measurement
        # does not.
        self.render("render-poblado-1.json")
        hh.close_out_evidence(self.config, self.scope)
        with open(os.path.join(self.scope_dir, hh.RENDER_SIGNALS_NAME),
                  encoding="utf-8") as f:
            signals = json.load(f)
        retired = signals["retired"]
        self.assertEqual(retired[0]["file"], "render-poblado-1.json")
        self.assertEqual(retired[0]["normalizedHash"],
                         hh.normalized_hash(TREE))

    def test_a_render_a_verdict_cites_is_not_deleted(self):
        # Deleting what a live verdict cites would leave the verdict
        # pointing at nothing.
        self.render("render-poblado-1.json")
        with open(os.path.join(self.scope_dir, "practices-certify.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"evidence": ["render-poblado-1.json"]}, f)
        hh.close_out_evidence(self.config, self.scope)
        self.assertIn("render-poblado-1.json", os.listdir(self.scope_dir))

    def test_nothing_else_in_the_scope_directory_is_touched(self):
        self.render("render-poblado-1.json")
        with open(os.path.join(self.scope_dir, "dependents.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"dependents": []}, f)
        hh.close_out_evidence(self.config, self.scope)
        self.assertIn("dependents.json", os.listdir(self.scope_dir))

    def test_an_existing_signals_file_is_extended_not_replaced(self):
        with open(os.path.join(self.scope_dir, hh.RENDER_SIGNALS_NAME), "w",
                  encoding="utf-8") as f:
            json.dump({"guarantees": {"distinctHash": True}}, f)
        self.render("render-poblado-1.json")
        hh.close_out_evidence(self.config, self.scope)
        with open(os.path.join(self.scope_dir, hh.RENDER_SIGNALS_NAME),
                  encoding="utf-8") as f:
            signals = json.load(f)
        self.assertTrue(signals["guarantees"]["distinctHash"])
        self.assertEqual(len(signals["retired"]), 1)


class TestLedgerRotation(RetentionCase):

    def test_the_closed_instances_rows_move_under_its_own_directory(self):
        self.ledger("operations.jsonl",
                    [{"instanceId": "inst-1", "writeSeq": 1},
                     {"instanceId": "inst-1", "writeSeq": 2}])
        self.ledger("checks.jsonl", [{"instanceId": "inst-1", "tool": "get"}])
        hh.close_out_evidence(self.config, self.scope)
        self.assertEqual(hh._read_jsonl(
            os.path.join(self.evidence, "operations.jsonl")), [])
        rotated = hh._read_jsonl(os.path.join(self.scope_dir, "operations.jsonl"))
        self.assertEqual(len(rotated), 2)
        self.assertEqual(len(hh._read_jsonl(
            os.path.join(self.scope_dir, "checks.jsonl"))), 1)

    def test_another_instances_rows_stay_where_they_are(self):
        # The failure this guards: rotating a live instance's journal would
        # reset its writeSeq and make every verdict of it look fresh.
        self.ledger("operations.jsonl",
                    [{"instanceId": "inst-1", "writeSeq": 1},
                     {"instanceId": "inst-2", "writeSeq": 1}])
        hh.close_out_evidence(self.config, self.scope)
        left = hh._read_jsonl(os.path.join(self.evidence, "operations.jsonl"))
        self.assertEqual([r["instanceId"] for r in left], ["inst-2"])

    def test_the_audit_trail_is_not_rotated(self):
        # gate-decisions.jsonl is one row per decision, session-start
        # summarises the day's, and the perimeter nudge dedupes by session
        # rather than by instance: moving it would repeat a prompt.
        self.ledger("gate-decisions.jsonl",
                    [{"instanceId": "inst-1", "event": "transition"}])
        hh.close_out_evidence(self.config, self.scope)
        left = hh._read_jsonl(os.path.join(self.evidence, "gate-decisions.jsonl"))
        self.assertTrue(any(r.get("event") == "transition" for r in left))

    def test_the_close_out_is_recorded(self):
        self.ledger("operations.jsonl", [{"instanceId": "inst-1", "writeSeq": 1}])
        hh.close_out_evidence(self.config, self.scope)
        rows = hh._read_jsonl(os.path.join(self.evidence, "gate-decisions.jsonl"))
        self.assertTrue(any(r.get("event") == "evidence-closed-out" for r in rows))

    def test_a_scope_with_nothing_to_rotate_writes_no_row(self):
        hh.close_out_evidence(self.config, self.scope)
        self.assertEqual(hh._read_jsonl(
            os.path.join(self.evidence, "gate-decisions.jsonl")), [])


if __name__ == "__main__":
    unittest.main()
