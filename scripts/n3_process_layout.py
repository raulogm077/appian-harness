"""Checks process-model layout from node coordinates.

Field experience, and an honest limit: the API exposes node coordinates but
neither node dimensions nor connection waypoints. So the thresholds below are
a proxy for "these do not overlap", not a proof, and this tells you where every
node sits -- never where any arrow goes.
"""
MIN_DX = 150
MIN_DY = 100
LANE_DY = 150


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
