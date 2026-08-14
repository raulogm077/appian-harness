# Installing appian-harness

> Part of the [appian-harness](../README.md) documentation.

This repository **is its own marketplace** — the manifest at
`.claude-plugin/marketplace.json` lists the plugin with `"source": "./"` under
the marketplace name `appian-harness`. A marketplace has to be registered before
the plugin inside it can be named, and registration is per installation rather
than something a public repository grants you, which is what makes the order of
these three steps load-bearing:

**1. Register the marketplace.** This makes the catalog known and installs
nothing.

```
/plugin marketplace add raulogm077/appian-harness
```

**From a local checkout instead**, which is the route to take while working on
the plugin itself — from a session standing in the directory that *contains*
the checkout:

```
/plugin marketplace add ./appian-harness
```

Not an absolute path, however quoted: the slash command rejects those outright
— see *The checkout path* below for what was measured.

Those two differ in more than the argument. A GitHub source installs what is
committed; a directory source has been observed copying the working tree **as
it stands, including files `.gitignore` excludes** — see [The installed copy
carries files that are not in
git](troubleshooting.md#the-installed-copy-carries-files-that-are-not-in-git),
including the 2026-08-14 measurement where a directory install delivered only
tracked files, which is the risk becoming historical rather than the warning
becoming wrong.

**2. Install the plugin from that marketplace, by its full name.**

```
/plugin install appian-harness@appian-harness
```

(This is not a typo. The part before the `@` is the plugin name, the part
after it is the marketplace name — this checkout's marketplace and the plugin
it carries share the name `appian-harness`, so the full install target really
is `appian-harness@appian-harness`. Do not delete half of it.)

The command opens the plugin's details and asks which scope to install into —
user, project or local. That prompt is the command working, not a failure.

**3. Restart Claude Code** — or run `/reload-plugins`, if the install summary
reports `Run /reload-plugins to activate.` rather than `Plugin is now active.`
Restarting works on every version. Until one or the other happens the plugin is
installed and doing nothing, because its hooks and agents only take effect once
a session has loaded it: an install that appears to succeed and then gates
nothing is the ordinary appearance of a skipped step 3.

**Skipping step 1 is the failure this section is written around.** Running
`/plugin install appian-harness` on its own — no marketplace registered, no
`@appian-harness` suffix — answers:

```
Plugin "appian-harness" not found in any marketplace
```

That message is accurate and reads like a missing plugin. It is a missing
*marketplace*: a plugin name given with no `@` is looked up across the
marketplaces already registered with your installation, and this one is not
among them until step 1 runs.

**The checkout path, and what to do about spaces.** This applies to the local
route only — a GitHub `owner/repo` argument has no spaces to lose. An earlier
version of this section admitted there was no documented quoting rule and said
to try the double-quoted absolute path first. On 2026-08-14 that advice was
executed against a checkout under `Proyecto Claude Code Cowork` — three spaces
— and the question dissolved rather than getting answered: **the slash command
rejects every absolute path before touching the disk**, with backslashes and
with forward slashes alike, answering

```
Invalid marketplace source format. Try: owner/repo, https://..., or ./path
```

That error's list is the whole accepted grammar. Quoting never gets a chance
to matter, because the only local form the slash command takes is a `./`
relative path — which is space-free however many spaces the ancestors of your
checkout have. Two things about it, both measured the same day:

- **It resolves against the session's working directory**, so stand in the
  directory that *contains* the checkout and add `./appian-harness`. From the
  wrong directory the failure names a path with a missing separator —
  `...Cowork.claude-plugin\marketplace.json` — which reads like a corrupted
  install and is only a `./` resolved somewhere you did not mean.
- **The shell route remains for absolute paths**, where the quoting rule is
  your shell's and you already know it. (Whether the CLI accepts a
  space-bearing absolute directory source has not itself been measured — what
  is measured is that the slash command never will:)

  ```sh
  claude plugin marketplace add "/path/with spaces/appian-harness"
  claude plugin install appian-harness@appian-harness
  ```

  These do not run inside a session, so what they install loads at the next
  start — which is step 3 either way.

If this plugin is ever published to a marketplace your installation already
trusts, only step 1 changes: add that marketplace instead of this checkout, and
name it after the `@` in step 2.

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
parse, and the marketplace's name is the `appian-harness` that step 2
names. The hooks were exercised directly, by feeding `run_hook.sh` a
payload the way Claude Code does — the command is in
[Troubleshooting](troubleshooting.md) — and
they answered correctly in six cases, including the whole chain ending in
`allow`: allow in an unconfigured project; ask with a config present and no
active task; ask for an object outside `allowedObjects`; **allow** with an
active task, the object in scope and a valid passing `practices-design.json`;
block on a stop with a task in flight and no verdicts; and
approve-with-recorded-debt on the repeat stop. Since `0.5.2` the first two of
those answers are not a dated claim but a test: `hooks/test_documented_probe.py`
extracts the published probe from this documentation and runs it on every CI
run, and since `0.5.3` it runs the whole-chain recipe the same way — which is
how that recipe was found to have never produced either answer it promised.
The closure chain was then run
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
no nodes for N3. Both of those returned 0 until 2026-08-09.

The three installation steps **were verified as slash commands on 2026-08-14**,
typed by a person inside Claude Code — for a long time the one surface nobody
here could exercise, because slash commands cannot be run from a shell. What
that session established, each answer observed rather than assumed: absolute
paths are rejected outright (the grammar finding above); `./appian-harness`
from the containing directory registers; `/plugin install
appian-harness@appian-harness` opens the scope prompt and installs at `user`
scope; `marketplace remove` uninstalls the plugin exactly as
[Troubleshooting](troubleshooting.md) warns; a first re-add from GitHub failed
with a transient `EBUSY` lock **whose retry succeeded with nothing deleted**,
against the error text's own advice; and the rebuilt copy matched git name for
name and byte for byte once line endings were normalized. Before that, the CLI
equivalents had been run — a weaker claim rather than the same one: on
2026-08-09 `claude plugin marketplace add raulogm077/appian-harness` and
`claude plugin install appian-harness@appian-harness --scope user` were
executed in that order against this repository, the marketplace registered
with a `github` source, and the installed copy under `~/.claude/plugins/cache`
compared file by file against `git ls-files` — identical, 38 files, nothing
extra. Repeating that comparison
on 2026-08-12, after five releases of auto-updates, changed the answer in both
directions: the 88 tracked files were identical in content once line endings
were normalized (the install writes CRLF on Windows, so a byte-level diff
reports everything changed and nothing is), and the copy carried **one file
git never had** — an uncommitted draft a directory install had swept up five
releases earlier, which updates never remove. Both halves of that
are now written up in [Troubleshooting](troubleshooting.md#the-installed-copy-carries-files-that-are-not-in-git).
The 2026-08-14 session closed that gap — and closed the reinstall question the
2026-08-12 ghost had opened: the remove-and-reinstall rebuilt the copy clean,
the file git never had gone with it. What is no longer hypothetical is the
failure mode either. This section used to open with a bare `/plugin install
appian-harness`; the first person to follow it copied that first code block,
and it answered `Plugin "appian-harness" not found in any marketplace` (field
experience). Hence the order, stated as steps. And the quoting question this
section once named a form to *try* for is settled the same way, by a person
running it: there is nothing to quote, because the slash command accepts no
absolute path at all.

