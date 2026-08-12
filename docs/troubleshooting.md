# Troubleshooting

> Part of the [appian-harness](../README.md) documentation.

### `Plugin "appian-harness" not found in any marketplace`

The marketplace was never added. A plugin name given with no `@` is looked up
across the marketplaces already registered with your installation, and
registration is something each installation does for itself — a public
repository does not put itself in your catalog, so on a fresh installation that
lookup has nowhere to succeed. It is not a corrupt manifest and not a misspelled
plugin name.

Run the commands in the order *Installing* gives them: `/plugin marketplace add`
pointed at `raulogm077/appian-harness`, or at your checkout, **first**, then `/plugin install
appian-harness@appian-harness`, then restart Claude Code. If it is the
first of those that failed rather than the install, the path is the thing to
look at — see the note there on paths containing spaces.

### Installed under the old marketplace name (`appian-harness@appian-harness-local`)

The marketplace was renamed from `appian-harness-local` to `appian-harness` —
one name for the plugin and the marketplace that carries it, instead of two.
Renaming the file does not rename an existing installation: Claude Code keeps
the old marketplace registered under `appian-harness-local`, so a checkout
updated in place ends up with **both** names known, one of them stale.

Migrate rather than let them coexist:

1. **Remove the old registration.** The argument is the `name` from the old
   `marketplace.json`, not a path:

   ```
   /plugin marketplace remove appian-harness-local
   ```

   or, from a shell:

   ```sh
   claude plugin marketplace remove appian-harness-local
   ```

   This also uninstalls the plugin that was installed from it — removing a
   marketplace from its last remaining scope takes the plugin with it, so
   step 3 below is not optional.

2. **Add it back under the new name.** Same command as *Installing* step 1,
   pointed at the same checkout, pulled to a version where
   `.claude-plugin/marketplace.json` already reads `"name": "appian-harness"`:

   ```
   /plugin marketplace add "C:\Users\you\My Projects\appian-harness"
   ```

3. **Reinstall,** now under the matching name from both sides of the `@`:

   ```
   /plugin install appian-harness@appian-harness
   ```

4. **Restart Claude Code** (or `/reload-plugins`), same as *Installing* step 3.

### The installed copy is behind the repository

`claude plugin update` compares the `version` field in
`.claude-plugin/plugin.json` against the one it installed. It does not look at
commits. A plugin whose version never moves answers `already at the latest
version` however far the source has travelled, and `claude plugin install` on
something already installed answers `already installed` and does nothing. Both
messages are accurate and neither updates anything, so a copy can sit commits
behind for weeks without a single error to notice.

Check rather than assume. `~/.claude/plugins/installed_plugins.json` records a
`gitCommitSha` per installed plugin; compare it with `git rev-parse HEAD` in the
checkout. On 2026-08-09 an installation sat at `24e8448` while the source was
three commits further on, including a fix — which is why this entry exists.

Two ways to move it:

- **Release a version.** Bump `version` in `.claude-plugin/plugin.json` *and* in
  the marketplace entry — they have to agree, and `claude plugin tag` refuses to
  tag when they do not. Then `claude plugin update appian-harness@appian-harness`
  has something to compare and acts on it. Note the fully qualified id: the bare
  name answers `Plugin "appian-harness" not found`.
- **Force a fresh install.** `claude plugin marketplace remove appian-harness`,
  add it again, then install. This picks up the current commit at an unchanged
  version, which is how the copy installed today got ahead of `24e8448`.

The first is the one to build a habit around; the second is for when you are
iterating on the plugin itself and versioning every experiment is absurd.

**Before you move it, read [`CHANGELOG.md`](../CHANGELOG.md).** An upgrade can make
a gate stop firing, and that is the one kind of change nothing reports at
runtime — a gate that starts firing tells you itself. `0.2.0` has two of them.

### The installed copy carries files that are not in git

`/plugin marketplace add` pointed at a directory copies that directory as it
stands. It does not consult `.gitignore` and it does not ask git what is
tracked: a copy installed that way on 2026-08-09 carried `.pytest_cache/` and
two `__pycache__/` trees whose `.pyc` files `.gitignore` excludes. Nothing
breaks — the skills, agents and hooks are the same files — but the plugin being
run is no longer the plugin the repository describes, and the gap widens every
time the tests are run before an install.

Two ways out, and the first is the one to prefer:

- **Install from GitHub.** A remote source can only carry what was committed, so
  the question does not arise.
- **Clean the tree before a directory install.** `git status --porcelain
  --ignored` lists everything that would travel; it is clean when it prints
  nothing.

Either way the repair is to fix the source and install again — installing
replaces the cached copy, so there is nothing to go and delete inside
`~/.claude/plugins/cache`.

Comparing an installed copy with `git ls-files` turns up one file that no
source produced: `.in_use/<pid>`, which Claude Code writes to mark the copy as
in use. That one belongs there. A `__pycache__` entry appearing after the hooks
have run does not, and no longer happens — `run_hook.sh` exports
`PYTHONDONTWRITEBYTECODE`, because bytecode written next to the source is
exactly what makes the copy stop being comparable.

### The hooks feel slow on Windows

The launcher probes for a working Python 3 before it can run anything, and on
Windows `python3` on PATH is usually the App Execution Alias in `WindowsApps` —
a reparse point that redirects to the real interpreter. It does not fail; it
just answers slowly, and whichever candidate wins the probe is then what runs
the hook. Probing the alias first therefore charged that cost twice on every
gated call.

`run_hook.sh` now orders the candidates by platform: `python`, `py -3`,
`python3` on Windows, and `python3` first everywhere else where `python` is
often absent or a Python 2. Measured on one machine with a python.org install
and the alias present, probe plus exec went from **13.1s to 2.6s** under load.

If it is still slow, check what `python3` resolves to:

```
command -v python3        # a WindowsApps path is the alias
command -v python
```

Removing the alias (Settings → Apps → Advanced app settings → App execution
aliases) helps every tool on the machine, not just this one.

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
   the hooks are genuinely silent. See
   [What this plugin does not do](../README.md#what-this-plugin-does-not-do).

To settle it rather than guess, feed a hook a payload the way Claude Code does:

```
printf '{"tool_name":"mcp__appian-dev__createInterface","tool_input":{"name":"Foo"},"cwd":"/abs/path/to/project"}' \
  | sh "/abs/path/to/appian-harness/hooks/run_hook.sh" "/abs/path/to/appian-harness" scope-gate
```

Absolute and quoted, both deliberately. Relative would work only from inside
the checkout, which is not where you are standing when you have a project to
ask about; unquoted breaks the moment either path contains a space, and on
Windows `C:/Users/you/My Documents/…` is an ordinary place to keep a checkout.

In a project with no config that prints `"permissionDecision":"allow"` with the
reason `appian-harness not configured for this project`; with a config and no
active task it prints `"ask"` and appends a line to `gate-decisions.jsonl`.

**The server segment has to name Appian**, which is why the payload says
`mcp__appian-dev__` and not `mcp__x__`. `WRITE_TOOL_RE` matches
`^mcp__…[Aa]ppian…__(create|update|…)`, so a probe against some other server
answers `allow` with the reason `not a write tool` — a JSON reply, so the hook
is demonstrably alive, and the wrong answer to the question you were asking. In
an unconfigured project it cannot mislead, because "not configured" is decided
first; in a configured one it looks exactly like a gate that has stopped
working.
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

cat > "$PROJ/evidence/TASK-3/appian-skill-loaded.json" <<'JSON'
{
  "task": "TASK-3",
  "skill": "appian",
  "source": "github.com/appian/dev-mcp-skills",
  "appianVersion": "26.7",
  "docsMcp": "appian-docs"
}
JSON

PAYLOAD='{"tool_name":"mcp__appian-dev__createInterface","tool_input":{"name":"Foo"},"cwd":"'"$PROJ"'"}'
printf '%s' "$PAYLOAD" | sh "$HARNESS/hooks/run_hook.sh" "$HARNESS" scope-gate
```

Two things in there are load-bearing and were missing from this recipe until
`0.5.3`, which is why it could not reach the answers below. The skill-load
record is a second thing the gate opens before any write — the tool schemas
carry no naming conventions and no creation order, so the gate reads a file
rather than trusting that the skill was loaded — and without it the chain stops
one reason earlier. And the payload names `appian-dev` because `WRITE_TOOL_RE`
matches `^mcp__…[Aa]ppian…__`: a server segment that does not name Appian is
`not a write tool`, and the gate allows it before looking at anything else.

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
heading. The rule is `_slug` in `scripts/validate_verdict.py`: lowercase the
heading text, drop every character that is not a word character, whitespace or
hyphen, then collapse runs of whitespace and underscores into single hyphens.
The references number their headings, so a real one makes the point:
`## 2. Choose the data source and access method` becomes
`#2-choose-the-data-source-and-access-method` — the number survives, the period
does not. Punctuation generally — colons, backticks, parentheses — is removed
rather than encoded.

⚠️ **This is not GitHub's rule, and this page used to say it was.** They agree
most of the time and differ on runs: GitHub keeps them, so `## Naming / prefixes`
anchors as `#naming--prefixes` there and `#naming-prefixes` here. Twenty-one of
this plugin's own reference headings differ between the two. **Do not copy an
anchor out of a rendered table of contents** — derive it from the heading, or
let the validator tell you, which is faster than either.

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
disables all six hooks for good — and it is not a defect that can be fixed
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

