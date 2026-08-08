---
name: appian-plan
description: Breaks an Appian specification into small, verifiable tasks ordered by dependency, each with its own acceptance criteria. Use after a specification exists and before building anything. Use when the next step is unclear, when work is being tracked in one large document, or when tasks span more than one object type at a time.
---

# Appian Plan

## Overview

`appian-plan` takes a specification — actors, entities and relationships, states and
transitions, an authorization matrix, expected volume, and what's explicitly out of
scope — and turns it into work that can actually be built and reviewed one piece at a
time.

It produces two artifacts:

1. **A plan** — a list of small tasks, each scoped to one vertical slice (or a
   coherent fragment of one), ordered by the dependencies the platform actually
   imposes, each carrying its own acceptance criterion.
2. **An operational state** — which task is active right now, which tasks are next,
   and what's blocking progress.

A naming note, since the word "state" does double duty here: when this skill means
the lifecycle of a business entity, it uses the specification's full section name,
"States and transitions," never a bare "state." Everywhere else in this skill,
"state" means the operational state file defined above — the current task, what's
next, and blockers — not entity lifecycle states.

Where those two artifacts live is configuration for the project this skill runs in —
this skill asks where they belong, it never assumes a filename or a directory. What
it does mandate is the *shape* of the content: slices instead of layers, a real
dependency order, and one acceptance criterion per task, written before that task
starts.

A downstream build step reads one task at a time from these artifacts and refuses to
start against an incomplete contract, so a task that can't be understood in isolation
— no scope, no criterion, no gates, nowhere to record what it produced — can't be
built safely either. *What a task needs*, below, names the four parts that step
expects.

## When to Use

- After a specification exists and before any object is created against a live
  environment.
- When the next step in a piece of work is unclear — turning "we need to build X"
  into an ordered list of small, checkable tasks.
- When work is being tracked in a single large document that keeps growing until
  nobody reads it end to end before making a decision.
- When a candidate task would touch more than one object type at once — that's the
  signal to split it before work starts, not after something breaks.

Building itself — writing SAIL, creating record types, running a create or update
call — is a separate step that consumes the tasks this skill produces; it should not
start from a specification directly.

## Vertical slices, not layers

An Appian slice is: **record type → query rule → interface → test case**, for one
piece of behaviour. Not "all record types, then all rules, then all interfaces".

Layer-by-layer construction defers every integration problem to the end, where
defects have already been repeated across every object built the same way.
A slice leaves a coherent part of the system in a valid state.

A plan built layer-by-layer looks organized — it groups similar work together — and
is the wrong shape anyway: nothing is checkable until every layer is finished, so the
first thing anyone can actually verify is the whole system at once.

Not every piece of behaviour is data-shaped. When a specification's *States and
transitions* section defines an entity's lifecycle, the matching slice is
process-shaped instead: **record type → state model → process model → action →
test case**. Both are slices, not layers — each one scopes and verifies one
coherent piece of behaviour end to end, whether that behaviour is queried and
displayed or driven through an entity's lifecycle.

## The dependency order Appian imposes

A generic planner orders work by convenience: biggest risk first, easiest first,
whatever the backlog tool sorts by. Appian's platform imposes an order of its own,
and a plan that ignores it produces tasks that cannot be executed in the sequence
written:

1. **The data source before the record type.** A record type is built on top of a
   data source (a table, or another record type); there is nothing to wrap until the
   source exists.
   Source: [Choose a Data Source for Your Record Type](https://docs.appian.com/suite/help/latest/configure-record-data-source.html)
2. **The record type before any query against it.** A query rule, a report, or an
   interface that reads record data can't be authored against fields that don't
   exist yet.
3. **Constants and rules before the interfaces that call them.** An interface that
   references a rule or constant that doesn't exist yet either fails to save, or
   fails once that reference is actually evaluated at run time — an unresolvable
   reference can't resolve to nothing and quietly work (field experience: this
   doesn't conflict with item 5 below — a reference inside a loop body over an
   empty list is never evaluated in the first place, so it stays silent instead).
4. **The objects before the security that protects them.** Record-level and
   field-level security are configured on top of an existing record type and
   existing fields; there is nothing to secure until the object is there.
   Source: [Field-Level Security](https://docs.appian.com/suite/help/latest/field-level-security.html)
5. **Test data before any screen with a list can be considered tested.**
   `a!forEach()` — and anything built on it, including grids and repeating layouts —
   returns an empty list and never evaluates its expression when the input is null
   or empty. A broken loop body passes every test run against empty tables; the
   defect only surfaces once rows exist to iterate over.
   Source: [a!forEach() Function — Using the items parameter](https://docs.appian.com/suite/help/latest/fnc_looping_a_foreach.html#usage-considerations)
6. **Entity lifecycle states and transitions, and the record type, before the
   process model.** A process model that drives an entity through its lifecycle
   enacts transitions the specification's *States and transitions* section already
   settled, and writes each change into that entity's record type; there is
   nothing to enact and nowhere to persist it until both exist (field experience).

A plan that lists tasks without this order can look complete and still not be
buildable in the sequence it's written.

## Two artifacts, not one: plan and state

A plan is written once and approved: the tasks, their dependencies, and their
acceptance criteria don't change because work started. State changes with every task
that closes: which one is active, which are next, what's blocking.

Merging the two into a single document makes both untrustworthy. A "plan" that a
task's status edits every hour is not something anyone can review and sign off on
once. A "state" that also carries the full task history and every acceptance
criterion grows without bound until nobody reads it before making a call.

Keep them separate:

- **Plan** — tasks, their dependencies, their acceptance criteria. Written once,
  changed only by deliberately re-planning.
- **State** — the current task, the ordered list of what's next, and any blockers.
  Rewritten every time a task closes or a blocker appears.

**Where they live is project configuration, not something this skill decides.** Ask
the project — or whoever is driving it — where the plan and the state file belong
before writing either one. Don't default to a specific filename or directory: a
convenient default silently becomes the convention the next project inherits without
anyone choosing it.

## What a task needs

Every task in the plan carries, at minimum, the four parts of the **task contract**
the build step consumes:

- **`allowedObjects`** — the exhaustive list of objects this task may create or
  change. Anything else, however related it looks, is out of scope for that task.
  A task that spans a record type, an interface, and a security configuration in one
  entry can't be reviewed or rejected as a unit; split it along the slice boundary.
- **`acceptanceCriteria`** — an observable statement that proves the task is done,
  written before any of the task's objects exist. Not "the interface was created,"
  but something a reviewer can check without trusting the builder's word for it —
  see *Common Rationalizations* below for why writing it first matters.
- **`requiredGates`** — the checks that must produce a result, one way or another,
  before the task can be handed off. Whatever verification the project requires.
  For anything touching record-level or field-level security, that gate has to
  include logging in as a user of each affected role: the design-time preview does
  not apply that security, so it cannot be the evidence a task is done.
  Source: [Field-level security in Appian Designer](https://docs.appian.com/suite/help/latest/field-level-security.html#main_content)
- **`evidenceFile`** — where this task's real identifiers and gate results get
  recorded, so the steps after build read a record instead of re-deriving one.
  Like the plan and the state, **where it lives is project configuration**: ask
  where evidence belongs rather than defaulting to a path.

Use those four names literally. The build step looks for exactly them, and a task
that describes the same four things in its own words still has to be translated by
whoever picks it up — which is the point at which one of them quietly goes missing.

Separately, and not part of the contract, every task needs **a place in the
dependency order**: which earlier tasks must close first, following the platform
order above. That one is a planning concern — it governs the sequence tasks are
written in, not what a builder is handed for any single task.

Both questions the contract answers — what this task may touch, and what "done"
means for it — should be answerable by reading the task on its own, without pulling
in the rest of the plan for context.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "I'll write the acceptance criteria when I get there" | Without a criterion fixed in advance, the criterion silently adjusts itself to whatever got built. There's nothing independent left to check the work against, and "done" becomes whatever the builder decided it was. |
| "This task is small enough to merge with the next one" | A task is the unit a reviewer can reject on its own. Merge two, and rejecting one part means unwinding both — even the part that was fine. |
| "We'll sort out the order once we start building" | The dependency order is what makes the plan executable in sequence, not a nicety. Sorting it out mid-build means discovering a query rule was scheduled before its record type only after the write already failed. |
| "Layers are more efficient — all the record types, then all the rules, then all the interfaces" | Layer-by-layer defers every integration problem to the end, where the same mistake has already been repeated across every object built the same way. A slice surfaces it once, in a system that's still in a valid state. |
| "The plan and the state are basically the same file, why keep two" | A plan that changes shape every time a task closes is not something anyone can review and approve once. Merge them and either nobody can tell what was actually approved, or the state stops being updated because touching the plan feels heavier than it should. |
| "The interface already works, we can add the security task later" | Working with security absent is not evidence it will work with security applied — field-level security changes what a component receives, not just who can view the screen, and it isn't enforced in the design-time preview. |
| "This task is too small to need its own gate" | A gate that only exists for large tasks means small tasks accumulate unverified changes until one of them turns out not to be small. |

## Red Flags

- A task with no acceptance criterion of its own — it can't be reviewed
  independently.
- A task with no `evidenceFile` — the build step has nowhere to record the real
  identifiers it created, so the next step re-derives them from the environment and
  the plan quietly becomes the only record of what was supposed to happen.
- A task that touches three or more object types at once (for example, a record
  type, an interface, and a process model in a single entry).
- A plan with no dependency order — tasks are listed, not sequenced against what
  the platform requires to exist first.
- Plan and state living in the same file.
- A plan ordered by object type ("all record types, then all rules, then all
  interfaces") rather than by slice.
- A task whose acceptance criterion only confirms the object was created, with no
  reference to the behaviour it's part of.
- A security task with no dependency on the objects it protects, or dropped from the
  plan because "the interface already works without it."
- A list, grid, or repeating-layout task marked ready to close without a dependency
  on the test-data task that populates the tables it reads.
- An entity lifecycle state that reached the plan with no defined transition in or
  out. `appian-specify` already flags this at the specification stage; accepting
  it into the plan without a second check just defers the same gap to build.

## Verification

Before treating a plan as ready to build against, confirm:

- [ ] Every task carries all four contract parts under those names —
      `allowedObjects`, `acceptanceCriteria`, `requiredGates`, `evidenceFile` — not
      three of them, and not the same ideas under different names.
- [ ] Every task has an acceptance criterion, written in the plan itself — not
      deferred to when the task starts.
- [ ] Every task names where its evidence gets recorded, and that location is
      recorded as project configuration rather than assumed.
- [ ] Tasks are ordered by dependency, following the platform order above (data
      source → record type → query → rule/constant → interface → security →
      verified with test data), not by convenience or by object type.
- [ ] Each task is scoped to one vertical slice, or a coherent fragment of one — not
      several unrelated object types bundled together.
- [ ] The plan and the operational state are two separate files, and both paths are
      recorded as project configuration, not assumed.
- [ ] The state file names exactly one current task, the ordered list of what's
      next, and any known blockers.
- [ ] Any task involving a list, grid, or repeating layout depends on a task that
      populates the tables it actually reads — not just the tables it's named after.
- [ ] Any task involving record-level or field-level security has a gate that
      requires signing in as a user of each affected role, not just a design-time
      preview.

If any box doesn't check, the plan isn't ready. Fix the plan itself before building
starts — don't patch a bad plan task by task while building is already underway.
