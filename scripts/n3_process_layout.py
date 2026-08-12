"""Checks process-model layout from node coordinates.

Field experience, and an honest limit: the API exposes node coordinates but
neither node dimensions nor connection waypoints. So the thresholds below are
a proxy for "these do not overlap", not a proof, and this tells you where every
node sits -- never where any arrow goes.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# The comment here used to open "Same value and same meaning as
# n2_interface_tree.EXIT_NOT_MEASURED and lint_skills" over a freshly typed
# `= 3`, which is a copy that knows it is one and says so instead of stopping
# being one. What survives the import is the part that is about this file:
# N2's vacuous pass has a narrower form here -- a layout naming no nodes had
# nothing to compare and reported OK, indistinguishable from a process model
# that was checked and found clean.
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

MIN_DX = 150
MIN_DY = 100

# The check ids jump from C3 to C5, and that gap is deliberate rather than an
# omission to be filled later. C4 was to be a lane check -- "the nominal path
# sits on one y, branches get their own" -- and nodes plus edges do not carry
# enough to decide it: nothing here says which path is nominal, and any rule
# guessing it from coordinates would only be re-asserting whatever layout it
# was given. A constant for it (LANE_DY) sat here unused while the README
# advertised the check; both are gone. Lanes are a judgement made by looking
# at the diagram, which is N5.


def _back_edges(edges):
    """Edges that close a cycle, found by DFS. Loops are legitimate: exempt from C3."""
    adj = {}
    for a, b in edges:
        adj.setdefault(a, []).append(b)
    back, state = set(), {}

    def visit(n):
        state[n] = 1
        for m in adj.get(n, []):
            if state.get(m) == 1:
                back.add((n, m))
            elif state.get(m) is None:
                visit(m)
        state[n] = 2

    for n in list(adj):
        if state.get(n) is None:
            visit(n)
    return back


def check_layout(nodes, edges):
    findings = []
    names = sorted(nodes)

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ax, ay = nodes[a]
            bx, by = nodes[b]
            if [ax, ay] == [bx, by]:
                findings.append({"check": "C1", "nodes": [a, b],
                                 "detail": "identical coordinates %s" % ([ax, ay],)})
            elif abs(ax - bx) < MIN_DX and abs(ay - by) < MIN_DY:
                findings.append({"check": "C2", "nodes": [a, b],
                                 "detail": "too close: dx=%d dy=%d (need dx>=%d or dy>=%d)"
                                           % (abs(ax - bx), abs(ay - by), MIN_DX, MIN_DY)})

    back = _back_edges(edges)
    for a, b in edges:
        if (a, b) in back:
            continue
        if a in nodes and b in nodes and nodes[b][0] <= nodes[a][0]:
            findings.append({"check": "C3", "nodes": [a, b],
                             "detail": "flow goes backwards: x %d -> %d" % (nodes[a][0], nodes[b][0])})

    has_in = set(b for _, b in edges)
    has_out = set(a for a, _ in edges)
    for n in names:
        if n not in has_in and n not in has_out:
            findings.append({"check": "C5", "nodes": [n], "detail": "node is not connected"})

    return findings


USAGE = """usage: n3_process_layout.py LAYOUT_JSON

LAYOUT_JSON  a file holding one process model's node coordinates and its
             connections, as the layout API returns them:

               {"nodes": {"<node name>": [x, y], ...},
                "edges": [["<from>", "<to>"], ...]}

             Coordinates only. This says where every node sits and nothing
             about where a connection routes -- the API exposes no waypoints
             (field experience) -- so a clean run is not a clean diagram.

Exit codes match the plugin's other checkers: 0 clean, 1 findings (or an input
that cannot be read), 2 usage, 3 NOT MEASURED -- nothing was checked, which a
layout naming no nodes is."""


def _shape_errors(data):
    """Rejects a malformed layout with a named reason instead of letting
    check_layout raise a TypeError three frames down."""
    if not isinstance(data, dict):
        return "layout must be a JSON object with 'nodes' and 'edges'"
    nodes, edges = data.get("nodes"), data.get("edges")
    if not isinstance(nodes, dict):
        return "'nodes' must be an object mapping each node name to [x, y]"
    for name, xy in nodes.items():
        if (not isinstance(xy, (list, tuple)) or len(xy) != 2
                or not all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in xy)):
            return "node %r must map to [x, y] with two numbers, got %r" % (name, xy)
    if not isinstance(edges, list):
        return "'edges' must be a list of [from, to] pairs"
    for edge in edges:
        if not isinstance(edge, (list, tuple)) or len(edge) != 2:
            return "edge %r must be a [from, to] pair" % (edge,)
    return None


def main(argv):
    if len(argv) != 2:
        print(USAGE, file=sys.stderr)
        return 2

    path = argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError as e:
        print("ERROR %s: cannot parse the layout as JSON: %s" % (path, e))
        return 1
    except OSError as e:
        print("ERROR %s: cannot read the layout: %s" % (path, e))
        return 1

    shape_error = _shape_errors(data)
    if shape_error:
        print("ERROR %s: %s" % (path, shape_error))
        return 1

    if not data["nodes"]:
        # Nodes are what get measured. A layout naming none of them -- with
        # or without edges -- compared nothing, and reporting that as clean
        # is the vacuous pass this plugin argues against everywhere else.
        print("NOT MEASURED %s: the layout names no nodes, so no separation, direction or "
              "connectivity check ran. This is not a clean layout; it is an unchecked one."
              % path)
        return EXIT_NOT_MEASURED

    findings = check_layout(data["nodes"], data["edges"])
    for f in findings:
        print("FINDING %s: %s at %s -- %s" % (path, f["check"], ", ".join(f["nodes"]), f["detail"]))
    if findings:
        print("\n%d finding(s)." % len(findings))
        return 1
    print("OK %s" % path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
