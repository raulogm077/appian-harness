# Changelog

This file exists because `0.2.0` changes what the harness does to a project that
upgrades and edits nothing. Two of those changes make a gate stop firing, and a
gate that stops firing announces nothing — which is the only kind of change that
genuinely needs a release note.

Versions follow semver read as `0.x`: the middle number carries new behaviour
and behaviour changes, because the API is still moving.

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
- The launcher's no-interpreter branch decided "is this the repeat Stop?" with
  `cat`, `tr` and `grep` — three external commands, in the one branch that runs
  only when the environment is too broken to start Python. On a stripped PATH
  they are missing as readily as `python3` is, so the test read false and
  *block once, then approve* became block forever. It now uses shell builtins
  only. Found by CI on Linux; a Windows-only run could not have found it,
  because Git for Windows ships those commands in the same directory as `sh`.

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
