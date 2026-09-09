---
name: appian-review
description: Certifies one Appian scope from outside the context that built it and asks for the close. Dispatches the single judge with the artifact and the contract, never with the builder's conclusion, and drives the bounded remediation loop when findings come back. Use when a scope has finished writing and its lane bought a reviewer — every task, and every micro whose change could alter what data is shown or who sees it. Use before asking to close anything on that lane; the close itself is the hook's, not this skill's.
---

## Overview

This is the phase that certifies. It does not build, it does not fix the
findings itself, and it does not close the scope — it dispatches the judge,
drives the remediation loop if there is one, and then writes
`request: "close"` into the scope file. **The hook does the closing**, and it
will refuse if the floor or the verdict says the scope is not ready.

One constraint carries the whole skill:

> **The judge receives the artifact and the contract. Never the builder's
> conclusion.**

An agent that wrote an object reads its own work with the intent still
visible. Hand a judge "this looks right because…", a summary of what was
done, or a claim that the tests pass, and you have biased the review before
it opened anything. Dispatch with the changed objects, the scope's
`allowedObjects` and its acceptance criteria, and the paths of the evidence —
nothing the builder wrote about itself.

The judge is **one agent**, `appian-practices-auditor`, with three strictly
independent invocations. That independence is the product: its counterpart in
the official layer is adversarial *self*-review, the same context judging its
own plan.

| Invocation | When | The question |
|---|---|---|
| `design` | Before the first write, on a `task` that creates an object or changes data structure, security or a process model | Is this a good solution? |
| `certify` | Here, at close — once per scope, once per functionality when the scope is partitioned | Contract, doctrine and evidence, gate by gate? |
| `risk` | Only when the scope is high risk | How does it fail? |

## When to Use

Use this skill when the scope's lane bought a reviewer:

- **Every `task`.** Except a delete-only scope: nothing remains to certify.
- **Every `micro` whose change could alter what data is shown or who sees
  it** — filters and query conditions, ordering, aggregation, calculations,
  `showWhen` and any visibility, field references, security. In 0.7 that is
  every micro touching an expression, which includes changing a label.
- **Every `micro` on an object reachable from a published site**, when the
  write is behavioural. Exposure buys a reviewer, never a size.

**Do not use it** when the scope wrote only `description` or `documentation`,
or only objects with no expression of their own — constants, folders,
documents, test cases. Those pay the deterministic floor and close. Zero
judges is a result there, not an omission, and buying one anyway is exactly
the ceremony this design removes.

The exemption is **demonstrated, not declared**. The builder may always ask
for a reviewer; what it cannot do is take one away.

## Dispatch: what the judge gets, and what it must not

Hand it:

- the object names or UUIDs the scope wrote, and the scope's contract;
- `task`, `instanceId` and `coversThroughWriteSeq`;
- **paths** to the evidence — renders, N2 trees, dependents — and derived
  signals. Never their contents.

Never hand it: a render, a log or an object dump pasted inline; the builder's
own assessment; another judge's verdict.

**When more than one invocation is owed, dispatch them in one message.**
Design and certify for several functionalities go out together, not one after
another. Sequential waiting was measured at 51-61% of the clock — 21 waits of
five to eleven minutes — and it wrecks the cache besides. **Nothing in this
harness ever sits polling a file**: dispatch, and act on what comes back.

An invocation that started and never produced a verdict is a limit of the
instrument with one bounded retry — not an absent verdict, and not a FAIL.
"The judge never arrived" and "the judge said FAIL" must not reach the same
terminal state.

## The remediation loop, and why it is small

**A cycle is: every finding of this round applied in one coherent batch, then
a single re-certify.** Never a re-emission per finding, never one per severity
class.

- **Three cycles at most**, or the user's decision. The bottom of the ladder
  is closing with the debt recorded, not another level of ceremony.
- **One grant extension per scope**, not one per cycle. If a finding requires
  touching an object outside the scope, that extension is asked once, with the
  object, its fresh dependents and the literal text of the finding that
  motivated it. The hook writes it from the answer; you do not.
- Once the extension is spent, a later finding needing another object **does
  not reopen the scope**: it is recorded as debt with an owner and settled in
  a new scope.
- **A third verdict that raises no new finding is refused by the validator.**
  That is enforcement, not advice. If nothing new came back, the cycle is
  over — apply what is open or close with the debt.

Do not chain subagents to chase a finding. The judge judges; the builder
fixes; you sequence the two.

## Not every FAIL means the same thing

Read the class before deciding what to do. It is in
`appian-best-practices/references/10-quality-gates.md`, and the gate enforces
it whether or not you read it:

| Class | Gates | What it means for you |
|---|---|---|
| **CARDINAL** | 1 platform correctness · 3 security · and the three never graded down (invalid reference, authorization gap, non-idempotent write) | Fix it. It blocks the close, with no exception and no cycles |
| **RECOMMENDED** | 2 functional behavior · 4 SAIL interfaces · 7 operations | One cycle to fix it. It blocks once; after that the scope closes with the finding recorded as debt |
| **CONTEXTUAL** | 5 performance · 6 maintainability | Judgement, not a blocker. Fix it if it is cheap and right; otherwise let it be recorded with its owner. **Never spend a remediation cycle arguing about one** |

A CONTEXTUAL finding that you disagree with is not a fight to have with the
judge. *Measure before optimizing*, and a reasonable local convention beats
the generic preference of the docs.

## Asking for the close

After a clean `certify` — or after the cycles are spent and the debt is
recorded — write `request: "close"` into the scope file with `Write` or
`Edit`. That is the whole of it. Do not delete the scope file, do not write a
status, do not decide the terminal state: the hook signs the transition, and
which terminal state a close earns is its call, not yours.

If the hook blocks, it says exactly what is missing. Read it and act on it —
the answer is never to stop again to force it through.

## Common Rationalizations

| The thought | Why it is wrong |
|---|---|
| "I'll tell the judge what I found, to save it time." | That is the builder's conclusion, and it is the one thing the dispatch may not carry. You would be buying agreement, not judgement. |
| "One judge is thin — I'll dispatch a second opinion." | Two agents voting is not more independence, it is twice the bill for the same question. One judge, three invocations, each with its own context. |
| "The finding is wrong, I'll re-run the certify." | A re-run with no new finding is refused from the third emission. Answer it, or record the disagreement as debt. |
| "I'll fix the findings one at a time and re-certify after each." | That is the pattern the loop exists to prevent — one cycle is one batch and one re-certify. |
| "Maintainability failed, so I have to fix it before closing." | CONTEXTUAL does not block. Recording it with an owner is the correct outcome. |
| "It is a small change, review is overkill." | If the change can alter what is shown or who sees it, the lane already decided. The exemption is demonstrated, not declared. |
| "I'll wait for the verdict file to appear before continuing." | Nothing here polls a file. Dispatch and act on what returns. |
| "I'll close it myself, the verdict passed." | The close is the hook's. Writing a terminal state yourself makes the scope file disagree with the signed projection. |

## Red Flags

- A dispatch containing a render, a log, an object dump, or any sentence
  about how the build went.
- Two judging agents dispatched for the same question.
- A second, third or fourth `certify` whose findings are the previous ones
  reworded.
- A remediation cycle spent on gate 5 or gate 6.
- More than one grant extension in a scope, or an extension asked without the
  literal finding that motivated it.
- The scope file edited to say `closed` by anything other than the hook.
- A judge dispatched for a phase the scope does not owe — `design` on a
  `micro`, `certify` on a delete-only scope, `risk` on a scope that is not
  high risk.
- Waiting in a loop for anything.

## Verification

Before this phase is finished:

- [ ] The judge was dispatched with the artifact and the contract, and with
      no conclusion, dump or log of the builder's.
- [ ] Every invocation the scope owed was dispatched, and invocations owed at
      the same time went out in one message.
- [ ] The verdict exists at `<evidenceDir>/<task>/practices-certify.NNN.json`
      with its unsuffixed copy, and the validator exits `0` on it.
- [ ] Every CARDINAL finding is fixed, not deferred.
- [ ] At most three cycles were spent, each one a batch and a single
      re-certify.
- [ ] At most one grant extension was used, and it names the finding that
      motivated it.
- [ ] `request: "close"` is written in the scope file, and the terminal state
      came back from the hook rather than from this skill.
