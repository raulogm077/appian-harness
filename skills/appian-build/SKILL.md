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
3b. **Audit the design — still before any write.** Dispatch
    `appian-practices-auditor` with `phase=design`, handing it this task's id,
    its contract, and the design being proposed. Its verdict lands at
    `<evidenceDir>/<task-id>/practices-design.json`, where `evidenceDir` is the
    project's evidence root from `.claude/appian-harness.json` at the project
    root — `evidence` when that file names none. That is the exact path the
    scope gate opens. If the verdict does not come back `PASS`, or
    `NOT_MEASURED` with a `notMeasuredClass` of `DEFERRED` carrying an `owner`
    and a `closingCondition`, **stop and report.** Those are the only two
    outcomes the gate accepts, so continuing produces a blocked write and a
    confused reader rather than progress. This precedes the build instead of
    following it because a design audit run after the object exists is a
    review: it arrives when the only remaining choices are to keep something
    known to be wrong or to rebuild it, and rebuilding costs more than
    deciding first.
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

## The design audit comes before the first write

Step 3b exists because this is the last moment where changing the answer is
still free. That audit judges whether this is a *good* way to solve the
problem — component choice, interaction pattern, the shape of the data model —
which is a different question from whether the platform is willing to run it.
Asked before the first write, its findings change a decision. Asked after, the
same findings are a review of something already paid for.

Nothing else produces that verdict. `appian-verify` dispatches
`phase=implementation` and `phase=qa` and scopes `design` out on purpose;
`appian-review` owns `phase=review`. If this skill does not dispatch the design
audit, no one does, and the gate's design check has nothing to read.

"Comes back PASS" is two conditions rather than one, because that is what the
gate checks. The verdict has to be structurally valid — every entry in its
`referencesApplied` resolving to a real file and a real heading, so a fabricated
citation fails exactly like a missing file — **and** its outcome has to be one
the gate accepts. Validating the verdict is the auditor's own last step; if the
validator exits nonzero, the audit is not finished and this task has not passed
anything. The gate also needs to resolve this plugin's root to run that
validation, and asks rather than allowing when it cannot.

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
audited, not to approve around the prompt. Step 3b is what has it audited.

The gate logs every question it asks — task, tool and reason — and the write log
records what actually got written afterward. Read together, they turn "do we
usually say yes to this prompt" into something measurable instead of a guess. If
the answer usually is yes, that is not evidence the gate is too strict; it is
evidence the contract needs to be split smaller at plan time, not approved around
at build time.

## The active task, written where the gates can read it

The gates enforce against a file, not against what this skill happens to know.
Its path is `activeTaskFile` in `.claude/appian-harness.json` at the project
root — `tasks/current.json` when that file names none — and keeping it current
is this skill's job, because this skill is what takes a task and what stops.

**When step 1 takes a task, write that file.** At minimum it carries two
fields, spelled exactly like this — the hooks look for these names and nothing
close to them, and a field name that nearly matches fails the same way a path
that nearly matches does:

```json
{
  "id": "<the task id>",
  "allowedObjects": ["<object>", "..."]
}
```

`id` is also what the verdict path is built from, so it has to be the same
string the design audit was dispatched with:
`<evidenceDir>/<id>/practices-design.json` is one path assembled from two
places, and they have to agree. `allowedObjects` is the contract's list,
written the way the write call will actually name each object — the gate reads
the target out of the tool's own arguments and compares strings, so an entry
that describes an object instead of naming it never matches.

**When step 7 stops, clear that file — delete it.** A stale active task is
worse than no active task: the next write is measured against the previous
task's contract, and allowed or questioned on grounds that have nothing to do
with it, while everything still looks like it is working.

Absence is not a lockout, and three cases differ:

- **No `.claude/appian-harness.json` at all** — every hook allows, approves or
  no-ops. That file's presence is the activation switch, so a project that has
  not adopted the harness is never blocked by it.
- **Config present, active task file absent** — the scope gate asks, naming the
  missing active task among its reasons. It does not refuse.
- **Active task file present but unreadable** — fail closed, which here also
  means ask rather than deny.

This file is not the plan's operational state, and the two must not grow into
each other. The operational state is written for a person: which task is
active, what is next, what is blocked. The active task file is the
machine-readable statement of which single task is in flight right now, written
by this skill when it takes one and removed when it stops. They name the same
task while a build is running, and that is fine — they are still different
artifacts, rewritten by different steps at different moments, and the one the
gates open cannot carry a queue.

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
- *"I'll get the design audited once there's something to look at."* Then it is
  not a design audit any more, it is a review: by the time there is something
  to look at, the decision it was supposed to inform has already been paid for
  in objects that exist. Waiting also guarantees the first write is stopped,
  because that verdict is what the scope gate opens before letting it through.
- *"I know which task I'm on, writing it to a file is bookkeeping."* The gates
  cannot read what this skill knows; they read the active task file. Skipping it
  does not make the build faster, it makes every single write ask.

## Red Flags

- Writing to the environment without having run the preflight classification.
- Issuing the first write with no `phase=design` verdict for this task, or with
  one whose outcome the gate does not accept.
- Taking a task without writing the active task file, or leaving it pointing at
  a task that already stopped.
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
- `appian-practices-auditor` ran with `phase=design` before the first write, and
  its verdict at `<evidenceDir>/<task-id>/practices-design.json` came back
  `PASS`, or `NOT_MEASURED` with `notMeasuredClass` `DEFERRED` and both an
  `owner` and a `closingCondition` — anything else stopped the build.
- The active task file was written when this task was taken, carries this task's
  `id` and its `allowedObjects` under exactly those names, and was deleted at
  STOP rather than left behind.
- Nothing outside `allowedObjects` was created, modified, or deleted.
- Every gate in `requiredGates` has a recorded result — PASS, FAIL, or NOT
  MEASURED with a reason — not silence and not an assumed PASS.
- Everything created or changed is recorded in `evidenceFile` with the real
  identifiers the environment returned, not the names the plan used to describe
  them.
- Any deletion, record-data deletion, mapped-field removal, or package import
  along the way was preceded by explicit user confirmation, not inferred.
- The invocation ended at STOP, with no attempt to pull in the next task.
