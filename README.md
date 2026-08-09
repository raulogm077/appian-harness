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

**CLOSE is not a skill.** The first five phases each have one; CLOSE is what the
`Stop` hook does. There is no `appian-close` to look for.

## What is in the box

| Path | What is there |
|---|---|
| `skills/` | Six skills: five lifecycle phases plus the cross-cutting doctrine |
| `skills/appian-best-practices/references/` | Eleven domain references, numbered `01`–`11`. Every verdict cites into these |
| `agents/` | Three judging agents: `appian-practices-auditor`, `appian-reviewer`, `appian-verifier` |
| `hooks/` | One `hooks.json` declaring five hooks, a POSIX launcher (`run_hook.sh`) and their Python implementation |
| `scripts/` | Four modules: `validate_verdict.py`, `lint_skills.py`, `n2_interface_tree.py`, `n3_process_layout.py` |
| `.claude-plugin/` | `plugin.json`, and a `marketplace.json` that makes this checkout its own marketplace |

The Python carries its own tests — 84 for `scripts/`, 40 for `hooks/`, standard
library only:

```
python3 -m unittest discover -s scripts
python3 -m unittest discover -s hooks
python3 scripts/lint_skills.py
```

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

## How it is used, end to end

One small task, all the way through. Say the request is *"users need to see the
requests that are still open"*, and the plan has already turned that into
`TASK-3: list open requests`. Paths below use the defaults; which of them are
configurable, and how, is *What the plugin asks of your project*.

**1. `appian-specify`** — asks one question at a time and writes a
specification: actors, entities and relationships, states and transitions, an
authorization matrix, expected volume, and an explicit *out of scope*. Nothing
automated checks this and nothing should; it is read by a person, and no Appian
object exists yet for a gate to have an opinion about.

**2. `appian-plan`** — reads that specification and writes **two** files: the
plan, and the operational state. Two rather than one because a plan is approved
and then stable while state changes every task, and a file that is both is
trusted as neither. It cuts the work into vertical slices — record type → query
rule → interface → test case — ordered by the dependencies Appian actually
imposes, and gives each task four named parts: `allowedObjects`,
`acceptanceCriteria`, `requiredGates`, `evidenceFile`. Still nothing automated,
but this is where the later prompts are decided: `TASK-3` listing seven objects
is a task that will stop at every write.

**3. `appian-build TASK-3`** — invoked by name and only by name; it carries
`disable-model-invocation: true` because it is the one skill with irreversible
side effects. In order, it:

- writes the active task file, `tasks/current.json`, as
  `{"id": "TASK-3", "allowedObjects": ["APP_openRequests", "..."]}` — spelled
  with those two keys, because the hooks look for those names and nothing near
  them;
- **preflights**: reads the real environment and classifies every object in
  scope as ABSENT, PRESENT AND CONFORMING, PRESENT BUT INCOMPLETE, or
  CONFLICTING. The remote state wins over any local document. All reads, so no
  gate fires;
- dispatches `appian-practices-auditor` with `phase=design` — *before the first
  write, while changing the answer is still free* — which writes
  `evidence/TASK-3/practices-design.json`;
- **then writes.** This is where the **scope gate** fires, on `PreToolUse`: is
  there an active task, is this object in its `allowedObjects`, is the task
  within the atomicity budget, and is that design verdict present, structurally
  valid and passing? It accumulates every failure rather than reporting the
  first, and the strongest thing it says is *ask*;
- every write is appended to `evidence/operations.jsonl` by the **write log** on
  `PostToolUse`, and a write that errors triggers the **failure notice**: do not
  retry blind, read back whether it persisted;
- records the identifiers the environment actually returned into the task's
  `evidenceFile`;
- **stops, and leaves the active task file exactly where it is.** One task, one
  stop — but stopping is a handoff into verification, not the end of the task,
  so the task stays in flight and `appian-review` clears the file at close. The
  ordinary consequence is that this stop is *blocked* by the closure gate,
  naming the three verdicts that do not exist yet. That is the harness stating
  the handoff rather than leaving it to memory.

**4. `appian-verify`** — a fresh invocation, because the builder is the worst
judge of its own work. It dispatches the auditor with `phase=implementation`
(→ `evidence/TASK-3/practices-implementation.json`), renders the screen
**twice** — once against a populated dataset, once against the identifier the
project guarantees does not exist — and only then dispatches `phase=qa`
(→ `practices-qa.json`). Both renders are required and neither substitutes for
the other: a loop over an empty list never evaluates its body, so a broken
screen passes every test case it has until a row exists (field experience).
Then `appian-verifier` emits a result for every gate in `requiredGates`, naming
the evidence behind each `PASS`, and the whole thing is consolidated into
`evidence/TASK-3/gates.md` so the next reader opens one account instead of
reassembling three.

**5. `appian-review`** — graduated by risk, so it does not run in full on
everything. What enters review gets two agents, both with `phase=review`:
`appian-reviewer` against the task contract, `appian-practices-auditor` against
domain doctrine. Neither reads the other's output before forming its own, and
neither is handed anything the builder wrote about why the change should pass.
The auditor's verdict goes to `evidence/TASK-3/practices-review.json`; the
findings go to `evidenceFile`. A review recorded only in `evidenceFile` closes
nothing, because that is not the file the gate opens. Then — **last, after the
verdict exists** — it deletes the active task file. That deletion is the
recorded act of closing the task, which is why it belongs to the phase that
runs last and not to the builder that stopped first.

**6. CLOSE** — no skill; the **closure gate** on `Stop`. While the active task
file names a task in flight, a stop cannot pass without valid, passing
`practices-implementation`, `practices-review` and `practices-qa`. It names
exactly which are missing, invalid or failing. On a repeated stop it approves
instead of deadlocking, and writes the omission to
`evidence/deferred-debt.jsonl` as `NOT_MEASURED` / `BLOCKING` — recorded, not
waived.

The sequencing is what makes that gate reach anything, so it is worth stating
outright: **a task is in flight from the moment `appian-build` takes it until
`appian-review` deletes the file, and the closure gate approves any stop with
nothing in flight.** Every stop in between — the builder's own, and any stop
during verification or review — meets the three-verdict check. Until
2026-08-09 `appian-build` deleted that file when it stopped, which left nothing
in flight and made this gate approve, unchecked, in exactly the flow everyone
uses; the check only ever bit on a session that happened to stop with a task
still open.

The visible cost of the fix is that a clean build now ends in a blocked stop.
That block is correct — the task really is unverified at that moment — and its
wording names the next phase rather than only what is missing. The wrong way
past it is deleting the active task file, which does not satisfy the gate but
retires it.

## The gates

Everything above is doctrine an agent can decide to skip. Five hooks make
skipping it **visible and awkward**, and make the cheapest forgery fail — they
cannot make forgery impossible for an agent that can write files. That
distinction is the honest version of what this section used to claim, and it is
worth stating before the list rather than after it: every input the gates read
is a plain file in your project, and the agent being gated can write all of
them. What the hooks remove is the *cheap* way past — the missing verdict, the
fabricated citation, the audit of one task copied over another's, the
unexplained deferral. What they cannot remove is an agent that sits down and
authors a coherent lie. The last line of defence there is a person reading the
citations, which is why the citations must resolve.

- **scope gate** (before any Appian write) — is there an approved active task,
  is this object inside its `allowedObjects`, is the task atomic, and is there a
  *passing* `design` audit for it? Not merely present: structurally valid, with
  citations that resolve, and an outcome of `PASS` or a sanctioned deferral.
- **closure gate** (on stop) — while the active task file names a task in
  flight, a stop does not pass without valid, passing `implementation`,
  `review` and `qa` verdicts. On a repeated stop it approves rather than
  deadlocking, and records the omission as `NOT MEASURED · BLOCKING` debt,
  because a guardrail that cannot be satisfied gets switched off and then
  protects nothing. With no task in flight it approves without checking
  anything — which is why the file survives the builder's stop and is cleared
  only at close; see the note at the end of the walkthrough.
- **write log** and **failure notice** — the harness records what was written,
  and tells an agent not to retry a failed write blind.
- **evidence-write log** (after any `Write` or `Edit`) — records edits aimed at
  the three files the gates themselves read: the evidence tree,
  `.claude/appian-harness.json`, and the active task file. It **logs and does
  not gate**, deliberately. The auditor legitimately writes verdicts and
  `appian-build` legitimately writes the active task file, and a hook cannot
  tell which agent is holding the pen — `PostToolUse` carries the tool and its
  arguments, never the identity of the subagent that called it. Gating would
  therefore question the harness's own correct operation on every task, which
  is the friction that gets a harness switched off; logging costs nothing and
  turns "did somebody write their own passing verdict?" from unanswerable into
  a line in `<evidenceDir>/evidence-writes.jsonl`.

The write gate never answers *deny* — the strongest thing it says is *ask* — and
when the closure gate blocks for missing verdicts it blocks once, approving a
second stop attempt and writing down what went unverified. Both shapes come from
the same reasoning: a guardrail with no way past it gets switched off, and then
it protects nothing. That escape is for missing verdicts only: a running hook
that cannot inspect something — an unreadable config, malformed JSON — asks or
blocks **every** time, with no second-attempt release, because a hook that
cannot see is not a hook that should be waved through. (Verified both ways: an
unparseable config blocks the repeat `Stop` exactly as it blocks the first.)

One case sits outside that rule, and it is worth naming rather than letting a
reader discover it. When **no Python interpreter can be found at all**, the hook
never starts, and `run_hook.sh` answers in its place from shell — where a `Stop`
hook has only *approve* and *block*, no *ask*. It therefore mirrors the
block-once shape rather than the block-always one, because blocking forever with
no way to satisfy the gate is the deadlock that gets guardrails switched off.
What it does not do is go quiet: it approves loudly, saying in the message that
no verdict was checked and that the task must not be treated as verified.

## How the best-practices guarantee actually works

The plugin's distinctive claim is that nothing gets written or certified without
the official doctrine having been applied to it. That claim deserves to be
explained rather than asserted, because part of it cannot be enforced at all.

**What is impossible.** A hook cannot see a subagent's transcript. There is
therefore no way for any gate here to verify that `appian-practices-auditor`
loaded `appian-best-practices` or opened the section it needed. Any plugin
claiming to enforce that is claiming something its hooks cannot check.

**What is verified instead: the trail.** Every verdict must carry a non-empty
`referencesApplied`, each entry shaped `<file>.md#<anchor>`. Before either gate
accepts a verdict, `scripts/validate_verdict.py` resolves every one of those
entries against `skills/appian-best-practices/references/`: the file has to
exist in this plugin, and the anchor has to match a heading actually present in
it. A fabricated citation fails there exactly like a missing file — and it
fails the *gate*, not just a linter, because the gate runs that validation
itself.

**What that proves.** That the cited section exists and any third party can go
and read it. That is the failure mode which actually occurs: not a refusal to
cite, but the plausible citation that turns out not to exist.

**What it does not prove.** That the auditor read the section. That the section
was the right one for the change. That the judgement built on it was sound.
Reading the citations and disagreeing with them is still a person's job; what
the plugin removes is the possibility of citations that cannot be checked.

Two things reinforce the trail without closing that gap. The three agents
declare `skills: [appian-best-practices]` in their frontmatter, and each is
instructed to restate a heading of that skill *before its first tool call*, so a
`Read` cannot stand in for having been given the doctrine. Both are stronger
than nothing and weaker than proof; the honest summary is that the citations are
checked mechanically and everything else is convention.

**Shape is not outcome, and the gates check both.** `validate_verdict.py`
deliberately says nothing about whether a verdict passed — it answers "is this a
well-formed audit of *this* task and *this* phase, whose citations resolve?" and
stops. The gates add the outcome check on top: a phase satisfies a gate only on
`PASS`, or on `NOT_MEASURED` with `notMeasuredClass: DEFERRED`, which the
validator requires to carry an `owner`, a `closingCondition` and a
`deferredCriterion` naming one entry off the plugin's closed deferrable list.
`FAIL` never satisfies — a gate that accepts a `FAIL` is not a gate.
`NOT_MEASURED` / `BLOCKING` never satisfies either: that class means the harness
could have measured this and did not, which is a process failure rather than a
limitation.

**A verdict is a claim about particular work, and it is checked as one.** Both
gates assemble the path they open from a task id and a phase, and both pass
those two strings to the validator, which rejects a document naming different
ones. Without that, `phase` was only ever checked against a list of four legal
values — so a single audit reading `{"task": "TASK-999", "phase": "qa"}` opened
all four gates once it was copied into all four filenames, and four copies of
one audit were indistinguishable from four independent ones. The deferrable
list is checked the same way: it lives in code as `DEFERRABLE_CRITERIA`, a
deferral must name which entry it invokes, and the entry it names has to be on
the list. The reference document lists the same ids and a test fails if the two
copies ever disagree.

## The verification pyramid

Each level is named by what it catches, and each is honest about what it cannot
see. Cheapest first.

| Level | Operates on | Catches |
|---|---|---|
| **N0** Syntax | the expression | Whether it parses and whether the rules it calls exist |
| **N1** Static | the source | Components, icons, enumerated values, patterns, accessibility rules |
| **N2** Structural | the **evaluated component tree** | Everything that only exists once data is resolved |
| **N3** Coordinates | process models | Overlapping nodes, proximity, backward flow, disconnected nodes |
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

**Where each level actually lives, since the table does not say.** N0 and N1 are
the platform's own checks and the doctrine in `appian-best-practices`; N4 is the
project's test cases and regression command; N5 and N6 are people. N2 and N3 are
the only levels this repository implements as code — `scripts/n2_interface_tree.py`
(`check_tree(tree, empty_path=False)`, over an evaluated component tree) and
`scripts/n3_process_layout.py` (`check_layout(nodes, edges)`, over node
coordinates). Both are importable modules with unit tests **and a command-line
entry point**:

```
python3 scripts/n2_interface_tree.py TREE_JSON [--empty-path]
python3 scripts/n3_process_layout.py LAYOUT_JSON
```

Each prints one line per finding and exits **0** clean, **1** findings, **2**
usage, **3** `NOT MEASURED`, so a clean run is distinguishable from a run that
never happened. That last code is what makes the sentence true, and it had to be
earned: both checkers used to answer `OK` and exit 0 when they did not
understand their input, so an unrecognised screen looked exactly like a checked
one. **N2** answers 3 when a tree holds no component of a type it judges — run
it with no arguments to see that vocabulary, which is built from the constant
the checks apply rather than restated beside it — and it names the types it saw
but does not judge even on a run that did measure something, so a partial gap is
visible instead of assumed empty. **N3** answers 3 when a layout names no nodes.
`lint_skills.py` uses the same code for its own zero-skills case, which is where
this plugin first argued that nothing checked is not a pass.
`appian-verify` names them and says what each catches and
what it cannot — but **no hook runs them for you**. They are checkers a verify
step invokes, not checks the harness performs on your behalf, and describing
them any other way would be the overclaim this plugin exists to argue against.

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
`scripts/` need Python 3 on the `PATH` and nothing beyond the standard library.
Any of `python3`, `python` or `py -3` will do: `hooks/run_hook.sh` probes them
in that order and runs the first that answers as Python 3, so the plugin does
not depend on a distribution having named the interpreter one particular way.

The hooks are invoked through `sh`, which macOS and Linux always provide and
which on Windows comes from Git Bash. **One configuration is not covered:
Windows without Git Bash installed.** There, Claude Code runs hook commands
through PowerShell, `sh` does not resolve, and the hooks do not run at all —
silently, because a command that cannot be found produces no decision. Install
[Git for Windows](https://git-scm.com/download/win) and the hooks work; Claude
Code wants it on Windows anyway, since without it there is no Bash tool either.

If no interpreter is found, `hooks/run_hook.sh` answers in the Python code's
place rather than going quiet: the scope gate asks, the closure gate blocks
once and then approves loudly on the repeat `Stop` so the session cannot
deadlock, the write log reports that the write was not recorded, and each
message names what was tried. In a project without `.claude/appian-harness.json`
it stays out of the way exactly as the hooks themselves do.

**How far the above was checked, and where it stops.** Both manifests exist and
parse, and the marketplace's name is the `appian-harness-local` that the second
command names. The hooks were exercised directly, by feeding `run_hook.sh` a
payload the way Claude Code does — the command is under *Troubleshooting* — and
they answered correctly in six cases, including the whole chain ending in
`allow`: allow in an unconfigured project; ask with a config present and no
active task; ask for an object outside `allowedObjects`; **allow** with an
active task, the object in scope and a valid passing `practices-design.json`;
block on a stop with a task in flight and no verdicts; and
approve-with-recorded-debt on the repeat stop. The closure chain was then run
again end to end against a scratch project, in the order a real task meets it:
block with the task in flight and nothing produced; **approve** once
`practices-implementation`, `practices-review` and `practices-qa` were present,
valid and passing; approve-with-debt on a repeat stop with them removed, with
the `deferred-debt.jsonl` line read back; and approve once the active task file
was deleted, which is what closing a task looks like to the gate.
`validate_verdict.py` was run the same way, accepting a citation resolved from a
real heading and rejecting both a fabricated anchor and a nonexistent reference
file. `n2_interface_tree.py` and `n3_process_layout.py` were run from the
command line over sample inputs, each returning findings with exit 1, a usage
message with exit 2, 0 on a clean input, and **3 on an input neither of them
understands** — a component tree of unrecognised types for N2, a layout naming
no nodes for N3. Both of those returned 0 until 2026-08-09. The two
`/plugin` commands themselves are **unverified**: they are Claude Code commands
rather than shell commands, and installing a plugin only means anything after a
restart, so nobody has run them for this repository.

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

**None of these five is machine-read.** They are what a project records so the
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
  "maxAllowedObjects": 3
}
```

Every key is optional and the values above are the defaults. **The file's
presence is the activation switch:** without it, every hook allows, approves or
no-ops, so the plugin installed in a project that does not use it stays out of
the way.

**Three keys, and the list is closed.** `evidenceDir`, `activeTaskFile` and
`maxAllowedObjects` are the whole of what the hooks open today. Every other key
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
| `<evidenceDir>/<task>/gates.md` | `appian-verify`, consolidating the per-gate report with both its verdicts | a person, or the review step. **No gate reads it** — it sits beside the verdicts so the task's evidence is one account rather than a directory to reassemble |
| `<evidenceDir>/operations.jsonl` | the write log | a person, afterwards |
| `<evidenceDir>/gate-decisions.jsonl` | the scope gate, every time it asks | a person, afterwards |
| `<evidenceDir>/deferred-debt.jsonl` | the closure gate when forced to approve unverified work (`BLOCKING`), and either gate when an accepted deferral opens it (`DEFERRED`) | a person, afterwards |
| `<evidenceDir>/evidence-writes.jsonl` | the evidence-write log, on any `Write` or `Edit` aimed at a file the gates read | a person, afterwards |

The four logs are append-only and nothing in the plugin reads them back, with
one exception: the deferred-debt register is re-read before appending, so one
deferral does not become one line per write attempt. They exist so that "how
often did this gate stop something, and did anyone answer yes?" — and "who
wrote this verdict?" — are questions with answers.

## Troubleshooting

### The hooks do nothing

In the order worth checking:

1. **Did you restart Claude Code after installing?** Hook configuration is read
   at startup.
2. **Is there a `.claude/appian-harness.json` at the project root?** Its
   presence is the activation switch. Without it every hook allows, approves or
   no-ops — by design, so the plugin does not get in the way of a project that
   has not adopted it. An empty `{}` is enough to turn it on; every key has a
   default.
3. **Is a Python 3 on `PATH`?** `run_hook.sh` probes `python3`, `python` and
   `py -3` in that order and takes the first that answers as Python 3 — probes
   rather than trusts, because `python` can still be a Python 2 and on Windows
   `python3` is often an execution-alias stub that resolves and then runs
   nothing. If none works the hooks still answer, loudly: the scope gate asks,
   the closure gate blocks once and then approves, and every message names what
   was tried.
4. **Are you on Windows without Git Bash?** That is the one configuration where
   the hooks are genuinely silent. See *What this plugin does not do*.

To settle it rather than guess, feed a hook a payload the way Claude Code does:

```
printf '{"tool_name":"mcp__x__createInterface","tool_input":{"name":"Foo"},"cwd":"/abs/path/to/project"}' \
  | sh hooks/run_hook.sh /abs/path/to/appian-harness scope-gate
```

In a project with no config that prints `"permissionDecision":"allow"` with the
reason `appian-harness not configured for this project`; with a config and no
active task it prints `"ask"` and appends a line to `gate-decisions.jsonl`.
Substitute `closure-gate` and a payload of `{"cwd":"..."}` to exercise the stop
path, and add `"stop_hook_active":true` to see the second attempt approve.

**`cwd` is read by Python**, so on Windows it must be a native path (`C:/…`),
not an MSYS `/c/…` one. Given the latter, the gate finds no config and the
probe looks like an unconfigured project. That is a trap of probing by hand,
not a fault in the plugin.

### Driving the scope gate all the way to `allow`

The one-liner above stops at the first missing thing, which is the point of it.
To see the whole chain — including the `CLAUDE_PLUGIN_ROOT` trap below, which
only appears once a verdict exists for the gate to refuse to validate — build a
scratch project. Set `HARNESS` to your checkout and run this as written:

```sh
HARNESS=/abs/path/to/appian-harness
PROJ=/abs/path/to/scratch-project     # on Windows write C:/… , not /c/…

mkdir -p "$PROJ/.claude" "$PROJ/tasks" "$PROJ/evidence/TASK-3"
printf '{}' > "$PROJ/.claude/appian-harness.json"
printf '{"id":"TASK-3","allowedObjects":["Foo"]}' > "$PROJ/tasks/current.json"

cat > "$PROJ/evidence/TASK-3/practices-design.json" <<'JSON'
{
  "task": "TASK-3",
  "phase": "design",
  "verdict": "PASS",
  "referencesApplied": ["10-quality-gates.md#three-outcomes-not-two"],
  "findings": [
    {
      "criterion": "three outcomes are used, and N/A is not a fourth",
      "verdict": "PASS",
      "evidence": "the proposed design records PASS, FAIL or NOT MEASURED per gate",
      "reference": "10-quality-gates.md#three-outcomes-not-two"
    }
  ]
}
JSON

PAYLOAD='{"tool_name":"mcp__x__createInterface","tool_input":{"name":"Foo"},"cwd":"'"$PROJ"'"}'
printf '%s' "$PAYLOAD" | sh "$HARNESS/hooks/run_hook.sh" "$HARNESS" scope-gate
```

That last line prints `"ask"`, with the reason
`cannot validate practices-design: no pluginRoot configured`. **This is the
`CLAUDE_PLUGIN_ROOT` trap, and it is not a problem with the verdict**: the
variable is set by Claude Code, not by your shell, and without it the gate
cannot resolve the references the verdict cites, so it refuses to accept a
verdict it cannot check. Export it and run the same line again:

```sh
printf '%s' "$PAYLOAD" | CLAUDE_PLUGIN_ROOT="$HARNESS" sh "$HARNESS/hooks/run_hook.sh" "$HARNESS" scope-gate
```

Now it prints `"permissionDecision":"allow"` with `scope and design audit check
out` — the whole chain: active task, object in `allowedObjects`, task within the
atomicity budget, and a design verdict that is present, structurally valid, about
this task and this phase, and passing.

The verdict above is also the **minimal passing example** of the schema. Every
field in it is required: `task` and `phase` have to match the path the gate
opens (`<evidenceDir>/TASK-3/practices-design.json`), `referencesApplied` must be
non-empty with each entry resolving to a real file and heading under
`skills/appian-best-practices/references/`, and each finding needs a
`criterion`, a `verdict` and non-empty `evidence`. The full schema, including
the fields a `NOT_MEASURED` verdict needs, is in
`agents/appian-practices-auditor.md`.

### The validator rejects my citation

Anchors in `referencesApplied` are **derived from headings**, not written by
hand, so the fix is nearly always to open the reference and look at the real
heading. The rule is GitHub's: lowercase the heading text, drop every character
that is not a word character, whitespace or hyphen, then collapse runs of
whitespace and underscores into single hyphens. The references number their
headings, so a real one makes the point: `## 2. Choose the data source and
access method` becomes `#2-choose-the-data-source-and-access-method` — the
number survives, the period does not. Punctuation generally — colons, backticks,
parentheses — is removed rather than encoded.

Run the validator directly to see which half failed; it distinguishes a
reference file that does not exist from an anchor that does not exist in it, and
it reports every problem at once rather than the first:

```
python3 scripts/validate_verdict.py <evidenceDir>/<task>/practices-design.json /path/to/appian-harness
```

Two adjacent failures look similar and are not: a verdict at the wrong path is
reported by the gates as *missing*, which reads as evidence to a person and as an
absence to the gate. The shape under `evidenceDir` is fixed —
`<evidenceDir>/<task>/practices-<phase>.json` — and only the root is yours.

### The gate asks too often

Read the ratio rather than adjusting the threshold. `<evidenceDir>/gate-decisions.jsonl`
has one line per question, with the reason; `<evidenceDir>/operations.jsonl` has
one line per write. If most questions are answered yes, that is not evidence the
gate is too strict — check the `reason` field, and it is usually the same one:
`allowedObjects` longer than `maxAllowedObjects`. That is a task that was sized
wrong at plan time. Splitting it is the fix; raising `maxAllowedObjects` changes
the number without changing what it measures, and carries the oversized contract
into the build.

### The first write is blocked even though preflight went fine

Preflight is all reads, so the scope gate never sees it; the stop lands on the
first create or update. The reason it prints will name every problem it found,
and the one people hit first is a missing `phase=design` verdict at
`<evidenceDir>/<task>/practices-design.json`. `appian-build` step 3b is what
produces it — nothing else in the lifecycle does, and `appian-verify` scopes
`design` out on purpose.

### The closure gate blocked my stop

First check which stop this is. If `appian-build` just finished, the block is
the expected one and the answer is not a workaround: the task is built and not
yet verified, and the reason names the phase that produces each missing
verdict. Run `appian-verify`, then `appian-review`. The block goes away because
the task closed, which is the point.

What does **not** work is deleting the active task file to get the stop
through. The gate approves any stop with nothing in flight, so that does not
satisfy it — it switches it off for the rest of the task.

### Everything went quiet and no gate has fired since

Check whether `.claude/appian-harness.json` still exists. **Removing that file
switches the whole harness off**, silently and completely: its presence is the
activation switch, so without it every hook allows, approves or no-ops exactly
as it does in a project that never adopted the plugin. Nothing announces the
change, and a session in which the gates simply stopped having opinions looks
identical to a session in which everything passed.

That is the cheapest bypass in the plugin, cheaper than the active task file —
deleting the task file disables one gate for one task, deleting the config
disables all five hooks for good — and it is not a defect that can be fixed
from inside, because a plugin that got in the way of projects which have not
adopted it would be worse. What exists instead is a record: an `Edit` or
`Write` aimed at that file is logged to `<evidenceDir>/evidence-writes.jsonl`
with `"target": "harness-config"` before it takes effect, so the moment it was
switched off is recoverable afterwards even though nothing stopped it. A
deletion by `rm` through the shell leaves no such line — the hook watches file
writes, not the whole filesystem.

### The closure gate blocks and the verdicts genuinely cannot be produced

Different case: the auditor is unavailable, or a step depends on a person who
is not there. Stop again. The gate blocks the first attempt and approves the
repeat, writing the omission to `<evidenceDir>/deferred-debt.jsonl` as
`NOT_MEASURED` / `BLOCKING`. It is recorded, not waived — the point is that the
session cannot deadlock, not that the work is now verified.

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
- **It does not run the N2 and N3 checkers for you.** They exist, they are
  tested, and they have command-line entry points that `appian-verify` names —
  but no hook invokes them, so a task where nobody ran them has no N2 or N3
  result, not a passing one. See the note under the pyramid.
- **It does not run your regression suite.** The command is something a project
  records so the person following the process can find it; no code here reads
  it or executes it.

- **It cannot make forgery impossible.** Every input the gates read — the
  evidence tree, the harness config, the active task file — is a plain file in
  your project, and the agent the gates constrain can write all of them with
  `Write` or `Edit`. The hooks close the cheap routes: a missing verdict, a
  citation that does not resolve, one audit filed under another task's or
  another phase's name, a deferral with nothing named behind it. An agent that
  deliberately authors a coherent false verdict still gets past them, and the
  only thing standing there is a person reading the citations. What the plugin
  adds is that the attempt is recorded rather than invisible — see the
  evidence-write log — and that skipping the work outright is awkward enough to
  be worth not doing.

Three things about the plugin itself, on the same terms:

- **Nobody has watched `skills:` preload.** The three agents declare
  `skills: [appian-best-practices]` in their frontmatter, and the field is
  documented — but this plugin was never installed in the session that built
  it, so no one here has observed an agent start with the doctrine already in
  context. The frontmatter is written on the documented contract, not on an
  observation. **Unverified.** The instruction to restate a heading before the
  first tool call exists partly as a check on exactly this: if the preload did
  not happen, that step is where it shows.
- **On Windows without Git Bash the hooks are silently absent.** Not degraded —
  absent. Claude Code runs the hook command through PowerShell, `sh` does not
  resolve, and a command that cannot be found produces no decision at all, so
  the plugin installs, looks healthy and enforces nothing. The remedy is
  installing [Git for Windows](https://git-scm.com/download/win). This is the
  one failure mode the fail-closed design cannot cover, because the code that
  would fail closed never starts.
- **The closure gate checks nothing once a task is closed.** Its reach is
  exactly the window in which a task is in flight — from `appian-build` taking
  it to `appian-review` deleting the active task file. Stops outside that
  window approve without opening a verdict, by design, and a task whose file was
  cleared early is indistinguishable from one that closed properly. See the note
  at the end of the walkthrough.
- **The gate cannot see a review exemption.** `appian-review` is graduated by
  risk and some changes legitimately do not enter it, but the gate asks for a
  valid `practices-review.json` and knows nothing about exemptions. Closing an
  exempt task is therefore recording the exemption and deleting the active task
  file; stopping before that blocks, and a repeat stop writes debt naming
  `practices-review` — accurate that it is absent, misleading about why.

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
