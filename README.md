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

## Requirements

Writing to Appian through an MCP server needs three things, and this plugin is
only one of them. They form a chain — each link is required by the one above it:

```
appian-harness  ──requires──▶  a design MCP (e.g. appian-dev)
                └─requires──▶  the official Appian skill
                                        └─requires──▶  a documentation MCP (e.g. appian-docs)
```

| Requirement | What it contributes | What happens without it |
|---|---|---|
| **A design MCP** (`appian-dev` or equivalent) | The write surface, and the only thing the write hooks fire on (the closure gate fires on `Stop`, with no MCP involved) | The plugin installs, its tests pass, it looks healthy — and **it gates nothing**, because there is no tool for the matcher to catch |
| **The official Appian skill**<br/>[`appian/dev-mcp-skills`](https://github.com/appian/dev-mcp-skills/) | Naming conventions, both sides of a relationship, the order objects must be created in, real UUIDs versus invented ones — everything the tool schemas describe parameters for but not correct use of | Objects get written with invented names and UUIDs, one-sided relationships, and wrong creation order. **No gate here catches that**: they check the contract, atomicity and the presence of a verdict |
| **A documentation MCP** (`appian-docs` or equivalent) | The official skill's function-availability checks run against it | Those checks return empty, and **empty is indistinguishable from "the function does not exist"** — the vacuous pass this plugin argues against everywhere else |

**This is enforced, not just documented.** `appian-build` loads the official
skill before the design audit and before the first write, and records the load
at `<evidenceDir>/<task>/appian-skill-loaded.json`. The scope gate opens that
file the same way it opens the design verdict: no record, or a record naming
another task, omitting `docsMcp`, or claiming a version the installed skill
does not declare, and the write asks instead of going through.

Be clear about what that is worth, on the same terms as the rest of this
plugin: **it does not prove the skill was loaded.** A hook cannot see an
agent's context — the same limit stated in
[How the best-practices guarantee actually works](docs/gates.md). What it
removes is the silent case: writing to a shared
environment having never opened the domain knowledge, with nothing anywhere
recording it. One check is stronger than that, and it is the reason
`appianVersion` is in the record at all: point `officialAppianSkillPath` at the
installed skill and the version claim gets compared against the file on disk
instead of taken on trust.

```json
{
  "officialAppianSkillPath": "~/.claude/skills/appian"
}
```

Optional, absolute or `~`-prefixed or project-relative. Left out, the check
falls back to presence only — which is the right default, since the skill is
normally installed at user scope, outside any project.

Verifying all three actually answer, before trusting any of it:

| Link | Check | A healthy answer |
|---|---|---|
| Design MCP | `validateExpression("1 + 1")` | `{"hasErrors": false, "errors": []}` |
| Official skill | Load it; read `**Appian Version:**` from its `SKILL.md` | The version your environment actually runs |
| Documentation MCP | Any real query | Documentation chunks, not an empty result |

`tools/list` is not a check: it is answered locally and never reaches Appian.

## Install

Three steps, and the order is load-bearing. This repository **is its own
marketplace**, and a marketplace has to be registered before the plugin inside
it can be named:

```
/plugin marketplace add raulogm077/appian-harness
/plugin install appian-harness@appian-harness
```

Then **restart Claude Code**, or run `/reload-plugins` if the install summary
asks for it. Until one or the other happens the plugin is installed and doing
nothing: its hooks and agents only take effect once a session has loaded them.

`appian-harness@appian-harness` is not a typo — the part before the `@` is the
plugin, the part after it is the marketplace, and here they share a name. Given
without the `@`, the name is looked up across the marketplaces you have already
registered and answers `Plugin "appian-harness" not found in any marketplace`,
which reads like a missing plugin and is a missing *marketplace*.

Installing from a local checkout, quoting a path that contains spaces, and what
the hooks need on `PATH`: **[docs/installing.md](docs/installing.md)**.

## Which path is yours

Three ways to use this, in ascending order of what they cost and what they
promise. A harness that demands the whole cycle for a label change teaches
people to route around it, so choose by what you are about to do — not by which
one sounds the most thorough.

They are not a commitment. One file decides which one you are on: run
`/appian-init` and a path-1 project becomes a governed one from the next tool
call; delete `.claude/appian-harness.json` and every hook goes back to
returning allow. Nothing about the choice is announced to a server or written
anywhere you cannot reverse, so starting on the cheapest path costs nothing if
the work turns out to deserve more.

### 1 — Advice, with nothing adopted

Install, and stop there. `appian-best-practices`, `appian-specify` and
`appian-plan` never read `.claude/appian-harness.json`, and the first of them
applies whether you write through an MCP server or by hand in Appian Designer.
So this path needs no project configuration, no `/appian-init` and no MCP
server: you get the eleven domain references, the Definition of Done, a written
specification and a task list ordered by dependency.

With no configuration file present every hook returns allow and exits 0. That
absence **is** the activation switch, not a breakage — nothing blocks, nothing
is logged, nothing is certified, and a project that never asked to be governed
is never nagged. If advice was all you wanted, you are finished here.

### 2 — One small change, judged small rather than assumed small

```
/appian-init          # adopt the harness into this project
/appian-build         # build exactly one task, then stop
/appian-verify        # run the gates, record the evidence
/appian-review        # certify from outside — or record the exemption
```

SPECIFY and PLAN are skipped. REVIEW is not, because deciding a change is too
small to review **is** review's work: it is weighed against four exemption
conditions by someone who did not build it, and who made the call is written
into the task's evidence. A task nobody routed here has not been found exempt —
it has been left unexamined.

One consequence catches everybody once. The closure gate cannot see an
exemption; it looks for a passing `practices-review.json` and nothing else. So
delete the active task file as soon as the exemption is recorded, or the next
stop blocks and records debt that is accurate about the absence and misleading
about the reason.

### 3 — A whole application

```
/appian-init          # adopt the harness into this project
/appian-specify       # turn the request into a written specification
/appian-plan          # break it into tasks, ordered by dependency
/appian-build         # build exactly one task, then stop
```

`appian-build` stops on purpose. What follows is `appian-verify`, then
`appian-review`, then the next task — and the `Stop` hook will not let a session
end mid-task without either the verdicts or a recorded reason. The full
walkthrough, with what each phase writes and what the gates read, is in
**[docs/workflow.md](docs/workflow.md)**.

### Before you trust a gate, check that it is alive

Paths 2 and 3 rest on the hooks, and a hook that cannot be launched does not
fail loudly — it does not run, and the plugin installs, looks healthy and
enforces nothing. Feed one a payload the way Claude Code does, and it stops
being a question. Both paths are spelled out because **neither is available to
you as a variable**:

```sh
HARNESS=/abs/path/to/appian-harness   # your checkout, or the highest version under
                                      # ~/.claude/plugins/cache/appian-harness/appian-harness
PROJ=/abs/path/to/your-project        # on Windows write C:/… , never /c/…

printf '{"tool_name":"mcp__appian-dev__createInterface","tool_input":{"name":"Foo"},"cwd":"%s"}' "$PROJ" \
  | sh "$HARNESS/hooks/run_hook.sh" "$HARNESS" scope-gate
```

Two traps, and the reason the paths are written out. `CLAUDE_PLUGIN_ROOT` is
substituted by Claude Code inside `hooks.json`; in your own shell it is empty,
and the command dies as `sh: /hooks/run_hook.sh: No such file or directory`.
And `cwd` is read by Python, so `$PWD` under Git Bash hands it an MSYS `/c/…`
path — the gate then finds no config and reports the project unconfigured
whatever its real state, which is the one wrong answer that looks like a right
one.

A JSON answer means the gates are live: `"permissionDecision":"allow"` with the
reason `appian-harness not configured for this project` if you are on path 1,
`"ask"` once a config exists and no task is active. Anything else — most often
`sh: command not found` on Windows without Git Bash, the one configuration where
the hooks are genuinely silent — means you are on path 1 whether you meant to be
or not. **[docs/troubleshooting.md](docs/troubleshooting.md)** takes it from
there.

## What is in the box

| Path | What is there |
|---|---|
| `skills/` | Seven skills: five lifecycle phases, the run orchestrator, and the cross-cutting doctrine |
| `skills/appian-best-practices/references/` | Eleven domain references, numbered `01`–`11`. Every verdict cites into these |
| `agents/` | Three judging agents: `appian-practices-auditor`, `appian-reviewer`, `appian-verifier` |
| `hooks/` | One `hooks.json` declaring six hooks, a POSIX launcher (`run_hook.sh`) and their Python implementation |
| `scripts/` | Eleven modules: `validate_verdict.py`, `lint_skills.py`, `lint_agents.py`, `n2_interface_tree.py`, `n3_process_layout.py`, `parallel_safety.py`, `check_readme_claims.py`, `check_manifest_agreement.py`, `check_package_integrity.py`, `check_evals.py`, and `exit_codes.py`, which holds the one constant six of them used to spell out separately |
| `commands/` | One command: `/appian-init`, which adopts the harness into a project |
| `evals/` | Six eval cases in the layout `claude plugin eval` expects — three routing, three safety. **Never executed**: the runner is in early access. `evals/README.md` says so first, because a suite of unrun cases is preparation, not coverage |
| `.claude-plugin/` | `plugin.json`, and a `marketplace.json` that makes this checkout its own marketplace |
| `SECURITY.md` | What this plugin executes on your machine, at which six hook entries, what it reads and writes — and where to report a vulnerability |
| `CONTRIBUTING.md` | The eight local checks, in the order CI runs them, and the release procedure that keeps the two manifests from drifting again |
| `CHANGELOG.md` | What each release changed for a project that upgrades and edits nothing. Read it before upgrading: a gate that *stops* firing announces nothing, so that is the only place it is announced |
| `.github/workflows/` | The checks, on Linux and Windows × Python 3.9 and 3.13 |

The Python carries its own tests — 285 for `scripts/`, 189 for `hooks/`, standard
library only:

```
python3 -m unittest discover -s scripts
python3 -m unittest discover -s hooks
python3 scripts/lint_skills.py
python3 scripts/lint_agents.py
python3 scripts/check_readme_claims.py
python3 scripts/check_manifest_agreement.py
python3 scripts/check_package_integrity.py
python3 scripts/check_evals.py
```

Five of those checkers answer `3`, not `0`, when they were handed nothing to
inspect. Zero skills linted, zero declared paths resolved, zero eval cases read:
none of that is a pass, and giving "not measured" its own exit code is what stops
a green run from meaning two different things.

**The launcher tests are the slow ones, and deliberately so.** They run
`run_hook.sh` through a real shell with the interpreter search starved, because
that fail-closed path is what answers when nothing else can — and it was the one
component with no tests at all. On Windows each invocation costs ~4s starved and
~8.5s with an interpreter, essentially all of it Git Bash and Python startup.
For the loop you run after every edit:

```
APPIAN_HARNESS_SKIP_SLOW=1 python3 -m unittest discover -s hooks
```

Default is to run them — a suite that skips by default is a suite that rots — so
the fast path is an opt-out you have to type, and CI never sets it.

## Skills

| Skill | Phase | What it does |
|---|---|---|
| `appian-specify` | SPECIFY | Turns a vague request into a written specification: actors, entities and relationships, states and transitions, an authorization matrix, volume, and an explicit **out of scope**. One question at a time. |
| `appian-plan` | PLAN | Breaks the specification into **vertical Appian slices** (record type → query rule → interface → test case), ordered by the dependencies the platform actually imposes, each with its own acceptance criteria. |
| `appian-build` | BUILD | Implements exactly one approved task and stops. Preflight before any write, asymmetric treatment of irreversible actions, no blind retries. Invoked by name, or by `appian-run` inside an authorized run. |
| `appian-verify` | VERIFY | Produces the per-gate report with evidence, in its own context. |
| `appian-review` | REVIEW | Independent review from a clean context, graduated by risk. |
| `appian-run` | orchestration | Builds a plan's pending tasks end to end without a keystroke per task. Authorization is granted once per run and checked by the gate; eight closed conditions stop it. Invoked by name — granting a run is the user's act. |
| `appian-best-practices` | cross-cutting | Official Appian best practices routed by domain, plus the quality gates that define done. Loaded before any write and before declaring an object finished. |

`appian-best-practices` carries eleven domain references — data model and record
types, SAIL interfaces, process models, expression rules, performance, security,
integrations, ALM and testing, sites and navigation, quality gates, reliability
and operations. The `SKILL.md` is the index: only the reference the change
touches gets opened.

**Description phrasing.** The seven `SKILL.md` files here write their trigger
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

## Documentation

This page is what you need to decide whether the plugin is for you and to get it
running. The manual is in `docs/`, and every page in it was part of this README
until it grew past the point where anyone could find anything in it.

| Page | Read it when |
|---|---|
| **[Installing](docs/installing.md)** | Installing from a local checkout, a path with spaces in it, or you want to know what the hooks need on `PATH` |
| **[Configuration](docs/configuration.md)** | Adopting the harness into a project — the one file the hooks read, and every key in it |
| **[Workflow](docs/workflow.md)** | Working through a real task end to end, running a whole plan without a keystroke per task, or building several at once |
| **[The gates](docs/gates.md)** | Understanding what each gate actually checks, what the best-practices guarantee is worth, and what each level of the verification pyramid does and does not prove |
| **[Troubleshooting](docs/troubleshooting.md)** | A gate fired and you disagree, the hooks do nothing, the installed copy is behind the repository, or the closure gate will not let you stop |
| **[When the harness is wrong](docs/when-the-harness-is-wrong.md)** | The plugin itself is the problem — including why you are never blocked, and what to record while you wait for a fix |

Two more, for changing the plugin rather than using it:
**[CONTRIBUTING.md](CONTRIBUTING.md)** carries the checks to run before you push
and the release procedure; **[SECURITY.md](SECURITY.md)** states what this plugin
executes on your machine, at which hook entries, and what it reads — including
the one file it opens that commonly holds credentials.

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
  result, not a passing one. See the note under the pyramid in
  [docs/gates.md](docs/gates.md).
- **It does not run your regression suite.** The command is something a project
  records so the person following the process can find it; no code here reads
  it or executes it.
- **It gates nothing at all without a design MCP configured.** The write and
  closure gates hang off Appian `mcp__*` write tools; with no such server in the
  session there is no tool to match, so the plugin installs, passes its tests, looks healthy and
  watches nothing. See *Requirements*. This is the second failure mode, after
  Windows without Git Bash, where the thing that would fail closed never runs.
- **It cannot prove the official Appian skill was loaded.** It checks that a
  load was recorded for the task, that the record is about that task, that it
  names a documentation MCP, and — when `officialAppianSkillPath` is set — that
  the version it claims matches the installed skill. An agent that writes that
  record without loading anything still gets through. Same limit, same reason,
  as the plugin's own doctrine.

- **It cannot make forgery impossible.** Every input the gates read — the
  evidence tree, the harness config, the active task file — is a plain file in
  your project, and the agent the gates constrain can write all of them with
  `Write` or `Edit`. The hooks close the cheap routes: a missing verdict, a
  citation that does not resolve, one audit filed under another task's or
  another phase's name, a deferral with nothing named behind it. An agent that
  deliberately authors a coherent false verdict still gets past them, and the
  only thing standing there is a person reading the citations. What the plugin
  adds is that the attempt is recorded rather than invisible — see the
  evidence-write log in [docs/configuration.md](docs/configuration.md) — and
  that skipping the work outright is awkward enough to
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
  at the end of the walkthrough in [docs/workflow.md](docs/workflow.md).
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
