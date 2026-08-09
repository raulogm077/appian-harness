"""Decides whether a set of Appian tasks may be built concurrently.

A git worktree isolates files. It does not isolate Appian. Two builders in
two worktrees calling `createRecordType` write to the same environment, so
the worktree protects the half of the problem that was already recoverable
and none of the half that is not.

This is the other half. Given the plan's tasks, it answers one question --
"can these run at the same time?" -- and refuses for reasons that are facts
about the tasks rather than judgements about them:

1. **Shared objects.** Two tasks whose `allowedObjects` intersect are two
   writers on one object. Nothing downstream can tell whose change a review
   is looking at.
2. **Dependency edges.** A task that depends on another cannot start beside
   it. The platform imposes an order -- data source before record type,
   record type before the query, constants before the interfaces that call
   them -- and "in parallel" does not suspend it.
3. **Destructive operations.** A deletion is the one action whose blast
   radius is not bounded by `allowedObjects`: it can break objects nobody
   listed. It runs alone, or not at all.
4. **Objects everything touches.** The application, a security group, a
   shared constant. Formally these are just objects, but a task that
   modifies one is a task every other task depends on without saying so.

Exit codes match the plugin's other checkers, including the one that
matters: **3 is NOT MEASURED, not a pass.** A plan this cannot read is a
plan nobody checked, and saying "OK" to it is exactly the vacuous green
this harness argues against everywhere else.

    0  the proposed groups are safe to run concurrently
    1  findings -- at least one group is not safe
    2  usage
    3  NOT MEASURED -- nothing recognisable to judge

Usage:
    python3 parallel_safety.py PLAN_JSON [--group T-1,T-2 --group T-3,T-4]

With no --group, every task in the plan is checked pairwise and the tool
reports the largest safe concurrent groups it can find.
"""
import json
import os
import sys

# Objects whose modification is felt by tasks that never name them. Matched
# case-insensitively against a substring of the object's name, because a
# plan writes names and not types -- this is a heuristic that produces a
# finding to be argued with, never a silent pass.
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
    """The plan's tasks, however the project spelled the container.

    Returns [] when nothing recognisable is there -- the caller turns that
    into NOT MEASURED rather than into a pass.
    """
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
    """id -> every task it depends on, directly or through a chain.

    Direct edges are not enough, and the gap is not theoretical: given
    T-1 <- T-2 <- T-3, nothing connects T-1 and T-3 directly, so a
    pairwise check on direct edges alone happily runs them together --
    starting T-3 before T-2 has even begun. The order the platform imposes
    is transitive, so the check has to be.

    A cycle is a broken plan rather than a safe one, so it is recorded
    (see `dependency_cycles`) instead of being followed forever.

    A fixed point rather than a recursive walk, and that is not a style
    choice: the recursive version cut each cycle short and then *cached*
    the truncated answer, so in T-1 <-> T-2 it reported that T-1 depends on
    itself and T-2 did not. Relaxing until nothing changes has no such
    order dependence -- sets only grow and are bounded by the task count,
    so it terminates, and every member of a cycle ends up containing
    itself.
    """
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

    `closure` is the transitive dependency map over the WHOLE plan. Without
    it this falls back to direct edges only, which is weaker: a pair can
    look independent while a chain connects them through a task neither one
    mentions. Callers that hold the plan should always pass it.
    """
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
    # Deduplicated because a destructive task in a group of four reports the
    # same fact once per pair, and a list that repeats itself gets skimmed.
    seen, unique = set(), []
    for f in findings:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def safe_groups(tasks):
    """Greedy partition into groups that are internally safe to run together.

    Greedy on purpose: the goal is a defensible answer a person can read,
    not the theoretical maximum. A bigger group found by a cleverer search
    would still need the same human sign-off, and it would be harder to
    argue with.
    """
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
        # Not a concurrency finding: a plan whose dependencies loop cannot
        # be executed in any order at all, concurrent or otherwise.
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
    # Said explicitly because the printed order looks like a schedule and is
    # not one. This answers "who may run together", never "who runs first" --
    # the plan's dependency order still governs that, and a group whose
    # predecessors have not closed is not ready no matter how safe it is.
    print("note: these groups say who may run TOGETHER, not in what order. "
          "Sequencing is still the plan's dependency order.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
