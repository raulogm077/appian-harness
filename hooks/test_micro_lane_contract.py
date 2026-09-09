"""The `micro` lane costs what the gate actually charges, and the skill says so.

Measured on P2-PASADA-4 (a label change on one interface): of the twenty-three
minutes between opening the scope and signing the close, one minute was the
work. Twelve and a half went to an `appian-practices-auditor` running
`phase=design` in front of the grant, and the tail after the read-back went to
a verification dispatch of the phase set 0.7 has since retired. The closure
gate asked for neither. Both were paid because `appian-build` described a
harder gate than the one that exists.

So there are two halves here, and they have to be tested together or the pair
drifts apart again:

  * the gate's half -- a v2 `micro` writes and closes with NO design verdict on
    disk and NO post-write verdict of any kind. `test_v07_end_to_end.py` proves
    the lane closes signed with zero asks, but its fixture writes a design
    verdict, so it cannot see whether the verdict was ever needed.
  * the skill's half -- wherever `appian-build` names one of those verdicts, it
    also names which rulebook or kind owes it. An unqualified announcement is
    how the twelve minutes got bought.

And one more, from the micro run that followed: the scope file is the state
machine, and the state gate only signs what a `Write` or an `Edit` lets it
observe. That run went right because the builder noticed on its own, under an
ambient instruction that prefers the shell for editing files -- the lane said
nothing either way. So the third half is documentary and has no gate behind
it in this release: wherever these two files move the scope, they name the
observable tool, and nowhere do they leave a shell write looking allowed.
"""
import json, os, re, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
from harness_hooks import (closure_gate, log_write, observe_reads,
                           scope_gate, state_gate)
from test_grant import GRANT
from test_harness_hooks import cfg, make_plugin_root, write_skill_record
from test_scope_schema import v2_scope
from test_state_gate import projection, read_scope, write_scope

SKILLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "skills")
BUILD = os.path.join(SKILLS, "appian-build", "SKILL.md")
MICRO_LANE = os.path.join(SKILLS, "appian-build", "references", "micro-lane.md")

# The verdicts a reader can be told to go and produce. `phase=design` is in the
# list because it is the dispatch, and the dispatch is what costs the minutes.
VERDICTS = ("practices-design", "practices-implementation", "practices-qa",
            "practices-review", "phase=design")

# What makes an announcement honest: it says which rulebook or which kind owes
# the verdict. Any one of these in the same block is enough.
QUALIFIERS = ("schemaVersion", "0.6", "micro", "v2")

BLOCK_START = re.compile(r"^(#|[-*] |\d+[a-z]?\. )")


def blocks(text):
    """Markdown split into the units a reader takes in one go: a heading, a
    list item with its continuation lines, a paragraph. Coarser than this and
    one qualified bullet would vouch for a whole unqualified section."""
    out, cur = [], []
    for line in text.splitlines():
        if BLOCK_START.match(line) or not line.strip():
            if cur:
                out.append("\n".join(cur))
                cur = []
            if line.strip():
                cur = [line]
        else:
            cur.append(line)
    if cur:
        out.append("\n".join(cur))
    return out


def micro_cfg(root, **scope_over):
    """A signed v2 `micro` with a grant and the skill record -- and NOTHING
    else on disk. Deliberately not `signed_cfg`: that fixture writes a design
    verdict, which is the exact file this lane is supposed to do without."""
    scope_over.setdefault("kind", "micro")
    scope_over.setdefault("grant", dict(GRANT))
    scope_over.setdefault("allowedObjects", ["GDE_INT_Lista", "_uuid-lista"])
    scope = v2_scope(**scope_over)
    make_plugin_root(root)
    write_skill_record(root, scope["id"])
    c = cfg(root, activeTask=scope)
    c = write_scope(c, scope)
    state_gate({"tool_name": "Write",
                "tool_input": {"file_path": c["activeTaskFile"]}}, c)
    return c


class TestAPresentationMicroNeedsNoVerdictAtAll(unittest.TestCase):
    def test_it_writes_and_closes_with_no_verdict_on_disk(self):
        with tempfile.TemporaryDirectory() as root:
            c = micro_cfg(root)
            evidence = os.path.join(c["evidenceDir"], c["activeTask"]["id"])
            self.assertFalse(
                os.path.isfile(os.path.join(evidence, "practices-design.json")),
                "the fixture must not hand the lane the verdict under test")

            out = scope_gate({"tool_name": "mcp__appian-dev__updateInterface",
                              "session_id": "s-micro", "tool_use_id": "tu-1",
                              "tool_input": {"uuid": "_uuid-lista",
                                             "expression": 'a!textField(label: "Tarifa")'}}, c)
            self.assertEqual(out["permissionDecision"], "allow",
                             out.get("permissionDecisionReason"))
            log_write({"tool_name": "mcp__appian-dev__updateInterface",
                       "tool_use_id": "tu-1",
                       "tool_input": {"uuid": "_uuid-lista"},
                       "tool_response": json.dumps({"uuid": "_uuid-lista",
                                                    "versionId": 4})}, c)

            # § 8.6: the write carried no expression, so `log-write`
            # classified it non-behavioural and the floor is proportional --
            # validate plus the re-read that accredits that only the
            # declared field changed. Two legs, not the five an interface
            # that touched its expression pays.
            observe_reads({"tool_calls": [
                {"tool_name": "mcp__appian-dev__validateDesignObject",
                 "tool_use_id": "tu-val",
                 "tool_input": {"uuid": "_uuid-lista"},
                 "tool_response": {"valid": True}},
                {"tool_name": "mcp__appian-dev__getInterface",
                 "tool_use_id": "tu-get",
                 "tool_input": {"uuid": "_uuid-lista"},
                 "tool_response": {"name": "GDE_INT_Lista",
                                   "description": "Tarifa"}}]}, c)

            scope = read_scope(c)
            scope["request"] = "close"
            c = write_scope(c, scope)
            state_gate({"tool_name": "Write",
                        "tool_input": {"file_path": c["activeTaskFile"]}}, c)
            c = dict(c, activeTask=read_scope(c))
            close = closure_gate({}, c)
            self.assertEqual(close["decision"], "approve", close)
            self.assertEqual(read_scope(c)["status"], "closed")
            self.assertEqual(projection(c)["scope"]["status"], "closed")

            # No verdict of any phase was produced, and the close is signed
            # anyway: that is the whole claim of this lane.
            produced = os.listdir(evidence) if os.path.isdir(evidence) else []
            self.assertEqual([f for f in produced if f.startswith("practices-")], [])

    def test_a_task_that_creates_still_owes_its_design_verdict(self):
        # The economy must come from the kind, not from the check going away:
        # the same scope declared `task` with a creation in its grant still
        # stops on the missing verdict.
        with tempfile.TemporaryDirectory() as root:
            c = micro_cfg(root, kind="task", intent=None)
            out = scope_gate({"tool_name": "mcp__appian-dev__createExpressionRule",
                              "session_id": "s-task", "tool_use_id": "tu-1",
                              "tool_input": {"name": "GDE_QRY_Nueva",
                                             "expression": "1+1"}}, c)
            self.assertEqual(out["permissionDecision"], "ask")
            self.assertIn("design", out["permissionDecisionReason"])


class TestTheBuildSkillAnnouncesOnlyTheGatesThatExist(unittest.TestCase):
    def test_the_micro_lane_reference_exists_and_is_routed_to(self):
        self.assertTrue(os.path.isfile(MICRO_LANE),
                        "the micro lane has no reference file to read")
        with open(BUILD, encoding="utf-8") as f:
            skill = f.read()
        self.assertIn("references/micro-lane.md", skill,
                      "SKILL.md never sends a micro to its own contract, so the "
                      "reader pays the wider lane's ceremony by default")

    def test_every_verdict_it_names_says_who_owes_it(self):
        offenders = []
        for label, path in (("appian-build/SKILL.md", BUILD),
                            ("appian-build/references/micro-lane.md", MICRO_LANE)):
            with open(path, encoding="utf-8") as f:
                for block in blocks(f.read()):
                    named = [v for v in VERDICTS if v in block]
                    if named and not any(q in block for q in QUALIFIERS):
                        offenders.append("%s names %s with no rulebook or kind: %r"
                                         % (label, named, block[:120]))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_micro_lane_dispatches_nobody_it_does_not_owe(self):
        with open(MICRO_LANE, encoding="utf-8") as f:
            lane = f.read()
        for agent in ("appian-practices-auditor", "appian-review"):
            for block in blocks(lane):
                if agent not in block:
                    continue
                self.assertTrue(
                    re.search(r"\b(never|not|no|nothing|without|do not|don't)\b",
                              block, re.I),
                    "%s appears in the micro lane outside a statement that it is "
                    "not dispatched: %r" % (agent, block[:120]))


# The mechanisms that change a file without the state gate ever running. That
# gate is a `PostToolUse` hook matched on `Write|Edit|MultiEdit|NotebookEdit`,
# so a scope written past those tools is a transition nobody signed, while
# `evidence/scope-projection.json` -- the authority -- still holds the old
# state. The next Appian write is then measured against a state the harness
# never saw and the scope gate degrades to `ask`: a second prompt, for a
# reason that is nowhere in the work. In the measured micro run the lane said
# nothing about this and the builder had to catch itself, under an ambient
# instruction that actively prefers the shell for editing files.
BYPASS = ("Bash", "heredoc", "cat >", "printf", "redirect", "external script")

# What both documents have to say out loud. The tools carry their backticks on
# purpose: a bare "write" is half the vocabulary of these files already, and
# would pass this check without the rule ever being stated.
REQUIRED = ("`Write`", "`Edit`", "state gate") + BYPASS

# Same phrasing as `test_the_micro_lane_dispatches_nobody`: naming a mechanism
# is fine, naming it outside a refusal is not.
NEGATION = re.compile(r"\b(never|not|no|nothing|without|do not|don't)\b", re.I)

# The three numbered steps that move the state machine -- the opening, the
# grant, the request. Each names the tool where it stands, because a rule met
# only in a section further down is a rule met after the step it governs.
STATE_STEPS = ("2", "4", "7")


class TestTheScopeFileIsWrittenWhereTheStateGateCanSeeIt(unittest.TestCase):
    def test_both_documents_state_the_rule_and_name_what_it_replaces(self):
        offenders = []
        for label, path in (("appian-build/SKILL.md", BUILD),
                            ("appian-build/references/micro-lane.md", MICRO_LANE)):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            missing = [tok for tok in REQUIRED if tok not in text]
            if missing:
                offenders.append("%s never names %s, so a builder writing the "
                                 "scope through the shell is following it, not "
                                 "breaking it" % (label, missing))
        self.assertEqual(offenders, [], "\n".join(offenders))

    def test_the_three_state_steps_of_the_micro_lane_name_the_tool(self):
        with open(MICRO_LANE, encoding="utf-8") as f:
            lane = blocks(f.read())
        for step in STATE_STEPS:
            found = [b for b in lane if b.startswith("%s. " % step)]
            self.assertTrue(found, "the micro lane has no step %s to check" % step)
            for block in found:
                self.assertTrue(
                    "`Write`" in block or "`Edit`" in block,
                    "step %s moves the scope but names no observable tool, so "
                    "the shell is left looking like a way to do it: %r"
                    % (step, block[:120]))

    def test_no_block_leaves_a_shell_write_of_the_scope_looking_allowed(self):
        offenders = []
        for label, path in (("appian-build/SKILL.md", BUILD),
                            ("appian-build/references/micro-lane.md", MICRO_LANE)):
            with open(path, encoding="utf-8") as f:
                for block in blocks(f.read()):
                    named = [m for m in BYPASS if m in block]
                    if named and not NEGATION.search(block):
                        offenders.append(
                            "%s names %s outside a refusal, which reads as "
                            "permission: %r" % (label, named, block[:120]))
        self.assertEqual(offenders, [], "\n".join(offenders))


if __name__ == "__main__":
    unittest.main()
