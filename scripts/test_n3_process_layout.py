import unittest
from n3_process_layout import check_layout

# Coordinates in the shape the layout API returns them.
GOOD = {"s": [100, 200], "a": [300, 200], "b": [500, 200], "c": [700, 200]}
EDGES = [("s", "a"), ("a", "b"), ("b", "c")]

class TestLayout(unittest.TestCase):
    def test_clean_layout_has_no_findings(self):
        self.assertEqual(check_layout(GOOD, EDGES), [])

    def test_exact_overlap_is_C1(self):
        nodes = dict(GOOD, b=[300, 200])          # b sits exactly on a
        self.assertTrue(any(f["check"] == "C1" for f in check_layout(nodes, EDGES)))

    def test_horizontal_crowding_is_C2(self):
        nodes = dict(GOOD, b=[360, 200])          # 60 px from a
        self.assertTrue(any(f["check"] == "C2" for f in check_layout(nodes, EDGES)))

    def test_vertical_crowding_is_C2(self):
        # The one that a horizontal-only rule misses: same x, 80 px apart.
        nodes = dict(GOOD, b=[300, 280])
        self.assertTrue(any(f["check"] == "C2" for f in check_layout(nodes, EDGES)))

    def test_backward_flow_is_C3(self):
        nodes = dict(GOOD, c=[420, 200])          # c is left of b
        self.assertTrue(any(f["check"] == "C3" for f in check_layout(nodes, EDGES)))

    def test_loop_back_edge_is_not_C3(self):
        edges = EDGES + [("c", "a")]              # a real loop, exempt
        self.assertEqual([f for f in check_layout(GOOD, edges) if f["check"] == "C3"], [])

    def test_orphan_node_is_C5(self):
        nodes = dict(GOOD, z=[900, 600])
        self.assertTrue(any(f["check"] == "C5" for f in check_layout(nodes, EDGES)))

if __name__ == "__main__":
    unittest.main()
