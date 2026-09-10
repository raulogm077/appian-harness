# Using the harness, end to end

> Part of the [appian-harness](../README.md) documentation.

This document follows one piece of work all the way through. The shorter ways in
are described where somebody first looks, in [Which path is
yours](../README.md#which-path-is-yours): advice with nothing adopted, which
needs no configuration and no MCP server, and one small change, which is most of
what anyone does. They are not lesser versions of what follows; they are the
right answer to a smaller question, and reaching for this page when one of them
fits is how a harness earns a reputation for getting in the way.

## How it is used, end to end

<figure>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/task-lifecycle-dark.svg">
    <img src="assets/task-lifecycle-light.svg" width="880"
         alt="One scope end to end: the size is decided and announced, permission is asked once, the work is built, a reviewer certifies it when the lane bought one, and the Stop hook writes the outcome. Three ways out are shown: close, abandon with a reason, and desist.">
  </picture>
  <figcaption>One scope, end to end. The size is announced before anything
  opens; permission is asked once; and the outcome is written by the hook, which
  is the only thing that can write it.</figcaption>
</figure>

**Everything starts at `appian-build`.** It is the only entry point, and the
first thing it does is decide what this is and say so.

### 1. It routes, in one line you can contradict

Three rules, and they are all you have to understand to use it:

1. The sentence names a **business entity that does not exist yet** as a record
   type → the specification phase runs first.
2. It names one and **it already exists** → this is a `task`.
3. It only touches **existing objects that qualify as small** → this is a
   `micro`.

The classification is announced **before the scope opens**, in one line naming
the size, the objects and whether this lane buys a reviewer. That line is the
cheapest place in the whole cycle to disagree with the harness, and it is put in
front of you on purpose.

### 2. Two sizes, and no third

| | What it is | What it carries |
|---|---|---|
| **`micro`** | One object, one intention | One sentence saying what the intention is. No task list — a scope that partitions is a `task` |
| **`task`** | Everything else | Optionally a partition: which objects belong to which subtask |

**There is no magnitude threshold.** Redesigning a whole 1,700-line interface is
one object and one intention, so it is a `micro`. What graduates the ceremony is
*what* changes and *how many objects*, never how much text was replaced — the
write tool replaces all of it every time, so a line count measures the
instrument rather than the work.

**Some things are never `micro`.** A record type is not, whatever its apparent
size. Nor is anything the harness reads as touching security, data, or something
irreversible: that raises the risk, and raised risk forces a `task` and adds an
adversarial pass asking *how does this fail* rather than *does this meet the
contract*. You do not declare that — **the hook observes it** from what the
scope actually touches, which is the point: a level you declare is a level you
can understate.

### 3. Permission, once

**One prompt per scope**, carrying the full list and what is going to happen to
each thing — created, updated, deleted. Not one per object, and not one per
write.

The grant is anchored to the opening it was given for. Editing the scope
afterwards invalidates it entirely rather than quietly widening it, and the only
thing that can extend it is the hook — at most once, and only for a remediation
cycle. If you find yourself spending that extension often, the defect is in the
preflight, not in the threshold.

**Anything irreversible asks anyway.** A deletion, a process start: no grant
covers those, because a grant is permission for a plan and those are the steps a
plan cannot take back.

### 4. It builds

Before the first write it **preflights** against the real environment, reading
every object in scope and classifying it — absent, present and conforming,
present but incomplete, conflicting. The remote state wins over any local
document, always: this artifact lives on a server you do not own alone.

Then it writes, and the hooks do four things around each write:

- the **scope gate** fires before it, and the strongest thing it ever says is
  *ask* — never *deny*;
- the **write log** records what was written, to which object, and whether the
  environment reported it as done, failed, or something the harness cannot
  classify. That third answer is not a pass: it forces a re-read;
- a write that errors triggers a **failure notice**: do not retry blind, read
  back whether it persisted;
- the **read observer** credits the verification reads it sees, tying each to
  the write it came after. A check taken *before* the write it would vouch for
  does not count.

### 5. The floor, which is not a phase you invoke

There is no verify step to remember. What a change has to clear is decided by
**what kind of object was touched**, and the closure gate enforces it from what
the hooks observed — not from what anyone reports.

An interface has to be re-read and rendered, populated and empty. An expression
rule has to run its test cases. A process model has its node graph checked. A
record type has to return rows. A deletion is certified by the object being
**absent afterwards**. Most other types buy a re-read and nothing more, and
saying so is more honest than implying otherwise. The whole table, and what each
row is worth, is in **[the gates](gates.md)**.

Two properties of the floor are worth knowing before you meet them:

- **A check nothing could have invalidated is not repeated.** A write to an
  object outside this scope does not expire this scope's checks, and neither
  does a change that could not alter behaviour — a description, for instance —
  even on an object published in a site.
- **A failing instrument never changes the size of the scope.** If a test render
  answers with a 500, the harness first checks that the failure is not a
  regression of the change itself, then looks for evidence by another route. If
  there is none, the scope finishes **waiting on a person** — while still being
  a `micro`. What it does not do is become bigger because a tool broke.

### 6. Certifying, when the lane bought a reviewer

A reviewer is bought by **what** changes, not by how much:

| Change | Reviewer? |
|---|---|
| A label, a format, a piece of text | No |
| A filter, a `showWhen` — anything altering what data is shown or who sees it | Yes |
| Anything on a screen reachable from a published site | Yes — and the work does not get bigger for it |

`appian-review` dispatches the judge with **the artifact and the contract, never
the builder's conclusion**, and never with a dump: a verdict cell that imports a
check names the row it came from, not the row's contents.

If findings come back, the remediation loop is **one batch and one
re-certification** — not a verdict per fix. It is capped at three, and a third
verdict bringing no new finding is rejected by the validator rather than accepted
as diligence.

**Not every finding blocks.** Gates are cardinal, recommended or contextual, and
only cardinal ones stop a close. Maintainability and performance are worth
knowing and are not worth a loop nobody finishes.

### 7. The hook closes it

`appian-review` writes a **request** to close. It does not close anything.

That distinction is the whole of how 0.7 keeps its outcomes honest: **the hook
is the only writer of the outcome, it signs what it writes, and any state that
turns up unsigned is reverted.** Editing the file by hand to say the work is
finished, or suspended, approves nothing.

There are seven outcomes and three of them are ways out you choose:

| | What it means |
|---|---|
| **Close** | Everything the floor asked for is there. Finished |
| **Finish waiting on a person** | Something only a person can settle — a screen reader, a real login per role — with a **named owner** and the condition that clears it |
| **Finish with debt** | The remediation cycles ran out. Recorded, owned, and announced at the start of the next session |
| **Abandon** | You are stopping, and you say why |
| **Desist** | Leave it as it stands |
| **Suspend / resume** | Park this to do something else. The grant does not live forever: come back too late and it is declared dead rather than silently honoured |

**Debt is never a shrug.** It carries an owner and the condition that closes it,
and the next session opens by telling you about it.

## Coming from 0.6

Work that was already open when you upgraded **closes under the rules it was
opened with** — the hooks keep the old rulebook for exactly that. You cannot open
new work while it is there, so finish or abandon it first.

**`/appian-init --adopt` is the one migration step that is not optional.** A
project that never re-runs it does not acquire the declared perimeter, falls back
to matching MCP servers by name, and lands in the failure mode 0.7 exists to
close. Until it is run, session start says so and the first write of each session
asks.

`activeRunFile` and `leaseFile` belong to that old rulebook. On anything opened
today they have no effect at all, and `/appian-init` no longer writes them.
`leaseFile` returns in a later release, with the parallelism recipe that would
give it something to do.

## Building several things at once

More than one builder can work at a time, and the isolation people reach for
covers the wrong half:

> **A git worktree isolates files. It does not isolate Appian.** Two builders in
> two worktrees calling `createRecordType` write to the same environment.

In 0.7 parallelism is **doctrine, not machinery**: judges are dispatched at the
same time rather than one after another, and nobody sits in a loop waiting on a
file. The lease register that would make concurrent *writers* safe is deliberately
not part of this release — it has no consumer until the full recipe exists, and
shipping half of it would look like coordination.

What you can do today is prove that a plan's tasks are genuinely independent
before you split them up. `scripts/parallel_safety.py` reads the plan's
`allowedObjects` and `dependsOn` and refuses on shared objects, on dependencies
**including transitive ones**, on anything destructive, and on objects everything
quietly depends on:

```
# partition the whole plan
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_safety.py" PLAN_JSON

# check one proposed group
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_safety.py" PLAN_JSON --group T-3,T-5
```

Exit `0` clean, `1` findings, `2` usage, `3` NOT MEASURED — and 3 is not a pass.
The transitive case is the one worth knowing: T-1 ← T-2 ← T-3 has no direct edge
between T-1 and T-3, and they are still not independent.

Reviewers and researchers stay read-only regardless. Concurrency here is for
multiplying perspectives and independent slices, never for multiplying writers on
one object.

## What the closure gate does not reach

Its reach is exactly the window in which a scope is open. A stop with nothing
open approves without opening a verdict, by design.

What 0.7 changed is that leaving that window early is no longer something the
agent can do by deleting a file. The hook is the only writer of the outcome, it
signs what it writes, and unsigned state is reverted — so a scope that vanished
without finishing is a scope that reverts, not one that quietly counted as done.
