# When the harness is wrong

> Part of the [appian-harness](../README.md) documentation.

It will be, eventually. A gate will name a defect that is not there, or a
register will state something that did not happen. This section exists because
what someone does in that moment decides whether the problem stays a bug or
turns into a divergence nobody can see.

### The boundary: a project consumes this plugin, it never modifies it

**Do not edit your installed copy.** Not to unblock yourself, not "just this
once". `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` is a **copy**
made at install time, one directory per version — not a link to anything. An
edit there works, right up until the next update replaces the directory and
silently reverts it. Nothing records that the edit existed, nothing records that
your project ever depended on it, and the behaviour you were relying on vanishes
between one session and the next.

That is worse than the original defect, because a defect is at least the same
for everyone. A patched copy makes one machine behave differently from every
other machine running the same declared version — and the declared version is
the only thing anyone can compare.

The same applies to per-project forks. If a project needs this plugin to behave
differently, that is a change to the plugin, released as a version, or it is not
a change at all.

### You are not blocked, and that is on purpose

No gate here refuses. The scope gate **asks**; the closure gate blocks once and
approves on the repeat, recording the omission as debt. So a defect in this
plugin costs you a confusing message and possibly a wrong line in a register —
never your afternoon, and never a reason to reach for the cache.

That is the design constraint the boundary forces: a tool its users cannot patch
must never hard-block, and must be conservative about what it asserts. If you
ever find a gate that traps you with no way through, **that is the bug**, and it
outranks whatever you were doing when you found it.

### An instrument that fails is not a bigger job

The commonest way the harness looks wrong is not a gate with an opinion — it is
a measurement that will not run. A render that returns an error, a check that
answers nothing, a tool that used to work on this object and now does not. It
feels like the work got harder, and the tempting conclusion is that the scope
was underestimated.

**It was not. A failing instrument never changes the size of the scope.** The
size answers a question about the work — how many objects it touches, how much
surface it exposes — and a defect in the environment answers none of that. What
the failure changes is only whether the floor for this object can be met by
another route.

**First, check the failure is not a regression of your own change.** This comes
before anything else, because the two look identical from the outside: a
serialization error can be the environment's limit, or it can be a structure the
expression you just wrote does not serialize. Any one of these three settles it:

- an earlier clean measurement of the same object in the same scope, taken
  before the write;
- the same failure reproduced **without** your change, against the previous
  version of the expression;
- the same failure observed on **another object of the same family**.

If none of them can be had, the doubt resolves towards the expensive side: the
scope closes `closed-pending-human`, never `closed`.

**Then look for the evidence by another route — once for each thing the broken
instrument was buying.** This is the step people collapse, and collapsing it is
what makes a floor look met when it is met in part. One instrument rarely buys
one guarantee: rendering an interface buys partial behaviour, the populated ≠
empty inequality, and automatable accessibility, all at once. Running its test
cases instead answers for behaviour and produces no tree, so it does not answer
for accessibility. Treat them together and you will certify something nobody
measured.

For each of them, in this order, stopping at the first that works:

1. **another surface or route of the same instrument**,
2. **another instrument that answers the same question** — for an interface,
   running its test cases,
3. **a test case created inside this same scope**.

**Then resolve what is left.** Whatever was covered closes normally. Whatever
was not closes as `NOT_MEASURED` / `REQUIRES_HUMAN`, well formed — with an owner
and the condition that closes it — and the scope finishes as
`closed-pending-human` **while still being `micro`**. That is the floor of the
staircase, and it is a real ending: the work is done, it is recorded, and one
named thing is waiting on a person. Nothing about it escalates.

Two things that are not instrument failures and should not be treated as one:

- **A clean empty render is a well-made empty state**, not a measurement that
  did not happen. An empty tree with no recognised signatures is legitimate as
  long as the populated half of the same pair measured, and the empty half
  carries an empty-state message or a non-empty text node. Read it the other way
  and the better your empty states are, the more ceremony they cost.
- **A read that failed is not a write that failed.** The register that records
  writes records writes.

### The three ways out, and none of them is "give up quietly"

Every scope ends one of three ways, and a person is shown all three rather than
being steered to the first:

- **Close.** Go through the checks and finish — including finishing as
  `closed-pending-human` or `closed-with-debt`, which are endings and not
  failures.
- **Abandon,** with a reason. The reason is the whole point: an abandoned scope
  with a recorded reason is a decision, and one without is an absence.
- **Desist.** Leave it as it is. Nothing is undone, nothing is claimed.

**Debt is what a close leaves behind, and it is never anonymous.** Anything left
pending carries an **owner** and the condition that closes it, written to
`evidence/deferred-debt.jsonl`. Debt without those two is not debt, it is a gap:
nobody can tell whether it still applies, so it survives forever. Session start
announces the open ones, which is what stops a deferral from being a way of
never dealing with something.

### What to record while you wait for a fix

In your own project's evidence, never in the plugin:

- what the harness claimed,
- what you did instead, and
- **the version it happened on**.

The third is the one people skip, and it is the one that matters. Without it a
workaround outlives its cause: nobody can tell whether it is still needed, so it
stays forever.

### Which version is actually running?

The line this plugin writes at session start begins with it — `appian-harness
<version>: …`. That is the **loaded** version, which is not the installed one:
the component inventory is fixed when the process starts, so an update applies
only after a restart, and a plugin can be installed, enabled and validated while
the running session has never heard of it. Every check on disk can be green
while the answer to "is the fix in?" is no.

To update:

```
claude plugin marketplace update <marketplace>
claude plugin update <plugin>@<marketplace>   # qualified; the short name is not found
```

then **restart Claude Code**. The marketplace is a git clone of the published
repository, so a fix that has not been pushed cannot arrive this way.

### Reporting

<https://github.com/raulogm077/appian-harness/issues>

Include the version from the session-start line, the hook's message verbatim,
and the relevant lines of whichever register looks wrong
(`evidence/operations.jsonl`, `evidence/deferred-debt.jsonl`,
`evidence/gate-decisions.jsonl`). Those three are usually enough to locate a
hook defect without any access to your project.
