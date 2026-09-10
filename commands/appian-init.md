---
description: Adopt a project into appian-harness — checks the three links, proves the hooks actually run and actually see your Appian servers, writes the config the gates read, and seeds the glossary.
argument-hint: "[project-root] [--adopt] [--dry-run]"
---

# Adopt the harness in this project

Turn a project into one this harness governs, and **say plainly what is not
working**. Everything written here is a **project** artifact: the plugin stays
reusable and learns nothing about this application.

Run it once per project. Re-running is safe: report what already exists and
change nothing that does.

**Two arguments change what it does.** `--adopt` is the narrow form — it fills
in what an already-adopted project is missing and touches nothing else, and it
is the one thing a project upgraded from 0.6 has to run. `--dry-run` prints
every file it would write and writes none.

**This command does not install anything.** It does not clone the official
Appian skill, does not install a toolkit, and does not run `claude mcp add`.
It checks what is there and tells the truth about it. If a prerequisite is
missing, say so and point at it; do not fill the gap by guessing.

## 1. Check the three links before writing anything

There is no point configuring a harness whose prerequisites are absent, and
session start will say so on every future session anyway. Confirm now, and
report each one:

| Link | How to confirm | Healthy |
|---|---|---|
| Design MCP | `validateExpression("1 + 1")` | `{"hasErrors": false, "errors": []}` |
| Official Appian skill | Load the `appian` skill; read `**Appian Version:**` from its `SKILL.md` | The version this environment runs |
| Documentation MCP | Any real query | Documentation chunks, not empty |

**Listing tools is not a check** — it never reaches Appian. If a link is
missing, say so plainly and set up what you can; do not pretend the project is
ready to build.

## 2. Prove the hooks run on this machine

A hook that cannot be launched does not fail loudly. It does not run, and the
plugin installs, looks healthy and enforces nothing. So run one, and **report
its literal answer** — not your reading of it.

Use the probe published in **[the README](../README.md#before-you-trust-a-gate-check-that-it-is-alive)**,
exactly as written there. One recipe, in one place: a second copy is a second
thing to keep true.

A JSON answer means the hooks are live. If the answer is `sh: command not
found`, report it and then say this, in these words:

> **«los hooks no se están ejecutando en esta máquina; el plugin está instalado
> y no gobierna nada.»**

That is Windows without Git Bash, and the risk stays accepted. What stops being
accepted is that it is **invisible**.

## 3. Prove the hooks can see your Appian servers

The twin of step 2, and the more dangerous of the two, because it has no
symptom at all: the hooks run, answer, greet you — and gate nothing.

Until 0.7 the gates matched Appian by looking for the string `appian` in the
MCP server's name, which is a name whoever ran `claude mcp add` chose. Call the
server `lcp`, `indra` or `appdev` and every gate in this plugin went quiet
while continuing to answer.

1. Read the MCP servers this session has registered.
2. **Fill `appianMcpToolPrefixes[]` from what is actually registered**, not from
   a convention. It is a **list**, because the perimeter covers **two** servers:
   the design one, whose tools write objects, and the **runtime** one, whose
   tools start processes and invoke rules. Declaring only the design server
   un-gates every process start in silence, which is the same failure wearing
   different clothes.
3. **Run the probe once per server**, and this is the same probe as step 2 with
   one substitution: put a **real write tool name from that server** in the
   payload's `tool_name` — `mcp__lcp__createInterface` if the server is called
   `lcp` — instead of the example's. Then read the answer:

   | The probe answers | What it means |
   |---|---|
   | `"permissionDecision":"ask"`, or an `allow` whose reason is about the scope | The perimeter covers this server |
   | `"permissionDecisionReason":"not a write tool"` | **Mismatch.** A genuine Appian write tool fell outside the perimeter, which is the whole failure |

   That second answer is the one to watch for, because it is the one that looks
   healthy. Report it, and say this, in these words:

   > **«Los hooks se están ejecutando pero no ven tus herramientas de Appian: el
   > plugin está instalado y no gobierna nada.»**

Session start re-checks this key every session and repeats that sentence when
it is missing or empty. Without it the gates fall back to matching server names
and **the first write of each session asks** — an informative notice is not
enough when what failed is the perimeter itself.

## 4. Ask before assuming

Four questions, and **ask them rather than defaulting** — a convenient default
silently becomes the convention the next project inherits without anyone
choosing it:

1. Where should the **specification** live?
2. Where should the **plan** and the **operational state** live? (Two files. A
   plan is approved once; state changes as work closes.)
3. Where should **decisions** be recorded — the constraints that shaped the
   design, with the reference that settled each one?
4. What command runs the **regression suite**, and which **identifier is
   guaranteed not to exist** so the empty path gets exercised on purpose?

Offer the layout below as a starting point, and take whatever the project says
instead.

## 5. Write `.claude/appian-harness.json`

Its **presence is the activation switch**: without it every hook allows,
approves or no-ops, so the plugin installed in a project that does not use it
stays out of the way.

```json
{
  "evidenceDir": "evidence",
  "activeTaskFile": "tasks/current.json",
  "maxAllowedObjects": 3,
  "officialAppianSkillPath": "~/.claude/skills/appian",
  "designMcpServer": "appian-dev",
  "docsMcpServer": "appian-docs",
  "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
  "measure": false,

  "specPath": "docs/specification.md",
  "planPath": "docs/plan.md",
  "statePath": "docs/state.md",
  "decisionsPath": "docs/decisions.md",
  "regressionCommand": "<the command>",
  "emptyPathIdentifier": "<an id guaranteed not to exist>"
}
```

**Report which half is which, and do not blur it.** The first eight are opened
by the hooks. The rest are **recorded for people and for the lifecycle skills
to read**, and no hook resolves them — saying otherwise would repeat the mistake
this plugin spent a paragraph apologising for.

Three notes worth making out loud when you write it:

- **`appianMcpToolPrefixes[]` is the one key with no safe default.** Step 3
  fills it. If step 3 could not, write what you found and repeat its sentence.
- **`measure` stays `false`.** It is opt-in instrumentation, and leaving it off
  is one file and one question fewer per piece of work, permanently. Turn it on
  only to measure the harness itself.
- **Do not write `activeRunFile` or `leaseFile`.** They belong to the previous
  rulebook, which the hooks keep so that work opened under the old rules can
  still finish under them. On anything opened today they have no effect, and a
  key that does nothing reads as a setting somebody chose.

**Omit a key you are not setting rather than writing `null` for it.** A config
full of nulls reads as *configured to nothing* rather than *not configured*.

## 6. Seed the glossary into the project's `CLAUDE.md`

Six terms, and only six. Everything else the harness keeps track of lives in
files and belongs in no text a person reads — if one of those turns up in a
message, the defect is the message's.

**Back up `CLAUDE.md` first, then merge.** Never overwrite: a project's
`CLAUDE.md` is somebody's work.

```markdown
## appian-harness — the six words

| Term | What it means |
|---|---|
| **Scope** (*alcance*) | The work that is open right now: which objects may be touched, and what for |
| **Size** (*tamaño*) | `micro` — one object, one intention — or `task` for everything else. The harness decides it and announces it before starting |
| **Permission** (*permiso*) | The "ok" asked **once per scope**, with the full list and what is going to happen to each thing |
| **Close** (*cierre*) | Go through the checks and finish. The other two ways out are **abandon**, with a reason, and **desist**, leaving it as it stands |
| **Debt** (*deuda*) | What was left pending, with an **owner** and the condition that clears it. Announced at the start of the next session |
| **Expiry** (*caducidad*) | A check stops counting when a write could have changed what it asserted. If nothing could have, it is not repeated |
```

The Spanish names are there because several of the harness's own messages use
them.

## 7. Create the state layer

```
evidence/          # written by the gates and the judge; commit it
tasks/             # the open scope lives here; one at a time
docs/
  specification.md # written when requirements have to be closed first
  plan.md          # written when splitting the work buys something
  state.md         # rewritten as work closes
  decisions.md     # what was decided and which reference settled it
```

Seed `state.md` so a session opening it after `/clear` can tell where things
stand — including the thing nothing else records:

```markdown
# Operational state
**Open now:** none yet
**Next:** — **Blocked:** —

## Ledger
| Work | Outcome | Evidence |
|---|---|---|
```

The ledger is the single source of truth for progress, and the one place work
that was **never started** is visible. The evidence tree shows what was built;
only this shows what was not.

## 8. Say what the regression command actually covers

The `regressionCommand` you seed is **scoped**: the object touched plus its
direct dependents, deduplicated by identity, with the application row
discounted. The whole-application sweep stays **opt-in** — for before a
delivery, not for every write.

And be honest about it, because this is where a regression suite quietly
overpromises: **most dependent types have no runnable check.** Enumerate what
can be executed and declare what cannot. The per-type floor the closure gate
enforces is the authority here — do not restate it, point at it — but the shape
is:

| Dependent type | What can actually be run |
|---|---|
| Interface | A test render, populated and empty |
| Expression rule | Its existing test cases |
| Process model | Its node graph, checked for the structural faults |
| Record type | A data read that proves the sync returns rows |
| Record data | A before/after difference |
| Web API · integration · connected system | Design validation |
| Everything else — sites, groups, constants, folders, documents, applications, user filters | **Nothing runnable.** The floor buys a re-read: the object is there and says what it should. That is a smaller claim, and it is the true one |

A command that lists thirty dependents and can exercise six of them has to say
which six. Report the split when you seed it.

## 9. Recommend deferred schema loading

The three Appian MCP servers total on the order of 168 tools, and their schemas
cost roughly **40–45 K tokens in every turn of every session**, whether or not
anything touches Appian. Registering them with **deferred schema loading** means
a tool's schema arrives only when the tool is about to be used.

It is the only lever that lowers what a session costs **without removing a
single guarantee**, so recommend it here, once, with that number attached.

## 10. Report, and say what is not ready

Print: the result of each of the three link checks; the **literal** answer the
hook probe gave; the result of the perimeter probe and what went into
`appianMcpToolPrefixes[]`; the paths written; the directories created; what
already existed and was left alone; the regression split from step 8; and the
next step — the build skill is the entry point, and it decides for itself
whether requirements or a plan are owed first.

If any check failed, **repeat it at the end**. The useful place for that news is
where somebody is about to act on it.

## Do not

- Do not create Appian objects. This is project setup, not build.
- Do not install anything, or offer to. Prerequisites are the reader's to put
  in place.
- Do not invent the four paths without asking.
- Do not overwrite an existing `.claude/appian-harness.json`, a plan, an
  evidence tree, or a `CLAUDE.md`. Report and leave them.
- Do not claim a link is present because a tool name appears in a list.
- Do not report a probe's meaning in place of its answer. Quote what it said.
