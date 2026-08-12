"""Holds evals/ to the shape `claude plugin eval` expects, before it can run.

`claude plugin eval` is in early access and does not respond on the account
this plugin is developed on -- neither `init` nor the runner. So the suite here
has never been executed, and the honest thing to do about that is two things:
say so in evals/README.md, and check mechanically what can be checked without
the runner.

What can: that every case has a prompt with content, that every case has at
least one grader, and that no grader merely restates its prompt. That last one
is the trap worth a check -- a grader that rewards the vocabulary of the prompt
scores well while the task goes undone, which produces exactly the confident
green this plugin exists to argue against.

What cannot: whether the skills actually pass. Nothing here claims that.

    python3 scripts/check_evals.py [root]

Exit 0 well-formed, 1 malformed, 3 no suite.
"""
import os
import re
import sys

EXIT_NOT_MEASURED = 3

# Two texts count as "the same claim" when their meaningful words overlap this
# far. Deliberately blunt: it catches copy-paste, which is the real failure,
# and says nothing about graders that legitimately quote a phrase.
RESTATEMENT_OVERLAP = 0.8
WORD = re.compile(r"[a-z0-9!-]+")
STOPWORDS = frozenset("a an and are as at be by for from in is it its of on or "
                      "that the to with when should must not response".split())


def _significant(text):
    return frozenset(w for w in WORD.findall(text.lower()) if w not in STOPWORDS)


def check(root):
    evals_dir = os.path.join(root, "evals")
    if not os.path.isdir(evals_dir):
        return EXIT_NOT_MEASURED, ["no evals/ directory under %s" % root]

    msgs = []
    cases = 0
    for entry in sorted(os.listdir(evals_dir)):
        case_dir = os.path.join(evals_dir, entry)
        prompt_path = os.path.join(case_dir, "prompt.md")
        if not os.path.isdir(case_dir) or not os.path.isfile(prompt_path):
            continue
        cases += 1

        with open(prompt_path, encoding="utf-8") as f:
            prompt = f.read()
        if not prompt.strip():
            msgs.append("%s/prompt.md is empty" % entry)

        graders_dir = os.path.join(case_dir, "graders")
        graders = []
        if os.path.isdir(graders_dir):
            graders = [g for g in sorted(os.listdir(graders_dir)) if g.endswith(".md")]
        if not graders:
            msgs.append("%s has no grader; a prompt with nothing scoring it would run, "
                        "produce output and assert nothing" % entry)
            continue

        prompt_words = _significant(prompt)
        for grader in graders:
            with open(os.path.join(graders_dir, grader), encoding="utf-8") as f:
                grader_text = f.read()
            if not grader_text.strip():
                msgs.append("%s/graders/%s is empty" % (entry, grader))
                continue
            grader_words = _significant(grader_text)
            if not grader_words:
                continue
            overlap = len(grader_words & prompt_words) / float(len(grader_words))
            if overlap >= RESTATEMENT_OVERLAP:
                msgs.append("%s/graders/%s restates its prompt (%.0f%% of its words come "
                            "from it); a grader that rewards the prompt's vocabulary "
                            "scores well while the task goes undone"
                            % (entry, grader, overlap * 100))

    if cases == 0:
        return EXIT_NOT_MEASURED, ["evals/ exists but declares no case; 0 were checked"]
    return (1 if msgs else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        print("OK every eval case has a prompt and a grader that is not a copy of it")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
