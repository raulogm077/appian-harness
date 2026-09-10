"""Holds evals/ to the shape `claude plugin eval` expects, before it can run.

Shape fails, judgement warns: docs/design-notes.md § check_evals.py · scope

    python3 scripts/check_evals.py [root]

Exit 0 well-formed (warnings possible), 1 malformed, 3 no suite.
"""
import difflib
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from exit_codes import EXIT_NOT_MEASURED  # noqa: E402
from lint_skills import parse_frontmatter  # noqa: E402

# Findings fail the build; warnings print and do not. Severity rides on the
# message: docs/design-notes.md § check_evals.py · WARNING_PREFIX
WARNING_PREFIX = "warning: "

# Warnings, never gates: both metrics are blunt and the numbers are measured.
# docs/design-notes.md § check_evals.py · similarity thresholds
DUPLICATE_SEQUENCE_WARNING = 0.9
RESTATEMENT_WARNING_OVERLAP = 0.8

# `!` is out of the word class: with it in, `evidence!` can never match the
# `evidence` in its prompt. docs/design-notes.md § check_evals.py · WORD
WORD = re.compile(r"[a-z0-9-]+")
NOT_A_WORD = re.compile(r"[^a-z0-9]+")
STOPWORDS = frozenset("a an and are as at be by for from in is it its of on or "
                      "that the to with when should must not response".split())

# Three words, two of them meaningful -- thin calibration, which is why this
# side warns: docs/design-notes.md § check_evals.py · phrase calibration
PHRASE_WORDS = 3
PHRASE_MEANING = 2

# A directory under evals/ is a case by default, and what is not one is
# enumerated here: docs/design-notes.md § check_evals.py · NOT_A_CASE
NOT_A_CASE = frozenset(("results",))

# The catalogue norm § 17.7 enumerates by name. Held because a count cannot
# hold it: docs/design-notes.md § check_evals.py · the catalogue
CATALOGUE = frozenset((
    "routing-specify-not-plan",
    "routing-negative-plain-question",
    "routing-certify-before-close",
    "safety-remedy-not-prompt-on-malformed-record",
    "safety-foreign-write-does-not-expire",
    "safety-record-type-never-micro",
    "safety-requires-human-closes-with-owner",
    "safety-batch-grant-one-prompt",
    "safety-created-uuid-no-false-ask",
    "safety-delete-closes-on-absence",
    "safety-non-behavioural-write-does-not-expire",
    "safety-one-recertify-per-cycle",
    "safety-literal-change-skips-reviewer-filter-does-not",
    "remedy-prompt-carries-a-runnable-fix",
    "migration-06-scope-in-flight-still-closes",
    "safety-instrument-failure-does-not-escalate-kind",
    "safety-instrument-failure-vs-regression",
    "safety-unsigned-status-reverts",
    "safety-illegal-transition-is-remedy-not-ask",
    "safety-perimeter-mismatch-is-loud",
    "safety-published-interface-is-micro-with-reviewer",
    "safety-description-only-on-published-object-keeps-proportional-floor",
    "safety-contextual-gate-does-not-block-closure",
    "safety-third-verdict-without-new-finding-is-rejected",
    "safety-cross-reference-row-catches-dangling-target",
    "safety-manual-type-closes-with-residue",
    "safety-residue-id-is-not-a-verdict-deferral",
))

# `appian-`-prefixed names that are not a component of this plugin: two MCP
# servers, the plugin, its command, and the official Appian skill.
NOT_A_COMPONENT = frozenset(("appian", "appian-dev", "appian-docs",
                             "appian-harness", "appian-init"))
COMPONENT_REF = re.compile(r"`(appian-[a-z][a-z-]*)`")


def _is_case_dir(name):
    return not (name in NOT_A_CASE or name.startswith(".") or name.startswith("__"))


def _significant(text):
    """The scorable vocabulary of a text.

    A token has to carry a letter, so a numeric grader has no vocabulary:
    docs/design-notes.md § check_evals.py · _significant
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

    Read through lint_skills' own parser, the one definition of the rule:
    docs/design-notes.md § check_evals.py · one frontmatter parser
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

    A router matching substrings alone would score such a case without
    routing: docs/design-notes.md § check_evals.py · trigger echo
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


def _components(root):
    """Every skill and judging agent the tree actually ships."""
    found = set()
    for path in glob.glob(os.path.join(root, "skills", "*", "SKILL.md")):
        found.add(os.path.basename(os.path.dirname(path)))
    for path in glob.glob(os.path.join(root, "agents", "*.md")):
        found.add(os.path.basename(path)[:-len(".md")])
    return found


def _destination_problems(entry, label, text, components):
    """Components a case routes to that the tree does not have.

    Shape is not enough: a grader can be perfectly formed and score a skill
    that was deleted two releases ago.
    docs/design-notes.md § check_evals.py · destinations
    """
    problems = []
    for name in sorted(set(COMPONENT_REF.findall(text))):
        if name in NOT_A_COMPONENT or name in components:
            continue
        problems.append("%s/%s routes to `%s`, which is neither a skill nor an agent in "
                        "this tree. A case that scores a component that does not exist "
                        "is well-formed and measures nothing" % (entry, label, name))
    return problems


def _catalogue_problems(cases):
    """The catalogue of norm § 17.7, as a set difference both ways.
    docs/design-notes.md § check_evals.py · the catalogue"""
    problems = []
    present = set(cases)
    if not present & CATALOGUE:
        # A suite sharing not one case with the catalogue is somebody else's
        # suite, or a fixture. Holding it to this one would report 27 absences
        # about a tree that never claimed them.
        return problems
    for name in sorted(CATALOGUE - present):
        problems.append("the case %r is named by norm 17.7 and is not in evals/. A "
                        "renamed or deleted case leaves the count right and the "
                        "catalogue short" % name)
    for name in sorted(present - CATALOGUE):
        problems.append("the case %r is in evals/ and not in the catalogue of norm 17.7. "
                        "Either the norm gained it -- amend CATALOGUE and say so -- or "
                        "the suite grew a case nothing asked for" % name)
    return problems


def _grader_problem(entry, grader, grader_text, prompt):
    """What is wrong with one grader, as a message, or None.

    WARNING_PREFIX rides on the message rather than a second list:
    docs/design-notes.md § check_evals.py · WARNING_PREFIX
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
    seen = []
    descriptions = _skill_descriptions(root)
    components = _components(root)
    for entry in sorted(os.listdir(evals_dir)):
        case_dir = os.path.join(evals_dir, entry)
        if not os.path.isdir(case_dir) or not _is_case_dir(entry):
            continue
        seen.append(entry)

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
                msgs.extend(_destination_problems(entry, "prompt.md", prompt, components))

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
            msgs.extend(_destination_problems(entry, "graders/" + grader,
                                              grader_text, components))

    if not seen:
        return EXIT_NOT_MEASURED, ["evals/ exists but declares no case; 0 were checked"]
    msgs.extend(_catalogue_problems(seen))
    return (1 if any(not m.startswith(WARNING_PREFIX) for m in msgs) else 0), msgs


def main(root):
    code, msgs = check(root)
    for m in msgs:
        if m.startswith(WARNING_PREFIX):
            print("WARNING: %s" % m[len(WARNING_PREFIX):])
        else:
            print("%s: %s" % ("ERROR" if code == 1 else "NOT MEASURED", m))
    if code == 0:
        # Says only what gated -- similarity and phrase echoes only warn:
        # docs/design-notes.md § check_evals.py · the OK line
        print("OK every eval case has a prompt and a grader with a criterion in it")
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  os.path.join(os.path.dirname(__file__), "..")))
