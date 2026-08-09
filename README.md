# appian-harness

A quality harness for building Appian applications with coding agents.

An agent with write access to an Appian environment can produce a great deal of
work that validates cleanly and is still wrong. `validateExpression` proves the
platform accepts an expression (field experience). A green test case proves a
path did not throw —
not that the path was ever exercised. Neither says anything about whether the
right component was chosen, whether the screen has a heading, or whether a colour
resolved from the database is readable against its background.

This plugin exists to close that gap. It is a set of lifecycle skills, a
Definition of Done expressed as quality gates, a verification pyramid that
states level by level what each kind of check does and does not prove, and a
set of hooks that stop the whole thing from being advice an agent can talk
itself out of.

## The guiding principle

> **Whoever builds does not certify.**

The agent that wrote an object is the worst possible judge of whether it is
finished. It knows what it intended, so it reads the artifact as if the intent
were present. Verification and review are therefore separate roles with their
own context, and the reviewer receives the **artifact and the contract — never
the builder's conclusion**. Handing a reviewer your verdict biases it toward
agreement.

Three consequences run through everything here:

1. **One task per invocation, then stop.** Not one phase. A task is the unit a
   reviewer can reject on its own.
2. **Three outcomes, not two.** `PASS`, `FAIL`, and `NOT MEASURED`. The third is
   not a pass, and it is the one that gets silently skipped.
3. **The remote state wins.** Your artifact lives on a server you do not own
   alone. There is no clean working tree to rely on, so every task begins with a
   preflight against the real environment.

## The cycle

```
SPECIFY → PLAN → [ BUILD → VERIFY → REVIEW ] → CLOSE
                    └───── per TASK, not per phase ─────┘
```

A human orchestrates between phases. An agent that chains specify → plan → build
→ review in one run loses exactly the checkpoints that catch work heading in the
wrong direction.

## Skills

| Skill | Phase | What it does |
|---|---|---|
| `appian-specify` | SPECIFY | Turns a vague request into a written specification: actors, entities and relationships, states and transitions, an authorization matrix, volume, and an explicit **out of scope**. One question at a time. |
| `appian-plan` | PLAN | Breaks the specification into **vertical Appian slices** (record type → query rule → interface → test case), ordered by the dependencies the platform actually imposes, each with its own acceptance criteria. |
| `appian-build` | BUILD | Implements exactly one approved task and stops. Preflight before any write, asymmetric treatment of irreversible actions, no blind retries. Manually invoked. |
| `appian-verify` | VERIFY | Produces the per-gate report with evidence, in its own context. |
| `appian-review` | REVIEW | Independent review from a clean context, graduated by risk. |
| `appian-best-practices` | cross-cutting | Official Appian best practices routed by domain, plus the quality gates that define done. Loaded before any write and before declaring an object finished. |

`appian-best-practices` carries eleven domain references — data model and record
types, SAIL interfaces, process models, expression rules, performance, security,
integrations, ALM and testing, sites and navigation, quality gates, reliability
and operations. The `SKILL.md` is the index: only the reference the change
touches gets opened.

**Description phrasing.** The six `SKILL.md` files here write their trigger
clause in the imperative ("Use when...", "Use after..."), not the third person
`plugin-dev:skill-development` recommends ("This skill should be used
when..."). That is a deliberate house style, kept consistent across every
skill in this plugin, not an oversight: `plugin-dev:skill-reviewer` found the
grammatical person does not itself affect whether a description triggers —
what does is the specificity of the conditions it states. `scripts/lint_skills.py`
accepts both forms, so a contributor who follows the official third-person
guidance is not rejected for it.

## Agents

The skills orchestrate; three agents do the judging, each in its own context so
that no judgement is formed by whoever produced the work.

| Agent | What it judges |
|---|---|
| `appian-practices-auditor` | One phase — `design`, `implementation`, `review` or `qa` — against the domain references, writing a verdict that cites the sections it applied. |
| `appian-verifier` | Whether the evidence on hand covers each gate the task's contract requires, naming the evidence behind every `PASS`. |
| `appian-reviewer` | Whether the change holds up against its contract, from the artifact alone — it is never handed the builder's conclusion. |

## The gates

Everything above is doctrine an agent can decide to skip. Four hooks make the
central parts of it hold whether or not the agent agrees:

- **scope gate** (before any Appian write) — is there an approved active task,
  is this object inside its `allowedObjects`, is the task atomic, and is there a
  *passing* `design` audit for it? Not merely present: structurally valid, with
  citations that resolve, and an outcome of `PASS` or a sanctioned deferral.
- **closure gate** (on stop) — a task does not close without valid, passing
  `implementation`, `review` and `qa` verdicts. On a repeated stop it approves
  rather than deadlocking, and records the omission as `NOT MEASURED ·
  BLOCKING` debt, because a guardrail that cannot be satisfied gets switched
  off and then protects nothing.
- **write log** and **failure notice** — the harness records what was written,
  and tells an agent not to retry a failed write blind.

The write gate never answers *deny* — the strongest thing it says is *ask* — and
when the closure gate blocks for missing verdicts it blocks once, approving a
second stop attempt and writing down what went unverified. Both shapes come from
the same reasoning: a guardrail with no way past it gets switched off, and then
it protects nothing. That escape is for missing verdicts only: a hook that
cannot inspect something at all — an unreadable config, malformed JSON — asks or
blocks every time, with no second-attempt release, because a hook that cannot
see is not a hook that should be waved through.

## The verification pyramid

Each level is named by what it catches, and each is honest about what it cannot
see. Cheapest first.

| Level | Operates on | Catches |
|---|---|---|
| **N0** Syntax | the expression | Whether it parses and whether the rules it calls exist |
| **N1** Static | the source | Components, icons, enumerated values, patterns, accessibility rules |
| **N2** Structural | the **evaluated component tree** | Everything that only exists once data is resolved |
| **N3** Coordinates | process models | Overlapping nodes, proximity, backward flow, lanes |
| **N4** Behaviour | test cases and the regression suite | Nominal, empty, null, error and repeat paths |
| **N5** Perceptual | a screenshot of the running site | Visual hierarchy, density, responsiveness, focus |
| **N6** Human | — | Screen reader, Design Guidance, real login per role |

**N2 is the level most harnesses are missing.** A rendered-interface test does
not return an image, but it returns the component tree **already evaluated with
resolved data** (field experience) — heading tags, labels, row headers,
empty-grid messages, and colours that came out of the database. Those colours
do not appear in the source at all, so no linter over the source will ever see
them. That is the gap a 1.6:1 status chip walks through.

Two operating notes for N2, both learned the hard way and offered as field
experience rather than documentation: the default response size cap truncates a
real screen, so raise it and trust the truncation flag rather than the byte
count; and some API surfaces fail to serialize certain component types, so pick
the surface that answers correctly rather than the one that answers first.

## Installing

Add the plugin to a marketplace your Claude Code installation trusts, then:

```
/plugin install appian-harness
```

To try it from a local checkout, this repository is its own marketplace — the
manifest at `.claude-plugin/marketplace.json` lists the plugin with `"source":
"./"`. Point Claude Code at the checkout, then install:

```
/plugin marketplace add /path/to/appian-harness
/plugin install appian-harness@appian-harness-local
```

The skills carry no runtime dependencies. The hooks and the validators under
`scripts/` need Python 3 on the `PATH` as `python`, and nothing beyond the
standard library.

## What the plugin asks of your project

The plugin is deliberately free of any assumption about your repository layout.
It asks for configuration rather than guessing.

| Configuration | Why it is needed |
|---|---|
| **Where the specification lives** | `appian-plan` reads it; `appian-build` resolves acceptance criteria against it. |
| **Where the plan and the operational state live** | Two files, not one. A plan is approved and stable; state changes every task. Keeping them together makes both untrustworthy. |
| **Which naming convention is frozen** | Object prefixes and names the agent must not invent. |
| **What command runs the regression suite** | The evidence of non-regression after any change that touches data or objects. |
| **Which identifier exercises the empty path** | An id that is guaranteed *not* to exist, so empty states are tested on purpose rather than by accident. |

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
  "maxAllowedObjects": 3
}
```

Every key is optional and the values above are the defaults. **The file's
presence is the activation switch:** without it, every hook allows, approves or
no-ops, so the plugin installed in a project that does not use it stays out of
the way.

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
| `<evidenceDir>/operations.jsonl` | the write log | a person, afterwards |
| `<evidenceDir>/gate-decisions.jsonl` | the scope gate, every time it asks | a person, afterwards |
| `<evidenceDir>/deferred-debt.jsonl` | the closure gate, when forced to approve unverified work | a person, afterwards |

The three logs are append-only and nothing in the plugin reads them back. They
exist so that "how often did this gate stop something, and did anyone answer
yes?" is a question with an answer.

## What this plugin does not do

Stated plainly, because a harness that overstates its coverage is worse than no
harness:

- **It does not replace human judgement over the rendered screen.** No level
  below N5 has seen the interface. Component choice, visual hierarchy and
  whether it reads on a phone are decided by looking at it.
- **It does not verify connection routing in process models.** The API exposes
  node coordinates but not waypoints (field experience), so the layout checks
  tell you where every node sits — not where any arrow goes.
- **It does not read Design Guidance.** Those warnings are not exposed
  programmatically (field experience). If they matter to you, they are a
  deferred criterion with a human owner, not a gate the harness can close.
- **It does not check node dimensions.** Width and height are not exposed
  (field experience), so the separation thresholds are a proxy for "these do
  not overlap", not a proof.
- **It does not certify security from a design environment.** Record-level and
  field-level restrictions are not applied to a designer (field experience),
  so testing there produces a false positive. That check requires a real user
  per role.

A criterion the harness cannot measure is reported as `NOT MEASURED`, with an
owner and a closing condition. It is never quietly upgraded to `PASS`.

## Sources

The citation policy applies to the plugin's reference documents — the domain
references under `appian-best-practices` — not to this README. There, every
claim about Appian platform behaviour must be cited to the official
documentation at `docs.appian.com/suite/help/latest/…` (using the `latest`
alias so links do not expire) or explicitly marked as field experience. A claim
never carries a URL that was not checked: either it resolves, or the claim is
marked instead.

There is a third label, used only where it applies. The reliability and
operations reference carries claims marked **`[engineering]`**: general
distributed-systems doctrine — idempotency, optimistic locking, backoff,
reconciliation — applied to Appian. These have no `docs.appian.com` page
because they are not platform-specific, and marking them that way keeps them
from being mistaken for platform behaviour Appian documents and guarantees.
The rule they share with the other two labels is the same: no claim goes
unlabelled, and no label is a URL nobody verified.

This README is a summary, not a reference document, and carries no citations
of its own. Platform-behaviour claims that come from field use are marked
`(field experience)` inline.

## License

MIT — see [LICENSE](LICENSE).
