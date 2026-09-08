"""Who writes the scope's state, and when the grant's clock is read.

Three frictions the owner observed in P2-PASADA-8 -- a `task` under scope
schema v2. None of them is a gate defect: the hook already rejects a status
outside § 4.2, already reverts a hand-written one, and never reads `grantedAt`
at all. All three are the skill describing the file less exactly than the
schema does, so the builder improvises and pays for the improvisation:

  1. The scope was reached for with `"status": "open"`. There is no such state.
     `SKILL.md` showed only the 0.6 two-field shape, so the v2 birth values had
     to be guessed, and a guess that misses fails the schema check outright --
     nothing signed, no projection, and the first Appian write asking.
  2. `status` and `statusWriteSeq` were edited by hand after birth. The state
     gate reverted them (`state-revert`, inst-p8-20260904, 13:39:43Z) and said
     so, which is the harness working; the cost was a hook cycle spent on a
     rule the skill never stated. The transitions are asked for with `request`
     and signed by the harness.
  3. `grantedAt` was composed with the question rather than read after the
     answer. No gate checks that field -- which is why the skill has to.

So these are documentary tests, the same shape as `test_micro_lane_contract`:
they read `appian-build` and its reference and fail when the rule stops being
stated. The behaviour they lean on is pinned separately in `test_state_gate`.
"""
import os, re, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_micro_lane_contract import BUILD, MICRO_LANE, blocks

DOCS = (("appian-build/SKILL.md", BUILD),
        ("appian-build/references/micro-lane.md", MICRO_LANE))

# Same vocabulary as the sibling contract test: naming a mechanism is fine,
# naming it outside a refusal is not.
NEGATION = re.compile(r"\b(never|not|no|nothing|without|do not|don't)\b", re.I)

# The quoted literal, not the bare word: "open the scope", "the opening" and
# `trigger: "open"` are all legitimate prose here, and only the value a
# constructor could copy into the file is under test.
OPEN_STATUS = '"open"'


def text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestTheScopeIsBornInFlight(unittest.TestCase):
    def test_both_documents_give_the_two_birth_values(self):
        for label, path in DOCS:
            body = text(path)
            for token in ('"status": "in-flight"', '"statusWriteSeq": 0'):
                self.assertIn(token, body,
                              "%s never shows %s, so the v2 birth values are "
                              "left to be guessed" % (label, token))

    def test_the_open_status_is_named_only_to_refuse_it(self):
        for label, path in DOCS:
            named = [b for b in blocks(text(path)) if OPEN_STATUS in b]
            self.assertTrue(named,
                            "%s never says %s is not a state, so nothing stops "
                            "the next builder reaching for it" % (label, OPEN_STATUS))
            for block in named:
                self.assertTrue(
                    NEGATION.search(block),
                    "%s names %s outside a refusal, which reads as permission: %r"
                    % (label, OPEN_STATUS, block[:120]))


class TestTheConstructorStopsWritingTheStateAtBirth(unittest.TestCase):
    def test_both_documents_hand_the_two_fields_back_to_the_harness(self):
        for label, path in DOCS:
            stated = [b for b in blocks(text(path))
                      if "statusWriteSeq" in b and NEGATION.search(b)]
            self.assertTrue(
                stated,
                "%s names `statusWriteSeq` only in a template: a builder reading "
                "it learns the field exists and not that editing it after birth "
                "is reverted" % label)

    def test_both_documents_name_the_transition_a_constructor_may_ask_for(self):
        for label, path in DOCS:
            body = text(path)
            self.assertIn('"request": "close"', body,
                          "%s never shows how a scope is asked to close" % label)
            self.assertIn("abandon:", body,
                          "%s never shows the abandon request carrying its motive, "
                          "and a bare `abandon` is refused rather than defaulted"
                          % label)


class TestGrantedAtIsReadAfterTheAnswer(unittest.TestCase):
    def test_every_block_naming_it_says_when_the_clock_is_read(self):
        for label, path in DOCS:
            named = [b for b in blocks(text(path)) if "grantedAt" in b]
            self.assertTrue(named,
                            "%s never names `grantedAt`, so nothing says when its "
                            "value is taken" % label)
            for block in named:
                self.assertRegex(
                    block, r"(?i)\bafter\b",
                    "%s names `grantedAt` without saying the clock is read after "
                    "the person answered, which is the whole defect: %r"
                    % (label, block[:120]))


if __name__ == "__main__":
    unittest.main()
