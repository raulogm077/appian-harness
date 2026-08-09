---
description: Set up a project to use appian-harness — writes the config the gates read, creates the state layer, and checks the three requirements are actually there.
argument-hint: "[project-root]"
---

# Adopt the harness in this project

Turn a project into one this harness governs. Everything here is a **project**
artifact: the plugin stays reusable and learns nothing about this application.

Run this once per project. Re-running it is safe — report what already exists
and change nothing that does.

## 1. Check the three requirements before writing anything

There is no point configuring a harness whose prerequisites are absent, and the
session-start hook will say so on every future session anyway. Confirm now, and
report each one:

| Link | How to confirm | Healthy |
|---|---|---|
| Design MCP | `validateExpression("1 + 1")` | `{"hasErrors": false, "errors": []}` |
| Official Appian skill | Load the `appian` skill; read `**Appian Version:**` from its `SKILL.md` | The version this environment runs |
| Documentation MCP | Any real query | Documentation chunks, not empty |

Listing tools is **not** a check — it never reaches Appian. If a link is
missing, say so plainly and set up what you can; do not pretend the project is
ready to build.

## 2. Ask before assuming

Four questions, and **ask them rather than defaulting** — a convenient default
silently becomes the convention the next project inherits without anyone
choosing it:

1. Where should the **specification** live?
2. Where should the **plan** and the **operational state** live? (Two files.
   A plan is approved once; state changes with every task.)
3. Where should **decisions** be recorded — the constraints that shaped the
   design, with the reference that settled each one?
4. What command runs the **regression suite**, and which **identifier is
   guaranteed not to exist** so the empty path gets exercised on purpose?

Offer the layout below as a starting point, and take whatever the project says
instead.

## 3. Write `.claude/appian-harness.json`

Its **presence is the activation switch**. Eight keys are read by code and the
list is closed; write the project's own answers alongside them so a future
session can find those too:

```json
{
  "evidenceDir": "evidence",
  "activeTaskFile": "tasks/current.json",
  "maxAllowedObjects": 3,
  "officialAppianSkillPath": "~/.claude/skills/appian",
  "designMcpServer": "appian-dev",
  "docsMcpServer": "appian-docs",
  "activeRunFile": null,
  "leaseFile": null,

  "specPath": "docs/specification.md",
  "planPath": "docs/plan.md",
  "statePath": "docs/state.md",
  "decisionsPath": "docs/decisions.md",
  "regressionCommand": "<the command>",
  "emptyPathIdentifier": "<an id guaranteed not to exist>"
}
```

**Report which half is which, and do not blur it.** The first eight are opened
by the hooks. The rest are **recorded for people and for the lifecycle skills to
read**, and no hook resolves them — saying otherwise would repeat the mistake
this plugin spent a paragraph apologising for.

Two of the eight decide how much the harness constrains this project, so ask
rather than defaulting them to `null`:

- **`activeRunFile`** — set it (`tasks/run.json`) if you want writes confined to
  a run somebody explicitly authorized. `appian-build` is model-invocable, so
  left `null` the model can start a build on its own; it still has to produce an
  active task file, a skill-load record and a passing design verdict first, but
  nothing asks *who said so*. Set it and that question has an answer.
- **`leaseFile`** — only for **concurrent builders**, and only pointing somewhere
  every worktree shares. A lease register each builder has a private copy of is
  worse than none, because it looks like coordination.

**Omit a key you are not setting rather than writing `null` for it.** For
`evidenceDir`, `activeTaskFile` and `maxAllowedObjects` the two are now the same
thing — the hooks read them so that an explicit `null` falls back to the default
exactly as an absent key does, which they did not always do, and a null used to
stop the write log dead. The reason to omit anyway is the next key: nothing
guarantees that equivalence for a key added later, and a config full of nulls
reads as *configured to nothing* rather than *not configured*.

## 4. Create the state layer

```
evidence/          # written by the gates and the auditors; commit it
tasks/             # the active task file lives here; one task in flight
docs/
  specification.md # SPECIFY writes this
  plan.md          # PLAN writes this; approved once
  state.md         # PLAN rewrites this whenever a task closes
  decisions.md     # what was decided and which reference settled it
```

Seed `state.md` so a session that opens it after `/clear` can tell where things
stand — including the thing nothing else records:

```markdown
# Operational state
**Current task:** none yet
**Next:** — **Blocked:** —

## Task ledger
| Task | Status | Evidence |
|---|---|---|
```

The ledger is the single source of truth for progress, and the one place a task
that was **never started** is visible. The evidence tree can show what was
built; only this can show what was not.

## 5. Report, and say what is not ready

Print: the requirement check for each of the three links, the paths written, the
directories created, what already existed and was left alone, and the next step
(`appian-specify` for a new module, `appian-plan` if a specification already
exists). If any requirement was missing, repeat it at the end — the useful place
for that news is where someone is about to act on it.

## Do not

- Do not create Appian objects. This is project setup, not build.
- Do not invent the four paths without asking.
- Do not overwrite an existing `.claude/appian-harness.json`, a plan, or an
  evidence tree. Report and leave them.
- Do not claim a link is present because a tool name appears in a list.
