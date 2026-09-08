"""A `task` that partitions, and the moment its evidence becomes attributable.

Two frictions measured in P2-PASADA-9 -- a v2 `task` with `tasks{}`, two
interfaces, one prompt. Neither is a gate defect: the hook already evaluates
atomicity per `tasks{}` entry, already rejects a partitioned `micro`, and
already files each write against whatever the active task file names at that
instant. Both are `appian-build` describing the file less completely than the
schema does, so the builder improvises and pays for the improvisation:

  1. `tasks{}` appears in `SKILL.md` only as `"tasks": null`. A builder opening
     a partitioned scope has no shape to copy, and went to the normative design
     document to find `{"O1-A": [...]}`. A skill you cannot build a v2 `task`
     from is a skill that sends its reader somewhere else.
  2. The two SAIL sources of P2-PASADA-9 were written before the scope was
     opened, so `evidence-writes.jsonl` filed them under P2-PASADA-8 -- the
     previous scope, already closed. Correct behaviour from the log, and an
     ordering the Core Process never stated: it had no numbered step that opens
     the scope at all.

So this file has the two halves the sibling contract tests use. The behavioural
half pins what the gate does with `tasks{}`, because a document is only worth
testing against a mechanism that exists. The documentary half reads
`appian-build` and fails when either rule stops being stated.
"""
import os, re, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import _scope_schema_errors, scope_gate, state_gate
from test_grant import GRANT
from test_harness_hooks import cfg, make_plugin_root, write_skill_record
from test_micro_lane_contract import BUILD, blocks
from test_scope_schema import v2_scope
from test_state_gate import write_scope

# Four DISTINCT names, deliberately: the budget counts objects, not entries,
# and a name paired with its own UUID is one object (`_canonical_object_count`).
# Pairs would count two and never reach the budget of three, so the test would
# pass whatever the gate did.
NAMES = ["GDE_INT_Uno", "GDE_INT_Dos", "GDE_INT_Tres", "GDE_INT_Cuatro"]
PARTITION = {"T-A": NAMES[:2], "T-B": NAMES[2:]}

NEGATION = re.compile(r"\b(never|not|no|nothing|without|do not|don't)\b", re.I)


def partition_grant(objects):
    """The measured grant: it covers the objects and creates nothing.

    `creates` is emptied on purpose. § 5.6 demands a design verdict from a
    `task` whose grant creates something, and this lane is the merely-modifying
    one -- leaving the fixture's creation in would stop the write on a reason
    that has nothing to do with partitioning.
    """
    grant = dict(GRANT)
    grant["objects"] = list(objects)
    grant["creates"] = []
    return grant


def task_cfg(root, **over):
    """A signed v2 `task`, partitioned unless the caller says otherwise."""
    over.setdefault("kind", "task")
    over.setdefault("intent", None)
    over.setdefault("allowedObjects", list(NAMES))
    over.setdefault("tasks", {k: list(v) for k, v in PARTITION.items()})
    over.setdefault("grant", partition_grant(NAMES))
    scope = v2_scope(**over)
    make_plugin_root(root)
    write_skill_record(root, scope["id"])
    c = cfg(root, activeTask=scope)
    c = write_scope(c, scope)
    state_gate({"tool_name": "Write",
                "tool_input": {"file_path": c["activeTaskFile"]}}, c)
    return c


def update(c, name):
    return scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                       "session_id": "s-part", "tool_use_id": "tu-1",
                       "tool_input": {"name": name,
                                      "expression": 'a!textField(label: "Tarifa")'}}, c)


class TestAtomicityIsMeasuredPerEntry(unittest.TestCase):
    def test_a_partitioned_union_over_the_budget_still_writes(self):
        # Four objects, budget three. Partitioned into two entries of two, the
        # scope is atomic where its union is not -- which is the whole reason
        # `tasks{}` exists.
        with tempfile.TemporaryDirectory() as root:
            c = task_cfg(root)
            self.assertEqual(c["maxAllowedObjects"], 3)
            out = update(c, NAMES[0])
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))

    def test_the_same_union_unpartitioned_is_not_atomic(self):
        # The control. Same four objects, same grant, `tasks` null: now the
        # budget applies to the union and the gate asks. Without this the test
        # above would pass on a gate that had stopped checking atomicity.
        with tempfile.TemporaryDirectory() as root:
            c = task_cfg(root, tasks=None, intent="cuatro objetos de una vez")
            out = update(c, NAMES[0])
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("not atomic", out["permissionDecisionReason"])

    def test_one_oversized_entry_asks_and_names_that_entry(self):
        # Partitioning is not a way past the budget: an entry that is itself
        # too big is reported, by id, so the remedy lands on the right subtask.
        with tempfile.TemporaryDirectory() as root:
            c = task_cfg(root, tasks={"T-A": list(NAMES), "T-B": ["GDE_INT_Cinco"]},
                         allowedObjects=NAMES + ["GDE_INT_Cinco"],
                         grant=partition_grant(NAMES + ["GDE_INT_Cinco"]))
            out = update(c, NAMES[0])
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("not atomic", out["permissionDecisionReason"])
            self.assertIn("T-A", out["permissionDecisionReason"])

    def test_an_object_only_inside_an_entry_is_out_of_scope(self):
        # `allowedObjects` is the union and the gate matches against it alone,
        # so an entry is documentation until its objects reach the union.
        with tempfile.TemporaryDirectory() as root:
            c = task_cfg(root, allowedObjects=NAMES[:2])
            out = update(c, NAMES[2])
            self.assertEqual(out["permissionDecision"], "ask")


class TestAPartitionedScopeIsATask(unittest.TestCase):
    def test_a_micro_carrying_entries_fails_the_schema(self):
        errors = _scope_schema_errors(v2_scope(kind="micro", tasks=PARTITION))
        self.assertTrue([e for e in errors if "micro" in e],
                        "a partitioned micro passed the schema: %r" % errors)

    def test_a_partitioned_task_passes_it(self):
        self.assertEqual(
            _scope_schema_errors(v2_scope(kind="task", intent=None,
                                          tasks=PARTITION,
                                          allowedObjects=list(NAMES))), [])


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestTheBuildSkillCanBeBuiltFrom(unittest.TestCase):
    """A v2 `task` is constructible from `appian-build` alone, or it is not."""

    def test_both_shapes_of_the_field_are_shown(self):
        body = text(BUILD)
        self.assertIn('"tasks": null', body,
                      "appian-build never shows the unpartitioned shape")
        self.assertIn('"tasks": {', body,
                      "appian-build never shows a populated `tasks{}`, so the "
                      "shape has to be fetched from the design document -- which "
                      "is the defect measured in P2-PASADA-9")
        self.assertIn("<taskId>", body,
                      "the populated example does not show that the keys are "
                      "subtask ids")

    def test_the_union_rule_is_stated_where_the_field_is(self):
        named = [b for b in blocks(text(BUILD))
                 if "union" in b.lower() and "allowedObjects" in b]
        self.assertTrue(named,
                        "nothing in appian-build says `allowedObjects` is the "
                        "union of the entries, so a builder may reasonably read "
                        "the two lists as alternatives")

    def test_atomicity_is_documented_per_entry(self):
        named = [b for b in blocks(text(BUILD))
                 if "tasks{}" in b and "entry" in b.lower()
                 and ("atomic" in b.lower() or "budget" in b.lower())]
        self.assertTrue(named,
                        "appian-build never says the budget is applied per "
                        "`tasks{}` entry rather than to the union, which is the "
                        "one thing partitioning changes at the gate")

    def test_partitioning_is_not_announced_as_a_third_kind(self):
        named = [b for b in blocks(text(BUILD))
                 if "tasks{}" in b and '"task"' in b and NEGATION.search(b)]
        self.assertTrue(named,
                        "appian-build never says `kind` stays `\"task\"` when "
                        "the scope partitions, leaving `tasks{}` looking like a "
                        "size of its own")

    def test_the_micro_exclusion_is_stated(self):
        named = [b for b in blocks(text(BUILD))
                 if "tasks" in b and "micro" in b and "null" in b]
        self.assertTrue(named,
                        "appian-build never says `tasks` is null in a micro, so "
                        "the schema rejection arrives with no warning")


class TestTheScopeIsOpenedBeforeTheEvidenceItAttributes(unittest.TestCase):
    def test_the_core_process_has_a_step_that_opens_the_scope(self):
        step = [b for b in blocks(text(BUILD)) if b.startswith("3a. ")]
        self.assertTrue(step,
                        "the Core Process has no step 3a: before P2-PASADA-9 it "
                        "had no numbered step that opened the scope at all, and "
                        "the ordering lived in a section further down")
        self.assertIn("`Write`", step[0],
                      "step 3a moves the scope but names no observable tool")
        self.assertIn("activeTaskFile", step[0],
                      "step 3a never names the file it opens")

    def test_that_step_comes_before_the_first_evidence_file(self):
        bs = blocks(text(BUILD))
        opens = [i for i, b in enumerate(bs) if b.startswith("3a. ")]
        record = [i for i, b in enumerate(bs) if "appian-skill-loaded.json" in b]
        self.assertTrue(opens and record)
        self.assertLess(opens[0], record[0],
                        "the load record is asked for before the scope is "
                        "opened, which is exactly the order that filed "
                        "P2-PASADA-9's evidence under P2-PASADA-8")

    def test_the_rule_is_stated_and_not_left_to_the_numbering(self):
        named = [b for b in blocks(text(BUILD))
                 if "<evidenceDir>/<task-id>/" in b and NEGATION.search(b)]
        self.assertTrue(named,
                        "no block refuses evidence written before the opening, "
                        "so a reader who skims the numbering learns nothing "
                        "about why the order matters")

    def test_the_whole_sequence_is_stated_in_one_place(self):
        # The friction was never a missing sentence, it was a missing sequence:
        # the order had to be assembled from four sections. One block has to
        # carry it end to end, in order.
        wanted = ("preflight", "scope", "evidence", "grant", "write", "close")
        for block in blocks(text(BUILD)):
            low = block.lower()
            at = [low.find(token) for token in wanted]
            if all(i >= 0 for i in at) and at == sorted(at):
                return
        self.fail("no single block of appian-build states the build's order "
                  "from preflight through the close, so it stays something the "
                  "reader has to assemble")


if __name__ == "__main__":
    unittest.main()
