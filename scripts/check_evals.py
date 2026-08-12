"""Holds evals/ to the shape `claude plugin eval` expects, before it can run.

`claude plugin eval` is in early access and does not respond on the account
this plugin is developed on -- neither `init` nor the runner. So the suite here
has never been executed, and the honest thing to do about that is two things:
say so in evals/README.md, and check mechanically what can be checked without
the runner.

What can: that every directory under evals/ is a case with a prompt, that every
case has a grader, and that the grader says something a judge could apply and is
not a retyped copy of its prompt. What cannot: whether the skills actually pass.
Nothing here claims that.

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
  other door, surviving as a "word" that overlapped with nothing.
- The 0.8 vocabulary overlap could fail a build, and it should not. It compares
  SETS, so it is blind to order, frequency, negation and morphology: a grader
  reading exactly "ALPHA BETA GAMMA" against a prompt asking for exactly that
  output scores 100% and is perfectly legitimate, while a full copy of the
  prompt padded with fresh vocabulary sits far below the line. The six shipped
  cases score 5-12%, so nothing has ever exercised it on real content. It is
  now a warning that reports and does not break a build, and the build-breaking
  half is near-exact duplication measured on the word SEQUENCE, which sees the
  order a set throws away.

    python3 scripts/check_evals.py [root]

Exit 0 well-formed (warnings possible), 1 malformed, 3 no suite.
"""
import difflib
import os
import re
import sys

EXIT_NOT_MEASURED = 3

# Findings fail the build; warnings are printed and do not. Carried on the
# message itself rather than in a third return value, so this checker keeps the
# `check(root) -> (exit_code, messages)` shape its three siblings have.
WARNING_PREFIX = "warning: "

# Two graders count as the same text when their normalised word sequences match
# this closely. Near-exact rather than exact: retyping a prompt in lower case
# with different punctuation is the same copy-paste, and normalisation is what
# makes it visible.
DUPLICATE_SEQUENCE_RATIO = 0.9

# Vocabulary overlap above this is reported, never fatal. It is an uncalibrated
# number -- no labelled examples exist to set it against -- and an uncalibrated
# number that can fail a build is a gate nobody can argue with. Silence would be
# the vacuous green this plugin argues against, so it speaks.
RESTATEMENT_WARNING_OVERLAP = 0.8

WORD = re.compile(r"[a-z0-9!-]+")
NOT_A_WORD = re.compile(r"[^a-z0-9]+")
STOPWORDS = frozenset("a an and are as at be by for from in is it its of on or "
                      "that the to with when should must not response".split())

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

    A token has to carry a letter to count. Without that, `"!!!"` was a word
    with no meaning that a judge could apply, and the grader holding nothing
    else passed.
    """
    return frozenset(w for w in WORD.findall(text.lower())
                     if w not in STOPWORDS and any(c.isalpha() for c in w))


def _normalized(text):
    """The text as an ordered list of bare words, punctuation and case gone.

    Ordered on purpose: this is the half of the check a set cannot do.
    """
    return [w for w in NOT_A_WORD.split(text.lower()) if w]


def _check_grader(entry, grader, grader_text, prompt, prompt_words):
    """Return (findings, warnings) for one grader file."""
    if not grader_text.strip():
        return ["%s/graders/%s is empty" % (entry, grader)], []

    grader_words = _significant(grader_text)
    if not grader_words:
        return ["%s/graders/%s has no criterion in it: every word is a stopword or "
                "punctuation, so there is nothing for a judge to apply"
                % (entry, grader)], []

    ratio = difflib.SequenceMatcher(None, _normalized(prompt), _normalized(grader_text),
                                    autojunk=False).ratio()
    if ratio >= DUPLICATE_SEQUENCE_RATIO:
        return ["%s/graders/%s restates its prompt almost word for word (%.0f%% of the "
                "same sequence); a grader that rewards the prompt's vocabulary scores "
                "well while the task goes undone" % (entry, grader, ratio * 100)], []

    overlap = len(grader_words & prompt_words) / float(len(grader_words))
    if overlap >= RESTATEMENT_WARNING_OVERLAP:
        return [], [WARNING_PREFIX + "%s/graders/%s draws %.0f%% of its vocabulary from "
                    "its prompt. Worth a second read -- but this compares word sets, so "
                    "it cannot tell a rewritten criterion from a copy, and it does not "
                    "fail the build" % (entry, grader, overlap * 100)]
    return [], []


def check(root):
    evals_dir = os.path.join(root, "evals")
    if not os.path.isdir(evals_dir):
        return EXIT_NOT_MEASURED, ["no evals/ directory under %s" % root]

    findings = []
    warnings = []
    cases = 0
    for entry in sorted(os.listdir(evals_dir)):
        case_dir = os.path.join(evals_dir, entry)
        if not os.path.isdir(case_dir) or not _is_case_dir(entry):
            continue
        cases += 1

        prompt_path = os.path.join(case_dir, "prompt.md")
        prompt = ""
        if not os.path.isfile(prompt_path):
            findings.append("%s has no prompt.md; a case with nothing to send is a case "
                            "that cannot run, and skipping it here is how it hides behind "
                            "the cases that can" % entry)
        else:
            with open(prompt_path, encoding="utf-8") as f:
                prompt = f.read()
            if not prompt.strip():
                findings.append("%s/prompt.md is empty" % entry)

        graders_dir = os.path.join(case_dir, "graders")
        graders = []
        if os.path.isdir(graders_dir):
            graders = [g for g in sorted(os.listdir(graders_dir)) if g.endswith(".md")]
        if not graders:
            findings.append("%s has no grader; a prompt with nothing scoring it would run, "
                            "produce output and assert nothing" % entry)
            continue

        prompt_words = _significant(prompt)
        for grader in graders:
            with open(os.path.join(graders_dir, grader), encoding="utf-8") as f:
                grader_text = f.read()
            found, warned = _check_grader(entry, grader, grader_text, prompt, prompt_words)
            findings.extend(found)
            warnings.extend(warned)

    if cases == 0:
        return EXIT_NOT_MEASURED, ["evals/ exists but declares no case; 0 were checked"]
    return (1 if findings else 0), findings + warnings


def main(root):
    code, msgs = check(root)
    for m in msgs:
        if m.startswith(WARNING_PREFIX):
            print("WARNING: %s" % m[len(WARNING_PREFIX):])
        else:
            print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        print("OK every eval case has a prompt and a grader that is not a copy of it")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
