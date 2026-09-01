import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from parallel_safety import (check_pair, check_group, safe_groups, tasks_of, main,
                             transitive_dependencies, dependency_cycles)


def task(tid, objects=(), depends=(), **over):
    t = {"id": tid, "allowedObjects": list(objects)}
    if depends:
        t["dependsOn"] = list(depends)
    t.update(over)
    return t


class TestSharedObjects(unittest.TestCase):
    """The rule a worktree cannot enforce: a worktree isolates files, and
    two builders in two worktrees still write to the same Appian."""

    def test_disjoint_tasks_may_run_together(self):
        self.assertEqual(check_pair(task("T-1", ["RGM_Candidate"]),
                                    task("T-2", ["RGM_Interview"])), [])

    def test_a_shared_object_is_refused(self):
        f = check_pair(task("T-1", ["RGM_Candidate"]), task("T-2", ["RGM_Candidate"]))
        self.assertTrue(f)
        self.assertIn("RGM_Candidate".lower(), " ".join(f).lower())

    def test_the_comparison_ignores_case_and_padding(self):
        f = check_pair(task("T-1", ["  RGM_Candidate "]), task("T-2", ["rgm_candidate"]))
        self.assertTrue(f)

    def test_a_string_instead_of_a_list_is_still_read(self):
        # Plans are written by people and by other agents; one object often
        # arrives as a bare string.
        f = check_pair(task("T-1", []), task("T-2", []))
        a = {"id": "T-1", "allowedObjects": "RGM_Candidate"}
        b = {"id": "T-2", "allowedObjects": "RGM_Candidate"}
        self.assertEqual(f, [])
        self.assertTrue(check_pair(a, b))


class TestDependencies(unittest.TestCase):
    """`in parallel` does not suspend the order the platform imposes."""

    def test_a_dependency_in_either_direction_is_refused(self):
        self.assertTrue(check_pair(task("T-2", ["B"], depends=["T-1"]), task("T-1", ["A"])))
        self.assertTrue(check_pair(task("T-1", ["A"]), task("T-2", ["B"], depends=["T-1"])))

    def test_dependencies_is_accepted_as_a_spelling(self):
        a = {"id": "T-2", "allowedObjects": ["B"], "dependencies": ["T-1"]}
        self.assertTrue(check_pair(a, task("T-1", ["A"])))


class TestDestructiveTasksRunAlone(unittest.TestCase):
    """A deletion's blast radius is not bounded by allowedObjects -- it can
    break objects nobody listed, which is exactly what makes it unsafe to
    run beside work that never mentioned them."""

    def test_a_destructive_task_is_refused_a_partner(self):
        f = check_pair(task("T-1", ["A"], title="Delete the obsolete record type"),
                       task("T-2", ["B"]))
        self.assertTrue(any("destructive" in x for x in f))

    def test_it_is_detected_in_spanish_too(self):
        f = check_pair(task("T-1", ["A"], description="Eliminar el record type antiguo"),
                       task("T-2", ["B"]))
        self.assertTrue(any("destructive" in x for x in f))

    def test_an_ordinary_task_is_not_flagged_as_destructive(self):
        f = check_pair(task("T-1", ["A"], title="Create the candidate record type"),
                       task("T-2", ["B"]))
        self.assertEqual(f, [])


class TestObjectsEverythingDependsOn(unittest.TestCase):
    def test_touching_a_group_is_flagged(self):
        f = check_pair(task("T-1", ["RGM_Reviewers Group"]), task("T-2", ["B"]))
        self.assertTrue(any("depend on" in x for x in f))

    def test_touching_the_application_is_flagged(self):
        f = check_pair(task("T-1", ["RGM_Application"]), task("T-2", ["B"]))
        self.assertTrue(any("depend on" in x for x in f))


class TestGrouping(unittest.TestCase):
    def test_findings_are_not_repeated_once_per_pair(self):
        # A destructive task in a group of three states the fact once: a
        # list that repeats itself gets skimmed.
        g = [task("T-1", ["A"], title="delete something"), task("T-2", ["B"]),
             task("T-3", ["C"])]
        f = check_group(g)
        self.assertEqual(len(f), len(set(f)))

    def test_independent_tasks_land_in_one_group(self):
        groups = safe_groups([task("T-1", ["A"]), task("T-2", ["B"]), task("T-3", ["C"])])
        self.assertEqual(len(groups), 1)

    def test_conflicting_tasks_are_split(self):
        groups = safe_groups([task("T-1", ["A"]), task("T-2", ["A"])])
        self.assertEqual(len(groups), 2)

    def test_a_chain_of_dependencies_is_fully_serialised(self):
        groups = safe_groups([task("T-1", ["A"]),
                              task("T-2", ["B"], depends=["T-1"]),
                              task("T-3", ["C"], depends=["T-2"])])
        self.assertEqual([len(g) for g in groups], [1, 1, 1])


class TestTasksOf(unittest.TestCase):
    def test_a_bare_list_is_accepted(self):
        self.assertEqual(len(tasks_of([task("T-1")])), 1)

    def test_a_tasks_key_is_accepted(self):
        self.assertEqual(len(tasks_of({"tasks": [task("T-1")]})), 1)

    def test_entries_without_an_id_are_not_tasks(self):
        self.assertEqual(tasks_of({"tasks": [{"allowedObjects": ["A"]}]}), [])


class TestExitCodes(unittest.TestCase):
    """0 clean, 1 findings, 2 usage, 3 NOT MEASURED -- and 3 is the one worth
    pinning. A plan this cannot read is a plan nobody checked."""

    def _run(self, plan, *extra):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "plan.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump(plan, f)
            return main(["parallel_safety.py", p] + list(extra))

    def test_unreadable_plan_shape_is_not_measured_not_ok(self):
        self.assertEqual(self._run({"nothing": "here"}), 3)

    def test_an_empty_task_list_is_not_measured(self):
        self.assertEqual(self._run({"tasks": []}), 3)

    def test_a_safe_requested_group_exits_zero(self):
        self.assertEqual(self._run({"tasks": [task("T-1", ["A"]), task("T-2", ["B"])]},
                                   "--group", "T-1,T-2"), 0)

    def test_an_unsafe_requested_group_exits_one(self):
        self.assertEqual(self._run({"tasks": [task("T-1", ["A"]), task("T-2", ["A"])]},
                                   "--group", "T-1,T-2"), 1)

    def test_a_group_naming_an_unknown_task_exits_one(self):
        self.assertEqual(self._run({"tasks": [task("T-1", ["A"])]},
                                   "--group", "T-1,T-9"), 1)

    def test_no_arguments_is_usage(self):
        self.assertEqual(main(["parallel_safety.py"]), 2)

    def test_a_missing_plan_file_is_usage(self):
        self.assertEqual(main(["parallel_safety.py", "no-such-plan.json"]), 2)



class TestTransitiveDependencies(unittest.TestCase):
    """Direct edges are not enough. Given T-1 <- T-2 <- T-3, nothing joins
    T-1 and T-3 directly, so a pairwise check on direct edges alone runs them
    together and starts T-3 before T-2 has begun."""

    CHAIN = [task("T-1", ["A"]),
             task("T-2", ["B"], depends=["T-1"]),
             task("T-3", ["C"], depends=["T-2"])]

    def test_the_closure_reaches_through_the_chain(self):
        closure = transitive_dependencies(self.CHAIN)
        self.assertEqual(closure["t-3"], {"t-2", "t-1"})

    def test_the_ends_of_a_chain_are_refused_as_a_pair(self):
        closure = transitive_dependencies(self.CHAIN)
        f = check_pair(self.CHAIN[0], self.CHAIN[2], closure)
        self.assertTrue(f)
        self.assertIn("through a chain", " ".join(f))

    def test_without_the_closure_the_check_is_weaker_and_says_nothing(self):
        # Documents the fallback honestly rather than pretending it is safe.
        self.assertEqual(check_pair(self.CHAIN[0], self.CHAIN[2]), [])

    def test_a_cycle_is_reported_rather_than_followed_forever(self):
        cyclic = [task("T-1", ["A"], depends=["T-2"]), task("T-2", ["B"], depends=["T-1"])]
        self.assertEqual(dependency_cycles(cyclic), ["t-1", "t-2"])

    def test_a_cyclic_plan_exits_one(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "plan.json")
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"tasks": [task("T-1", ["A"], depends=["T-2"]),
                                     task("T-2", ["B"], depends=["T-1"])]}, f)
            self.assertEqual(main(["parallel_safety.py", p]), 1)

if __name__ == "__main__":
    unittest.main()
