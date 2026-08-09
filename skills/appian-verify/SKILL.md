---
name: appian-verify
description: Verifies one built Appian task gate by gate and records the evidence. Use after appian-build finishes a task and before it is reviewed or closed — when asked to "verify this task", "run the gates", "check the evidence", or "is this task done". Not mid-build, and not a substitute for appian-review's independent design judgement.
---

## Overview

This is the VERIFY phase of the lifecycle `SPECIFY → PLAN → BUILD → VERIFY → REVIEW → CLOSE`. It
takes one task that `appian-build` has already finished and produces the evidence a reviewer or a
close step can read without re-deriving it: a per-gate report, and two independent audits of
whether official best practices were actually followed.

This skill orchestrates, it does not judge. It does not read the artifact and decide for itself
whether a gate passes — it dispatches the agents whose job that is, and consolidates what they
return. That follows the plugin's guiding principle: whoever builds does not certify. Running
verification in its own context, separate from the context that built the task, is not a
formality — an agent that just wrote an object reads it charitably, because it already knows what
it intended.

Two agents do the actual judging:

- **`appian-practices-auditor`**, dispatched twice — once with `phase=implementation`, once with
  `phase=qa` — to judge whether the domain rules the change touches were followed, and whether the
  test evidence actually covers what the QA gate requires.
- **`appian-verifier`**, dispatched once, to produce the per-gate report: `PASS`, `FAIL`, or
  `NOT MEASURED` (with its class) for every gate the task's contract requires, naming the evidence
  behind every `PASS`.

## When to Use

Use after `appian-build` finishes a task and before that task is reviewed or closed. This skill
needs the task contract `appian-build` already established — `allowedObjects`,
`acceptanceCriteria`, `requiredGates`, `evidenceFile` — and the real artifact the task produced,
not a description of it.

Do not use mid-build, and do not use in place of `appian-review`. This skill checks whether the
evidence a task's gates require actually exists and covers what it claims to cover; it does not
render an independent judgement on whether the artifact itself is well designed or holds up under
scrutiny. That is `appian-review`'s job, run separately, against its own closed threshold.

## Core Process

1. Read the task's contract — the four parts `appian-build` produced. If any part is missing, stop
   and say so rather than verifying against an incomplete contract.
2. Ask the project for what this skill needs and does not assume: which identifier is guaranteed
   not to exist, so the empty path gets exercised on purpose rather than by accident; and what
   command runs the regression suite, so non-regression has evidence behind it.

   Evidence has a **root** and a **shape**, and only the root is the project's. The root is
   `evidenceDir` in `.claude/appian-harness.json` — default `evidence` when that file names none.
   The shape under it is this plugin's contract, not a convention a project gets to restyle:
   every phase verdict is `<evidenceDir>/<task>/practices-<phase>.json`. That is the exact path
   the plugin's gates open, so a verdict written anywhere else is a verdict they report as
   missing. Do not confuse this with `evidenceFile`, the per-task record `appian-plan` assigns
   and `appian-build` writes real identifiers into: that one the plan places, and it says nothing
   about where these verdicts go.
3. Dispatch `appian-practices-auditor` with `phase=implementation`, handing it the artifact and the
   contract. It judges whether the domain rules the change touches were actually followed, and
   writes its verdict to `<evidenceDir>/<task>/practices-implementation.json`.
4. Dispatch `appian-practices-auditor` again with `phase=qa` — only after both a populated render
   and an empty-path render exist; see *Verification runs with populated data* below. It judges
   whether the test evidence covers the gate it claims to close, and writes its verdict to
   `<evidenceDir>/<task>/practices-qa.json`.
5. Dispatch `appian-verifier`, handing it the contract and the real artifact — never a summary of
   what the builder believes it did. It emits a result for every gate in `requiredGates`, naming
   the evidence behind every `PASS`.
6. Consolidate: fold the verifier's per-gate report together with both practices verdicts into one
   record, `<evidenceDir>/<task>/gates.md`, so a reviewer or the close step reads a single account
   of this task's state instead of opening three files and reconciling them by hand. No gate reads
   this file — it sits beside the verdicts so that whoever opens the task's evidence finds one
   account rather than a directory to reassemble.
7. Hand off to `appian-review`. This skill's job ends at the consolidated record; it does not
   proceed into review on its own, and it does not close the task. The active task file
   `appian-build` wrote is still in flight and stays that way — leave it alone. `appian-review`
   deletes it when the task closes, which is after this skill, not during it.

If any dispatch reports `FAIL`, or `NOT MEASURED` in its blocking class, record that plainly in the
consolidated record and stop there — do not reinterpret a blocking result as resolved because the
rest of the task looks fine.

## Verification runs with populated data

Testing with empty tables is not testing. A loop over a null or empty list never evaluates its
body; a broken screen passes every test case it has, right up until a row actually exists to
iterate over (field experience). The `phase=qa` dispatch in step 4 is worthless if it only ever saw
empty tables — it would be auditing evidence that could not have caught the one defect this level
exists to catch.

This is why step 2 asks the project for the identifier that is guaranteed not to exist, instead of
assuming one: the empty path has to be exercised **on purpose**, with a render that deliberately
hits it, not left to whatever the tables happened to contain when someone ran the case. Dispatch
the `qa` audit only once both exist — a render against the project's populated dataset, and a
render against the empty-path identifier. Neither substitutes for the other: the populated render
proves the nominal path works, the empty-path render proves the empty state was not silently
skipped over.

## The task is still in flight while this skill runs

`appian-build` writes the active task file when it takes a task and leaves it in place when it
stops, because a build stopping is a handoff and not a close — this skill is the reason it stopped.
So the task is still in flight here, and the closure gate is still watching: stopping in the middle
of verification blocks, naming the verdicts that do not exist yet. That is accurate. Produce them,
or hand the task to `appian-review`, which is where the file is finally cleared.

The one thing that must not happen here is deleting that file to make a stop go through. The gate
approves any stop with nothing in flight, so removing it does not satisfy the check — it removes
the check, for every phase this skill and `appian-review` are supposed to close.

## Two deterministic checkers this plugin ships

`appian-verifier` and the practices auditor both reason about evidence. Two of the checks are
mechanical enough to be code, and this plugin ships them as scripts under `scripts/`. Nothing
dispatches them automatically — run them and feed their output to the dispatch that needs it.

```
python scripts/n2_interface_tree.py TREE_JSON [--empty-path]
python scripts/n3_process_layout.py LAYOUT_JSON
```

Both print one line per finding and exit non-zero when they find any, so a `NOT MEASURED` here is
distinguishable from a clean run rather than being assumed.

- **N2 — `n2_interface_tree.py`**, over the **evaluated** component tree a rendered-interface test
  returns. What it catches that nothing else can: colours that resolved out of the database and
  appear nowhere in the interface's source, so no check over the source will ever see them (field
  experience). It also reads contrast ratios, unlabelled inputs, grids with no label or row header,
  destructive controls with no confirmation, and technical values leaking into user-visible text.
  Pass `--empty-path` for the empty-path render from step 4 — that is what turns on the empty-state
  check. What it cannot do: it has not seen the screen. It says nothing about component choice or
  visual hierarchy, which is why the rendered screen still needs a person.
- **N3 — `n3_process_layout.py`**, over a process model's node coordinates and connections. It
  catches nodes stacked on each other, nodes crowded below the separation thresholds, flow that runs
  backwards along the x axis outside a real loop, and orphan nodes. What it cannot do: the API
  exposes coordinates but neither node dimensions nor connection waypoints (field experience), so it
  tells you where every node **sits** and never where any connection **routes**. A clean N3 run is
  not a clean diagram.

## What this skill does not cover

Two of the four phases `appian-practices-auditor` supports are out of scope here, on purpose.
`phase=design` belongs before a single write happens — that is `appian-build`'s preflight concern,
not this skill's. `phase=review` belongs to `appian-review`, which dispatches its own independent
reviewer against a closed exemption threshold; running it here would blur two roles this plugin
deliberately keeps separate. This skill dispatches exactly `phase=implementation` and `phase=qa`,
nothing else.

## Common Rationalizations

| Rationalization | Reality |
|---|---|
| "The tests pass, so it is verified." | A test that never exercises the path proves nothing. Green against an empty table says nothing about a populated one — see *Verification runs with populated data*. |
| "I'll verify it myself, I already know the change." | Whoever builds does not certify. Verifying in the same context that built the task carries the builder's intent into a check that is supposed to be independent of it. |
| "I read `appian-best-practices` while I was building it, that covers the implementation gate." | Reading a reference while building is not evidence to a third party. The `phase=implementation` verdict is a written audit that cites the sections it applied, checkable by anyone — not the builder's account of having been careful. |
| "The gate report has no FAIL, so the task is done." | `NOT MEASURED` is not a pass. A report with zero `FAIL` and several blocking `NOT MEASURED` results is not evidence the task is finished — it is evidence nobody checked. |
| "The QA audit already ran once with real data; running it again against the empty-path identifier is redundant." | They catch different defects. A screen can pass the populated render and still never show an empty-state message, because the code path that would have rendered one never runs against real data either. |
| "The verifier and the practices auditor said much the same thing, one report is enough." | They answer different questions. The auditor judges whether the rules for this domain were followed, with citations. The verifier judges whether the evidence in front of it covers what this task's specific gates require. A citation to the right section is not the same claim as evidence that covers a criterion. |
| "Verification is finished, so I'll clear the active task file on my way out." | The task is not closed, it is reviewed next. Clearing the file leaves nothing in flight, and the closure gate approves a stop with nothing in flight without opening a single verdict — including the `review` one that has not been produced yet. `appian-review` clears it, at close. |
| "N3 came back clean, so the process model reads properly." | N3 sees coordinates, not connections (field experience). It can tell you no two nodes are stacked and still be looking at a diagram whose arrows cross the whole canvas. |

## Red Flags

- A gate recorded `PASS` in the consolidated record with no evidence named — not this skill's call
  to make; if a dispatch did not name evidence, that is a problem with the dispatch, not something
  to smooth over while consolidating.
- The `qa` dispatch running against only the populated dataset, or only the empty-path identifier,
  instead of both.
- `appian-verifier` or `appian-practices-auditor` handed a description of the change instead of the
  real artifact.
- Proceeding to `appian-review` before both practices verdicts and the verifier's report exist.
- A blocking `NOT MEASURED` result folded into the consolidated record as if it were resolved.
- Reusing a previous task's practices verdicts or gate report for a different task.
- A verdict written anywhere other than `<evidenceDir>/<task>/practices-<phase>.json` — under a
  different root, outside the task's directory, or with the phase spelled differently. It reads
  as evidence to a person and as an absence to the gates, which is the worst of both.
- The active task file deleted here, for any reason. It is cleared at close by `appian-review`;
  removing it mid-flight does not pass the closure gate, it retires it.

## Verification

Before handing this task's evidence to review or closure, confirm:

- [ ] The task contract was read in full before anything was dispatched; any missing part stopped
      the process instead of being assumed.
- [ ] `appian-practices-auditor` ran with `phase=implementation` against the real artifact, and its
      verdict names the reference sections it applied.
- [ ] Both a populated-data render and an empty-path render exist before the `qa` dispatch ran, and
      the `phase=qa` verdict names both.
- [ ] `appian-verifier` ran against the contract and the real artifact, producing a result for every
      gate in `requiredGates` — never silence.
- [ ] Every `PASS` in the consolidated record names the evidence that produced it.
- [ ] No `FAIL` or blocking `NOT MEASURED` was treated as resolved before handoff.
- [ ] This task was verified in a context separate from the one that built it.
- [ ] The active task file is still in place, untouched, and the task was handed to
      `appian-review` rather than treated as closed here.
