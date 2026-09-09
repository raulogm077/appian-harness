import io, json, os, tempfile, unittest
from contextlib import redirect_stdout, redirect_stderr
from n2_interface_tree import (CATEGORIES, categories_of, category_census,
                               check_tree, contrast_ratio, main,
                               normalize_tree, normalized_hash, render_record,
                               render_signals, value_nodes)

def node(t, **kw):
    d = {"#t": t}
    d.update(kw)
    return d

class TestContrast(unittest.TestCase):
    def test_black_on_white_is_21(self):
        self.assertAlmostEqual(contrast_ratio("#000000", "#FFFFFF"), 21.0, places=1)

    def test_amber_on_white_is_below_wcag_aa(self):
        # The real defect shape: a catalogue colour that only exists once data resolves.
        self.assertLess(contrast_ratio("#FFC107", "#FFFFFF"), 4.5)

class TestChecks(unittest.TestCase):
    def test_low_contrast_pair_is_flagged(self):
        tree = node("Text", text="Pending", color="#FFC107", backgroundColor="#FFFFFF")
        self.assertTrue(any(f["check"] == "contrast" for f in check_tree(tree)))

    def test_destructive_dynamic_link_without_confirm_is_flagged(self):
        tree = node("DynamicLink", label="Delete candidate")
        self.assertTrue(any(f["check"] == "destructive" for f in check_tree(tree)))

    def test_destructive_button_with_confirm_is_clean(self):
        tree = node("Button", label="Delete candidate", confirmMessage="Are you sure?")
        self.assertEqual([f for f in check_tree(tree) if f["check"] == "destructive"], [])

    def test_technical_text_leaking_to_the_user_is_flagged(self):
        tree = node("Text", text="null")
        self.assertTrue(any(f["check"] == "technical-text" for f in check_tree(tree)))

    def test_grid_without_label_or_rowheader_is_flagged(self):
        tree = node("Grid", columns=[])
        found = {f["check"] for f in check_tree(tree)}
        self.assertIn("grid-accessibility", found)

    def test_input_without_label_is_flagged(self):
        tree = node("TextField", value="x", saveInto="local!x")
        self.assertTrue(any(f["check"] == "input-label" for f in check_tree(tree)))

    def test_empty_grid_message_required_only_on_the_empty_path(self):
        tree = node("Grid", label="Rows", rowHeader=1, columns=[])
        self.assertEqual([f for f in check_tree(tree) if f["check"] == "empty-state"], [])
        self.assertTrue(any(f["check"] == "empty-state" for f in check_tree(tree, empty_path=True)))

    def test_nested_children_are_walked(self):
        tree = node("Column", children=[node("Text", text="null")])
        self.assertTrue(any(f["check"] == "technical-text" for f in check_tree(tree)))


class TestDetectionIsByPropertySignature(unittest.TestCase):
    """The rewrite of § 16 Fase 3. The old checker keyed on a closed list of
    `#t` values, so a component Appian renamed, wrapped or shipped after the
    list was written went unjudged -- and the run still said OK. What a node
    CARRIES is what decides which checks apply to it."""

    def test_a_type_name_the_checker_never_heard_of_is_still_judged(self):
        # `GridField` is not in any vocabulary here; it carries `rows`.
        tree = node("GridField", rows=[])
        found = {f["check"] for f in check_tree(tree)}
        self.assertIn("grid-accessibility", found)

    def test_an_input_is_whatever_writes_a_value_back(self):
        self.assertIn("input", categories_of({"#t": "SomeNewFieldWidget",
                                              "value": "x",
                                              "saveInto": "local!x"}))

    def test_a_layout_wrapper_belongs_to_no_category(self):
        # And that is the honest answer: nothing about a column is judged,
        # so claiming coverage over it would be the vacuous pass.
        self.assertEqual(categories_of({"#t": "ColumnLayout", "contents": []}), ())

    def test_an_alternative_label_spelling_is_not_a_false_finding(self):
        tree = node("GridField", rows=[], labelText="Rows", rowHeader=1)
        self.assertEqual([f for f in check_tree(tree)
                          if f["check"] == "grid-accessibility"], [])

    def test_the_census_counts_by_category_not_by_type(self):
        tree = node("Section", children=[
            node("Text", text="a"), node("Text", text="b"),
            node("Widget", value=1, saveInto="local!x")])
        census = category_census(tree)
        self.assertEqual(census["text"], 2)
        self.assertEqual(census["input"], 1)
        self.assertEqual(census["grid"], 0)


class TestNormalization(unittest.TestCase):
    """§ 8.5. Two renders of an untouched screen already differ: a fresh
    `_cId` per node, a re-encrypted `saveInto` and a new `durationMs`.
    Comparing raw renders is a test that cannot fail."""

    def _render(self, cid, nonce, duration):
        return {"#t": "Form", "_cId": cid, "diagnostics": {"durationMs": duration},
                "contents": [{"#t": "TextField", "_cId": cid + "-1",
                              "label": "Name", "value": "Ana",
                              "saveInto": "enc:" + nonce}]}

    def test_two_equivalent_renders_normalize_to_the_same_hash(self):
        a = self._render("111", "aaa", 12)
        b = self._render("999", "zzz", 4210)
        self.assertNotEqual(json.dumps(a, sort_keys=True),
                            json.dumps(b, sort_keys=True))
        self.assertEqual(normalized_hash(a), normalized_hash(b))

    def test_a_real_change_does_move_the_hash(self):
        a = self._render("111", "aaa", 12)
        b = self._render("111", "aaa", 12)
        b["contents"][0]["value"] = "Bea"
        self.assertNotEqual(normalized_hash(a), normalized_hash(b))

    def test_normalization_never_nulls_value_text_or_values(self):
        tree = {"value": "keep", "text": "keep", "values": ["keep"],
                "_cId": "x", "saveInto": "enc:nonce"}
        out = normalize_tree(tree)
        self.assertEqual(out["value"], "keep")
        self.assertEqual(out["text"], "keep")
        self.assertEqual(out["values"], ["keep"])
        self.assertNotIn("_cId", out)
        self.assertEqual(out["saveInto"], "<handler>")

    def test_the_handler_survives_as_presence(self):
        # Whether a node HAS a saveInto is signal; its ciphertext is noise.
        with_handler = normalize_tree({"label": "x", "saveInto": "enc:a"})
        without = normalize_tree({"label": "x"})
        self.assertNotEqual(with_handler, without)


class TestTheTwoGuaranteesAndTheCorollary(unittest.TestCase):
    """§ 8.5: (3) the populated has strictly more value-bearing nodes is the
    guarantee; (2) the hashes differ is its corollary."""

    POPULATED = {"#t": "Form", "contents": [
        {"#t": "Grid", "label": "Rows", "rowHeader": 1,
         "data": [{"name": "Ana"}, {"name": "Bea"}]},
        {"#t": "TextField", "label": "Name", "value": "Ana",
         "saveInto": "enc:1"}]}
    EMPTY = {"#t": "Form", "contents": [
        {"#t": "Grid", "label": "Rows", "rowHeader": 1, "data": [],
         "emptyGridMessage": "Sin candidatos"},
        {"#t": "TextField", "label": "Name", "value": "", "saveInto": "enc:1"}]}

    def test_populated_carries_strictly_more_value_nodes(self):
        self.assertGreater(value_nodes(self.POPULATED), value_nodes(self.EMPTY))

    def test_the_pair_satisfies_both_guarantees(self):
        signals = render_signals(self.POPULATED, self.EMPTY)
        self.assertTrue(signals["guarantees"]["distinctHash"])
        self.assertTrue(signals["guarantees"]["strictlyMoreValueNodes"])
        self.assertTrue(signals["guarantees"]["credits"])

    def test_a_foreach_that_never_iterated_fails_the_inequality(self):
        # The defect the hash alone cannot catch: same structure, no data.
        signals = render_signals(self.EMPTY, self.EMPTY)
        self.assertFalse(signals["guarantees"]["strictlyMoreValueNodes"])
        self.assertFalse(signals["guarantees"]["distinctHash"])

    def test_a_truncated_render_credits_nothing(self):
        truncated = dict(self.POPULATED)
        truncated["diagnostics"] = {"truncated": True}
        signals = render_signals(truncated, self.EMPTY)
        self.assertTrue(signals["populated"]["truncated"])
        self.assertFalse(signals["guarantees"]["credits"])

    def test_a_render_error_credits_nothing(self):
        broken = dict(self.POPULATED)
        broken["diagnostics"] = {"error": "expression evaluation error"}
        signals = render_signals(broken, self.EMPTY)
        self.assertFalse(signals["guarantees"]["credits"])

    def test_the_record_is_small_enough_to_travel(self):
        # § 12.3: what goes up is the verdict, not the input. A screen is
        # 218 KB; this is the thing that replaces it.
        record = render_record(self.POPULATED)
        self.assertLess(len(json.dumps(record)), 2000)


class TestCLI(unittest.TestCase):
    """The entry point is the whole point of these checks being reachable:
    an importable module with no `main` is a check nothing can run."""

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["n2_interface_tree.py"] + args)
        return code, out.getvalue(), err.getvalue()

    def tree_file(self, root, tree, name="tree.json"):
        p = os.path.join(root, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(tree, f)
        return p

    def test_clean_tree_exits_zero(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.tree_file(t, node("Text", text="Pending", color="#000000",
                                       backgroundColor="#FFFFFF"))
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_findings_exit_nonzero_and_are_printed(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.tree_file(t, node("Text", text="Pending", color="#FFC107",
                                       backgroundColor="#FFFFFF"))
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 1)
            self.assertIn("contrast", out)

    def test_empty_path_flag_turns_on_the_empty_state_check(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.tree_file(t, node("Grid", label="Rows", rowHeader=1, columns=[]))
            self.assertEqual(self.run_main([p])[0], 0)
            code, out, _ = self.run_main([p, "--empty-path"])
            self.assertEqual(code, 1)
            self.assertIn("empty-state", out)

    def test_no_argument_is_a_usage_error_on_stderr(self):
        code, _out, err = self.run_main([])
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertIn("EVALUATED component tree", err)

    def test_unreadable_input_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "tree.json")
            open(p, "w", encoding="utf-8").write("{not json")
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 1)
            self.assertIn("ERROR", out)

    def test_record_mode_emits_the_signals_of_a_pair(self):
        pair = TestTheTwoGuaranteesAndTheCorollary
        with tempfile.TemporaryDirectory() as t:
            a = self.tree_file(t, pair.POPULATED, "poblado.json")
            b = self.tree_file(t, pair.EMPTY, "vacio.json")
            out_path = os.path.join(t, "render-signals.json")
            code, out, _ = self.run_main(["--record", a, b, "--out", out_path])
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as f:
                signals = json.load(f)
            self.assertTrue(signals["guarantees"]["strictlyMoreValueNodes"])
            self.assertIn("normalizedHash", signals["populated"])

    def test_record_mode_reports_a_pair_that_proves_nothing(self):
        pair = TestTheTwoGuaranteesAndTheCorollary
        with tempfile.TemporaryDirectory() as t:
            a = self.tree_file(t, pair.EMPTY, "a.json")
            b = self.tree_file(t, pair.EMPTY, "b.json")
            code, _out, _ = self.run_main(["--record", a, b])
            self.assertEqual(code, 1)


class TestUnrecognisedTreeIsNotAPass(unittest.TestCase):
    """A tree carrying no property any of these checks is about must not come
    back `OK`, exit 0 -- indistinguishable from a screen that was checked and
    found clean. That is the vacuous pass `lint_skills.py` refuses when it
    declines to claim "All skills passed" over zero files, and it breaks the
    plugin's own claim that these exit codes tell a clean run from a run that
    never happened."""

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["n2_interface_tree.py"] + args)
        return code, out.getvalue(), err.getvalue()

    def tree_file(self, root, tree):
        p = os.path.join(root, "tree.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(tree, f)
        return p

    def test_a_tree_of_pure_layout_is_not_measured(self):
        tree = node("SectionLayout", contents=[node("ColumnLayout", contents=[])])
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, tree)])
            self.assertEqual(code, 3)
            self.assertIn("NOT MEASURED", out)
            self.assertNotIn("OK ", out)

    def test_a_tree_with_no_component_nodes_at_all_is_not_measured(self):
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, {"totalCount": 0})])
            self.assertEqual(code, 3)
            self.assertIn("NOT MEASURED", out)

    def test_a_recognised_tree_is_still_a_clean_pass(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.tree_file(t, node("Text", text="Pending", color="#000000",
                                       backgroundColor="#FFFFFF"))
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)
            self.assertNotIn("NOT MEASURED", out)

    def test_the_categories_that_did_not_run_are_named(self):
        # A measured run still says which categories were absent, so the gap
        # is visible rather than assumed to be nothing.
        tree = node("Text", text="Pending")
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, tree)])
            self.assertEqual(code, 0)
            self.assertIn("grid", out)
            self.assertIn("input", out)

    def test_findings_on_an_otherwise_unmeasured_tree_are_still_printed(self):
        # Contrast fires on a node whose other properties this checker does
        # not judge. The finding is real and is printed -- and a run that
        # measured only that is still reported for what it measured.
        tree = node("Mystery", color="#FFC107", backgroundColor="#FFFFFF")
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, tree)])
            self.assertIn("contrast", out)
            self.assertEqual(code, 1)

    def test_the_usage_text_lists_the_categories_from_the_constant(self):
        # A checker whose vocabulary is invisible cannot be used
        # deliberately, and a vocabulary restated by hand drifts.
        _code, _out, err = self.run_main([])
        for c in CATEGORIES:
            self.assertIn(c, err)

if __name__ == "__main__":
    unittest.main()
