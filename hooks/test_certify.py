"""Where the judge's verdict meets the close (norm §§ 5.4, 9.1, 9.3, 11.1).

Two questions, and they are separate: WHETHER this scope owes a certify at
all -- zero judges is a result, not an omission -- and, when it does, what
its cells do to the close. The matrix's own shape is checked in
`scripts/test_verdict_matrix.py`; this file is about the effect.
"""
import json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "scripts"))
from validate_verdict import GATES, NATURE_BY_GATE, NATURE_IMPORTED, \
    NATURE_JUDGED_ON_EVIDENCE
from harness_hooks import (certify_is_owed, certify_report, closure_gate,
                           latest_verdict, log_write, observe_reads,
                           risk_errors, scope_gate, state_gate)
from test_floor import interface_floor_batch
from test_grant import GRANT, signed_cfg
from test_state_gate import read_scope, write_scope

REF = "06-security.md#record-level-security"


def credited_rows(config, instance_id="inst-1"):
    """The ledger rows a cell may cite: this instance's, and not the ones
    that only prove a call returned green."""
    path = os.path.join(config["evidenceDir"], "checks.jsonl")
    rows = []
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("instanceId") == instance_id \
                        and row.get("guaranteeClass") != "green-signal-only" \
                        and row.get("toolUseId"):
                    rows.append(row)
    return rows


def certify_cells(objects, tool_use_id, **per_gate):
    """A full matrix over `objects`, every cell PASS unless overridden.

    `per_gate` takes `gate3={...}` and merges it into that gate's cell, so a
    test says only what it is changing.
    """
    cells = []
    for obj in objects:
        for gate in GATES:
            cell = {"object": obj, "gate": gate,
                    "nature": NATURE_BY_GATE[gate], "verdict": "PASS"}
            if NATURE_BY_GATE[gate] == NATURE_IMPORTED:
                cell["toolUseId"] = tool_use_id
                cell["result"] = "ok"
            elif NATURE_BY_GATE[gate] == NATURE_JUDGED_ON_EVIDENCE:
                cell["citesRow"] = tool_use_id
            over = per_gate.get("gate%d" % gate)
            if over:
                cell.update(over)
            cells.append(cell)
    return cells


def fail_cell(gate, **over):
    """One failing cell, with everything a non-PASS owes."""
    cell = {"verdict": "FAIL", "evidence": "what was looked at",
            "impact": "what it costs", "remedy": "what to do"}
    if NATURE_BY_GATE[gate] != NATURE_IMPORTED:
        cell["reference"] = REF
    cell.update(over)
    return cell


def write_verdict(config, scope, phase, version=1, copy=True, **over):
    """One verdict on disk, the way § 11.1 says they land: the version the
    gate reads, plus the unsuffixed copy for readers that expect it.

    `version=None` writes ONLY the copy -- the shape a judge that overwrote
    a fixed name would leave, which the gate must refuse.
    """
    v = {
        "task": scope["id"],
        "instanceId": scope.get("instanceId"),
        "phase": phase,
        "verdict": "PASS",
        "coversThroughWriteSeq": 99,
        "referencesApplied": [REF],
        "findings": [],
    }
    v.update(over)
    d = os.path.join(config["evidenceDir"], scope["id"])
    os.makedirs(d, exist_ok=True)
    names = []
    if version is not None:
        names.append("practices-%s.%03d.json" % (phase, version))
    if copy or version is None:
        names.append("practices-%s.json" % phase)
    for name in names:
        with open(os.path.join(d, name), "w", encoding="utf-8") as f:
            json.dump(v, f)
    return os.path.join(d, names[0])


def write_certify(config, scope, objects=None, version=1, copy=True, **over):
    """A certify verdict for this scope, citing rows the hook really saw."""
    rows = credited_rows(config, scope.get("instanceId"))
    tool_use_id = rows[0]["toolUseId"] if rows else "tu-none"
    objects = objects or list(scope.get("allowedObjects") or ["obj"])[:1]
    over.setdefault("objects", objects)
    over.setdefault("matrix", certify_cells(objects, tool_use_id))
    return write_verdict(config, scope, "certify", version=version, copy=copy,
                         **over)


class Cycle:
    """One micro that writes an interface, pays its floor and asks to close."""

    def build(self, root, **scope_over):
        c = signed_cfg(root, **scope_over)
        self.write(c, "mcp__appian-dev__updateInterface", "tu-w1",
                   uuid="_uuid-lista", expression="a!textField()")
        return self.verify(c)

    def write(self, c, tool, tool_use_id, **tool_input):
        scope_gate({"tool_name": tool, "session_id": "s-c",
                    "tool_use_id": tool_use_id, "tool_input": tool_input}, c)
        # A response with no uuid classifies `ambiguous`, and an ambiguous
        # write is not a confirmed one: creates answer with the uuid they
        # minted, so the fixture does too.
        log_write({"tool_name": tool, "tool_use_id": tool_use_id,
                   "tool_input": tool_input,
                   "tool_response": json.dumps(
                       {"uuid": tool_input.get("uuid") or "_uuid-nuevo",
                        "versionId": 1})}, c)

    def verify(self, c):
        c = dict(c, activeTask=read_scope(c))
        observe_reads({"tool_calls": interface_floor_batch("_uuid-lista")}, c)
        return dict(c, activeTask=read_scope(c))

    def ask_to_close(self, c):
        scope = read_scope(c)
        scope["request"] = "close"
        c = write_scope(c, scope)
        state_gate({"tool_name": "Write",
                    "tool_input": {"file_path": c["activeTaskFile"]}}, c)
        return dict(c, activeTask=read_scope(c))

    def stop(self, c, repeat=False):
        return closure_gate({"stop_hook_active": True} if repeat else {}, c)


class TestZeroJudgesIsAResult(unittest.TestCase):
    """§ 5.4: `micro` means one object and one intention, not zero judges --
    and not a judge either, when the write cannot change what is shown or
    who sees it. Buying one "just in case" is the waste of § 1.3."""

    def test_a_scope_that_wrote_nothing_owes_no_certify(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root)
            self.assertFalse(certify_is_owed(c, read_scope(c)))

    def test_a_description_only_write_owes_no_certify(self):
        # `behavioural: false` (§ 7.6): description and documentation cannot
        # alter the screen, so demanding a judge here checks in a way that
        # can never fail.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = signed_cfg(root)
            cycle.write(c, "mcp__appian-dev__updateInterface", "tu-d",
                        uuid="_uuid-lista", description="nueva descripción")
            self.assertFalse(certify_is_owed(dict(c, activeTask=read_scope(c)),
                                             read_scope(c)))

    def test_a_constant_owes_no_certify(self):
        # A type with no expression of its own: four constants are four
        # clicks in Designer, and paying a judge from the second is ceremony.
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, allowedObjects=["GDE_CON_Uno"])
            Cycle().write(c, "mcp__appian-dev__createConstant", "tu-k",
                          name="GDE_CON_Uno", value="1")
            self.assertFalse(certify_is_owed(dict(c, activeTask=read_scope(c)),
                                             read_scope(c)))

    def test_touching_an_expression_buys_exactly_one_certify(self):
        # The measured consequence of 0.7 having no literal scanner yet: a
        # micro that touches an expression pays one certify, and that is the
        # expensive side, which is where it should fail.
        with tempfile.TemporaryDirectory() as root:
            c = Cycle().build(root)
            self.assertTrue(certify_is_owed(c, read_scope(c)))

    def test_a_delete_only_task_owes_no_certify(self):
        with tempfile.TemporaryDirectory() as root:
            grant = dict(GRANT, deletions={"GDE_CON_Viejo": "confirmed"},
                         objects=["GDE_CON_Viejo"])
            c = signed_cfg(root, kind="task", intent=None, grant=grant,
                           allowedObjects=["GDE_CON_Viejo"])
            Cycle().write(c, "mcp__appian-dev__deleteConstant", "tu-x",
                          uuid="GDE_CON_Viejo")
            self.assertFalse(certify_is_owed(dict(c, activeTask=read_scope(c)),
                                             read_scope(c)))

    def test_an_unclassified_action_fails_to_the_expensive_side(self):
        with tempfile.TemporaryDirectory() as root:
            c = signed_cfg(root, kind="task", intent=None)
            Cycle().write(c, "mcp__appian-dev__createRecordType", "tu-r",
                          name="GDE_INT_Lista")
            self.assertTrue(certify_is_owed(dict(c, activeTask=read_scope(c)),
                                            read_scope(c)))


class TestAMissingCertifyBlocksTheClose(unittest.TestCase):
    def test_the_close_names_the_judge_it_still_owes(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.ask_to_close(cycle.build(root))
            out = cycle.stop(c)
            self.assertEqual(out["decision"], "block")
            self.assertIn("no certify verdict", out["reason"])

    def test_a_dispatch_that_never_wrote_is_told_apart_from_no_dispatch(self):
        # § 9.1: "the judge never started" and "the judge said FAIL" must not
        # reach the same terminal state.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            observe_reads({"tool_calls": [
                {"tool_name": "Task", "tool_use_id": "tu-agent",
                 "tool_input": {"subagent_type": "appian-practices-auditor",
                                "prompt": "run the certify phase"}}]}, c)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertIn("dispatched and never wrote its verdict", out["reason"])

    def test_the_dispatch_is_recorded_with_its_phase(self):
        with tempfile.TemporaryDirectory() as root:
            c = Cycle().build(root)
            observe_reads({"tool_calls": [
                {"tool_name": "Task", "tool_use_id": "tu-agent",
                 "tool_input": {"subagent_type": "appian-practices-auditor",
                                "prompt": "the certify phase for this scope"}}]}, c)
            rows = [json.loads(l) for l in open(
                os.path.join(c["evidenceDir"], "gate-decisions.jsonl"),
                encoding="utf-8") if l.strip()]
            dispatch = [r for r in rows if r.get("event") == "judge-dispatched"]
            self.assertEqual(len(dispatch), 1)
            self.assertEqual(dispatch[0]["phase"], "certify")

    def test_a_clean_certify_lets_the_scope_close(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"])
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "approve", out)
            self.assertEqual(read_scope(c)["status"], "closed")


class TestTheGateReadsTheHighestVersion(unittest.TestCase):
    def test_the_versioned_verdict_wins_over_the_unsuffixed_copy(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            scope = read_scope(c)
            write_certify(c, scope, objects=["_uuid-lista"])
            write_certify(c, scope, objects=["_uuid-lista"], version=2)
            self.assertTrue(latest_verdict(c, scope["id"], "certify")
                            .endswith("practices-certify.002.json"))

    def test_the_copy_alone_certifies_nothing(self):
        # § 9.4: with a fixed name the second emission overwrites the first,
        # so by the third there is nothing on disk to compare against and
        # the cap silently stops existing. The gate refuses to close on a
        # verdict that left it no corpus.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          version=None)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("unsuffixed copy", out["reason"])

    def test_the_copy_still_ships_beside_the_version(self):
        # Not forbidden -- § 11.1 keeps it for readers that expect it.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            scope = read_scope(c)
            write_certify(c, scope, objects=["_uuid-lista"])
            scope_dir = os.path.join(c["evidenceDir"], scope["id"])
            self.assertIn("practices-certify.json", os.listdir(scope_dir))
            self.assertTrue(latest_verdict(c, scope["id"], "certify")
                            .endswith("practices-certify.001.json"))

    def test_a_stale_copy_cannot_certify_what_the_judge_moved_on_from(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            scope = read_scope(c)
            # The copy passes; the current version does not.
            write_certify(c, scope, objects=["_uuid-lista"])
            write_certify(c, scope, objects=["_uuid-lista"], version=1,
                          verdict="FAIL",
                          matrix=certify_cells(
                              ["_uuid-lista"],
                              credited_rows(c)[0]["toolUseId"],
                              gate3=fail_cell(3)))
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("CARDINAL", out["reason"])


class TestTheSevenGatesDoNotBlockAlike(unittest.TestCase):
    """§ 9.3, at the only place where it means anything: the close."""

    def _close_with(self, root, gate, repeat=False):
        cycle = Cycle()
        c = cycle.build(root)
        scope = read_scope(c)
        write_certify(c, scope, objects=["_uuid-lista"], verdict="FAIL",
                      matrix=certify_cells(["_uuid-lista"],
                                           credited_rows(c)[0]["toolUseId"],
                                           **{"gate%d" % gate: fail_cell(gate)}))
        c = cycle.ask_to_close(c)
        out = cycle.stop(c)
        if repeat:
            out = cycle.stop(c, repeat=False)
        return c, out

    def test_a_cardinal_fail_blocks_without_cycles(self):
        with tempfile.TemporaryDirectory() as root:
            c, out = self._close_with(root, 1)
            self.assertEqual(out["decision"], "block")
            self.assertIn("CARDINAL", out["reason"])
            self.assertEqual(read_scope(c)["status"], "closing")

    def test_a_cardinal_fail_is_not_waived_by_a_second_stop(self):
        # "Blocks the close. No exception and no cycles" -- the forced Stop
        # still closes (a Stop hook has only approve and block), but with the
        # debt recorded, never as a clean close.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="FAIL",
                          matrix=certify_cells(["_uuid-lista"],
                                               credited_rows(c)[0]["toolUseId"],
                                               gate3=fail_cell(3)))
            c = cycle.ask_to_close(c)
            cycle.stop(c)
            out = cycle.stop(c, repeat=True)
            self.assertEqual(out["decision"], "approve")
            self.assertEqual(read_scope(c)["status"], "closed-with-debt")

    def test_a_recommended_fail_blocks_once(self):
        with tempfile.TemporaryDirectory() as root:
            c, out = self._close_with(root, 4)
            self.assertEqual(out["decision"], "block")
            self.assertIn("RECOMMENDED", out["reason"])

    def test_and_does_not_block_twice(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="FAIL",
                          matrix=certify_cells(["_uuid-lista"],
                                               credited_rows(c)[0]["toolUseId"],
                                               gate7=fail_cell(7)))
            c = cycle.ask_to_close(c)
            self.assertEqual(cycle.stop(c)["decision"], "block")
            out = cycle.stop(c)
            self.assertEqual(out["decision"], "approve", out)
            self.assertEqual(read_scope(c)["status"], "closed-with-debt")

    def test_a_contextual_fail_never_blocks(self):
        # Maintainability: "this logic should live in an expression rule" is
        # a judgement, and it used to cost three remediation cycles.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="FAIL",
                          matrix=certify_cells(["_uuid-lista"],
                                               credited_rows(c)[0]["toolUseId"],
                                               gate6=fail_cell(6)))
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "approve", out)
            self.assertEqual(read_scope(c)["status"], "closed")

    def test_but_it_is_recorded_with_its_owner(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="FAIL",
                          matrix=certify_cells(["_uuid-lista"],
                                               credited_rows(c)[0]["toolUseId"],
                                               gate5=fail_cell(5)))
            cycle.stop(cycle.ask_to_close(c))
            debt = [json.loads(l) for l in open(
                os.path.join(c["evidenceDir"], "deferred-debt.jsonl"),
                encoding="utf-8") if l.strip()]
            contextual = [d for d in debt if d.get("class") == "CONTEXTUAL"]
            self.assertEqual(len(contextual), 1)
            self.assertTrue(contextual[0]["owner"])
            self.assertEqual(contextual[0]["gate"], 5)

    def test_a_never_graded_down_finding_blocks_inside_a_contextual_gate(self):
        # The three the doctrine never grades down are CARDINAL wherever
        # they land -- including gate 6, which otherwise does not block.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="FAIL",
                          matrix=certify_cells(
                              ["_uuid-lista"], credited_rows(c)[0]["toolUseId"],
                              gate6=fail_cell(6,
                                              neverGradedDown="non-idempotent-write")))
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("CARDINAL", out["reason"])


class TestAVerdictThatExpiredDoesNotCertify(unittest.TestCase):
    def test_a_write_after_the_verdict_expires_it(self):
        # § 7.6, whose full consumer is exactly this gate.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          coversThroughWriteSeq=0)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("certifies an artifact that has since changed",
                          out["reason"])

    def test_a_verdict_of_another_instance_never_covers_this_one(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          instanceId="inst-OTHER")
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")


class TestAPendingJudgementCloses(unittest.TestCase):
    def test_a_requires_human_certify_closes_pending_human(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            row = credited_rows(c)[0]["toolUseId"]
            cells = certify_cells(["_uuid-lista"], row)
            for cell in cells:
                if cell["gate"] == 4:
                    cell.update({"verdict": "NOT_MEASURED",
                                 "evidence": "the screen needs a person",
                                 "impact": "unknown", "remedy": "look at it",
                                 "reference": REF})
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="NOT_MEASURED",
                          notMeasuredClass="REQUIRES_HUMAN",
                          owner="the scope's owner",
                          closingCondition="somebody opens the screen",
                          deferredCriterion="visual-judgement-on-rendered-screen",
                          matrix=cells)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "approve", out)
            self.assertEqual(read_scope(c)["status"], "closed-pending-human")

    def test_a_blocking_not_measured_is_a_process_failure(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            row = credited_rows(c)[0]["toolUseId"]
            cells = certify_cells(["_uuid-lista"], row)
            for cell in cells:
                if cell["gate"] == 4:
                    cell.update({"verdict": "NOT_MEASURED", "evidence": "e",
                                 "impact": "i", "remedy": "r", "reference": REF})
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="NOT_MEASURED", notMeasuredClass="BLOCKING",
                          matrix=cells)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("process failure", out["reason"])


class TestTheFloorIsAskedBeforeTheJudge(unittest.TestCase):
    def test_a_scope_that_skipped_its_floor_is_not_saved_by_a_verdict(self):
        # The floor is free and the judge is not. A scope that never paid
        # its legs is not made closeable by buying an opinion.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = signed_cfg(root)
            cycle.write(c, "mcp__appian-dev__updateInterface", "tu-w1",
                        uuid="_uuid-lista", expression="a!textField()")
            c = dict(c, activeTask=read_scope(c))
            write_certify(c, read_scope(c), objects=["_uuid-lista"])
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")

    def test_the_report_separates_what_blocks_from_what_is_debt(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            row = credited_rows(c)[0]["toolUseId"]
            write_certify(c, read_scope(c), objects=["_uuid-lista"],
                          verdict="FAIL",
                          matrix=certify_cells(["_uuid-lista"], row,
                                               gate1=fail_cell(1),
                                               gate4=fail_cell(4),
                                               gate6=fail_cell(6)))
            report = certify_report(c, read_scope(c))
            self.assertEqual(len(report["blocking"]), 1)
            self.assertEqual(len(report["recommended"]), 1)
            self.assertEqual(len(report["contextual"]), 1)
            self.assertEqual(report["missing"], [])

class TestNoJudgeReceivesADump(unittest.TestCase):
    """§ 9.1 and § 12.3, held where they can be held: the contract is that a
    judge is handed paths, hashes and derived signals. The dispatch itself is
    a subagent call this harness cannot inspect from inside, so what is
    asserted is the shape of what a verdict is allowed to carry, and that
    every document defining the dispatch says so."""

    def test_a_cell_cites_a_row_by_id_and_never_by_content(self):
        # The imported cells carry a `toolUseId` and the row's `result` --
        # not the response. That is what keeps a 218 KB render out of the
        # verdict and out of whoever reads it next.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            scope = read_scope(c)
            path = write_certify(c, scope, objects=["_uuid-lista"])
            with open(path, encoding="utf-8") as f:
                verdict = json.load(f)
            for cell in verdict["matrix"]:
                if cell["nature"] == NATURE_IMPORTED:
                    self.assertIn("toolUseId", cell)
                    self.assertEqual(sorted(cell) , sorted(
                        ["object", "gate", "nature", "verdict", "toolUseId",
                         "result"]))

    def test_the_whole_verdict_stays_small(self):
        # A judge that fills its context with dumps stops fitting in one.
        # 40 KB is the norm's own ceiling for what may reach a context
        # without a summarising script in front of it (§ 12.3).
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            path = write_certify(c, read_scope(c), objects=["_uuid-lista"])
            self.assertLess(os.path.getsize(path), 40 * 1024)

    def test_every_document_that_dispatches_forbids_dumps(self):
        # The rule lives where the dispatch is written, or it lives nowhere.
        root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        for rel in (os.path.join("agents", "appian-practices-auditor.md"),
                    os.path.join("skills", "appian-review", "SKILL.md")):
            with open(os.path.join(root, rel), encoding="utf-8") as f:
                text = f.read().lower()
            self.assertIn("dump", text, rel)
            self.assertTrue("paths, hashes and derived signals" in text, rel)
            self.assertIn("builder's conclusion", text, rel)


class TestATaskEmitsItsVerdictsWithoutBeingAskedTwice(unittest.TestCase):
    """The DoD's own words: a task's verdicts are produced WITHOUT manual
    re-emission. Seven re-emissions asked for by hand were the most expensive
    defect of the session that motivated this redesign."""

    def test_one_clean_cycle_emits_one_certify_and_closes(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = signed_cfg(root, kind="task", intent=None)
            cycle.write(c, "mcp__appian-dev__updateInterface", "tu-w1",
                        uuid="_uuid-lista", expression="a!textField()")
            c = cycle.verify(c)
            write_certify(c, read_scope(c), objects=["_uuid-lista"], version=1)
            # The unsuffixed copy § 11.1 keeps for readers expecting it.
            write_certify(c, read_scope(c), objects=["_uuid-lista"])
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "approve", out)
            scope_dir = os.path.join(c["evidenceDir"], read_scope(c)["id"])
            versions = [f for f in os.listdir(scope_dir)
                        if f.startswith("practices-certify.0")]
            self.assertEqual(versions, ["practices-certify.001.json"])

    def test_a_third_emission_with_nothing_new_never_reaches_the_gate(self):
        # Enforcement, not a reported magnitude: the validator refuses it,
        # so the close reads "invalid" rather than accepting the re-run.
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            scope = read_scope(c)
            row = credited_rows(c)[0]["toolUseId"]
            same = [{"id": "f-1", "criterion": "c", "verdict": "FAIL",
                     "evidence": "e"}]
            for version in (1, 2, 3):
                write_certify(c, scope, objects=["_uuid-lista"],
                              version=version, verdict="FAIL",
                              findings=same,
                              matrix=certify_cells(["_uuid-lista"], row,
                                                   gate6=fail_cell(6)))
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("raises no finding", out["reason"])

    def test_but_a_real_cycle_is_accepted(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            scope = read_scope(c)
            row = credited_rows(c)[0]["toolUseId"]
            for version, ids in ((1, ["f-1"]), (2, ["f-1", "f-2"]),
                                 (3, ["f-3"])):
                write_certify(
                    c, scope, objects=["_uuid-lista"], version=version,
                    findings=[{"id": i, "criterion": "c", "verdict": "FAIL",
                               "evidence": "e"} for i in ids],
                    matrix=certify_cells(["_uuid-lista"], row))
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "approve", out)

class TestAHighRiskScopeBuysTheThirdInvocation(unittest.TestCase):
    """§ 5.8 row C: two judges, three when the damage class is high. Without
    this the third invocation existed in the agent and in the prose and in
    no branch of the code -- which is the dead branch P6 forbids."""

    def _high(self, root):
        # `risk` is never declared here: § 5.3 makes it a damage class the
        # hook OBSERVES and stamps into the file and the projection
        # together. So the fixture earns it -- an updateObjectSecurity is
        # high by observation -- rather than writing the label.
        cycle = Cycle()
        c = signed_cfg(root, kind="task", intent=None)
        c = self._security_read(c, ["G1"], "tu-pre")
        cycle.write(c, "mcp__appian-dev__updateInterface", "tu-w1",
                    uuid="_uuid-lista", expression="a!textField()")
        cycle.write(c, "mcp__appian-dev__updateObjectSecurity", "tu-w2",
                    uuid="_uuid-lista", role="viewer")
        c = cycle.verify(c)
        # § 8.1: the security row is paid by the diff, not by the ok.
        c = self._security_read(c, ["G1", "G2"], "tu-post")
        self.assertEqual(read_scope(c)["risk"], "high",
                         "the hook did not observe the damage class")
        write_certify(c, read_scope(c), objects=["_uuid-lista"])
        return cycle, c

    def _security_read(self, c, viewers, tool_use_id):
        c = dict(c, activeTask=read_scope(c))
        observe_reads({"tool_calls": [
            {"tool_name": "mcp__appian-dev__getObjectSecurity",
             "tool_use_id": tool_use_id,
             "tool_input": {"uuid": "_uuid-lista"},
             "tool_response": json.dumps({"name": "_uuid-lista",
                                          "roleMap": {"viewers": viewers}})}]}, c)
        return dict(c, activeTask=read_scope(c))

    def test_a_standard_scope_owes_no_risk_verdict(self):
        with tempfile.TemporaryDirectory() as root:
            cycle = Cycle()
            c = cycle.build(root)
            write_certify(c, read_scope(c), objects=["_uuid-lista"])
            self.assertEqual(risk_errors(c, read_scope(c)), [])
            self.assertEqual(cycle.stop(cycle.ask_to_close(c))["decision"],
                             "approve")

    def test_a_high_risk_scope_cannot_close_without_it(self):
        with tempfile.TemporaryDirectory() as root:
            cycle, c = self._high(root)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("how does it fail", out["reason"])

    def test_and_closes_with_it(self):
        with tempfile.TemporaryDirectory() as root:
            cycle, c = self._high(root)
            write_verdict(c, read_scope(c), "risk")
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "approve", out)
            self.assertEqual(read_scope(c)["status"], "closed")

    def test_a_failing_risk_verdict_blocks(self):
        with tempfile.TemporaryDirectory() as root:
            cycle, c = self._high(root)
            write_verdict(c, read_scope(c), "risk", verdict="FAIL",
                          findings=[{"id": "r-1",
                                     "criterion": "a retry duplicates the write",
                                     "verdict": "FAIL", "evidence": "e"}])
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("a retry duplicates the write", out["reason"])

    def test_the_risk_verdict_owes_no_matrix(self):
        # It asks how the thing fails, not whether it meets its contract.
        with tempfile.TemporaryDirectory() as root:
            cycle, c = self._high(root)
            path = write_verdict(c, read_scope(c), "risk")
            with open(path, encoding="utf-8") as f:
                self.assertNotIn("matrix", json.load(f))
            self.assertEqual(risk_errors(c, read_scope(c)), [])

    def test_the_copy_alone_does_not_answer_for_risk_either(self):
        with tempfile.TemporaryDirectory() as root:
            cycle, c = self._high(root)
            write_verdict(c, read_scope(c), "risk", version=None)
            out = cycle.stop(cycle.ask_to_close(c))
            self.assertEqual(out["decision"], "block")
            self.assertIn("unsuffixed copy", out["reason"])


if __name__ == "__main__":
    unittest.main()
