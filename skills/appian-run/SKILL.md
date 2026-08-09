---
name: appian-run
description: Builds a plan's pending tasks end to end without a keystroke per task, stopping only where a person adds something. Use when several planned tasks are ready to build and driving them one at a time is the bottleneck. Use after a plan exists and its tasks carry their full contracts.
disable-model-invocation: true
argument-hint: "[task-ids or 'all']"
---

## Overview

This skill exists because the human gate was in the wrong place. `appian-build`
builds one task and stops, which is right — the task is the unit a reviewer can
reject on its own. What was wrong is that **starting** each one needed a person,
so a twenty-task plan cost twenty interventions that decided nothing, while the
decisions worth a person's attention were spread thin among them.

So authorization moves: **granted once for a run, bounded, and checked
deterministically** rather than re-requested per task. This skill carries that
run. It does not build, judge, or write to Appian — it sequences the phases that
do, and it stops where stopping is worth something.

This skill only runs when invoked by name (`disable-model-invocation: true`).
Granting a run is the user's act, not something to infer from context.

## When to Use

- Several planned tasks are ready and driving them one at a time is the
  bottleneck.
- Not for a single task — invoke `appian-build` directly.
- Not before a plan exists whose tasks carry all four contract parts. A run over
  an incomplete contract just fails later and less legibly.

## What a run is

Write the authorization where the gate reads it — `activeRunFile` in
`.claude/appian-harness.json`, `tasks/run.json` by default:

```json
{
  "authorizedTasks": ["T-3", "T-4", "T-5"],
  "grantedBy": "<who granted it>",
  "grantedAt": "<when>",
  "maxTasks": 5,
  "tasksCompleted": 0
}
```

`authorizedAll: true` covers the plan. The scope gate refuses a write from a
task outside the list and refuses one once `tasksCompleted` reaches `maxTasks`
— **a budget that renews itself when it runs out is not a budget.** Increment
`tasksCompleted` as each task closes.

**`maxTasks` and `tasksCompleted` are required, and both must be whole
numbers.** A grant with no budget is not a run, it is standing permission, and
the gate refuses it as such — as it refuses `"maxTasks": "5"`, `true`, or a
`tasksCompleted` of `null`. Each of those used to read as a *wider* grant than
the file appeared to make, silently, because the run kept working. Same rule as
the risk tier: a malformed field buys more ceremony, never less.

**Delete the run file when the run ends** — finished, stopped or abandoned. It
is an authorization, not a log: one left behind with `authorizedAll` still true
authorizes the next session too, for a plan nobody was thinking about when they
granted it. The evidence tree is where a run's history belongs.

If the project has not configured `activeRunFile`, the harness behaves exactly
as it always did and nothing here is enforced. Say so rather than implying a
guard that is not running.

## Core Process

1. **Read the plan and the operational state.** Take the pending tasks in
   dependency order.
2. **Decide what may run at once**, if anything will:
   ```
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parallel_safety.py" PLAN_JSON
   ```
   Sequential is the default and is fine. Concurrency also needs a worktree per
   builder **and** a shared `leaseFile` — see *Building several tasks at once*
   in `appian-build`, including why a worktree alone is not enough.
3. **Write the run authorization**, with who granted it and its budget.
4. **For each task, in order:** `appian-build` → `appian-verify` →
   `appian-review`. Each phase is invoked as itself; this skill adds nothing to
   what they do and removes nothing either.
5. **On a FAIL:** re-enter `appian-build` for the same task, up to
   `maxFixAttempts` (default **2**). A fix is more writes, so the
   `implementation` and `qa` verdicts that predate it are now stale and the
   closure gate will say so — re-run those phases too rather than closing on
   them. Budget exhausted: stop and escalate.
6. **After each close**, increment `tasksCompleted` and continue.
6b. **When the run ends, delete the run file** — on the last task, at a stop, or
   on abandoning it. Leaving it is how a grant outlives the plan it was for.
7. **At the end**, report per task: what was built, which gates passed, what was
   deferred and to whom. Then check the run as a whole for the review-theatre
   pattern — findings raised across cycles with none classified actionable. One
   clean review is a clean review; ten in a row without a single actionable
   finding is a claim about the *process*, and a run is the first thing that
   produces enough cycles to see it.

## The eight stops

The run continues on its own unless one of these holds. They are closed and
explicit, because "it seemed fine to keep going" is what an unattended loop is
for and also how it goes wrong:

1. **Anything irreversible** — deleting an object, deleting record data,
   removing a mapped field, importing a package. **No authorization covers
   this, ever.** The gate prompts regardless of any run.
2. Preflight returns `CONFLICTING`.
3. The `design` verdict is not `PASS` nor a sanctioned deferral.
4. A `FAIL` that survives the fix budget.
5. `NOT_MEASURED · BLOCKING` — the harness could have measured it and did not.
6. The scope gate would ask for any reason other than the first write of an
   authorized task.
7. The run budget is spent.
8. A task the plan marked `requiresHumanConfirmation` — the optional sixth
   contract field in `appian-plan`. Not a risk tier: it says the decision is
   not the builder's, so no amount of scrutiny substitutes for asking.

At a stop, hand the person the task, the reason and the evidence — not a
summary of how it was going.

## Context across a long run

Twenty tasks in one session exhausts context, and this is the skill in the best
position to do something about it: between tasks, the durable state is the
evidence tree, the operational state and the run file. Nothing needed to
continue lives only in the conversation. So compacting, or starting a clean
session and re-reading those three, is safe **between** tasks and not during
one. Prefer it to letting a run degrade into a session that has forgotten its
own first half.

## Common Rationalizations

| Thought | Why it's wrong |
|---|---|
| "The run is authorized, so I can delete this too." | No authorization covers the irreversible. That is the one decision granting a run explicitly does not grant, and the gate prompts regardless. |
| "Parallel builders will make this much faster." | The speed here comes from removing human round-trips, not from concurrent writes. Appian is one shared environment: two builders on one object is a change that silently loses, and a worktree does not prevent it. |
| "The review failed, I fixed it, so it's done." | A fix is more writes. The `implementation` and `qa` verdicts now predate the artifact they certify — the closure gate measures that against the write log. Re-run them. |
| "It failed twice, once more will do it." | Three attempts at the same task is not persistence, it is a task that was specified or sized wrong. Escalate with what was tried. |
| "I'll increase maxTasks so the run can finish." | A budget you raise when it binds never bound anything. Finishing the plan is a new grant, made deliberately. |
| "Nothing was actionable across ten reviews, the work is clean." | Or the review stopped doubting. That is exactly the pattern a run is long enough to reveal and a single task is not — check it before believing the first reading. |

## Red Flags

- Building a task outside the authorized list, or after the budget is spent.
- Raising `maxTasks` mid-run instead of ending the run.
- Continuing past any of the eight stops.
- Concurrent builders with no `leaseFile`, or with one that is not shared
  across their worktrees.
- Closing a task on verdicts that predate its last write.
- A run that reports only successes — no deferrals, no stops, nothing
  escalated — across many tasks, with nobody asking whether that is plausible.
- Compacting in the middle of a task rather than between tasks.

## Verification

Before reporting a run finished:

- [ ] Every task built was in the authorized list, and the budget was never
      raised to accommodate the work.
- [ ] Every task went through build, verify and review — none skipped because
      the run was going well.
- [ ] No task closed on a verdict older than its most recent write.
- [ ] Every stop is reported with its task, its reason and its evidence.
- [ ] Any irreversible action was confirmed by a person at the moment it
      happened, not pre-authorized by the run.
- [ ] `tasksCompleted` matches the number of tasks that actually closed.
- [ ] The run file is gone. An authorization that outlives its run authorizes
      the next one.
- [ ] Every object lease this run took has been released.
- [ ] The run was checked for the review-theatre pattern across its cycles.
