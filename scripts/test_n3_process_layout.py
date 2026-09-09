import io, json, os, tempfile, unittest
from contextlib import redirect_stdout, redirect_stderr
import n3_process_layout as n3
from n3_process_layout import check_layout, main

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

class TestCLI(unittest.TestCase):
    """The entry point is the whole point of these checks being reachable:
    an importable module with no `main` is a check nothing can run."""

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["n3_process_layout.py"] + args)
        return code, out.getvalue(), err.getvalue()

    def layout_file(self, root, nodes, edges):
        p = os.path.join(root, "layout.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f)
        return p

    def test_clean_layout_exits_zero(self):
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.layout_file(t, GOOD, EDGES)])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_overlap_exits_nonzero_and_names_both_nodes(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.layout_file(t, dict(GOOD, b=[300, 200]), EDGES)
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 1)
            self.assertIn("C1", out)
            self.assertIn("a, b", out)

    def test_no_argument_is_a_usage_error_on_stderr(self):
        code, _out, err = self.run_main([])
        self.assertEqual(code, 2)
        self.assertIn("usage", err)
        self.assertIn("node coordinates", err)

    def test_malformed_layout_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "layout.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"nodes": {"s": [100]}, "edges": []}, f)
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 1)
            self.assertIn("ERROR", out)

    def test_unreadable_input_is_reported_not_raised(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "layout.json")
            open(p, "w", encoding="utf-8").write("{not json")
            code, out, _ = self.run_main([p])
            self.assertEqual(code, 1)
            self.assertIn("ERROR", out)


class TestEmptyLayoutIsNotAPass(unittest.TestCase):
    """N2's vacuous pass in its narrower N3 form: a layout naming no nodes has
    nothing to check, and must not answer OK, exit 0 -- indistinguishable
    from a process model that was checked and found clean."""

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(["n3_process_layout.py"] + args)
        return code, out.getvalue(), err.getvalue()

    def layout_file(self, root, nodes, edges):
        p = os.path.join(root, "layout.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"nodes": nodes, "edges": edges}, f)
        return p

    def test_an_empty_node_set_is_not_measured(self):
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.layout_file(t, {}, [])])
            self.assertEqual(code, 3)
            self.assertIn("NOT MEASURED", out)
            self.assertNotIn("OK ", out)

    def test_edges_without_nodes_are_still_not_measured(self):
        # Nodes are what get measured. Edges naming nodes that are not
        # there measure nothing.
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.layout_file(t, {}, [["a", "b"]])])
            self.assertEqual(code, 3)
            self.assertIn("NOT MEASURED", out)

    def test_a_layout_with_nodes_is_still_measured(self):
        with tempfile.TemporaryDirectory() as t:
            code, out, _ = self.run_main([self.layout_file(t, GOOD, EDGES)])
            self.assertEqual(code, 0)
            self.assertNotIn("NOT MEASURED", out)

if __name__ == "__main__":
    unittest.main()


class TestProcessGraphChecks(unittest.TestCase):
    """§ 8.3: what `change-review.md § Process Model Checks` specifies
    without starting any process. It does not prove a gateway's condition is
    right; it proves the gateway is not broken."""

    START = {"id": 1, "type": "START", "name": "Start", "coordinates": [0, 0],
             "connections": [{"targetNodeId": 3}]}
    TASK = {"id": 3, "type": "USER_TASK", "name": "Review", "coordinates": [200, 0],
            "connections": [{"targetNodeId": 2}]}
    END = {"id": 2, "type": "END", "name": "End", "coordinates": [400, 0],
           "connections": []}

    def test_a_valid_path_from_start_to_end_is_clean(self):
        self.assertEqual(
            n3.process_graph_findings([self.START, self.TASK, self.END]), [])

    def test_an_unreachable_node_is_G1(self):
        stray = {"id": 4, "type": "SCRIPT_TASK", "name": "Orphaned",
                 "coordinates": [200, 300], "connections": [{"targetNodeId": 2}]}
        checks = [f["check"] for f in n3.process_graph_findings(
            [self.START, self.TASK, self.END, stray])]
        self.assertIn("G1", checks)

    def test_a_gateway_pointing_at_a_node_that_does_not_exist_is_G2(self):
        gateway = {"id": 5, "type": "XOR", "name": "Approved?",
                   "coordinates": [200, 0],
                   "decision": {"conditions": [{"expression": "=true",
                                                "targetNodeId": 99}],
                                "defaultPath": 2}}
        start = dict(self.START, connections=[{"targetNodeId": 5}])
        findings = n3.process_graph_findings([start, gateway, self.END])
        self.assertIn("G2", [f["check"] for f in findings])
        self.assertTrue(any("99" in f["detail"] for f in findings))

    def test_a_gateway_whose_only_exits_are_conditions_is_connected(self):
        # The false positive this guards: treating decision targets as
        # non-edges reports every XOR as an orphan and every node past it
        # as unreachable.
        gateway = {"id": 5, "type": "XOR", "name": "Approved?",
                   "coordinates": [200, 0],
                   "decision": {"conditions": [{"expression": "=true",
                                                "targetNodeId": 2}],
                                "defaultPath": 2}}
        start = dict(self.START, connections=[{"targetNodeId": 5}])
        self.assertEqual(n3.process_graph_findings([start, gateway, self.END]), [])

    def test_an_orphan_with_no_connections_at_all_is_G3(self):
        orphan = {"id": 6, "type": "SCRIPT_TASK", "name": "Dead",
                  "coordinates": [200, 600], "connections": []}
        checks = [f["check"] for f in n3.process_graph_findings(
            [self.START, self.TASK, self.END, orphan])]
        self.assertIn("G3", checks)

    def test_no_start_node_is_not_a_clean_graph(self):
        checks = [f["check"] for f in n3.process_graph_findings([self.TASK, self.END])]
        self.assertIn("G1", checks)

    def test_the_layout_view_is_derived_from_the_same_input(self):
        coords, edges = n3.layout_from_nodes([self.START, self.TASK, self.END])
        self.assertEqual(sorted(coords), ["End", "Review", "Start"])
        self.assertIn(["Start", "Review"], edges)


class TestGraphCLI(unittest.TestCase):

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = n3.main(["n3_process_layout.py"] + args)
        return code, out.getvalue(), err.getvalue()

    def nodes_file(self, root, nodes):
        p = os.path.join(root, "nodes.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(nodes, f)
        return p

    def test_a_clean_model_exits_zero(self):
        g = TestProcessGraphChecks
        with tempfile.TemporaryDirectory() as t:
            p = self.nodes_file(t, [g.START, g.TASK, g.END])
            code, out, _ = self.run_main(["--graph", p])
            self.assertEqual(code, 0)
            self.assertIn("OK", out)

    def test_a_broken_model_exits_one_and_names_the_check(self):
        g = TestProcessGraphChecks
        orphan = {"id": 6, "type": "SCRIPT_TASK", "name": "Dead",
                  "coordinates": [200, 600], "connections": []}
        with tempfile.TemporaryDirectory() as t:
            p = self.nodes_file(t, [g.START, g.TASK, g.END, orphan])
            code, out, _ = self.run_main(["--graph", p])
            self.assertEqual(code, 1)
            self.assertIn("G3", out)

    def test_nodes_without_ids_are_not_measured(self):
        with tempfile.TemporaryDirectory() as t:
            p = self.nodes_file(t, [{"name": "no id"}])
            code, out, _ = self.run_main(["--graph", p])
            self.assertEqual(code, 3)
            self.assertIn("NOT MEASURED", out)
