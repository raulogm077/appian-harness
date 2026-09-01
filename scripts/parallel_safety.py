# This docstring is the tool's help text, so it stays ASCII. What it refuses
# on: docs/design-notes.md § parallel_safety.py · the four refusal reasons
"""Decides whether a set of Appian tasks may be built concurrently.

    python3 parallel_safety.py PLAN_JSON [--group T-1,T-2 --group T-3,T-4]
    0 safe  1 findings  2 usage  3 NOT MEASURED -- nothing to judge, not a pass

With no --group every task is checked pairwise and the largest safe groups are
reported. A worktree isolates files; it does not isolate Appian."""
import json
import os
import sys

# Substring match on names, because a plan writes names and not types:
# docs/design-notes.md § parallel_safety.py · shared-object hints
SHARED_OBJECT_HINTS = (
    "application",
    "group",
    "constant",
    "connectedsystem",
    "connected system",
)

DESTRUCTIVE_HINTS = ("delete", "remove", "drop", "borrar", "eliminar")


def _norm(value):
    return str(value).strip().lower()


def tasks_of(plan):
    """The plan's tasks, however the project spelled the container. Returns []
    when nothing recognisable is there, which the caller turns into NOT
    MEASURED rather than into a pass."""
    if isinstance(plan, list):
        candidates = plan
    elif isinstance(plan, dict):
        candidates = plan.get("tasks") or plan.get("plan") or []
    else:
        return []
    return [t for t in candidates if isinstance(t, dict) and t.get("id")]


def _objects(task):
    raw = task.get("allowedObjects") or []
    if isinstance(raw, str):
        raw = [raw]
    return {_norm(o) for o in raw if str(o).strip()}


def _depends_on(task):
    raw = task.get("dependsOn") or task.get("dependencies") or []
    if isinstance(raw, str):
        raw = [raw]
    return {_norm(d) for d in raw if str(d).strip()}


def transitive_dependencies(tasks):
    """id -> every task it depends on, directly or through a chain. A fixed
    point rather than a recursive walk, which miscaches cycles:
    docs/design-notes.md § parallel_safety.py · the transitive closure"""
    closure = {_norm(t["id"]): set(_depends_on(t)) for t in tasks}
    changed = True
    while changed:
        changed = False
        for node, deps in closure.items():
            grown = set(deps)
            for dep in deps:
                grown |= closure.get(dep, set())
            if grown != deps:
                closure[node] = grown
                changed = True
    return closure


def dependency_cycles(tasks):
    """Tasks that end up depending on themselves. A plan, not a race."""
    closure = transitive_dependencies(tasks)
    return sorted(t for t, deps in closure.items() if t in deps)


def _is_destructive(task):
    """Whether this task's own description admits to deleting something."""
    haystack = " ".join(str(task.get(k, "")) for k in
                        ("id", "title", "name", "description", "acceptanceCriteria"))
    haystack = _norm(haystack)
    return any(h in haystack for h in DESTRUCTIVE_HINTS)


def _shared_objects(task):
    return {o for o in _objects(task) if any(h in o for h in SHARED_OBJECT_HINTS)}


def check_pair(a, b, closure=None):
    """Why these two tasks may not run concurrently. Empty list means they may.
    Callers holding the plan should always pass `closure`; without it the check
    is weaker: docs/design-notes.md § parallel_safety.py · check_pair without the closure"""
    findings = []
    a_id, b_id = a.get("id"), b.get("id")
    a_key, b_key = _norm(a_id), _norm(b_id)

    overlap = _objects(a) & _objects(b)
    if overlap:
        findings.append(
            "%s and %s both claim %s: two writers on one object, and no reviewer "
            "downstream can tell whose change they are looking at"
            % (a_id, b_id, ", ".join(sorted(overlap))))

    a_deps = closure.get(a_key, set()) if closure else _depends_on(a)
    b_deps = closure.get(b_key, set()) if closure else _depends_on(b)
    for dependent, dependency, deps in ((a_id, b_id, a_deps), (b_id, a_id, b_deps)):
        if _norm(dependency) in deps:
            indirect = "" if _norm(dependency) in _depends_on(
                a if dependent == a_id else b) else " (through a chain)"
            findings.append("%s depends on %s%s: the platform's order is not suspended by "
                            "running them at the same time" % (dependent, dependency, indirect))

    for task, other in ((a, b), (b, a)):
        if _is_destructive(task):
            findings.append("%s looks destructive, so it runs alone: a deletion's blast radius "
                            "is not bounded by allowedObjects and can break objects %s never "
                            "listed" % (task.get("id"), other.get("id")))
        shared = _shared_objects(task)
        if shared:
            findings.append("%s touches %s, which other tasks depend on without naming it -- "
                            "confirm that is really independent of %s before running them "
                            "together" % (task.get("id"), ", ".join(sorted(shared)),
                                          other.get("id")))
    return findings


def check_group(tasks, closure=None):
    """Every reason this group of tasks may not run concurrently."""
    findings = []
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            findings.extend(check_pair(a, b, closure))
    # One fact per pair repeats across a group, and a repetitive list gets
    # skimmed. docs/design-notes.md § parallel_safety.py · deduplicated findings
    seen, unique = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def safe_groups(tasks):
    """Greedy partition into groups that are internally safe to run together.
    Greedy on purpose, not for want of a better search:
    docs/design-notes.md § parallel_safety.py · greedy grouping"""
    closure = transitive_dependencies(tasks)
    groups = []
    for task in tasks:
        for group in groups:
            if not check_group(group + [task], closure):
                group.append(task)
                break
        else:
            groups.append([task])
    return groups


def main(argv):
    args = argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 2

    plan_path, requested = args[0], []
    i = 1
    while i < len(args):
        if args[i] == "--group" and i + 1 < len(args):
            requested.append([t.strip() for t in args[i + 1].split(",") if t.strip()])
            i += 2
        else:
            print("unrecognised argument: %s" % args[i], file=sys.stderr)
            return 2

    if not os.path.isfile(plan_path):
        print("no such plan file: %s" % plan_path, file=sys.stderr)
        return 2
    try:
        with open(plan_path, encoding="utf-8") as f:
            plan = json.load(f)
    except (ValueError, OSError) as e:
        print("cannot read %s: %s" % (plan_path, e), file=sys.stderr)
        return 2

    tasks = tasks_of(plan)
    if not tasks:
        print("NOT MEASURED: no tasks with an `id` found in %s -- nothing was checked, which "
              "is not the same as nothing being wrong" % plan_path)
        return 3

    by_id = {_norm(t["id"]): t for t in tasks}
    closure = transitive_dependencies(tasks)
    findings = []

    cycles = dependency_cycles(tasks)
    if cycles:
        # Not a concurrency finding, so it is reported alone:
        # docs/design-notes.md § parallel_safety.py · cycles
        print("the plan's dependencies form a cycle involving: %s -- this plan cannot be "
              "executed in any order, sequential or concurrent" % ", ".join(cycles))
        return 1

    if requested:
        for names in requested:
            missing = [n for n in names if _norm(n) not in by_id]
            if missing:
                findings.append("group %s names tasks not in the plan: %s"
                                % (",".join(names), ", ".join(missing)))
                continue
            group = [by_id[_norm(n)] for n in names]
            for f in check_group(group, closure):
                findings.append("group %s: %s" % (",".join(names), f))
        for f in findings:
            print(f)
        if findings:
            return 1
        print("OK %d group(s) safe to build concurrently" % len(requested))
        return 0

    groups = safe_groups(tasks)
    for group in groups:
        print("concurrent group: %s" % ", ".join(t["id"] for t in group))
    solo = [g for g in groups if len(g) == 1]
    print("%d task(s) in %d group(s); %d must run alone"
          % (len(tasks), len(groups), len(solo)))
    # Said out loud because the printed order looks like a schedule and is not:
    # docs/design-notes.md § parallel_safety.py · groups are not a schedule
    print("note: these groups say who may run TOGETHER, not in what order. "
          "Sequencing is still the plan's dependency order.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
