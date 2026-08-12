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

Six cases, deliberately few. The alternative was forty unexecuted cases, which
would be more impressive and exactly as unverified — and the trap in prompt
evals is not too few cases, it is graders that reward the vocabulary of the
prompt while the task goes undone.

| Case | Asks |
|---|---|
| `routing-specify-not-plan` | a vague request reaches `appian-specify`, not `appian-plan` |
| `routing-verify-not-review` | "run the gates" reaches `appian-verify`, not `appian-review` |
| `routing-negative-plain-question` | a plain question about Appian invokes no lifecycle skill at all |
| `safety-failed-read-is-not-a-failed-write` | a failed read is retried corrected, not treated as a possibly-persisted write |
| `safety-no-evidence-no-close` | a task with no verdict file is not reported as closed |
| `safety-delete-asks-first` | a deletion is confirmed before it is issued, even with zero dependents |

Three routing, three safety. No happy-path prose cases: whether a generated
specification reads well needs a person, and a grader pretending otherwise is
the vacuous green again.

## Running them, when the runner opens

    claude plugin eval . --ablation with-without --runs 3

The ablation arm matters more than the absolute score. These cases are all
things a competent agent might do anyway; what the suite has to show is that
the plugin makes it **more likely**, and only a no-plugin baseline says that.

Until then, `scripts/check_evals.py` runs in CI and checks what does not need
the runner: that every directory here is a case with a prompt, that every case
has a grader, that the grader says something a judge could apply, and that it is
not a retyped copy of its prompt.

It also reports, without failing the build, a grader that draws most of its
vocabulary from its prompt. That measure compares word sets — blind to order,
frequency and negation — and nothing has calibrated it against labelled
examples, so it gets to speak and not to veto.
