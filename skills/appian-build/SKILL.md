---
name: appian-build
description: Implements exactly one approved task against an Appian environment and stops. Use when the next pending task from the plan is ready to be built, either invoked by name or as a step inside an authorized run. Use before any create or update call against a live Appian environment, because it establishes the preflight and the scope contract that the verification step depends on.
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

## Which lane this is, before anything else

Two rulebooks are live at once, and the scope file says which one applies: a scope
carrying `"schemaVersion": 2` is governed by the 0.7 state machine, and a scope
without that field by the 0.6 rules it opened under. **A v2 scope with
`"kind": "micro"` is described in full by
[`references/micro-lane.md`](references/micro-lane.md) — read that file and stop
reading this one.** It is the whole contract: seven steps, two templates, and what
each gate actually checks. Where the two disagree, it wins for a micro; the rest of
this file is written for the wider lane and for 0.6 scopes, and following it in a
micro buys a design audit and two post-write phases that no gate in that lane will
ever open.

Everything a micro genuinely owes is in that file. Do not rebuild the contract by
reading `hooks/harness_hooks.py`: a measured run spent five minutes doing exactly
that, for a contract that fits on one page.

## What authorizes a write

This skill used to carry `disable-model-invocation: true`, so it could only
start when a person typed its name. The intent was right — no spontaneous
writes the user did not ask for — but the mechanism put the human gate on
*starting each task*, which decides almost nothing, and a twenty-task plan cost
twenty interventions that were not decisions.

Authorization is now **per run rather than per invocation**, and it is checked
rather than assumed:

- **Invoked by name with a task id** — the user is asking for this task. Build it.
- **Inside an authorized run** — a project that configures `activeRunFile`
  records who granted the run, which tasks it covers and its budget there. The
  scope gate refuses a write from a task outside that list, or once the budget
  is spent. The key is opt-in and inert when absent.
- **Neither** — if the project configured `activeRunFile` and there is no run,
  every write asks. Stop and say so instead of approving past the prompt.

**No authorization ever covers the irreversible.** Deleting an object, deleting
record data, removing a mapped field or importing a package prompts regardless
of any run — see *Stop before anything irreversible*. A grant that quietly
included deletions would be a master key, which is the opposite of what
granting a run is for.

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
3a. **Open and sign the new scope — with `Write`, and before this task puts
    anything else on disk.** Preflight has just read the real identifiers back,
    so this is the first moment the contract can be stated in full: write
    `activeTaskFile` in the shape its rulebook requires (*The active task,
    written where the gates can read it*), and let the `PostToolUse` state gate
    observe that write and sign the opening.

    **Nothing belonging to this task is written under `<evidenceDir>/<task-id>/`
    until that signature exists.** The evidence log files every write it records
    against whichever id `activeTaskFile` names at that instant, so a load
    record, a SAIL source or a read-back saved while the file still names the
    previous scope is attributed to a task that already closed. Measured in
    P2-PASADA-9: two SAIL sources of the new task were recorded under
    P2-PASADA-8, because they were written before the scope was. Preflight is
    exempt because it is all reads and files nothing.

3b. **Load the official Appian skill — before the design audit and before any
    write.** [`appian/dev-mcp-skills`](https://github.com/appian/dev-mcp-skills/)
    carries what the MCP tool schemas cannot: naming conventions, the fact
    that a relationship has to be declared on both sides, the order objects
    must be created in, and real UUIDs as against invented ones. **None of
    that is anything this plugin's gates measure** — they check the
    contract, atomicity and the presence of a verdict — so a write issued
    without it fails in exactly the way nothing here would catch. It comes
    before 3c because domain knowledge is what a good design decision is
    made *with*; a design audited without it was audited against the wrong
    thing.

    **Load it to the depth this scope needs, and no further.** Its own
    loading strategy asks for seven universal files — about 198 KB, near
    50.000 tokens — for any Appian work at all. Paying that for a `micro`
    over one constant is ceremony; never paying it leaves the guarantee
    hollow. So:

    | Size | What you open |
    |---|---|
    | `micro` | Its `SKILL.md`, plus **the domain reference for the object you are touching**. And `confirmation-patterns.md`, always, on any deletion |
    | `task` | Its `SKILL.md`, plus the full universal block, plus the domain — **once per scope**, not once per object |

    Depth is bought once and reused. Re-opening a reference you already read
    in this scope buys nothing and is charged twice.

    **Do not write a load record.** The hook writes
    `<evidenceDir>/<task-id>/appian-skill-loaded.json` from what it observed
    — the skill invocation and the reads under the skill's root — and its
    `referencesLoaded[]` is the list of files you actually opened. That is
    the point: the old record was three fields any agent could type without
    opening a thing, and it caused 97 of 116 measured `ask`s buying a
    guarantee that a JSON had three keys. What the hook could not observe is
    marked as declared, never as verified.

    One consequence worth knowing: the official skill's
    function-availability checks depend on the documentation MCP, and
    without it they return empty — and **empty reads as "the function does
    not exist."** If this session has no documentation MCP, stop and say so;
    do not write on an unverified function.

3c. **Audit the design — still before any write, when this scope owes one.**
    A 0.6 scope always owes it. A v2 scope owes it when it is a **`task`** that
    creates an object or touches data structure, security or a process model;
    a v2 **`micro` never owes it**, and the gate returns early for it, so an
    audit dispatched there is twelve minutes nobody will read. Where it is
    owed: dispatch
    `appian-practices-auditor` with `phase=design`, handing it this task's id,
    its contract, and the design being proposed. Its verdict lands at
    `<evidenceDir>/<task-id>/practices-design.json`, where `evidenceDir` is the
    project's evidence root from `.claude/appian-harness.json` at the project
    root — `evidence` when that file names none. That is the exact path the
    scope gate opens. If the verdict does not come back `PASS`, or
    `NOT_MEASURED` with a `notMeasuredClass` of `DEFERRED` carrying an `owner`,
    a `closingCondition` and a `deferredCriterion` off the plugin's closed
    list, **stop and report.** Those are the only two
    outcomes the gate accepts, so continuing produces a blocked write and a
    confused reader rather than progress. This precedes the build instead of
    following it because a design audit run after the object exists is a
    review: it arrives when the only remaining choices are to keep something
    known to be wrong or to rebuild it, and rebuilding costs more than
    deciding first.
4. Implement, using `appian-best-practices` for the domains the change touches.
5. Local verification.
6. Record what was created or changed, with real identifiers.
7. **STOP.** Do not continue to the next task, and leave the active task file
   in place — the task is still in flight until it is verified and reviewed.
   Hand control back to whoever started this. **Stopping is a handoff, not a
   close**, and the unit
   this skill produces is one task ending in a stop — never one phase, and
   never two tasks. That does not change inside a run: a run means fewer
   keystrokes between tasks, not bigger tasks.

### The order those steps happen in, stated once

Read-only preflight → **open and sign the new scope** → the evidence this task
owes, starting with its load record → the grant → the Appian writes → the
read-back that verifies them → `"request": "close"` → `closed` at the next stop.

Only the first arrow is free to move. Everything after the opening is filed
against the scope that was signed, so opening it early is what makes the rest of
the sequence attributable at all — and a file this task wrote before the opening
belongs, as far as every log is concerned, to whatever came before.

## The Task Contract

A task is not "built" from a description alone — it is built against a written
contract with four parts. Where this contract lives is project configuration,
not something this skill hardcodes; if the project has not said where its plan
and operational state live, ask rather than guess a path.

- **`allowedObjects`** — the exhaustive list of objects this task may create or
  modify, each entry a **name or a UUID** (see *The active task, written where
  the gates can read it*). Anything else, however related it looks, is out of
  scope for this invocation.
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

## Where a design audit is owed, it comes before the first write

Step 3c names which scopes owe one; a v2 `micro` is not among them, and this
section is about the rest. It exists because this is the last moment where
changing the answer is still free. That audit judges whether this is a *good*
way to solve the problem — component choice, interaction pattern, the shape of
the data model — which is a different question from whether the platform is
willing to run it.
Asked before the first write, its findings change a decision. Asked after, the
same findings are a review of something already paid for.

Nothing else produces that verdict. `appian-review` owns `certify` and `risk`,
and it runs after the writing is done. If this skill does not dispatch the
design audit, no one does, and the gate's design check has nothing to read.

"Comes back PASS" is two conditions rather than one, because that is what the
gate checks. The verdict has to be structurally valid — every entry in its
`referencesApplied` resolving to a real file and a real heading, so a fabricated
citation fails exactly like a missing file — **and** its outcome has to be one
the gate accepts. Validating the verdict is the auditor's own last step; if the
validator exits nonzero, the audit is not finished and this task has not passed
anything. The gate also needs to resolve this plugin's root to run that
validation, and asks rather than allowing when it cannot.

## The scope gate measures the contract, not the write

A `PreToolUse` hook checks every write before it reaches the environment, and it
accumulates every reason it finds rather than reporting the first:

| It checks | And asks when |
|---|---|
| An active task exists | Nothing has been scoped and approved |
| The object is in `allowedObjects` | No identifier in the call matches an entry |
| The task is inside an authorized run | The project configured `activeRunFile` and this task is outside the grant, or its budget is spent. Inert when unconfigured |
| No other task holds the object | The project configured `leaseFile` and somebody else has it. Inert when unconfigured |
| Irreversible actions | **Always**, for a delete or a record-data overwrite — and it names whether the impact assessment exists |
| The task is atomic | The canonical object count of `allowedObjects` — or of a single `tasks{}` entry, when the scope partitions — is over the configured budget |
| The official skill was loaded | No load record for this task, or one that does not match |
| The `design` verdict passes | Missing, structurally invalid, or an outcome the gate does not accept |

The atomicity one is worth dwelling on, because it is the one people argue
with.

That prompt is not the hook being obstructive. It is measuring the same thing
`appian-plan`'s *One task, one object* names: a task whose `allowedObjects` needs
that many entries to describe was sized wrong before this skill ever started.
Answering "yes, proceed" past the prompt does not fix that — it just carries the
oversized contract into the build.

The same gate asks for one thing the contract does not carry, in the scopes that
owe it — every 0.6 scope, and a v2 `task` that creates or touches structure,
security or a process model, never a v2 `micro`: a `design` audit
for this task that passes, at `<evidenceDir>/<task>/practices-design.json`,
where `evidenceDir` is the project's root from `.claude/appian-harness.json`.
Judging whether this is a good way to solve the problem — before the first
write, while changing the answer is still cheap — is what that half of the gate
protects. Preflight is all reads, so it passes untouched; the stop lands on the
first create or update in step 4, and the way past it is to have the design
audited, not to approve around the prompt. Step 3c is what has it audited.

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

**Step 3a is where that file gets written** — after the preflight, so the real
identifiers are already in hand, and before this task writes any evidence of its
own. Which shape it takes depends on
the rulebook the scope opens under, and the two are not interchangeable — the
hooks look for these names and nothing close to them, and a field name that
nearly matches fails the same way a path that nearly matches does.

**Under the 0.6 rulebook** — a file carrying no `schemaVersion` — the minimum
is two fields:

```json
{
  "id": "<the task id>",
  "allowedObjects": ["<object>", "..."]
}
```

**Under scope schema v2 that same two-field file is not a v2 scope.** With no
`schemaVersion` the dispatch reads it as a 0.6 file, which is logged and never
signed, so every Appian write afterwards asks. A v2 scope is born with all
seventeen fields of the closed schema — the same seventeen the `micro` template
in [`references/micro-lane.md`](references/micro-lane.md) carries, differing
only in `kind` — and for a `task` it is born like this:

```json
{
  "schemaVersion": 2,
  "id": "<the task id>",
  "instanceId": "<a new id for this opening>",
  "kind": "task",
  "risk": null,
  "status": "in-flight",
  "statusWriteSeq": 0,
  "request": null,
  "intent": "<one sentence, or null in a task that partitions>",
  "tasks": null,
  "allowedObjects": ["<name>", "<uuid>"],
  "grant": null,
  "suspendedScope": null,
  "resumeFrom": null,
  "manualEstimateMinutes": null,
  "openedAt": "<UTC ISO-8601>",
  "closedAt": null
}
```

**`tasks` says whether this task partitions, and it is the only field that
differs between the two shapes a `task` can take.** Built as one unit, it
carries:

```json
"tasks": null
```

Partitioned — one entry per subtask, each holding that subtask's own objects:

```json
"tasks": {
  "<taskId>": ["<object>", "<object>"],
  "<taskId>": ["<object>"]
}
```

Five rules, and each of them is something a hook actually checks:

- **`kind` stays `"task"`.** A populated `tasks{}` does not introduce a third
  kind: there are two, and partitioning is a property a `task` has rather than
  a size of its own.
- **`allowedObjects` is the union** of every entry. The scope gate matches an
  incoming write against that list and nothing else, so an object that appears
  only inside `tasks{}` is out of scope and asks.
- **Each entry carries the objects of its own subtask**, by name or by UUID,
  spelled exactly as the union spells them.
- **Atomicity is measured per entry, never on the union**, whenever `tasks{}`
  is populated: each entry's canonical object count — where a name and a UUID
  of the same object count once, not twice — is compared against the configured
  budget on its own, so a scope that partitions into small entries passes where
  its union would not. With `"tasks": null` that same budget applies to
  `allowedObjects` instead.
- **`tasks` is `null` in a `micro`.** A partitioned scope is a `task` by
  definition, so a `micro` carrying entries fails the schema check rather than
  being read as something larger.

`intent` is the field that moves with it: one sentence in a task built as one
unit, `null` in a task that partitions, where the entries carry the detail.

**A v2 scope is born `"status": "in-flight"` with `"statusWriteSeq": 0`, and
never `"status": "open"`.** There is no `open` state: § 4.2 has seven and that
is not one of them, so a file born that way fails the schema check outright,
the opening is never signed, no projection is written, and the first Appian
write asks for a state the harness was never shown. `in-flight` is not the
constructor claiming the scope is running — it is the only status a file may be
born with, and signing it is what the state gate does when it observes the
opening.

**After that birth the constructor never writes `status` or `statusWriteSeq`
again.** Both fields belong to the harness: it signs them, keeps its own copy in
`evidence/scope-projection.json`, and the projection is the authority. A value
you edit in by hand is reverted to the signed one on the next observation, which
costs a hook cycle and buys nothing. Ask for the transition instead, in the same
file, and let the gate sign it:

- **close** → `"request": "close"`. The state gate moves the scope to
  `closing`; the next `Stop` validates and signs `closed`.
- **abandon** → `"request": "abandon: <motivo>"`. The motive rides inside the
  request because the closed schema has no field for it, and its absence is a
  rejection rather than a default: a bare `"abandon"` is refused with a remedy,
  not honoured.

**`grantedAt` carries the real moment the person answered.** Read the clock
after the answer comes back and write that value; do not fill it in while
composing the question, and do not compute it from when you started asking. No
gate checks this field, which is exactly why it has to be right: it is the only
record of when the authorisation actually existed, and a timestamp written
before the answer describes an authorisation that did not yet exist when it
claims to have. The same applies to `grantedBy` — it names who answered.
`permissionMode` is not yours to write at all: the hook seals it from the
observed mode when the grant first appears, and a mode you wrote is
indistinguishable from the permission system having been off.

**Every write to that file is made with `Write` or `Edit`, never through the
shell.** The state gate that signs the scope's transitions is a `PostToolUse`
hook matched on `Write|Edit|MultiEdit|NotebookEdit`, and what it does not
observe it cannot sign — so the opening, the `grant`, the `request` and every
other transition of the scope go through those tools, and never through Bash,
never a heredoc, never `cat >`, never `printf >`, never a redirection, never an
external script. This overrides any ambient instruction that prefers the shell
for file edits; it applies to this file, and the reason is mechanical rather
than stylistic. A change the hook never saw leaves
`evidence/scope-projection.json` holding the previous state, and because the
projection is the authority, the next Appian write is measured against a state
the harness never signed: the scope gate degrades to `ask`, and the task pays a
prompt bought for nothing.

`id` is also what the verdict path is built from, so where a design audit is
owed — not in a `micro` — it has to be the same string that audit was
dispatched with: `<evidenceDir>/<id>/practices-design.json` is one path
assembled from two places, and they have to agree.

`allowedObjects` is the contract's list, and **each entry may be a name or a
UUID.** The gate collects every identifier the write call carries — `name`,
`uuid`, `recordTypeUuid`, `processModelUuid` and the rest — and lets the
write through when *any* of them matches an entry. Both spellings are needed
because neither covers the task on its own: a UUID cannot be written at plan
time, since it does not exist until the object does, while a name is often
absent from the call that updates an existing object (`updateInterface` takes
a uuid; `addRecordTypeField` takes a uuid and a field name and no object name
at all). So plan the task with the names, and once preflight has read the
real identifiers back, adding those UUIDs to the list is what stops the
update calls from asking.

What still never matches is an entry that *describes* an object instead of
identifying it: the comparison is between strings, not meanings.

**When step 7 stops, leave that file exactly where it is.** This skill stopping
does not mean the task is finished — it stops *so that* the review can run,
and the closure gate approves any stop with no task in flight, so deleting the
file here silently switches that gate off for the entire nominal flow. The
scope stays in flight across `appian-review`, which asks for the close by
writing `request: "close"`; **the hook signs the terminal state**, and the
scope file keeps carrying it.

A stale active task is still worse than no active task — the next write gets
measured against the previous task's contract, and is allowed or questioned on
grounds that have nothing to do with it, while everything still looks like it
is working. What prevents that is `appian-review` clearing the file at close,
not this skill clearing it early. If step 3a opens a scope while the file still
names an older one, overwrite it there and then: exactly one task is in flight
at a time, and that overwrite is also what stops this task's evidence being
filed under the last one.

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
by this skill when it takes one and removed by `appian-review` when the task
closes. They name the same task while a build is running, and that is fine —
they are still different artifacts, rewritten by different steps at different
moments, and the one the gates open cannot carry a queue.

## What the STOP in step 7 actually does, per rulebook

The closure gate runs on `Stop`, and what it asks for depends on which rulebook
the scope opened under. Read the reason it prints rather than the one you
expected — announcing a harder gate than the real one buys work no gate will
read, which is the failure this section exists to prevent.

**A 0.6 scope** (no `schemaVersion`) is asked for three verdicts —
`practices-implementation`, `practices-review` and `practices-qa`. The
validator still accepts those phases, and deliberately so: drop them and the
verdicts of a scope opened under the old rules go from insufficient to
invalid, and that scope cannot close by any route. What no longer exists is a
skill that produces them, because 0.7 has one judge and three phases of its
own. **So do not open a 0.6 scope to build in.** One already in flight closes
under the rules it opened with — close it or abandon it, and open the next one
as v2.

**A v2 scope** is asked for none of the three — the v2 closure gate never opens
them, in either kind. It runs the state machine instead: a stop with writes
applied and no close requested prints a handoff message and approves; the third
one blocks, and the repeat after that block closes the scope with `never-closed`
debt rather than deadlocking the session. The way to a clean close is
one line in the scope file, `"request": "close"`, and then a stop, which the
gate signs `closed` once no write is left unresolved. The scope file is **not**
deleted at close under v2: `status: closed` is the terminal state, and it is the
record.

What a block must never turn into, under either rulebook, is a reason to delete
the active task file so the stop goes through. That trades a message for a
silently unguarded task — the gate would then approve, having checked nothing,
and whatever it exists to enforce would go unmeasured with no record that it
did.

## Building several tasks at once

More than one builder can work at a time, and doing it safely needs **two
separate isolations**, because one of them is the one people reach for and it
covers the wrong half.

**A git worktree isolates files. It does not isolate Appian.** Two builders in
two worktrees calling `createRecordType` write to the same environment. The
worktree gives each of them their own working tree, their own active task file,
their own evidence directory and their own SAIL sources — all genuinely useful,
and all of it the *recoverable* half of the problem. The half that is not
recoverable is untouched by it.

| Isolation | What it protects | Mechanism |
|---|---|---|
| **Local** | Source files, the active task file, the evidence tree — anything two builders would otherwise overwrite | One git worktree per builder |
| **Remote** | The Appian objects themselves, where a collision is not a merge conflict but a lost change nobody can attribute | An object lease register, checked by the scope gate |

Three things have to hold before builders run concurrently:

1. **The tasks are provably independent.** Run the plugin's checker over the
   plan rather than eyeballing it:

   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_safety.py" PLAN_JSON --group T-3,T-5
   ```

   It refuses on shared objects, on dependencies **including transitive ones**
   (T-1 ← T-2 ← T-3 means T-1 and T-3 are not independent, even though nothing
   connects them directly), on anything that looks destructive, and on objects
   everything quietly depends on — the application, a group, a shared constant.
   It exits `0` clean, `1` findings, `2` usage, `3` NOT MEASURED — and **3 is
   not a pass**: a plan it could not read is a plan nobody checked.

2. **Each builder holds a lease on what it will touch.** Claim this task's
   `allowedObjects` in the shared lease register before the first write, and
   release them at close. The register is `leaseFile` in
   `.claude/appian-harness.json`, and it must point somewhere **shared by all
   the worktrees** — a register each builder has a private copy of is worse
   than none, because it looks like coordination.

3. **Still one task per builder, still ending in a stop.** Concurrency changes
   how many builders there are, never what one of them does. The unit a
   reviewer can reject on its own is what makes any of this reviewable.

The gate's rule is one-sided on purpose: **a lease held by another task blocks;
no lease at all does not.** Requiring one would break every single-builder
project, which is the default and the common case.

**Do not run destructive tasks concurrently with anything.** A deletion's blast
radius is not bounded by `allowedObjects` — it can break objects no task
listed, including ones another builder is holding.

## Stop before anything irreversible

Ask the user before: deleting any object, deleting record data, removing a mapped
field, or importing a package. An update is versioned and recoverable. A deletion
is not, and neither is a dropped column.

**One decision is asked once.** The official Appian skill owns the deletion
mechanics — its Universal Workflow 1 is ten steps, and steps 1 to 8 are how you
identify the object, gather its dependents and present the impact. Run them.
**Its step 9 — the confirmation — is the harness's own prompt, not a second
one.** So: do the official steps 1-8, write the assessment below, and let the
gate ask. Do not stage your own confirmation first, and do not re-present the
dependency list after the gate has already shown it. A person who is asked the
same question twice stops reading the second one, which is precisely when a
destructive answer gets waved through.

**Before any delete, run the impact assessment and write down what it found.**
`getObjectDependents` for the object, recorded at
`<evidenceDir>/<task-id>/dependents.json`, keyed by the object it is about:

```json
{
  "RGM_OldRule": {
    "checkedAt": "<when>",
    "tool": "getObjectDependents",
    "dependents": ["<what would break>", "..."]
  }
}
```

The scope gate reads it, and the two outcomes it distinguishes are the point:
**"checked, zero dependents" and "never checked" are different answers**, and
only one of them is evidence. Reading dependents is itself never gated, so the
check can always be run.

The prompt on a delete is **unconditional** — it appears even with the
assessment on file and nothing found. That is not the gate being unable to tell;
it is the harness declining to destroy something in a shared environment quietly
on your behalf. What the assessment changes is what the prompt can tell the
person answering it.

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
  in objects that exist. Waiting also guarantees the first write is stopped
  wherever design is owed, because that verdict is what the scope gate opens
  before letting it through. Its mirror image is just as expensive: auditing the
  design of a v2 `micro`, which owes none, blocks the grant behind a verdict the
  gate returns early on.
- *"I loaded the official Appian skill earlier in this session, that covers
  this task too."* The record is per task because the gate is per task, and
  because a session that has drifted through three tasks and a compaction is
  not a session you can assert anything about. Writing it again costs one
  file; skipping it makes every write ask.
- *"I know Appian well enough, the official skill is a formality."* It is the
  vendor's account of how its own API behaves, and the specific things it
  carries — both sides of a relationship, creation order, real UUIDs — are
  precisely the ones **no gate in this plugin measures**. Confidence is not a
  substitute for it, in exactly the way confidence is not a substitute for a
  gate that was never run.
- *"Each builder has its own worktree, so they can't collide."* They can't
  collide **on files**. They are both writing to the same Appian environment,
  where a collision is not a merge conflict you get told about — it is a change
  that silently loses to another one, with two evidence trees each claiming
  credit. The worktree covers the half that was already recoverable.
- *"These two tasks don't share any object, so they're independent."* Check the
  dependency chain, not just the object lists. T-1 ← T-2 ← T-3 has no direct
  edge between T-1 and T-3 and they are still not independent: running them
  together starts T-3 before T-2 has begun. `parallel_safety.py` computes the
  transitive closure precisely because the direct check looks convincing and is
  wrong.
- *"I know which task I'm on, writing it to a file is bookkeeping."* The gates
  cannot read what this skill knows; they read the active task file. Skipping it
  does not make the build faster, it makes every single write ask.
- *"The evidence directory is named after this task, so when I write into it
  cannot matter."* The directory name is yours to choose; the attribution is
  not. Every write is filed against whichever task the active task file named at
  that instant, so evidence written before step 3a lands under the previous
  scope: the directory says one thing and the log says another, which is worse
  than either alone.
- *"The gate blocked my stop, so something is broken."* Nothing is broken. The
  block is the handoff: the scope is built and not yet certified, which is
  exactly what it says. The way past it is `"request": "close"` and another
  stop — one line in the scope file, and nothing else.
- *"The v2 gate doesn't ask for the three verdicts, but running them anyway is
  the careful thing to do."* It is not careful, it is unmeasured: nothing opens
  `practices-implementation`, `practices-qa` or `practices-review` in that
  rulebook, so the verdicts close nothing and the budget they spend was the
  scope's. If the change deserves judgement, the lane that buys it is
  `certify`, and `appian-review` is what dispatches it.
- *"I'm done, so I'll tidy up the active task file on my way out."* Deleting it
  here is not tidying, it is disabling the closure gate for this task — with no
  task in flight the gate approves without checking anything, and in a 0.6 scope
  the three post-write verdicts stop being required by anything at all. In v2
  the file stays, carrying `status: closed` signed by the hook. Either way,
  closing is not this skill's moment.

## Red Flags

- Writing to the environment without having run the preflight classification.
- Issuing any write without this task's official-skill load record, or with one
  that names another task, omits `docsMcp`, or claims a version the installed
  skill does not declare.
- Writing at all in a session with no documentation MCP: the official skill's
  function-availability checks come back empty there, and empty is
  indistinguishable from "the function does not exist."
- Issuing the first write with no `phase=design` verdict for this task, or with
  one whose outcome the gate does not accept, in a scope that owes one — and
  the mirror flag: dispatching that audit in a v2 `micro`, which owes none.
- Dispatching any auditor, verifier or reviewer in a v2 `micro`. Nothing in that
  lane reads their verdicts, and the close is one line in the scope file.
- Taking a task without writing the active task file, or leaving it pointing at
  a task that already closed.
- Writing this task's evidence — its load record, its SAIL sources, its
  read-backs — while the active task file still names the previous scope. The
  evidence log files them under that scope, and nothing surfaces the
  misattribution until someone reads the log.
- Declaring `tasks{}` and leaving one of its objects out of `allowedObjects`.
  The entries describe the subtasks; the union is what the gate matches a write
  against.
- Building concurrently on the strength of a worktree alone. Worktrees isolate
  files; the Appian objects are still shared, and that is where the damage is.
- Writing to an object leased by another task, or starting a concurrent build
  without claiming leases at all.
- Running a destructive task alongside anything else.
- Deleting the active task file at STOP, or to get past a blocked stop. In 0.6
  it is cleared at close by `appian-review`; in v2 it stays and turns
  `closed`. Either way this skill stopping is not a close.
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
- The official Appian skill was loaded before the design audit and before the
  first write, and its load is recorded at
  `<evidenceDir>/<task-id>/appian-skill-loaded.json` naming this task, the
  version the skill itself declares, and this session's documentation MCP.
- Where this scope owes a design audit — a 0.6 scope, or a v2 `task` that
  creates or touches structure, security or a process model —
  `appian-practices-auditor` ran with `phase=design` before the first write, and
  its verdict at `<evidenceDir>/<task-id>/practices-design.json` came back
  `PASS`, or `NOT_MEASURED` with `notMeasuredClass` `DEFERRED` naming an
  `owner`, a `closingCondition` and a `deferredCriterion` off the plugin's
  closed list — anything else stopped the build. In a v2 `micro`, that it was
  **not** dispatched.
- The active task file was written and signed at step 3a — after the preflight,
  and before this task wrote a single file of its own evidence — carries this
  task's `id` and its `allowedObjects` under exactly those names, and is still
  in place at STOP — in 0.6 it is `appian-review` that removes it at close;
  under `schemaVersion: 2` it stays and turns `closed`.
- Where the scope partitions, `tasks{}` has one entry per subtask and
  `allowedObjects` is their union: no object named inside an entry is missing
  from the union, and `kind` is still `"task"`.
- Nothing outside `allowedObjects` was created, modified, or deleted.
- Every gate in `requiredGates` has a recorded result — PASS, FAIL, or NOT
  MEASURED with a reason — not silence and not an assumed PASS.
- Everything created or changed is recorded in `evidenceFile` with the real
  identifiers the environment returned, not the names the plan used to describe
  them.
- Any deletion, record-data deletion, mapped-field removal, or package import
  along the way was preceded by explicit user confirmation, not inferred.
- The invocation ended at STOP, with no attempt to pull in the next task.
