import unittest
from n2_interface_tree import check_tree, contrast_ratio

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

if __name__ == "__main__":
    unittest.main()
