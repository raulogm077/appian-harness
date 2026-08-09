---
name: appian-build
description: Implements exactly one approved task against an Appian environment and stops. Use when the next pending task from the plan is ready to be built. Use before any create or update call against a live Appian environment, because it establishes the preflight and the scope contract that the verification step depends on.
disable-model-invocation: true
argument-hint: "[task-id]"
---

## Overview

This is the build phase, and the only skill in this set with real, irreversible
side effects: it writes to a live Appian environment that other people may also
depend on. Everything about its shape follows from that one fact.

It takes a single task — already broken down and ordered by a planning step — and
either builds it or stops and explains why not. It does not plan, and it does not
chain multiple tasks together. One invocation, one task, one stop.

Because writes here cannot be undone by editing a local file, this skill produces
and consumes **the task contract**: the explicit boundary of what one task is
allowed to touch, what proves it is done, and what evidence has to exist before it
is handed off. The contract is written down rather than held in the executor's
head so that whatever picks the task up next — a verification step, a reviewer, a
person — reads it instead of re-deriving it from the work that was done.

## When to Use

Use this skill when a task has already been planned — it has objects in scope,
acceptance criteria, and required gates — and the next thing to happen is real
work against the environment. Use it before issuing any create or update call
against a live Appian environment: skipping straight to the write means skipping
the preflight and the scope contract that everything downstream depends on.

This skill only runs when invoked by name with a task id
(`disable-model-invocation: true`); it does not trigger itself, because it has
side effects the user did not necessarily ask for in that exact moment.

## Core Process

1. Read the operational state; take **one** task.
2. Read its contract: objects in scope, acceptance criteria, required gates.
3. **Preflight — before any write.** Inspect the real environment and classify
   every object in scope:
   - **ABSENT** — create it.
   - **PRESENT AND CONFORMING** — do not recreate it.
   - **PRESENT BUT INCOMPLETE** — change only what is missing.
   - **CONFLICTING** — stop and report.
   The remote state wins over any local document. This replaces the clean-tree
   check that version control gives you elsewhere: here the artifact lives on a
   server you do not own alone.
4. Implement, using `appian-best-practices` for the domains the change touches.
5. Local verification.
6. Record what was created or changed, with real identifiers.
7. **STOP.** Do not continue to the next task.

## The Task Contract

A task is not "built" from a description alone — it is built against a written
contract with four parts. Where this contract lives is project configuration,
not something this skill hardcodes; if the project has not said where its plan
and operational state live, ask rather than guess a path.

- **`allowedObjects`** — the exhaustive list of objects this task may create or
  modify. Anything else, however related it looks, is out of scope for this
  invocation.
- **`acceptanceCriteria`** — an observable statement that proves the task is
  done. Not "the interface was created" but what a reviewer can check without
  trusting the executor's word for it.
- **`requiredGates`** — the checks that must produce a result, one way or
  another, before this task can be handed off.
- **`evidenceFile`** — where the real identifiers and gate results for this task
  get recorded, so the next step in the pipeline reads a record instead of
  re-deriving one.

The contract is written in these four names deliberately: it is meant to be read
by a verification step, a review step, and a scope-enforcement hook, none of
which should have to re-derive it. If any of the four parts is missing before
step 3 begins, that is itself a reason to stop: building against an incomplete
contract just moves the missing decision to later, where it is harder to catch.

## The scope gate measures the contract, not the write

A `PreToolUse` hook checks every write against the active task's `allowedObjects`
before it reaches the environment. When that list is longer than the project's
configured budget, the gate asks instead of letting the write through.

That prompt is not the hook being obstructive. It is measuring the same thing
`appian-plan`'s *One task, one object* names: a task whose `allowedObjects` needs
that many entries to describe was sized wrong before this skill ever started.
Answering "yes, proceed" past the prompt does not fix that — it just carries the
oversized contract into the build.

The same gate asks for one thing the contract does not carry: a `design` audit
for this task that passes, at `<evidenceDir>/<task>/practices-design.json`,
where `evidenceDir` is the project's root from `.claude/appian-harness.json`.
Judging whether this is a good way to solve the problem — before the first
write, while changing the answer is still cheap — is what that half of the gate
protects. Preflight is all reads, so it passes untouched; the stop lands on the
first create or update in step 4, and the way past it is to have the design
audited, not to approve around the prompt.

The gate logs every question it asks — task, tool and reason — and the write log
records what actually got written afterward. Read together, they turn "do we
usually say yes to this prompt" into something measurable instead of a guess. If
the answer usually is yes, that is not evidence the gate is too strict; it is
evidence the contract needs to be split smaller at plan time, not approved around
at build time.

## Stop before anything irreversible

Ask the user before: deleting any object, deleting record data, removing a mapped
field, or importing a package. An update is versioned and recoverable. A deletion
is not, and neither is a dropped column.

Object versioning is not a transactional rollback: reverting an object does not
undo schema changes, data, groups, or the effects of processes that already ran.

## After a failure, never retry blind

On a timeout, tool error or ambiguous result, do not re-issue the write. Check
with a read whether it persisted, record what did and did not, and resume from the
first unverified result. If you cannot determine the state, stop and ask.

## Common Rationalizations

- *"The call timed out, so nothing happened."* A timeout is silence, not a
  negative result. It says nothing about whether the write reached the server
  and persisted before the connection dropped. Read before you decide.
- *"I'm already here, I'll fix this too."* Touching anything outside
  `allowedObjects` invalidates the review of this task, because the reviewer is
  checking the contract, not the diff. A real problem noticed along the way
  becomes a new task for the plan, not a scope change made unilaterally mid-build.
- *"It's the same phase, I'll keep going."* The unit this skill produces is one
  task ending in STOP, not one phase. A phase can contain many tasks; collapsing
  them removes the checkpoint a reviewer needs to reject one without reopening
  the rest.
- *"The local file says it exists, so it exists."* The plan and the operational
  state describe intent, not the current state of the server. Preflight exists
  precisely because local documents drift from remote reality; the remote read
  always wins.
- *"It's broken, I'll delete it and recreate it clean."* Deletion is the
  irreversible half of an asymmetric pair — ask first, always. Recreating an
  object from scratch also throws away its version history, its security
  configuration, and whatever else depends on it, none of which a clean rebuild
  restores.
- *"I can't run that gate here, but the code is clearly correct, so I'll mark it
  PASS."* A gate that was not actually executed is NOT MEASURED, never PASS.
  Confidence in the implementation is not a substitute for the check the gate
  was defined to run.

## Red Flags

- Writing to the environment without having run the preflight classification.
- Recreating an object that preflight already found PRESENT.
- Retrying a write after an error or timeout without first reading back whether
  it persisted.
- Touching an object that is not listed in this task's `allowedObjects`.
- Continuing to a CONFLICTING object instead of stopping and reporting it.
- Closing out the task with a required gate left with no recorded result.
- Starting the next task instead of stopping after this one.

## Verification

Before handing this task off:

- Every object listed in scope was classified in preflight (ABSENT, PRESENT AND
  CONFORMING, PRESENT BUT INCOMPLETE, or CONFLICTING), and no CONFLICTING object
  was written to without stopping first.
- Nothing outside `allowedObjects` was created, modified, or deleted.
- Every gate in `requiredGates` has a recorded result — PASS, FAIL, or NOT
  MEASURED with a reason — not silence and not an assumed PASS.
- Everything created or changed is recorded in `evidenceFile` with the real
  identifiers the environment returned, not the names the plan used to describe
  them.
- Any deletion, record-data deletion, mapped-field removal, or package import
  along the way was preceded by explicit user confirmation, not inferred.
- The invocation ended at STOP, with no attempt to pull in the next task.
