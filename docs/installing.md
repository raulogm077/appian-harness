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
the plugin itself:

```
/plugin marketplace add "C:\Users\you\My Projects\appian-harness"
```

Those two differ in more than the argument. A GitHub source installs what is
committed; a directory source copies the working tree **as it stands, including
files `.gitignore` excludes** — see [The installed copy carries files that are
not in git](troubleshooting.md#the-installed-copy-carries-files-that-are-not-in-git).

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
route only — a GitHub `owner/repo` argument has no spaces to lose.
`/plugin marketplace add`
takes a directory containing `.claude-plugin/marketplace.json`, a direct path to
a `marketplace.json`, a GitHub `owner/repo`, or a git URL. The documented
local-path examples are all relative and none of them contains a space, so
**there is no documented quoting rule** for the case that matters if your
checkout lives under `My Projects` or `Documents and Settings`. Try the
double-quoted absolute path first, as written above. If the argument was split
on the space, the error names a path truncated at the first one —
`C:\Users\you\My` rather than the folder you meant — which is how that failure
is told apart from a path that is simply wrong.

Two routes avoid the question instead of answering it, and either beats guessing
twice:

- **Type a relative path with no space in it.** Start Claude Code in the
  directory that *contains* the checkout and add it as `./appian-harness`. That
  is the shape the documentation shows, and the argument stays space-free
  however many spaces the ancestors of the path have.
- **Use the shell commands rather than the slash commands**, where the quoting
  rule is your shell's and you already know it:

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
no nodes for N3. Both of those returned 0 until 2026-08-09.

The three installation steps are **not verified as slash commands**: `/plugin
marketplace add` and `/plugin install` run inside Claude Code, so nobody here
can type them from a shell. Their CLI equivalents were run, which is a weaker
claim rather than the same one: on 2026-08-09 `claude plugin marketplace add
raulogm077/appian-harness` and `claude plugin install
appian-harness@appian-harness --scope user` were executed in that order against
this repository, the marketplace registered with a `github` source, and the
installed copy under `~/.claude/plugins/cache` compared file by file against
`git ls-files` — identical, 38 files, nothing extra. What that leaves untested
is the slash-command surface itself, the scope prompt step 2 opens, and the
restart in step 3. What is no longer hypothetical is the failure mode. This
section used to open with a bare `/plugin install appian-harness`; the first
person to follow it copied that first code block, and it answered `Plugin
"appian-harness" not found in any marketplace` (field experience). Hence the
order, stated as steps. The quoting of a path containing spaces is unverified in
a different way — the documentation does not address it at all, which is why the
section names a form to try first and two routes that do not depend on the
answer, rather than presenting one as settled.

