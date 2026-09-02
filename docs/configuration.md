# What the plugin asks of your project

> Part of the [appian-harness](../README.md) documentation.

**Start here:** `/appian-init` checks the three requirements, asks where this
project wants its specification, plan, state and decisions to live, writes
`.claude/appian-harness.json`, and creates the state layer including the task
ledger. Run it once per project. Everything below is what it sets up, and what
to do if you would rather do it by hand.

The plugin is deliberately free of any assumption about your repository layout.
It asks for configuration rather than guessing.

| Configuration | Why it is needed |
|---|---|
| **Where the specification lives** | `appian-plan` reads it; `appian-build` resolves acceptance criteria against it. |
| **Where the plan and the operational state live** | Two files, not one. A plan is approved and stable; state changes every task. Keeping them together makes both untrustworthy. |
| **Which naming convention is frozen** | Object prefixes and names the agent must not invent. |
| **What command runs the regression suite** | The evidence of non-regression after any change that touches data or objects. |
| **Which identifier exercises the empty path** | An id that is guaranteed *not* to exist, so empty states are tested on purpose rather than by accident. |

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
  "leaseFile": null,
  "activeRunFile": null,
  "designMcpServer": "appian-dev",
  "docsMcpServer": "appian-docs",
  "measure": false
}
```

Every key is optional and the values above are the defaults. **The file's
presence is the activation switch:** without it, every hook allows, approves or
no-ops, so the plugin installed in a project that does not use it stays out of
the way.

**Nine keys, and the list is closed.** `evidenceDir`, `activeTaskFile`,
`maxAllowedObjects`, `officialAppianSkillPath`, `leaseFile`, `activeRunFile`,
`designMcpServer`, `docsMcpServer` and `measure` are the whole of what the
hooks open today. `measure` is opt-in instrumentation, off by default: only
the literal `true` turns it on, and it is what makes `manualEstimateMinutes`
in the active task file exist at all (anchored write-once to
`manual-estimates.jsonl`; without it the field is inert and one row says so). Every other key
in this file is inert to the plugin: nothing rejects an extra one, and nothing
acts on it either. A project is free to record more here for its own use — the
five items above are worth writing down somewhere — as long as it does not
expect the harness to notice.

`activeTaskFile` holds the task the gates enforce against — its `id` and its
`allowedObjects`. `maxAllowedObjects` is the atomicity budget: past it, the
scope gate asks.

`evidenceDir` works differently, and the distinction is the whole contract:
**your project chooses that root, and the plugin fixes the shape underneath
it.** A file written to any other shape is one the gates report as missing —
which reads as evidence to a person and as an absence to the gate.

| Path | Written by | Read by |
|---|---|---|
| `<evidenceDir>/<task>/practices-<phase>.json` | `appian-practices-auditor`, one per phase | Both gates. The scope gate reads `design`; the closure gate reads `implementation`, `review`, `qa` |
| `<evidenceDir>/<task>/appian-skill-loaded.json` | `appian-build`, when it loads the official Appian skill for the task | The scope gate, before every write — see [Requirements](../README.md#requirements) |
| `<evidenceDir>/<task>/dependents.json` | `appian-build`, before any delete or record-data overwrite | The destructive guard. "Checked, zero dependents" and "never checked" are different answers |
| `<evidenceDir>/<task>/gates.md` | `appian-verify`, consolidating the per-gate report with both its verdicts | a person, or the review step. **No gate reads it** — it sits beside the verdicts so the task's evidence is one account rather than a directory to reassemble |
| `<evidenceDir>/operations.jsonl` | the write log | a person, afterwards |
| `<evidenceDir>/gate-decisions.jsonl` | the scope gate, every time it asks | a person, afterwards |
| `<evidenceDir>/risk-downgrades.jsonl` | the closure gate, when a task closes on the `trivial` tier | a person, afterwards. Cheaper ceremony is allowed; choosing it is recorded |
| `<evidenceDir>/deferred-debt.jsonl` | the closure gate when forced to approve unverified work (`BLOCKING`), and either gate when an accepted deferral opens it (`DEFERRED`) | a person, afterwards |
| `<evidenceDir>/evidence-writes.jsonl` | the evidence-write log, on any `Write` or `Edit` aimed at a file the gates read | a person, afterwards |
| `<evidenceDir>/task-closures.jsonl` | the closure gate, one row per close outcome: `closed`, `closed-pending-human` or `closed-with-debt` | a person, afterwards — and `measure_evidence.py`, reporting closes by state |
| `<evidenceDir>/manual-estimates.jsonl` | the hooks, anchoring `manualEstimateMinutes` write-once when `measure: true` | `measure_evidence.py`, as the manual metric's denominator |

The seven logs are append-only, and four of them are re-read before appending —
the deferred-debt, risk-downgrade, task-closure and manual-estimate registers —
so that one deferral, or one task closing on the cheap tier, does not become
one line per attempt. The closure gate can fire repeatedly for the same task, and a register
that repeats itself is a register nobody reads. They exist so that "how
often did this gate stop something, and did anyone answer yes?" — and "who
wrote this verdict?" — are questions with answers.

