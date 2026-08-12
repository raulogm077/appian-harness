"""Holds evals/ to the shape `claude plugin eval` expects, before it can run.

`claude plugin eval` is in early access and does not respond on the account
this plugin is developed on -- neither `init` nor the runner. So the suite here
has never been executed, and the honest thing to do about that is two things:
say so in evals/README.md, and check mechanically what can be checked without
the runner.

What can, and fails a build: that every directory under evals/ is a case with a
prompt, that every case has a grader, and that the grader says something a judge
could apply. What can only be guessed at, and therefore warns: whether a grader
is a retyped copy of its prompt, and whether a prompt is built out of the
phrases its target skill advertises. What cannot be checked here at all: whether
the skills actually pass. Nothing here claims that.

Three findings from an independent review shaped the current version, all three
measured on the first one rather than argued about:

- A directory holding graders/ and no prompt.md was skipped, not failed -- the
  guard read it as "not a case". Alone it produced exit 3, the code a caller
  skips; beside one valid case it produced exit 0 and the broken directory
  vanished. So a directory under evals/ is now a case by default, and what is
  NOT a case is a closed list.
- A grader with no scorable vocabulary passed. `"the response should not"` is
  entirely stopwords -- including `not`, the word carrying the criterion -- and
  the empty word set was skipped rather than failed. `"!!!"` passed through the
  other door, surviving as a "word" that overlapped with nothing. Both die in
  the same branch now: an empty vocabulary is a finding.
- No similarity number fails a build any more. Both are blunt: the vocabulary
  overlap compares SETS, blind to order, frequency, negation and morphology --
  a grader reading exactly "ALPHA BETA GAMMA" against a prompt asking for
  exactly that output scores 100% and is perfectly legitimate. The sequence
  ratio, which briefly was the gate, scores a verbatim copy 1.00 and the same
  copy with one sentence added 0.72, clean past both thresholds. So it stopped
  byte-for-byte paste and advertised protection against copying in general. The
  line is now: shape fails, judgement warns. Whether a file exists, has content
  and says something applicable is a fact; whether two texts are "the same
  claim" is an opinion held by an uncalibrated number.

- The prompts were built out of the phrases the skill descriptions advertise --
  the same defect one layer earlier, and the one this file was not watching.
  See `_trigger_echo`.

    python3 scripts/check_evals.py [root]

Exit 0 well-formed (warnings possible), 1 malformed, 3 no suite.
"""
import difflib
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402
from lint_skills import parse_frontmatter  # noqa: E402

# Findings fail the build; warnings are printed and do not. Carried on the
# message itself rather than in a second list beside it, so severity has one
# home instead of two that can fall out of step, and `check(root)` keeps
# returning `(exit_code, messages)`.
#
# This comment used to say "the shape its three siblings have". Two of the four
# expose a `check()` at all, and one of those returns a bare list -- a count of
# its own family, wrong, in the file that argues counts in prose go stale. So
# the shape is described and not tallied.
WARNING_PREFIX = "warning: "

# Two ways of asking "is this grader just its prompt again", both of them
# warnings, neither of them a gate.
#
# The sequence ratio was a build failure until it was measured against the thing
# it claims to stop. A verbatim copy scores 1.00 and is caught; the same copy
# with one sentence added drops to 0.72 on the sequence and 0.64 on the
# vocabulary, which is clean past both. So the hard branch stopped byte-for-byte
# paste and nothing else -- the least likely form of the defect -- while
# advertising protection against the whole of it. A metric that catches only the
# careless case has a place; a build gate that promises more than it delivers
# does not.
DUPLICATE_SEQUENCE_WARNING = 0.9
RESTATEMENT_WARNING_OVERLAP = 0.8

# `!` was in this class once, and it weakened the metric silently: `evidence!`
# was a token that could never match `evidence` in its prompt, while
# `evidence.` matched fine, because `.` was never in the class. The asymmetry
# had no reason behind it and its effect was that emphatic graders read as less
# similar to their prompts than they are. SAIL names survive the removal --
# `a!queryRecordType` becomes `a` (a stopword) and `queryrecordtype` on both
# sides of the comparison, so the pair still meets.
WORD = re.compile(r"[a-z0-9-]+")
NOT_A_WORD = re.compile(r"[^a-z0-9]+")
STOPWORDS = frozenset("a an and are as at be by for from in is it its of on or "
                      "that the to with when should must not response".split())

# A phrase is three words, and it has to carry two that mean something before a
# match counts -- "the task is" is grammar, "run the gates" is a trigger.
#
# Three rather than a tuned number: measured against the six shipped prompts it
# found one echo and no false positives, and the one it found was real. That is
# thin calibration, which is exactly why this side of the check warns and never
# fails.
PHRASE_WORDS = 3
PHRASE_MEANING = 2

# Directories under evals/ that are not cases, named one by one. The closed
# list is the point: "anything without a prompt.md is not a case" is exactly
# what let a half-written case disappear from the count. `results` is where the
# runner writes its scores; dot- and dunder-prefixed directories are tool
# artefacts (`.pytest_cache`, `__pycache__`), never authored content.
NOT_A_CASE = frozenset(("results",))


def _is_case_dir(name):
    return not (name in NOT_A_CASE or name.startswith(".") or name.startswith("__"))


def _significant(text):
    """The scorable vocabulary of a text.

    A token has to carry a letter to count: `Score 1` and `Score 0` would
    otherwise contribute `1` and `0`, and a grader holding nothing but digits
    would read as having said something. Punctuation is out one step earlier
    now that `!` has left WORD -- `"!!!"` yields no tokens at all -- but the
    letter test is what keeps a numeric grader from passing for vocabulary.
    """
    return frozenset(w for w in WORD.findall(text.lower())
                     if w not in STOPWORDS and any(c.isalpha() for c in w))


def _normalized(text):
    """The text as an ordered list of bare words, punctuation and case gone.

    Ordered on purpose: this is the half of the check a set cannot do.
    """
    return [w for w in NOT_A_WORD.split(text.lower()) if w]


def _phrases(words):
    return set(tuple(words[i:i + PHRASE_WORDS])
               for i in range(len(words) - PHRASE_WORDS + 1))


def _skill_descriptions(root):
    """Skill name -> the description that decides when it fires.

    Read through lint_skills' own parser rather than a second one written here.
    The frontmatter rule has one definition in this repository and this file is
    not going to become its second.
    """
    found = {}
    skills_dir = os.path.join(root, "skills")
    if not os.path.isdir(skills_dir):
        return found
    for entry in sorted(os.listdir(skills_dir)):
        path = os.path.join(skills_dir, entry, "SKILL.md")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            meta, _ = parse_frontmatter(f.read())
        if meta.get("description"):
            found[entry] = meta["description"]
    return found


def _trigger_echo(entry, prompt, descriptions):
    """A prompt built out of the words a skill advertises, or None.

    The axis this file was not watching. It was written to catch a grader that
    copies its prompt, and the same defect one layer earlier -- a prompt that
    copies the skill description -- went unchecked: `routing-verify-not-review`
    asked for "run the gates", which appian-verify's description names as one of
    its four trigger phrases, in a prompt of thirteen words. A router doing
    nothing but substring matching scored that case, so the case measured
    nothing about routing.
    """
    spoken = _phrases(_normalized(prompt))
    for skill in sorted(descriptions):
        for phrase in sorted(spoken & _phrases(_normalized(descriptions[skill]))):
            if len(_significant(" ".join(phrase))) >= PHRASE_MEANING:
                return (WARNING_PREFIX + "%s/prompt.md says \"%s\", a phrase from the "
                        "description of skills/%s. Worth a second read -- a router that "
                        "only matches substrings would score this case without routing "
                        "anything. A prompt reads better as the situation the user is in "
                        "than as the words the skill advertises"
                        % (entry, " ".join(phrase), skill))
    return None


def _grader_problem(entry, grader, grader_text, prompt):
    """What is wrong with one grader, as a message, or None.

    The message carries WARNING_PREFIX when the problem is worth reading and
    not worth failing a build over -- severity rides with the sentence, which
    is the whole reason there is no second list to keep in step with this one.
    """
    if not grader_text.strip():
        return "%s/graders/%s is empty" % (entry, grader)

    grader_words = _significant(grader_text)
    if not grader_words:
        return ("%s/graders/%s has no criterion in it: every word is a stopword or "
                "punctuation, so there is nothing for a judge to apply" % (entry, grader))

    ratio = difflib.SequenceMatcher(None, _normalized(prompt), _normalized(grader_text),
                                    autojunk=False).ratio()
    overlap = len(grader_words & _significant(prompt)) / float(len(grader_words))
    if ratio >= DUPLICATE_SEQUENCE_WARNING or overlap >= RESTATEMENT_WARNING_OVERLAP:
        return (WARNING_PREFIX + "%s/graders/%s restates its prompt (%.0f%% of the same "
                "word sequence, %.0f%% of its vocabulary drawn from it). Worth a second "
                "read: a grader that rewards the prompt's vocabulary scores well while "
                "the task goes undone. One message rather than two, because two "
                "similarity numbers firing on one file is one finding reported twice"
                % (entry, grader, ratio * 100, overlap * 100))
    return None


def check(root):
    evals_dir = os.path.join(root, "evals")
    if not os.path.isdir(evals_dir):
        return EXIT_NOT_MEASURED, ["no evals/ directory under %s" % root]

    msgs = []
    cases = 0
    descriptions = _skill_descriptions(root)
    for entry in sorted(os.listdir(evals_dir)):
        case_dir = os.path.join(evals_dir, entry)
        if not os.path.isdir(case_dir) or not _is_case_dir(entry):
            continue
        cases += 1

        prompt_path = os.path.join(case_dir, "prompt.md")
        prompt = ""
        if not os.path.isfile(prompt_path):
            msgs.append("%s has no prompt.md; a case with nothing to send is a case that "
                        "cannot run, and skipping it here is how it hides behind the "
                        "cases that can" % entry)
        else:
            with open(prompt_path, encoding="utf-8") as f:
                prompt = f.read()
            if not prompt.strip():
                msgs.append("%s/prompt.md is empty" % entry)
            else:
                echo = _trigger_echo(entry, prompt, descriptions)
                if echo:
                    msgs.append(echo)

        graders_dir = os.path.join(case_dir, "graders")
        graders = []
        if os.path.isdir(graders_dir):
            graders = [g for g in sorted(os.listdir(graders_dir)) if g.endswith(".md")]
        if not graders:
            msgs.append("%s has no grader; a prompt with nothing scoring it would run, "
                        "produce output and assert nothing" % entry)
            continue

        for grader in graders:
            with open(os.path.join(graders_dir, grader), encoding="utf-8") as f:
                grader_text = f.read()
            problem = _grader_problem(entry, grader, grader_text, prompt)
            if problem:
                msgs.append(problem)

    if cases == 0:
        return EXIT_NOT_MEASURED, ["evals/ exists but declares no case; 0 were checked"]
    return (1 if any(not m.startswith(WARNING_PREFIX) for m in msgs) else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        if m.startswith(WARNING_PREFIX):
            print("WARNING: %s" % m[len(WARNING_PREFIX):])
        else:
            print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        # Says only what gated. Similarity and phrase echoes warn, so claiming
        # here that no grader copies its prompt would be this file asserting the
        # half of its own output it deliberately does not enforce.
        print("OK every eval case has a prompt and a grader with a criterion in it")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
