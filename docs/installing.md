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
— see *The checkout path* below.

Those two differ in more than the argument. A GitHub source installs what is
committed; a directory source copies the working tree as it stands, and has
been observed carrying files `.gitignore` excludes — see [The installed copy
carries files that are not in
git](troubleshooting.md#the-installed-copy-carries-files-that-are-not-in-git),
which also records the later measurement where a directory install delivered
only tracked files. That is the risk becoming historical rather than the
warning becoming wrong.

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

### The checkout path, and what to do about spaces

This applies to the local route only — a GitHub `owner/repo` argument has no
spaces to lose. **The slash command rejects every absolute path before touching
the disk**, with backslashes and with forward slashes alike, answering

```
Invalid marketplace source format. Try: owner/repo, https://..., or ./path
```

That error's list is the whole accepted grammar, so there is nothing to quote:
the only local form the slash command takes is a `./` relative path, which is
space-free however many spaces the ancestors of your checkout have. Two things
follow:

- **It resolves against the session's working directory**, so stand in the
  directory that *contains* the checkout and add `./appian-harness`. From the
  wrong directory the failure names a path with a missing separator —
  `...Cowork.claude-plugin\marketplace.json` — which reads like a corrupted
  install and is only a `./` resolved somewhere you did not mean.
- **The shell route remains for absolute paths**, where the quoting rule is
  your shell's and you already know it:

  ```sh
  claude plugin marketplace add "/path/with spaces/appian-harness"
  claude plugin install appian-harness@appian-harness
  ```

  These do not run inside a session, so what they install loads at the next
  start — which is step 3 either way.

If this plugin is ever published to a marketplace your installation already
trusts, only step 1 changes: add that marketplace instead of this checkout, and
name it after the `@` in step 2.

### What the plugin needs on the machine

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
The risk of that configuration is accepted; what is not accepted is that it
should be invisible, which is what step 2 of `/appian-init` below is for.

If no interpreter is found, `hooks/run_hook.sh` answers in the Python code's
place rather than going quiet: the scope gate asks, the closure gate blocks
once and then approves loudly on the repeat `Stop` so the session cannot
deadlock, the write log reports that the write was not recorded, and each
message names what was tried. In a project without `.claude/appian-harness.json`
it stays out of the way exactly as the hooks themselves do.

### Adopting a project with `/appian-init`

Installing the plugin governs nothing on its own. A project is adopted by
running `/appian-init` inside it, once. The command is idempotent — it dry-runs,
reports what already exists, and backs up and merges rather than overwriting —
so running it a second time is safe and mostly quiet.

What it does, in order:

1. **Checks the three links** the plugin depends on: the design MCP server, the
   official Appian skill, and the documentation MCP server.

2. **Runs the `hooks/run_hook.sh` probe on this machine and reports its literal
   answer.** If the answer is `command not found`, it says so in these words:

   > *«los hooks **no se están ejecutando** en esta máquina; el plugin está
   > instalado y no gobierna nada»*

   That is the Windows-without-Git-Bash case above, named out loud instead of
   left to be inferred from gates that never fire.

3. **Runs the perimeter probe** and fills `appianMcpToolPrefixes[]` from the
   servers the session has registered, rather than from a naming convention. If
   the declared perimeter does not match what is registered, it says:

   > **«Los hooks se están ejecutando pero no ven tus herramientas de Appian: el
   > plugin está instalado y no gobierna nada.»**

   This is the twin of the previous case, and the more dangerous of the two: the
   hooks run, answer, and see nothing. [Configuration](configuration.md#the-perimeter-which-tools-the-gates-are-allowed-to-see)
   has what the key covers and why it is a list.

4. **Writes `.claude/appian-harness.json` in full**, including
   `appianMcpToolPrefixes[]`, `regressionCommand`, `emptyPathIdentifier` and
   `measure` (which defaults to `false`). The `regressionCommand` it seeds is
   **scoped to the work**: the object touched plus its direct dependents,
   deduplicated, with the application row discounted. A sweep of the whole
   application stays opt-in, for before a delivery rather than for every write.
   It also enumerates **which dependent types actually have an instrument** and
   declares the ones that do not — a command that lists many dependents and can
   execute few has to say which few.

5. **Seeds a one-page glossary** into the project's `CLAUDE.md`, so the terms a
   person meets during a scope are defined where they will read them.

6. **Recommends registering the MCP servers with deferred schema loading**,
   which is the one lever that lowers the resident context cost without giving
   up a guarantee. [Configuration](configuration.md#registering-the-mcp-servers-so-they-cost-less)
   has the numbers.

**What `/appian-init` does not do is install anything.** It adopts a project
that already has its MCP servers and the official Appian skill in place; it does
not clone that skill, install a toolkit, or run `claude mcp add` for you. That
half of the command is not in this release, so if the three links in step 1 are
not there, step 1 reports their absence and you set them up yourself.

### How far this is checked, and where it stops

Both manifests parse, and the marketplace's name is the `appian-harness` that
step 2 names. The three installation steps are exercised as slash commands,
typed by a person inside Claude Code, which is the one surface a shell cannot
reach: absolute paths are rejected outright, `./appian-harness` from the
containing directory registers, `/plugin install appian-harness@appian-harness`
opens the scope prompt and installs, and `marketplace remove` uninstalls the
plugin exactly as [Troubleshooting](troubleshooting.md) warns.

The hooks are exercised directly, by feeding `run_hook.sh` a payload the way
Claude Code does — the command is in [Troubleshooting](troubleshooting.md) — and
they answer correctly through the whole chain ending in `allow`: allow in an
unconfigured project; ask with a config present and no active scope; ask for an
object outside `allowedObjects`; **allow** with a scope open, the object in it
and a valid passing `practices-design.json`; block on a stop with a scope in
flight and no verdicts; and approve-with-recorded-debt on the repeat stop. Those
answers are a test rather than a dated claim:
`hooks/test_documented_probe.py` extracts the published probe and the
whole-chain recipe from the documentation and runs them, which is how that
recipe was found to have never produced either answer it promised.

The closure chain is run the same way, end to end against a scratch project, in
the order a real scope meets it: block with the scope in flight and nothing
produced; **approve** once the verdicts the scope's size calls for are present,
valid and passing — `certify` and, when the scope carries risk, `risk`, plus
`design` where the size requires it; approve-with-debt on a repeat stop with
them removed, with the `deferred-debt.jsonl` line read back; and approve once
the active scope file is gone, which is what closing looks like to the gate. A
scope opened before 0.7 closes on `implementation`, `review` and `qa` instead:
those phases stay accepted, and obsolete, precisely so it can.

`validate_verdict.py` is exercised the same way, accepting a citation resolved
from a real heading and rejecting both a fabricated anchor and a nonexistent
reference file. `n2_interface_tree.py` and `n3_process_layout.py` are run from
the command line over sample inputs, each returning findings with exit 1, a
usage message with exit 2, 0 on a clean input, and **3 on an input neither of
them understands** — a component tree of unrecognised types for N2, a layout
naming no nodes for N3.

Comparing an installed copy against `git ls-files` is a check worth running
after any install from a directory source, and [Troubleshooting](troubleshooting.md#the-installed-copy-carries-files-that-are-not-in-git)
gives the two traps in doing it: normalize line endings before trusting a
content diff, and expect `.in_use/<pid>`, which belongs there. A
remove-and-reinstall is what rebuilds the copy clean; an update lays new files
over the old directory and deletes nothing.
