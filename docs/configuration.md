# What the plugin asks of your project

> Part of the [appian-harness](../README.md) documentation.

**Start here:** `/appian-init` adopts a project. It checks the three links the
plugin depends on, runs the two probes that answer whether the hooks govern
anything on this machine, writes `.claude/appian-harness.json`, and seeds a
one-page glossary into the project's `CLAUDE.md`. Run it once per project —
[Installing](installing.md#adopting-a-project-with-appian-init) walks through
what it does and what it reports. Everything below is what it sets up, and what
to do if you would rather do it by hand.

The plugin is deliberately free of any assumption about your repository layout.
It asks for configuration rather than guessing.

| Configuration | Why it is needed |
|---|---|
| **Where the specification lives** | `appian-plan` reads it; `appian-build` resolves acceptance criteria against it. |
| **Where the plan and the operational state live** | Two files, not one. A plan is approved and stable; state changes every task. Keeping them together makes both untrustworthy. |
| **Which naming convention is frozen** | Object prefixes and names the agent must not invent. |
| **What command runs the regression suite** | `regressionCommand`: the evidence of non-regression after any change that touches data or objects. |
| **Which identifier exercises the empty path** | `emptyPathIdentifier`: an id that is guaranteed *not* to exist, so empty states are tested on purpose rather than by accident. |

**These five are recorded, not resolved by code.** They are what a project records so the
people and agents following the process can find them, and the skills act on
them as prose: `appian-plan` opens the specification because the skill tells it
to, not because a hook resolved a key. No code in this plugin reads any of the
five — a project that writes them into a config file gets a note to its future
self, not behaviour. The regression command in particular is run by whoever is
following the process; the harness never runs it for them. That is the line
between doctrine an agent applies and a gate that holds without it, and it is
worth knowing before you expect a value recorded here to take effect on its own.

A sixth location — where a task's evidence gets recorded — is asked for per task
rather than once per project: `appian-plan` writes it into each task as
`evidenceFile`, and `appian-build` refuses to start without it. That is a
different thing from `evidenceDir` below: the plan places `evidenceFile`, and it
has no say over where the gates' verdicts go.

Everything specific to one application — the requirements document, real object
identifiers, test fixtures, the environment — stays in your project. None of it
belongs here.

### The one file the hooks read

The gates need paths they can open without asking anyone, so they read one file
at your project root, `.claude/appian-harness.json`:

```json
{
  "evidenceDir": "evidence",
  "activeTaskFile": "tasks/current.json",
  "maxAllowedObjects": 3,
  "officialAppianSkillPath": null,
  "designMcpServer": "appian-dev",
  "docsMcpServer": "appian-docs",
  "appianMcpToolPrefixes": ["mcp__appian-dev__", "mcp__appian__"],
  "measure": false
}
```

Every key is optional and the values above are the defaults, with one exception
worth naming here rather than discovering later: **`appianMcpToolPrefixes` has
no default.** The list above is what `/appian-init` fills it with on a typical
project, not what the hooks assume when the key is absent — absent, they fall
back to guessing from server names, which is the subject of *The perimeter*
below.

**The file's presence is the activation switch:** without it, every hook allows,
approves or no-ops, so the plugin installed in a project that does not use it
stays out of the way.

**Eight keys, and the list is closed.** `evidenceDir`, `activeTaskFile`,
`maxAllowedObjects`, `officialAppianSkillPath`, `designMcpServer`,
`docsMcpServer`, `appianMcpToolPrefixes` and `measure` are the whole of what a
0.7 scope makes the hooks open. Every other key in this file is inert to the
plugin: nothing rejects an extra one, and nothing acts on it either. A project
is free to record more here for its own use — the five items above are worth
writing down somewhere — as long as it does not expect the harness to notice.

`activeTaskFile` holds **one scope**: the work open right now, which objects it
may touch, and what for. Its schema is closed — a field the schema does not
declare is rejected rather than quietly ignored — and its `schemaVersion` is
what tells the hooks which rulebook to apply, which is the subject of *Two keys
a 0.7 project does not set* below. `maxAllowedObjects` is the atomicity budget:
past it, the scope gate asks.

`measure` is opt-in instrumentation, off by default: only the literal `true`
turns it on, and it is what makes `context-floor.json` and
`manualEstimateMinutes` exist at all. With it on, `manualEstimateMinutes` in the
scope file is anchored write-once to `manual-estimates.jsonl`; without it the
field is inert and one row says so.

`evidenceDir` works differently, and the distinction is the whole contract:
**your project chooses that root, and the plugin fixes the shape underneath
it.** A file written to any other shape is one the gates report as missing —
which reads as evidence to a person and as an absence to the gate.

### The perimeter: which tools the gates are allowed to see

`appianMcpToolPrefixes` is a **list**, and the list is the point. The perimeter
covers **two** servers, not one: the design server (`mcp__appian-dev__`, which
writes objects) and the runtime server (`mcp__appian__`, which starts processes
and invokes rules). Declare only the design one and process starts leave the
perimeter silently — the gates keep answering, so nothing looks broken.

Declaring the prefixes is how the gates match by declaration instead of guessing
from a server's name. Without the key they fall back to matching names that
contain `appian`, which is the failure this key exists to close: a server
registered as `lcp` or `indra` leaves the plugin installed and governing
nothing, and because the hook still answers, it is indistinguishable from a gate
that is working. So the fallback is not silent. Session start says so out loud,
in these words:

> **«Los hooks se están ejecutando pero no ven tus herramientas de Appian: el
> plugin está instalado y no gobierna nada.»**

and **the first write of the session asks**. An informative notice is not enough
when what failed is the perimeter, because a scope gate that sees no Appian
tools approves everything without a word. `/appian-init` fills the key from what
the session has registered and runs the perimeter probe before any of this can
happen; `session-start` re-checks it every session afterwards.

### Two keys a 0.7 project does not set

`activeRunFile` and `leaseFile` are read by the hooks, and they belong to the
rulebook a scope opened before 0.7 still closes under. They are read on that
branch only — the branch a scope with no `schemaVersion` takes — and they have
**no effect on a 0.7 scope**: the current path never opens either file.
`/appian-init` does not write them, and a project adopted on 0.7 has no reason
to.

They are named here because they are still reachable, not because they are
configuration anyone should be setting. The reason they survive at all is the
same reason the closure gate still accepts three obsolete phases: a scope opened
under the old rules has to be able to close, and removing what it depends on
would strand it.

### What the gates write under `evidenceDir`

| Path | Written by | Read by |
|---|---|---|
| `<evidenceDir>/<scope>/practices-<phase>.json` | `appian-practices-auditor`, one per invocation | Both gates. The scope gate reads `design`; the closure gate reads `certify` and `risk`. It also still accepts `implementation`, `review` and `qa` — obsolete, and accepted on purpose, so a scope opened before 0.7 can still close |
| `<evidenceDir>/<scope>/appian-skill-loaded.json` | **`observe-reads`, from what it saw**: the invocation of the official Appian skill and the reads under its root. A copy without `observedBy` was written by hand and credits nothing | The scope gate, before every write — as a remedy to the model, no longer as a question to a person |
| `<evidenceDir>/<scope>/dependents.json` | `appian-build`, before any delete or record-data overwrite, carrying `to-be-created` and `collisions` | The destructive guard. "Checked, zero dependents" and "never checked" are different answers |
| `<evidenceDir>/<scope>/render-poblado.json`, `render-vacio.json` | `appian-build`, one render per path | a person, and the judge in the phase that has one. The names are fixed; a render written to any other name is one nothing reads |
| `<evidenceDir>/<scope>/n2-poblado.json`, `n2-empty.json` | `n2_interface_tree.py`, one signal per render | the same. The trees themselves never travel — a signal is what a 218 KB tree reduces to |
| `<evidenceDir>/<scope>/render-signals.json` | `n2_interface_tree.py --record`, and the retention at close, which leaves the normalized hash of every render it retired | a person. Without a ceiling, evidence grows without limit |
| `<evidenceDir>/operations.jsonl` | `log-write`, one row per Appian write call | a person, afterwards |
| `<evidenceDir>/checks.jsonl` | `observe-reads`, one row per verification read of a batch: the call it came from, its object, the sequence it was taken at, its result and the class of guarantee it buys | the closure gate, which reads it as the floor — a read taken before the write it would accredit does not count |
| `<evidenceDir>/gate-decisions.jsonl` | the hooks: a name bound to a UUID, a state transition, every `ask` and its reason, a judge dispatched, a scope closed | a person, afterwards. In a `micro` scope this row *is* the account — no narrative is written |
| `<evidenceDir>/deferred-debt.jsonl` | the closure gate when forced to approve unverified work (`BLOCKING`), and either gate when an accepted deferral opens it (`DEFERRED`) | a person, afterwards, and `session-start`, which announces open debt |
| `<evidenceDir>/evidence-writes.jsonl` | `state-gate`, on any `Write` or `Edit` aimed at a file the gates read | a person, afterwards |
| `<evidenceDir>/task-closures.jsonl` | the closure gate, one row per close outcome: `closed`, `closed-pending-human` or `closed-with-debt` | a person, afterwards — and `measure_evidence.py`, reporting closes by state |
| `<evidenceDir>/manual-estimates.jsonl` | the hooks, anchoring `manualEstimateMinutes` write-once when `measure: true` | `measure_evidence.py`, as the manual metric's denominator |
| `<evidenceDir>/sessions.jsonl` | the hooks, one row per session: its id and its transcript path | the suspended-scope expiry count (sessions, not clocks), and `measure_evidence.py` as the pointer to the transcript |
| `<evidenceDir>/risk-downgrades.jsonl` | the closure gate, **on the rulebook a pre-0.7 scope closes under only** — a scope of that vintage taking the reduced verdict set its declared tier bought | a person, afterwards. A 0.7 scope never writes a row here: risk is observed by the hook, so there is no downgrade to record |

All nine logs are append-only, and four of them are re-read before appending —
the deferred-debt, risk-downgrade, task-closure and manual-estimate registers —
so that one deferral, or one scope closing on the cheap path, does not become
one line per attempt. The closure gate can fire repeatedly for the same scope, and a register
that repeats itself is a register nobody reads. They exist so that "how
often did this gate stop something, and did anyone answer yes?" — and "who
wrote this verdict?" — are questions with answers. Rotation is per closed
scope, so re-reading them does not grow without a ceiling either.

### How much evidence one scope leaves

The count a third party sees on opening `evidence/`, and the number to watch
release over release:

| Scope | Artefacts |
|---|---|
| `micro` with no reviewer, non-behavioural write | **1** |
| `micro` with a reviewer | **7** |
| `task`, one object, with a design verdict | **8** |

A scope that produces more than its size calls for is producing evidence nobody
reads; a scope that produces less is missing something a gate will name.

### Registering the MCP servers so they cost less

`/appian-init` recommends registering the Appian MCP servers with **deferred
schema loading**, and it is worth doing on the first day. The three servers come
to around 168 tools between them, on the order of **40–45 K tokens in every turn
of every session**, whether that session touches Appian or not. Deferring the
schemas is the only lever here that lowers the resident cost without removing a
single guarantee: a tool whose schema is fetched when it is first needed governs
exactly as much as one whose schema was resident all along.
