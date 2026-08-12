# Changelog

This file exists because `0.2.0` changes what the harness does to a project that
upgrades and edits nothing. Two of those changes make a gate stop firing, and a
gate that stops firing announces nothing — which is the only kind of change that
genuinely needs a release note.

Versions follow semver read as `0.x`: the middle number carries new behaviour
and behaviour changes, because the API is still moving.

## 0.3.0 — 2026-08-12

Nothing the harness *does* to your project changed in this release. It is here
under a minor rather than a patch because the package gains a document you
should actually read before upgrading, and a patch number says "nothing to look
at".

### Added

**`SECURITY.md` — what this plugin executes on your machine.** A plugin that
installs six hook entries is asking for execution in every session, and nothing
here said so plainly or offered anywhere to report a problem. It was written
from the source rather than from memory, and one thing came back the opposite of
how it had been assumed:

> The requirements check opens **`~/.claude.json`** — the file that commonly
> carries MCP `env` blocks with API tokens. It parses the whole file and takes
> the **keys** of `mcpServers`, and of the block for this project only. Never a
> value, never a token. What leaves that read is a yes/no per configured server
> name in the session-start message.

Not a defect. In a project with no `.claude/appian-harness.json` the file is
never opened at all, because `_build_config` returns first. But it is not
something a reader would guess, so it is stated in bold, with the honest coda
that there is no switch to opt out of it today. The negative claims beside it
were verified before being written, not asserted: no network, no telemetry, no
subprocess in `harness_hooks.py`, no `eval` or `exec`.

**`CONTRIBUTING.md`, with the release procedure the manifest drift needed.** A
checker that catches drift without a documented procedure that runs it only
moves the gap. Both facts in that procedure were probed against a throwaway
repository rather than inferred from documentation: `claude plugin tag` exits 1
and refuses when the two manifests disagree, and **also** refuses on a dirty
working tree — the second costs a confusing minute, because the version message
disappears from that failure and a manifest pair that does agree looks like the
mismatch case failing anyway.

**`evals/` — six cases that have never been executed.** `claude plugin eval` is
in early access and does not respond on the account this plugin is developed on,
neither `init` nor the runner. Six and not forty: forty unexecuted cases would
be more impressive and exactly as unverified, and the trap in prompt evals is
not too few cases — it is graders that reward the vocabulary of the prompt while
the task goes undone. Three routing, three safety, one of them the `0.2.4`
regression. `evals/README.md` says "never been executed" in its first sentence
and a test asserts the caveat is still there.

**Issue templates**, which ask for the four things every hook report needs and
nobody sends unprompted: plugin version, OS, the Python the launcher found, and
the hook's output.

### Changed

**Three new gates in CI, for three things nothing was checking.** Each had
already failed silently at least once.

- `check_manifest_agreement.py`. `marketplace.json` sat at `0.2.1` while
  `plugin.json` said `0.2.4`, stale across three consecutive releases, because
  nothing at install time reads the entry — `plugin.json` wins and the entry is
  ignored. The drift was invisible right up to the point it would have blocked
  a release.
- `check_package_integrity.py`. Every test in this repository imports
  `harness_hooks.py` directly, which proves the program is correct and says
  nothing about whether Claude Code can start it. `hooks.json` names paths, and
  a hook whose command cannot be found does not ask and does not block: it does
  not run, and the plugin installs, looks healthy and enforces nothing. Paths
  are matched case-exactly, because NTFS resolves `Run_Hook.sh` to
  `run_hook.sh` and ext4 does not.
- `lint_agents.py`. `lint_skills.py` walks `skills/` and stops, so for four
  releases nothing looked at the three agents, whose `description` decides
  whether they are ever dispatched. It shares `has_trigger` and
  `parse_frontmatter` with the skill linter **by import**, with a test asserting
  object identity so a future copy fails — two copies of one rule is the defect
  `test_matcher_parity` exists to catch.

All three answer `3`, not `0`, when handed nothing to inspect.

`scripts/` goes from 135 tests to 178. `hooks/` is unchanged at 186.

## 0.2.4 — 2026-08-11

### Fixed

**A failed read is no longer announced as a failed write.** `0.2.3` taught the
write *log* to ask whether a tool was a write before recording it. The failure
notice was the same defect in the same file and did not get the same fix, and it
is the louder of the two: the log is a file someone reads later, while this
speaks straight into the agent's context in the same turn.

Both halves of its matcher were wrong, and each in a way the plugin had already
corrected somewhere else:

- `hooks.json` routed it a bare `mcp__.*`. Not "any Appian tool" — **any MCP
  server in the session**. A failed Figma, Supabase or Drive call came back
  described as a failed Appian write. This is the identical over-reach
  `WRITE_TOOL_RE` was narrowed to fix; this path never received it.
- Nothing on the Python side asked whether the name was a write at all, which is
  the omission `0.2.3` fixed for `log_write` and only for `log_write`.

The advice it gave is what makes this more than cosmetic. *"Do not retry this
write; check with a read whether it persisted"* is right for a write and
**backwards for a read**: nothing persisted, there is no partial state to
record, and a read that failed on a stale table name or a misspelled field wants
exactly one thing — to be issued again, corrected. It was observed doing
precisely that to a session whose next step was a corrected re-read.

A failed read now gets no notice at all. Its own error says more than this hook
can, and narrating another vendor's tools was never this plugin's job.

Also gone: the `"unknown tool"` fallback, which substituted a placeholder into a
sentence asserting a write had failed — a claim about an event it could not
identify, which is the habit the `0.2.3` tests exist to break.

Five tests in `test_logging_and_handoff_debt.py`, beside the `log_write` ones
they mirror, including one that reads the matcher back out of `hooks.json` so
that narrowing only the Python half fails. Verified by reverting the fix: four
of the five fail, and the fifth is the regression guard that must pass either
way.

### Changed

**The routing invariant now covers all three consumers, not two.** The write
matcher is spelled out verbatim in three `hooks.json` entries and JSON cannot
say it once, so editing one copy and not the others is the standing failure
mode. `test_matcher_parity.py` asserted `JSON ⊇ WRITE_TOOL_RE` for the scope
gate and the write log; the failure notice was the third copy and had no such
assertion, which is exactly how it sat at a bare `mcp__.*` unnoticed — broader
than the invariant rather than narrower, so nothing downstream ever failed.

## 0.2.3 — 2026-08-10

The three defects in `0.2.2` were found by the one person who can also fix them.
That is not the normal case, and this release is about the normal case: someone
using this plugin hits a defect they cannot fix, on a Thursday evening, and has
to decide what to do next. The dangerous answer — edit the installed copy — is
the one nothing had argued against.

### Added

**A written boundary, in the README: a project consumes this plugin, it never
modifies it.** With the reason, because "don't do that" is not an argument. The
cache is a **copy** made at install time, one directory per version; an edit
there works until the next update replaces the directory and silently reverts
it. Nothing records that the edit existed or that a project depended on it, so
one machine ends up behaving differently from every other machine running the
same declared version — and the declared version is the only thing anyone can
compare. A per-project fork is the same problem with more steps.

The section also states the constraint the boundary forces, which was already
true and never written down: **a tool its users cannot patch must never
hard-block, and must be conservative about what it asserts.** No gate here
refuses — the scope gate asks, the closure gate blocks once and then approves
with recorded debt — so a defect in this plugin costs a confusing message, never
an afternoon. A gate that traps someone with no way through is itself the bug,
and it outranks whatever they were doing.

And what to record meanwhile, in the project's own evidence: what the harness
claimed, what was done instead, and **the version it happened on**. The third is
the one people skip and the one that matters — without it a workaround outlives
its cause and nobody can tell whether it is still needed.

**A reporting path.** There was none, so the only in-band response to a defect
was to improvise, and what someone improvises is editing the cache.

### Changed

**The session-start line now names the running version** — `appian-harness
0.2.3: …`. Installed is not loaded: the component inventory is fixed when the
process starts, so an update applies only after a restart, and a plugin can be
installed, enabled and validated while the running session has never heard of
it. Every check on disk green, and the answer to "is the fix in?" still no. The
plugin root is the cache directory of the version in use, so this hook is the
one place that can answer, and it now does — falling back to the bare name if it
cannot, because the version is a courtesy and the requirements report is not.

### Tests

178 → 180 in `hooks/`.

## 0.2.2 — 2026-08-10

Three defects, found on a real project where one task sat in flight for two
days. They share a root: each states something the harness cannot actually
know, in a file a human is meant to trust later. None is a crash, which is why
all three survived 167 passing tests.

### Fixed

**Reads were recorded as writes.** `hooks.json` routes a bare
`invoke|start|execute|run|test` on purpose — it is the net that keeps a real
write from escaping the scope gate — and the Python half narrows it with
`WRITE_TOOL_RE`, which has always said an expression rule has no side effects.
`log_write` never asked. Three `appian_invoke_expression_rule` calls made
during an unrelated investigation were logged as writes of the task that
happened to be in flight, which expired all three of its verdicts and left its
closure gate unsatisfiable. The filter now runs where the plugin already draws
the line; the JSON matcher stays broad, and
`test_the_write_log_receives_them_too` still holds `JSON ⊇ WRITE_TOOL_RE`.
Narrowing the JSON matcher instead would trade a false entry for a missed
write — the wrong trade, worth stating because the shape invites that fix.

**`test_reads_and_replays_stay_free_on_both_sides` only checked one side.** Its
name promised two; its body asserted `WRITE_TOOL_RE` and stopped. The other
side is not the JSON matcher — it is what the hooks do with what the matcher
hands them. The missing assertion is the one that would have caught the above.

**Handoffs were recorded as closes.** The debt register said `task 'X' closed
via a repeated Stop`. It never was a close: `activeTask` is re-read from the
task file on every invocation, so a task that had really closed approves at the
top of `closure_gate` and never reaches the debt path — arriving there *means*
the task is still in flight. `closure_gate`'s own docstring already separated
the two cases ("that block is not a failure report"); the register now matches
it. And it appended unconditionally, so a task waiting on a human decision
collected one identical line per session: measured on the project that found
this, eleven entries, ten of them the same sentence, burying the only one that
carried an owner and a closing condition. Repeats of the same omission are now
skipped — skipped, not deduplicated in place, because this register is
append-only and rewriting history to keep it tidy is the failure mode it exists
to prevent. A different set of missing phases is new information and is still
appended.

**Verdict freshness rode on the file's mtime.** So the mtime *was* the claim,
and mtime is not a claim anyone made: `touch` cleared an expiry without
re-running a single audit — the rubber stamp the check exists to prevent — and
a clone, a copy or a restore from backup rewrote every mtime at once, so
freshness did not survive moving the project. Verdicts now carry `recordedAt`,
the auditor's own statement about its own verdict.

### Changed

`appian-practices-auditor` writes `recordedAt` (UTC, `YYYY-MM-DDThh:mm:ssZ`).
**Backward compatible:** the field is optional and every verdict already on
disk lacks it, so `_staleness_error` falls back to mtime when it is absent or
unparseable — a malformed value must never buy a pass an absent one could not.
`validate_verdict` checks the shape when present, so a misspelling fails loudly
instead of silently degrading to the old behaviour.

### Tests

167 → 178 in `hooks/`, 132 → 135 in `scripts/`.

## 0.2.1 — 2026-08-10

### Fixed

The launcher's no-interpreter branch decided "is this the repeat Stop attempt?"
with `cat`, `tr` and `grep` — three external commands, in the one branch that
runs only when the environment is already too broken to start Python. On a PATH
stripped bare they are missing as readily as `python3` is, so the test read
false and *block once, then approve loudly* became **block forever** — the
deadlock that branch exists to prevent. It now uses shell builtins only.

Found by CI on Linux, on the first push that ran it. A Windows-only run could
not have found it: Git for Windows ships those commands in the same directory
as `sh.exe`, so there, the shell being findable means they are too.

### Why this is 0.2.1 and not part of 0.2.0

0.2.0 was pushed before CI reported. Shipping this fix under the same version
number would leave an installation made from that commit answering "already at
the latest version" forever — which is precisely the drift `0.1.1` was released
to fix, and which this file was created to stop happening again. The rule costs
one line in two manifests; not following it costs an installation that never
updates and never says so.

## 0.2.0 — 2026-08-10

### Read this before upgrading

**Your MCP server has to have `appian` in its name, or it is no longer gated.**
The write matcher was `mcp__.*__(create|update|…)`, which measured *any* MCP
server's writes against an Appian task's `allowedObjects` — Supabase branches,
Figma files, Google Drive documents. It is now
`mcp__…appian…__(appian_)?(create|update|…)`. If your Appian server is
configured under a name without that substring, **every write through it stops
being checked, silently and immediately.** There is no warning for this: the
gate does not fire, so nothing says anything. `designMcpServer` does not help —
Claude Code evaluates the matcher in `hooks/hooks.json` before the plugin's
configuration is read. Rename the server, or edit that matcher.

**`appian-build` no longer carries `disable-model-invocation`.** The model can
start a build without a person typing the skill's name. Four preconditions still
stand between that and a write — an active task file, the object in
`allowedObjects`, the official-skill load record, a passing `design` verdict —
and it has to produce all four. If you want the old guarantee, configure
`activeRunFile`; it is checked, not trusted. Nothing else about write-time
behaviour changes when it is left unset.

### Gated now, and it was not before

- **Runtime invocation.** `appian_invoke_process_model`, `appian_invoke_agent`,
  `start_process`, `execute` and `testProcessModel` start real work and write
  real data in a shared environment, and passed with no gate at all. Reads and
  replays stay free on purpose — `invoke_expression_rule`, `testRule`,
  `runAllInterfaceTestCases` — because gating discovery and verification is how
  a harness gets switched off.
- **`updateRecordData` counts as destructive** and prompts like a delete. The
  premise separating the two — an update is versioned and recoverable — is true
  of a design object and false of a row: a row has no version history, so
  overwriting one is exactly as irreversible as deleting it.

### Verdicts expire

The closure gate compares each verdict against the write log
(`<evidenceDir>/operations.jsonl`). A review that comes back FAIL, a fix, and a
re-run of `review` alone used to close the task on `implementation` and `qa`
verdicts that certified an artifact which no longer existed. Now it says so.
`design` is exempt — it is *supposed* to precede every write.

A task that closed yesterday can therefore block today, on the same evidence.
That is the change working.

### Citations must resolve inside the plugin

`referencesApplied` entries are checked against
`skills/appian-best-practices/references/` and may not leave it. A reference
like `../../../README.md#the-gates` used to resolve, because the check degraded
to comparing filenames when the path escaped the root — so an agent could write
its own markdown, give it whatever heading it liked, cite it, and have both
gates accept that as settled doctrine. **A verdict that passed on such a
citation now fails.**

### Ceremony is proportional to declared risk

A fifth task-contract field, `risk`, decides how many verdicts close a task:
`trivial` one, `standard` (the default, and what anything unrecognised means)
three, `high` four — the fourth being an adversarial pass asking *how does this
fail* rather than *does this meet the contract*. A typo buys more ceremony,
never less. Declaring `trivial` is not prevented; it is written to
`<evidenceDir>/risk-downgrades.jsonl`, so it stays answerable afterwards.

Both directions are behaviour changes: a task that needed three verdicts closes
on one if you call it trivial, and needs four if you call it high.

### New

- **`/appian-run`** — sequences build → verify → review across a plan without a
  keystroke per task. Authorization is per run, written where the gate reads it,
  and **it must name a budget**: `maxTasks` and `tasksCompleted`, both whole
  numbers. A grant with no budget is standing permission, not a run. Delete the
  file when the run ends.
- **`/appian-init`** — adopts the harness into a project: config, state layer,
  evidence tree.
- **`requiresHumanConfirmation`** — an optional sixth contract field. Not a risk
  tier: it says the decision is not the builder's, so an unattended run stops
  and hands the task to a person.
- **`scripts/parallel_safety.py`** — decides which tasks may be built at once,
  from `allowedObjects` and `dependsOn`, transitive dependencies included.
- **`scripts/check_readme_claims.py`** — holds the README's counts and lists to
  the tree. Its own drift is the reason it exists.
- **CI** — Linux and Windows, Python 3.9 and 3.13. `isfile_exact` exists because
  NTFS is case-insensitive and ext4 is not, so a single-platform run would have
  let exactly that back in.

### Fixed

- An explicit `"evidenceDir": null` (as opposed to an absent key) returned
  `None` and crashed the hook. The scope gate turns a crash into a noisy `ask`,
  but both logging hooks emit `{}` and exit 0 — so a null stopped the write log
  in silence, and an empty write log makes every later verdict look fresh.
- `hooks/hooks.json` and `WRITE_TOOL_RE` are two halves of one matcher in two
  languages, and nothing compared them: verbs added to the Python half alone
  were gates that could never fire, because the call was never routed.
  `hooks/test_matcher_parity.py` now checks the invariant against the real tool
  catalogue of both Appian MCP servers.
- The `risk` verdict — the extra opinion the expensive tier buys — was the one
  verdict that never went stale, because the staleness check keyed on the tuple
  `risk` is appended to rather than on which phases follow the writes.
- A run authorization with no `maxTasks`, with `"maxTasks": "5"`, or with
  `"tasksCompleted": null` skipped the budget check entirely instead of failing.
  Each read as a wider grant than the file appeared to make, and the run kept
  working, so nobody found out.
- Writes aimed at the run authorization or the lease register were not recorded
  in `evidence-writes.jsonl`, though both are files the gates read and the agent
  can edit.
- `check_readme_claims.py` claimed to check that every config key the hooks read
  is documented, and could not see `maxAllowedObjects`, which reaches the config
  through a helper. It was documented by luck while the checker reported
  agreement.

## 0.1.1 — 2026-08-09

The first release that was actually a release. Packaging: one name for the
plugin and its marketplace, an install route that does not depend on the
author's machine, and a launcher that stopped writing bytecode into its own
installation.

The bump itself was the fix. `claude plugin update` compares the version field,
not the commit, and every change up to then had left that field at `0.1.0` — so
the updater kept answering "already at the latest version" while an installation
sat three commits back, including a fix, with nothing reporting a problem. This
file is the other half of that lesson.

## 0.1.0

Not a release. The version the scaffold carried from the first commit and never
moved off, through everything the harness became in between. It is listed here
so the gap between it and `0.1.1` is on the record rather than looking like a
missing entry.
