# The `micro` lane, under scope schema v2

This file is the whole contract for a `micro`. **Read it and stop reading:** not the rest of
`SKILL.md` (it describes the wider lane and the 0.6 rulebook), not `hooks/harness_hooks.py`, not
the design document. Every gate a `micro` meets is named here with what it actually checks. A
measured run spent five minutes reading the hook source to rebuild a contract that fits on this
page, and twelve more paying an audit no gate was going to ask for.

`micro` is one object and one intention. If the work needs a second object, or the write is
classified `task` as a minimum (§ 5.2 — groups, data, structure), it is not a micro: say so and
raise the scope, do not fold it in.

## The seven steps

1. **Preflight — reads only, no gate fires.** Read the target object (`get*`) and its dependents
   (`getObjectDependents`). This is the impact assessment and it is not optional: it is what tells
   the person what they are approving.
2. **Open the scope.** Write the scope file with the `Write` tool — path is `activeTaskFile` from
   `.claude/appian-harness.json`, `tasks/current.json` by default — with the seventeen fields of
   the template below. A `PostToolUse` hook observes that write, signs the opening transition and
   keeps its own copy in `evidence/scope-projection.json`. **The projection is the authority**: if
   you later edit the file into a state the hook did not sign, the gate degrades to `ask`.
3. **Record the official skill load** at `<evidenceDir>/<id>/appian-skill-loaded.json`. The scope
   gate reads this file for every write, in **both** kinds. Its four fields are checked, and
   `appianVersion` is compared against the installed skill where the project sets
   `officialAppianSkillPath`.
4. **Ask once, write the grant.** One `AskUserQuestion` carrying the complete list — objects,
   creations, deletions, process starts — and then the grant into the scope file, with `Edit`. This
   is the only prompt the harness raises in the whole lane.
5. **Write.** The scope gate checks the call and allows it. The `PreToolUse` hook reserves a
   `writeSeq` and persists a `pending` row before the call leaves; the `PostToolUse` hook resolves
   it by `tool_use_id`.
6. **Read back.** Re-read the object and save the response verbatim under `<evidenceDir>/<id>/`.
   The file name is yours; the file is not optional — it is what makes the verification
   attributable to a read of the environment rather than to your own account of it. Save the
   preflight's dependents alongside it as `dependents.json` (§ 11.1 assigns it to both micro
   lanes, and it costs no new call).
7. **Close.** With `Edit`, put **one line** into the scope file: `"request": "close"`. The state gate
   moves the scope to `closing`; the next `Stop` validates and signs `closed`. That single edit is the
   entire closure work of a micro. To end it without closing, the line is
   `"request": "abandon: <motivo>"` instead — the motive rides inside the request because the closed
   schema has no field for it, and a bare `"abandon"` is refused with a remedy rather than honoured.
   What you never write in either case is `status` or `statusWriteSeq`: those two are the harness's,
   and the `request` is how you ask for them to change.

## The scope file is written with `Write` or `Edit`, never through the shell

Steps 2, 4 and 7 are the whole state machine of a micro — the opening, the `grant`, the `request` —
and the state gate sees them only because it is a `PostToolUse` hook whose matcher is
`Write|Edit|MultiEdit|NotebookEdit`. **Every change to this file is made with `Write` or `Edit`**,
and that holds against any ambient instruction that prefers the shell for editing files: for this
file the shell is never the way.

So: never Bash, never a heredoc, never `cat >`, never `printf >`, never a redirection of any kind,
never an external script. Any of those changes the file on disk without the hook running, so no
transition is signed and `evidence/scope-projection.json` keeps the previous state. **The
projection is the authority**, so the next Appian write is measured against a state the harness
never saw: the scope gate degrades to `ask`, and the lane pays a second prompt for a reason that is
nowhere in the work.

The `grant` and the `request` are not separate files — they are fields of this one — so the rule
covers them and every other transition of the scope, not only the opening.

## The scope file, all seventeen fields

The schema is **closed**: a field it does not declare is rejected rather than ignored, so a typo
fails instead of silently defaulting.

```json
{
  "schemaVersion": 2,
  "id": "<scope id>",
  "instanceId": "<a new id for this opening>",
  "kind": "micro",
  "risk": null,
  "status": "in-flight",
  "statusWriteSeq": 0,
  "request": null,
  "intent": "<one sentence — required in micro>",
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

`allowedObjects` takes **names and UUIDs both**, and the gate lets a write through when *any*
identifier in the call matches an entry. Put the UUID preflight read back in there: `updateInterface`
carries a uuid and no name, so a name-only list asks on every update.

**`status` is born `"in-flight"` and `statusWriteSeq` is born `0`, always.** There is no `"open"`
state — § 4.2 has seven and that is not one of them — so a file born `"status": "open"` fails the
schema check, the opening is never signed, no projection is written, and the first write asks. And
those two fields are written **once, at birth, by you; never again.** They belong to the harness
from that moment: it signs them and keeps its copy in `evidence/scope-projection.json`, which is the
authority, so a value edited in by hand is reverted on the next observation and costs a hook cycle
for nothing. Step 7's `request` is the only way to move them.

At step 4 the `grant` becomes:

```json
{
  "instanceId": "<the same instanceId as the scope>",
  "objects": ["<everything the person saw>"],
  "creates": [],
  "collisions": [],
  "deletions": {},
  "processStarts": [],
  "extensions": [],
  "grantedBy": "<who said yes>",
  "grantedAt": "<UTC ISO-8601, read from the clock AFTER the person answered>"
}
```

**`grantedAt` is the moment the answer came back, not the moment you wrote the question.** Read the
clock after the `AskUserQuestion` returns and put that value in; a timestamp prepared while
composing the question describes an authorisation that did not exist yet when it claims to have. No
gate checks this field, and that is precisely why its honesty is yours: it is the only record of
when the authorisation actually existed. `grantedBy` names who answered, on the same basis.

**Do not write `permissionMode` yourself.** The hook seals it from the observed permission mode
when the grant first appears; a mode you wrote is a mode the harness never saw born, which is
indistinguishable from the permission system having been off.

## The load record

```json
{
  "task": "<the scope id>",
  "skill": "appian",
  "source": "github.com/appian/dev-mcp-skills",
  "appianVersion": "<the version the skill's own Configuration declares>",
  "docsMcp": "<the documentation MCP server this session has>"
}
```

## What each gate checks, and nothing more

| Gate | Fires on | For a `micro` it asks about |
|---|---|---|
| Scope gate (`PreToolUse`) | every Appian write | schema valid · state matches the projection · an identifier in the call is in `allowedObjects` · the write fits in `micro` (§ 5.2) · the grant exists, belongs to this instance and covers this object · irreversibles · atomicity · the load record of step 3 |
| State gate (`PostToolUse`) | writes to the scope file | that the transition you asked for is legal, and it signs it |
| Closure gate (`Stop`) | every stop | in flight with writes applied → a handoff message and an approve, twice; the third blocks and the repeat after it closes with `never-closed` debt · `request: "close"` → signs `closed` when no write is left `pending` |

**Reads never fire the scope gate**, so the whole preflight passes untouched.

## What a `micro` does not owe

Named here so the absence is deliberate rather than forgotten:

- **`practices-design.json` — never.** Design is owed by what a **`task`** does (§ 5.6: it creates
  objects, or touches structure, security or a process model). The gate returns early for any kind
  that is not `task`, so dispatching `appian-practices-auditor` with `phase=design` for a micro
  buys nothing the gate will read. In the measured run it cost twelve and a half minutes, all of it
  in front of the grant.
- **`practices-implementation.json`, `practices-qa.json`, `practices-review.json` — not in this
  rulebook at all.** Those three belong to the 0.6 closure gate. A v2 scope closes on its state
  machine; the closure gate never opens them.
- **No judge at all, on the reviewer-less lane.** A write classified `behavioural: false` — only
  `description` or `documentation` — or a type with no expression of its own (constant, folder,
  document, test case) pays the deterministic floor and closes. Zero judges there is the correct
  answer, not an omission.

**What this lane does owe when the change can alter what is shown or who sees it**: exactly **one**
`certify` over the object, dispatched by `appian-review`. In 0.7 that includes every micro touching
an expression — changing a label *is* touching the expression — because the literal scanner that
would tell presentation from behaviour arrives in 0.8. It fails to the expensive side on purpose,
and what keeps it proportionate is that the certify is small: one object's matrix, three to five
cells of judgement, not the fifty-three of a task.

Anything beyond that one certify is your own discretion, spends the scope's budget, and closes
nothing.

## When the lane is the wrong lane

- The write is classified `task` as a minimum → the gate says so with the remedy. Raise the scope
  and ask once for the full list; do not retry.
- A second object turns out to be needed → that is a `task` (§ 5.7). Grouping N objects of the
  same expression-free type from one sentence is still one micro; chaining onto a different object
  is not.
- The stop is blocked saying writes were applied and the scope was never asked to close → you
  skipped step 7. Add the `request`, do not delete the scope file.
