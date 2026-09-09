"""Checks process-model layout from node coordinates.

    usage: n3_process_layout.py LAYOUT_JSON
    exit: 0 clean, 1 findings or unreadable input, 2 usage, 3 NOT MEASURED

The API exposes no node dimensions and no waypoints, so this says where every
node sits and never where an arrow goes:
docs/design-notes.md § n3_process_layout.py · coordinates only"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402

# The proxy for "these do not overlap", not a proof:
# docs/design-notes.md § n3_process_layout.py · the thresholds
MIN_DX = 150
MIN_DY = 100

# C4 is missing on purpose: coordinates cannot decide lanes, so that is N5.
# docs/design-notes.md § n3_process_layout.py · the C4 gap


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


# --- § 8.3 · the graph checks, from listProcessModelNodes --------------
#
# What `change-review.md § Process Model Checks` specifies WITHOUT starting
# anything, cited and not reinvented. It does not prove a gateway's
# condition is right; it proves the gateway is not broken, which was half
# the residue a process-model close used to carry whole.
START_NODE_ID = 1
END_NODE_ID = 2


def _node_index(nodes):
    index = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), int):
            index[node["id"]] = node
    return index


def _outgoing(node):
    """Every node this one points at: flow connections and, on a gateway,
    the decision targets. A gateway whose only exits are conditions is
    connected -- treating those as non-edges would report every XOR as an
    orphan."""
    targets = []
    for conn in node.get("connections") or []:
        if isinstance(conn, dict) and isinstance(conn.get("targetNodeId"), int):
            targets.append(conn["targetNodeId"])
    decision = node.get("decision")
    if isinstance(decision, dict):
        for cond in decision.get("conditions") or []:
            if isinstance(cond, dict) and isinstance(cond.get("targetNodeId"), int):
                targets.append(cond["targetNodeId"])
        if isinstance(decision.get("defaultPath"), int):
            targets.append(decision["defaultPath"])
    return targets


def process_graph_findings(nodes):
    """G1 reachability, G2 dangling targets, G3 orphans. Empty = clean."""
    findings = []
    index = _node_index(nodes)
    if not index:
        return findings

    def where(node_id):
        node = index.get(node_id) or {}
        name = node.get("name")
        if isinstance(name, dict):
            name = next(iter(name.values()), None)
        return "%s(%s)" % (node_id, name or node.get("type") or "?")

    # G2 first: a dangling target is also what makes reachability lie.
    for node_id, node in sorted(index.items()):
        for target in _outgoing(node):
            if target not in index:
                findings.append({"check": "G2", "nodes": [where(node_id)],
                                 "detail": "points at node %d, which does not exist "
                                           "in this process model" % target})

    reachable, stack = set(), [START_NODE_ID]
    if START_NODE_ID in index:
        while stack:
            current = stack.pop()
            if current in reachable:
                continue
            reachable.add(current)
            for target in _outgoing(index.get(current, {})):
                if target in index:
                    stack.append(target)
        for node_id in sorted(set(index) - reachable):
            findings.append({"check": "G1", "nodes": [where(node_id)],
                             "detail": "not reachable from Start (node %d)"
                                       % START_NODE_ID})
        if END_NODE_ID in index and END_NODE_ID not in reachable:
            findings.append({"check": "G1", "nodes": [where(END_NODE_ID)],
                             "detail": "the graph forms no path from Start to End"})
    else:
        findings.append({"check": "G1", "nodes": ["start"],
                         "detail": "no Start node (id %d): reachability cannot be "
                                   "decided, so nothing here is a clean graph"
                                   % START_NODE_ID})

    incoming = set()
    for node in index.values():
        incoming.update(_outgoing(node))
    for node_id, node in sorted(index.items()):
        if node_id in (START_NODE_ID, END_NODE_ID):
            continue
        if node_id not in incoming and not _outgoing(node):
            findings.append({"check": "G3", "nodes": [where(node_id)],
                             "detail": "orphan: no incoming and no outgoing connection"})
    return findings


def layout_from_nodes(nodes):
    """The coordinate view of the same input, so one fetch feeds both
    halves instead of asking the agent for two shapes."""
    coords, edges = {}, []
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), int):
            continue
        name = node.get("name")
        if isinstance(name, dict):
            name = next(iter(name.values()), None)
        label = str(name or node["id"])
        xy = node.get("coordinates")
        if isinstance(xy, (list, tuple)) and len(xy) == 2 \
                and all(isinstance(c, (int, float)) and not isinstance(c, bool)
                        for c in xy):
            coords[label] = [xy[0], xy[1]]
        for target in _outgoing(node):
            edges.append([label, str(target)])
    known = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), int):
            name = node.get("name")
            if isinstance(name, dict):
                name = next(iter(name.values()), None)
            known[str(node["id"])] = str(name or node["id"])
    edges = [[a, known.get(b, b)] for a, b in edges]
    return coords, edges


USAGE = """usage: n3_process_layout.py LAYOUT_JSON
       n3_process_layout.py --graph NODES_JSON

LAYOUT_JSON  a file holding one process model's node coordinates and its
             connections, as the layout API returns them:

               {"nodes": {"<node name>": [x, y], ...},
                "edges": [["<from>", "<to>"], ...]}

             Coordinates only. This says where every node sits and nothing
             about where a connection routes -- the API exposes no waypoints
             (field experience) -- so a clean run is not a clean diagram.

--graph      NODES_JSON is what `listProcessModelNodes` returns: the list of
             nodes with their `id`, `coordinates`, `connections` and, on a
             gateway, its `decision`. It runs the graph checks of the
             official review reference -- reachability from Start, dangling
             `targetNodeId`, orphan nodes -- and then the layout checks over
             the coordinates of the same input.

             It does not prove a gateway's condition is right. It proves the
             gateway is not broken, which needs no process started.

Exit codes match the plugin's other checkers: 0 clean, 1 findings (or an input
that cannot be read), 2 usage, 3 NOT MEASURED -- nothing was checked, which a
layout naming no nodes is."""


def _shape_errors(data):
    """A named reason for a malformed layout, instead of a TypeError raised
    three frames down in check_layout."""
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


def _graph_mode(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except ValueError as e:
        print("ERROR %s: cannot parse the nodes as JSON: %s" % (path, e))
        return 1
    except OSError as e:
        print("ERROR %s: cannot read the nodes: %s" % (path, e))
        return 1

    nodes = data.get("nodes") if isinstance(data, dict) else data
    if not isinstance(nodes, list) or not _node_index(nodes):
        print("NOT MEASURED %s: no node carried an integer `id`, so neither the graph "
              "nor the layout checks ran. This is not a clean process model; it is an "
              "unchecked one." % path)
        return EXIT_NOT_MEASURED

    findings = process_graph_findings(nodes)
    coords, edges = layout_from_nodes(nodes)
    if coords:
        findings.extend(check_layout(coords, edges))
    for f in findings:
        print("FINDING %s: %s at %s -- %s"
              % (path, f["check"], ", ".join(str(n) for n in f["nodes"]), f["detail"]))
    if findings:
        print("\n%d finding(s)." % len(findings))
        return 1
    print("OK %s" % path)
    return 0


def main(argv):
    if len(argv) == 3 and argv[1] == "--graph":
        return _graph_mode(argv[2])
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
        # Nodes are what get measured, so naming none of them is unchecked,
        # not clean. docs/design-notes.md § n3_process_layout.py · no nodes is not measured
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
