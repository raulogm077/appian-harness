---
name: appian-review
description: Runs an independent review of one Appian change, graduated by risk, handing the reviewer the artifact and the contract while withholding the builder's conclusion — and closes the task, clearing the active task file as its last act. Use when a change creates an object, writes data, exposes information, changes authorization, queries at volume, or touches a screen a user sees. Use equally when a change looks small or cosmetic enough to be exempt — judging that against the four exemption conditions, recording who made the call, and then clearing the active task file is this phase's own work. Use before closing any task, on either path.
---

## Overview

`appian-review` is the REVIEW phase of the lifecycle `SPECIFY → PLAN → [BUILD →
VERIFY → REVIEW] → CLOSE`, run once per task, after the change has been built and
whatever gate step the project runs has recorded its evidence. Its job is narrow:
certify the change from outside the context that built it.

The guiding constraint is the one the whole skill exists to protect: **the
reviewer receives the artifact and the contract, never the builder's
conclusion.** An agent that wrote an object reads its own work as if the intent
behind it were still visible; a verdict handed to a reviewer — "this looks right
because…", a summary of what was done, a claim that the tests pass — biases the
review toward agreement before the reviewer has looked at anything. Dispatch the
reviewer with the changed object(s) and the task's contract (its
`allowedObjects` and `acceptanceCriteria`) and nothing the builder wrote about
itself.

Review is **graduated by risk**: it does not run in full on every change, and it
does not run at all on some. The entry threshold below decides which; nothing in
this skill substitutes for evaluating it explicitly.

Two independent agents run per change that enters review, both dispatched with
`phase=review`:

- **`appian-reviewer`** — checks the change against its task contract: does it do
  what the acceptance criteria describe, and only what `allowedObjects` permits.
- **`appian-practices-auditor`** — checks the change against domain doctrine: the
  same quality gates and cardinal rules a build step is expected to have already
  applied, audited from outside that step.

That second agent is where `appian-best-practices` enters this phase, and the
duplication is the design rather than an oversight. Every phase before this one
consults the doctrine to *prevent* — `appian-specify` on entities, security and
volume, `appian-plan` on naming and which gates a task requires, `appian-build`
on the domains it writes. This phase applies the same doctrine to *verify*,
from a context that did not produce the work. Prevention and independent
verification are two layers, not one done twice: the first decides what gets
built, and only the second can catch what the first talked itself into.

Both read the same artifact and the same contract; neither reads the other's
output before forming its own, and neither reads anything the builder wrote
about why the change should pass. Record every finding either agent raises,
with its classification (actionable or not) and, for anything not actionable,
the stated reason, into the task's evidence — the same location `appian-plan`
and `appian-build` already call `evidenceFile`. This skill does not invent a
second place for that record.

The auditor's verdict is the one exception, and it is not this skill's choice:
it goes to `<evidenceDir>/<task>/practices-review.json`, where `evidenceDir`
is the project's root from `.claude/appian-harness.json` (default `evidence`)
and everything under it is the plugin's fixed shape. That is the file the
plugin's closure gate opens when it asks whether this change was reviewed, so
a review recorded only in `evidenceFile` closes nothing.

## The active task file is cleared at close, by this skill

`appian-build` writes the active task file — `activeTaskFile` in
`.claude/appian-harness.json`, `tasks/current.json` when that file names none —
when it takes a task, and deliberately leaves it in place when it stops. A task
is not finished because the building stopped; it stops so that verification and
review can happen. The file therefore stays in flight through `appian-verify`
and through this skill, and **this skill deletes it as the last act of the
task**, because review is the last phase before close and nothing after it would
have a reason to look.

That ordering is the whole point, so it is worth stating as a sequence rather
than a rule: the verdicts are written first, and the deletion comes last. It is
the recorded act of closing, not a cleanup step that could be done early.
Deleting the file before `practices-review.json` exists produces a task that
looks closed to the closure gate — with nothing in flight it approves without
checking anything — while the review it was waiting on never happened.

**If the project builds concurrently, releasing this task's object leases is
part of the same closing act.** `appian-build` claims them before its first
write; nothing else is positioned to know the task is over. A lease left behind
is the same defect as an active task file left behind, one layer down: the
object stays blocked for every other builder, and it looks like coordination
rather than like a leak. Release the leases and delete the active task file
together, in that order, as the last thing this phase does.

Two paths reach that deletion, and both end the same way:

- **The change entered review.** Both agents ran with `phase=review`, the
  auditor's verdict is at `<evidenceDir>/<task>/practices-review.json`, and
  every finding is recorded with its classification. Then delete the file.
- **The change was exempt.** The entry threshold below was evaluated by someone
  outside the build step — never by whoever made the change — and the exemption,
  with who made the call and against which four conditions, is written into the
  task's evidence. Then delete the file.

Evaluating the entry threshold is itself this phase's work, so this skill is
invoked once per task even when the answer turns out to be "exempt". A task that
nobody routed here has not been found exempt; it has been left unexamined, and
its active task file is still sitting in flight.

One consequence of the exempt path is worth knowing before it surprises you: the
closure gate has no way to see an exemption. It asks for a valid, passing
`practices-review.json` and nothing else, so a stop taken while an exempt task is
still in flight blocks, and a repeated stop records `NOT_MEASURED` / `BLOCKING`
debt naming `practices-review` — accurate about the absence, misleading about the
reason. Delete the active task file once the exemption is recorded and the stop
passes cleanly; the gate is quiet because the task is closed, which is the truth
of it.

## When to Use

Review **enters** when a change:

- creates an object;
- writes data;
- exposes information;
- changes authorization;
- queries at volume; or
- touches a screen a user sees.

Any one of these is sufficient to trigger review — they are not a checklist that
all must hold.

A change is **exempt only when every one of the following holds, all at once**:

- it creates no new object;
- it touches no data, permissions, or queries;
- it does not change which component is used or the screen's structure; and
- it is a local, bounded change.

Missing even one of the four is enough to require review. And the exemption
decision is not the builder's to make: **the agent that produced the change
cannot classify its own change as exempt** — the same principle that keeps a
deferred gate from closing itself out with no owner other than whoever wanted it
closed. Route the exemption call to whatever already stands outside the build
step for this project, rather than letting it default to silence because no one
was asked.

## High-risk changes get a third question

A task the plan declared `high` — data model, security, architecture,
integrations, anything hard to reverse — takes one more pass: dispatch
`appian-practices-auditor` again with **`phase=risk`**, and its verdict lands
at `<evidenceDir>/<task>/practices-risk.json`. The closure gate requires it for
those tasks and for no others.

The reason it is worth a fourth opinion is that it asks a **different
question**, not a stricter version of the same one:

| Phase | Question |
|---|---|
| `review` | Does this do what the contract says, and only that? |
| `practices` (`phase=review`) | Does this follow the rules of the domains it touches? |
| **`risk`** | **How does this fail?** Under concurrency, at 10× volume, when a neighbouring object changes underneath it, reached by someone the authorization matrix did not consider — and if it were wrong, how would anyone find out? |

Three agents agreeing on a change they each judged on a different premise is
worth something. Three agents agreeing because they asked the same question
three times is worth nothing, and costs three times as much. That is the whole
test for whether a lens deserves to exist.

**Nothing here is a majority vote.** A single well-evidenced finding from one
reviewer outweighs two clean verdicts from the others, because the clean ones
are silence about a question they never asked.

Where Agent Teams are available, these are genuinely independent lines of
reasoning and can run in parallel — they share an artifact and a contract, and
nothing else. Where they are not, running them as sequential dispatches loses
nothing but wall-clock: each already receives its own context and none of them
reads another's output before forming its own. **Do not make the parallel form
a requirement.** The guarantee lives in the independence, not in the
concurrency.

## Review theatre

If across two or more cycles the reviewer raised substantive findings and
**none** were classified as actionable, the process is validating, not
doubting. That is an auditable property of the review process itself —
check it.

An agent that agrees with every finding it is shown is not a cheap reviewer; it
is an uninformative one. Two clean cycles in a row can mean the change really
was clean twice — or it can mean whoever classifies findings as actionable has
quietly started rubber-stamping. The two look identical from the outside unless
the classification history is actually checked, which is why this is a property
of the *process*, not of any single review.

## Common Rationalizations

| Thought | Why it's wrong |
|---|---|
| "The reviewer agreed with everything, so review is going well." | Agreement is not evidence of quality; it is either evidence the change was clean or evidence the review stopped doubting. Only the finding-to-actionable ratio across cycles distinguishes the two — see *Review theatre* above. |
| "This change is obviously cosmetic, I'll mark it exempt and move on." | The agent that made the change is the one instance disqualified from making that call. "Obviously" is exactly the word that precedes a missed criterion — check all four conditions explicitly, or hand the call to someone outside the build step. |
| "I'll summarize what I built so the reviewer doesn't waste time re-deriving it." | A summary is a conclusion. Handing it over biases the reviewer toward agreement before it has read the artifact. Hand over the object and the contract; let the reviewer re-derive the rest. |
| "The last review of a change like this one passed clean, so this one will too." | Each change gets its own review against its own contract. Resemblance to a prior clean review is not evidence — it is the same shortcut that produces review theatre if repeated across cycles. |
| "The finding wasn't marked actionable, so nothing needs to change here." | True only if the classification was made by someone with standing to make it, for a real reason. A pattern of findings that never land as actionable is the signal this skill exists to catch, not a track record to lean on. |
| "Both reviewers came back clean, so the change is solid." | The two agents audit different things — the contract and the doctrine — not the same thing twice. Agreement between them says nothing about what neither one is scoped to check. |
| "I'll clear the active task file first so the session can stop, then review." | That inverts the only ordering that makes the file mean anything. With nothing in flight the closure gate approves a stop without checking a single verdict, so the review it was waiting on becomes optional at exactly the moment it was about to happen. Verdicts first, deletion last. |
| "This change is exempt, so there is nothing for me to do here." | The exemption *is* the work: evaluated by someone outside the build step, checked against all four conditions, written into the task's evidence, and then the active task file cleared. A task nobody routed here has not been found exempt — it is unexamined, and still in flight. |

## Red Flags

- A reviewer dispatched with the builder's summary, explanation, or "this should
  be fine because…" instead of the artifact and the contract.
- A change marked exempt by the same agent or session that produced it.
- An exemption claim that satisfies some of the four conditions without checking
  all four.
- `appian-reviewer` or `appian-practices-auditor` invoked without `phase=review`,
  blurring build-time assistance with independent certification.
- Two or more review cycles in a row with zero findings classified actionable,
  and no one has asked why.
- A finding reclassified from actionable to not-actionable with no reason
  recorded.
- Findings that exist only in a reviewer's own output, never written into the
  task's evidence.
- A change that touches data, permissions, or an on-screen component treated as
  if it met the exemption threshold without being checked against it.
- The active task file deleted before the `phase=review` verdict exists, or
  before an exemption has been recorded. That deletion is the act of closing;
  taken early it hands the closure gate a session with nothing in flight, which
  it approves without checking anything.
- The active task file still in place after this skill has finished. The task is
  closed and the file now measures the *next* task's writes against this task's
  contract, while everything still looks like it is working.
- Object leases from this task still held after it closed. Nothing later has a
  reason to look, so they stay held forever — every other builder is blocked
  from an object nobody is working on, and the register reads like coordination
  instead of like a leak.
- A verdict reused from before a fix. If anything was rewritten in response to a
  finding, the `implementation` and `qa` verdicts that predate the rewrite
  certify an artifact that no longer exists; the closure gate now measures that
  against the write log and says so, but noticing it here is cheaper.

## Verification

Before treating a change as reviewed:

- [ ] The entry threshold was evaluated explicitly — not assumed — and any
      exemption was checked against all four conditions, by someone other than
      whoever made the change.
- [ ] `appian-reviewer` and `appian-practices-auditor` both ran with
      `phase=review`, against the same artifact and the same task contract.
- [ ] Neither reviewer received the builder's conclusion, summary, or verdict —
      only the artifact and the contract.
- [ ] Every finding from either agent is recorded with its classification
      (actionable / not actionable) and, where not actionable, the stated
      reason.
- [ ] The auditor's `phase=review` verdict exists at
      `<evidenceDir>/<task>/practices-review.json` — not merely somewhere in
      the task's evidence.
- [ ] Findings and classifications are written into the task's evidence, not
      left stranded in a reviewer's own output.
- [ ] The last two or more review cycles were checked for the review-theatre
      pattern — substantive findings raised but none classified actionable —
      and if present, it was flagged rather than passed through.
- [ ] The active task file was deleted, and deleted **last** — after the
      `phase=review` verdict existed, or on the exempt path after the exemption
      was recorded by someone outside the build step. Not before either, and not
      left behind.
