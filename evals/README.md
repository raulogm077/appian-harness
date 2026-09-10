# Evals

**This suite has never been executed.** `claude plugin eval` is in early access
and does not respond on the account this plugin is developed on — neither
`claude plugin eval init` nor the runner. Every case here was written against
the documented layout and reviewed by hand; none has produced a score.

That distinction matters more here than it would elsewhere, because this plugin
spends a README arguing that a gate nobody ran is not a gate that passed. A
suite of unexecuted cases is preparation, not coverage, and this file exists so
nobody reads the directory as the second thing.

## What is here

27 eval cases — 3 routing, 22 safety, and two named for what they are rather
than by prefix: `remedy-prompt-carries-a-runnable-fix` and
`migration-06-scope-in-flight-still-closes`. The count grew with 0.7 and the reason is
worth stating, because the previous version of this file argued the other way:
these are not cases somebody thought of, they are the cases the design names.
Each one is a rule 0.7 had to be argued into, written down where it can be
checked rather than only asserted. A rule with no case is a rule that survives
by being remembered.

**Routing — does the work reach the right phase at all?**

| Case | Asks |
|---|---|
| `routing-specify-not-plan` | a vague request reaches the specification phase, not a task breakdown |
| `routing-certify-before-close` | "mark it done" gets it certified first, and the close is not the skill's to perform |
| `routing-negative-plain-question` | a plain question about Appian invokes no lifecycle at all |

The last one is the case that keeps the other two honest. A harness that fires
on every mention of Appian is a harness people disable.

**Safety — the rules that cost something to get wrong.** They fall into five
groups.

*Proportion.* That the ceremony fits the work, which is the whole argument of
0.7: `safety-record-type-never-micro` ·
`safety-published-interface-is-micro-with-reviewer` ·
`safety-literal-change-skips-reviewer-filter-does-not` ·
`safety-instrument-failure-does-not-escalate-kind` ·
`safety-instrument-failure-vs-regression`.

*Not paying twice.* That a check nothing could have invalidated is not repeated:
`safety-foreign-write-does-not-expire` ·
`safety-non-behavioural-write-does-not-expire` ·
`safety-description-only-on-published-object-keeps-proportional-floor` ·
`safety-one-recertify-per-cycle`.

*Not asking a person what is not theirs to answer.* A question that is not a
decision is waste with a prompt attached:
`safety-remedy-not-prompt-on-malformed-record` ·
`safety-illegal-transition-is-remedy-not-ask` ·
`safety-created-uuid-no-false-ask` · `safety-batch-grant-one-prompt` ·
`remedy-prompt-carries-a-runnable-fix`.

*Closing honestly.* That what did not get checked is named rather than absorbed:
`safety-requires-human-closes-with-owner` · `safety-delete-closes-on-absence` ·
`safety-manual-type-closes-with-residue` ·
`safety-residue-id-is-not-a-verdict-deferral` ·
`safety-third-verdict-without-new-finding-is-rejected` ·
`safety-contextual-gate-does-not-block-closure` ·
`safety-cross-reference-row-catches-dangling-target`.

*Not being fooled.* That the cheap route through the gates is closed:
`safety-unsigned-status-reverts` · `safety-perimeter-mismatch-is-loud` ·
`migration-06-scope-in-flight-still-closes`.

No happy-path prose cases: whether a generated specification reads well needs a
person, and a grader pretending otherwise is the vacuous green again.

## Running them, when the runner opens

    claude plugin eval . --ablation with-without --runs 3

The ablation arm matters more than the absolute score. These cases are all
things a competent agent might do anyway; what the suite has to show is that
the plugin makes it **more likely**, and only a no-plugin baseline says that.

Until then, `scripts/check_evals.py` runs in CI on one principle: **shape fails,
judgement warns.** That every directory here is a case with a prompt, that every
case has a grader, and that the grader says something a judge could apply are
facts, and a build fails on them.

Two of its checks are newer and are not about shape. A case that **routes to a
component this tree does not have** fails: the suite carried a routing case
aimed at a deleted skill for a whole release, perfectly well-formed and green
on every run, which is what shape alone buys. And the **catalogue is held by
name**, in both directions — a case the design names and the directory lacks,
and a case the directory has that the design does not. A count cannot do that:
27 cases under 27 wrong names is the right number and the wrong suite.

Whether a grader is "really just the prompt again", and whether a prompt is
built out of the phrases its target skill advertises, are opinions held by blunt
numbers — so they print and let the build through. Both are worth reading and
neither is worth obeying: a verbatim copy of a prompt scores 1.00 on the
similarity check and the same copy with one sentence added scores 0.72, which is
clean. It catches carelessness, not intent, and says so where it prints.
