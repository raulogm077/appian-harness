# Security

This plugin runs code on your machine. Installing it is granting that code
execution in every session, so this file states exactly what runs, when, what it
reads, what it writes, and what it does not do. Read it before installing rather
than after.

## What installing this grants

The plugin declares six hook entries in `hooks/hooks.json`. Claude Code starts
them as ordinary child processes, **with your user's permissions** — the same
access as any command you run in that terminal. There is no sandbox between a
hook and your filesystem. Nothing here drops privileges, and nothing here asks
for any.

Every entry runs the same command:

```
sh "${CLAUDE_PLUGIN_ROOT}/hooks/run_hook.sh" "${CLAUDE_PLUGIN_ROOT}" <subcommand>
```

`hooks/run_hook.sh` probes for a working Python 3 (`python`, `py -3`, `python3`
on Windows; `python3`, `python`, `py -3` elsewhere) by running
`-c 'import sys; sys.exit(...)'` against each candidate, then `exec`s the first
that answers on `hooks/harness_hooks.py`. If none answers, the shell script
emits the hook's fail-closed decision itself and exits 0 — it never falls
silent, and it never invokes anything else.

`harness_hooks.py` imports `calendar`, `json`, `os`, `re`, `sys` and `time` from
the standard library, plus `scripts/validate_verdict.py` from this repository,
which imports the same set. **There are no third-party dependencies**, so
installing this plugin installs no packages.

## What runs, and when

| Event | Matcher | Subcommand | Timeout | What it may return |
|---|---|---|---|---|
| `SessionStart` | — | `session-start` | 15s | `additionalContext` only. Never blocks |
| `PreToolUse` | Appian MCP write tools | `scope-gate` | 15s | `allow` or `ask`. **Never `deny`** |
| `PostToolUse` | Appian MCP write tools | `log-write` | 15s | `{}`. Appends one log line |
| `PostToolUse` | `Write\|Edit\|MultiEdit\|NotebookEdit` | `log-evidence-write` | 15s | `{}`. Appends one log line |
| `PostToolUseFailure` | Appian MCP write tools | `failure-notice` | 15s | `additionalContext` only |
| `Stop` | `*` | `closure-gate` | 20s | `approve` or `block` |

The Appian matcher is
`mcp__[a-zA-Z0-9_-]*[Aa]ppian[a-zA-Z0-9_-]*__(appian_)?(create|update|add|…).*`
— it requires `appian` in the MCP server name, so tool calls to your other MCP
servers are not routed to this plugin at all.

Two entries are broader than that and worth knowing about. The
`log-evidence-write` entry fires on **every** `Write`, `Edit`, `MultiEdit` and
`NotebookEdit` in the session, and the `Stop` entry fires on every stop, in
every project. Both exit immediately when the project is not configured (below);
what they cost an unconfigured project is one process start.

## What it reads

In a **configured** project, from the project root the hook payload reports as
`cwd`:

- `.claude/appian-harness.json` — the harness config,
- the active task file (`tasks/current.json` by default, or what the config
  names),
- under the evidence directory (`evidence/` by default): the per-task verdicts,
  `dependents.json`, `appian-skill-loaded.json`, and the registers
  `operations.jsonl`, `deferred-debt.jsonl` and `risk-downgrades.jsonl` (the
  last two are re-read before appending, to avoid repeating an entry),
- the lease register and the run-authorization file, when the project configures
  them,
- `.mcp.json` in the project, and **`~/.claude.json` in your home directory**,
- the official Appian skill's `SKILL.md` — `~/.claude/skills/appian/SKILL.md`
  unless the config points elsewhere. Its **presence** is tested by default;
  the file is opened and scanned for the `**Appian Version:**` line only when
  the project sets `officialAppianSkillPath`,
- `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`, for the version reported
  at session start,
- the hook payload on stdin.

**`~/.claude.json` deserves the emphasis.** That file commonly holds MCP server
definitions including `env` blocks with API tokens, and the requirements check
parses the whole file to answer one question: which MCP servers are declared.
It reads the **keys** of `mcpServers`, and of the `mcpServers` block under the
entry for this project only — never the values, never a token. What leaves that
read is a yes/no per configured server name in the session-start message. If you
would rather it did not open the file at all, there is no switch for that today;
the alternative is not configuring the plugin for that project.

Environment variables read: `CLAUDE_PLUGIN_ROOT`, and in the launcher
`CLAUDE_PROJECT_DIR`, `OS` and `PWD`. The launcher sets
`PYTHONDONTWRITEBYTECODE=1` so the installed copy does not grow `__pycache__`
directories and stays comparable with `git ls-files`.

## What it writes

Five registers, all **append-only** (`open(path, "a")`), all under the
project's evidence directory, plus `os.makedirs` for that directory when it does
not exist:

| File | One line per | Fields |
|---|---|---|
| `operations.jsonl` | Appian write call | timestamp, task id, tool name, object identifier, `ok`/`error` |
| `evidence-writes.jsonl` | edit to a file the gates read | timestamp, task id, tool name, which input, file path, result |
| `gate-decisions.jsonl` | scope-gate `ask` | timestamp, task id, tool name, `ask`, reason |
| `deferred-debt.jsonl` | unverified handoff, or a deferred criterion | timestamp, task id, missing phases or criterion, owner, closing condition |
| `risk-downgrades.jsonl` | task closed as `trivial` | timestamp, task id, declared tier, phases required |

No hook truncates, overwrites or deletes anything, and nothing is written
outside the configured evidence directory. `operations.jsonl` records the
*identifier* the write targeted — the name or UUID it was called with — not the
tool's arguments and not its response, so the payload of a write does not land
in a log.

## What it does not do

Verified in the source, not assumed:

- **No network.** Nothing imports `urllib`, `socket`, `http`, or any HTTP
  client, and nothing opens a connection. The plugin never contacts Appian,
  GitHub, or anything else.
- **No telemetry.** Nothing is reported anywhere. The registers above are files
  in your project and stay there.
- **No credential reads.** No hook opens a keychain, a `.env`, a token store, or
  an MCP server's credentials. `~/.claude.json` is the one file it opens that
  commonly *contains* credentials, and it takes only server names from it — see
  above.
- **No subprocesses beyond the interpreter probe.** `run_hook.sh` runs the
  Python candidates and nothing else; `harness_hooks.py` never spawns a process.
- **No `eval`, no `exec`, no dynamic import** of anything outside this
  repository.

## The activation switch

**A project without `.claude/appian-harness.json` gets nothing.** In that case
`_build_config` returns before any other path is resolved: the hooks allow,
approve or no-op, and the only thing touched inside your project is the `isfile`
test on that one path. Home directory, skill and plugin manifest are not read;
no register is created. What still happens is the process start itself — the
launcher probing for an interpreter, and Python importing the plugin's own two
modules from the install directory. Installing this plugin at user scope therefore does not change what
happens in your unrelated projects, beyond the cost of starting a process.

## What the gates are not

The gates constrain a cooperating agent. They are not a boundary against a
hostile one, and the plugin says so in its own code: the agent the gates
constrain can write every file the gates read — the verdicts, the config, the
active task file. `log_evidence_write` exists because of that, and it logs
rather than blocks. It does not prevent forgery; it makes forgery leave a line.

If your threat model is an adversarial agent rather than a fallible one, this
plugin is not the control you need.

## Reporting a vulnerability

Email **raulogm07@gmail.com** with `appian-harness` in the subject. Do not open a
public issue for a vulnerability report.

You will get an acknowledgement **within 5 working days**, and an assessment —
including a decision not to fix, with the reason — within 15. This is a
single-maintainer project; those are the honest numbers, not a service level.

Useful in a report: the plugin version from the session-start line (the *loaded*
version, which is not always the installed one), your operating system, the hook
and subcommand involved, and the smallest input that reproduces it.

In scope: `hooks/`, `scripts/`, `commands/`, the skills and agents, and the
manifests — anything this repository ships and executes.

Out of scope: your Appian environment, the MCP servers this plugin talks
through, the official Appian skill, and Claude Code itself. Report those to
whoever ships them.

Fixes land in the latest released version. There are no backports.
