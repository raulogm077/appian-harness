import io, json, os, tempfile, unittest
from contextlib import redirect_stdout, redirect_stderr
from n2_interface_tree import CHECKED_TYPES, check_tree, contrast_ratio, main

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
        tree = node("TextField", value="x")
        self.assertTrue(any(f["check"] == "input-label" for f in check_tree(tree)))

    def test_empty_grid_message_required_only_on_the_empty_path(self):
        tree = node("Grid", label="Rows", rowHeader=1, columns=[])
        self.assertEqual([f for f in check_tree(tree) if f["check"] == "empty-state"], [])
        self.assertTrue(any(f["check"] == "empty-state" for f in check_tree(tree, empty_path=True)))

    def test_nested_children_are_walked(self):
        tree = node("Column", children=[node("Text", text="null")])
        self.assertTrue(any(f["check"] == "technical-text" for f in check_tree(tree)))

class TestCLI(unittest.TestCase):
    """The entry point is the whole point of these checks being reachable:
    an importable module with no `main` is a check nothing can run."""

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


class TestUnrecognisedTreeIsNotAPass(unittest.TestCase):
    """A tree whose component types this checker does not judge used to come
    back `OK`, exit 0 -- indistinguishable from a screen that was checked and
    found clean. That is the same vacuous pass `lint_skills.py` fixed when it
    stopped claiming "All skills passed" over zero files, and it also broke
    the plugin's own claim that these exit codes tell a clean run from a run
    that never happened."""

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

    def test_a_plausible_but_unrecognised_tree_is_not_measured(self):
        # The walkthrough's probe: "GridField" is a plausible Appian type
        # name and is not one this checker judges.
        tree = node("GridField", labelText="Open requests",
                    rows=[node("GridRowLayout", contents=[node("TextItem", content="Pending")])])
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, tree)])
            self.assertEqual(code, 3)
            self.assertIn("NOT MEASURED", out)
            self.assertNotIn("OK ", out)
            self.assertIn("GridField", out)          # names what it did not judge
            self.assertIn("TextField", out)          # and what it would have

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

    def test_partial_recognition_names_the_unjudged_types_without_changing_the_verdict(self):
        # Some recognised, some not: the run DID measure something, so the
        # exit code stands -- but which types went unjudged is said out loud
        # rather than left for the reader to assume it was nothing.
        tree = node("SectionLayout", children=[node("Text", text="Pending"),
                                               node("GridField", labelText="Rows")])
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, tree)])
            self.assertEqual(code, 0)
            self.assertIn("GridField", out)
            self.assertIn("SectionLayout", out)

    def test_findings_on_an_unrecognised_tree_are_printed_and_still_not_measured(self):
        # Contrast does not care about the node's type, so it can fire on a
        # tree this checker otherwise does not understand. The finding is
        # real and is printed -- but a run that judged none of the types it
        # exists to judge is not a measured run.
        tree = node("GridField", color="#FFC107", backgroundColor="#FFFFFF")
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.tree_file(t, tree)])
            self.assertIn("contrast", out)
            self.assertIn("NOT MEASURED", out)
            self.assertEqual(code, 3)

    def test_the_usage_text_lists_the_vocabulary_from_the_constant(self):
        # A checker whose vocabulary is invisible cannot be used
        # deliberately, and a vocabulary restated by hand drifts.
        _code, _out, err = self.run_main([])
        for t in CHECKED_TYPES:
            self.assertIn(t, err)

if __name__ == "__main__":
    unittest.main()
