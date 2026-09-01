# Design notes

Why the code is shaped the way it is, and the measurements behind the choices
that look arbitrary. One entry per decision, stated in the present tense.

This file exists so the source files do not have to carry it. Comments in code
say what the current line does and no more; anything that needs a paragraph,
a measurement or a platform trap to justify it is written down here and cited
from the code as `docs/design-notes.md § <name>`.

Two neighbours, so entries land in the right place:

- **`CHANGELOG.md`** — what changed in each release, and what a project that
  upgrades and edits nothing will notice.
- **`docs/troubleshooting.md`** — what a user does when something misbehaves.

Here: what a maintainer needs to know before editing a line.

---

## `run_hook.sh` § why a launcher exists

`hooks.json` used to invoke `python`, which exists on neither macOS nor most
Linux distributions — only `python3` does. A hook whose command cannot be
found does not ask and does not block: **it does not run**. The plugin
installed, looked healthy, and enforced nothing.

`harness_hooks.py` is fail-closed, but that safety net is inside the program.
The launcher's job is to make sure the program starts, and to answer in its
place when it cannot.

## `run_hook.sh` § shell form, not exec form

`hooks.json` invokes the launcher as a command string:

```
sh "${CLAUDE_PLUGIN_ROOT}/hooks/run_hook.sh" "${CLAUDE_PLUGIN_ROOT}" <sub>
```

The hooks reference generally prefers the exec form (`args`) for commands
carrying a path placeholder, and that preference is about quoting. Here it
would break the platform it means to help: exec form spawns the executable
from the process PATH, and Git for Windows puts `git.exe` on PATH via
`Git\cmd` while leaving `sh.exe` in `Git\bin`, usually not on PATH at all.
Shell form on Windows runs the command string *through* Git Bash, where `sh`
is guaranteed by definition — and on macOS and Linux shell form is `sh -c`,
where `sh` is guaranteed too.

## `run_hook.sh` § the plugin root arrives as an argument

Not derived from `$0`: on Windows `${CLAUDE_PLUGIN_ROOT}` expands to a
backslash path, and `dirname "C:\...\hooks\run_hook.sh"` returns `.`. The
placeholder is substituted by Claude Code, so passing it explicitly is the
only form that holds on every platform.

## `run_hook.sh` § `PYTHONDONTWRITEBYTECODE`

The interpreter is about to import `harness_hooks.py` — and, through the
closure gate, `validate_verdict.py` — from inside the installed plugin. Python
caches bytecode next to the source, so a plugin that starts out identical to
its repository grows `__pycache__` directories the first time a hook fires.
Nothing breaks, but the copy stops being comparable with `git ls-files`, which
is how anyone checks what they are actually running.

## `run_hook.sh` § interpreter probe order is platform-dependent, and measured

Each candidate is probed rather than trusted: `python` can still be a Python 2,
and on Windows `python3` is often an App Execution Alias stub that resolves on
PATH and then fails to run anything. The probe reads its stdin from
`/dev/null` — the hook payload on the real stdin has to survive untouched as
far as the `exec`.

On POSIX, `python` is often absent or a Python 2, so `python3` first is both
correct and cheap.

On Windows the alias usually *succeeds* and is simply slow. Measured on a
normal python.org install with the alias present:

| candidate | probe time |
|---|---|
| `python3` | ~2040 ms |
| `python`  | ~1070 ms |

The winner of the probe is what `exec` then runs for the real work, so probing
the alias first roughly doubled the fixed cost of every hook in the plugin.
`$OS` is set to `Windows_NT` by Windows itself and is visible in Git Bash, so
the branch costs nothing — no subprocess, no `uname`.

## `run_hook.sh` § the degraded path uses builtins only

Everything below the interpreter search runs only when none of the three
candidates works, which means the environment is already broken. A PATH
stripped bare is missing `cat` and `grep` exactly as readily as it is missing
`python3`.

`is_repeat_stop` used to be `payload=$(cat)` piped through `tr -d '[:space:]'`
into `grep -q` — three external commands. On a starved PATH the pipeline
failed, the test read false, and *block once, then approve loudly* became
**block forever**: the deadlock that branch exists to prevent. Linux CI caught
it and this machine never could, because Git for Windows ships coreutils in
the same directory as `sh.exe`: if the shell is findable at all, so are `cat`
and `grep`.

The replacement is `read` (a builtin), with `|| [ -n "$_line" ]` to keep a last
line that has no newline after it. The whitespace collapse reproduces what
`tr -d` did: word-split on IFS, re-join with an empty IFS, so
`"stop_hook_active":true` and `"stop_hook_active": true` compare equal —
nothing obliges Claude Code to pick one spelling. `set --` inside a function
touches only the function's own positional parameters.

## `run_hook.sh` § the degraded path still honours rule 3

A plugin installed in a project that does not use it must not get in the way.
Without an interpreter the config cannot be parsed, but its **presence** can
still be tested, and presence is the activation switch: absent, answer exactly
as the Python path answers for an unconfigured project; present, fail closed
and say so loudly.

The project root comes from `CLAUDE_PROJECT_DIR`, which Claude Code exports on
every hook process, rather than from the payload's `cwd` that the Python path
reads. Parsing JSON out of a shell is not worth the fragility for a degraded
path.

The `closure-gate` branch mirrors `closure_gate()`: a Stop hook has only
`approve` and `block`, with no `ask`, so blocking on every attempt would
deadlock the session — and the first thing anyone does with a deadlocked
guardrail is switch it off. `systemMessage` is the whole record in this mode,
because writing the deferred-debt entry would need the config parsed.

---

## `harness_hooks.py` § the two-stage matcher

`hooks.json` decides which tool calls reach this process at all; `WRITE_TOOL_RE`
decides what to do with the ones that arrive. A tool the JSON matcher does not
route is a tool `scope_gate` never sees in production, however broad the Python
pattern is.

**The invariant: `hooks.json` must route everything `WRITE_TOOL_RE` gates.**
The Python side is deliberately narrower on the runtime verbs — the JSON side
routes a bare `invoke|start|run|test`, this one names specific tools — and
narrower is safe: extra routing costs one no-op call. Broader here than there
is the unsafe direction, and it is silent. `test_matcher_parity.py` reads
`hooks.json`, applies both patterns to the real tool catalogue of the two
Appian MCP servers, and fails if anything the Python side gates would not be
routed.

That invariant is also why there is no `re.IGNORECASE`. Claude Code applies the
JSON matcher as written and has no flag to make it case-insensitive — that
matcher spells `[Aa]ppian` by hand for exactly that reason — so a
case-insensitive pattern on the Python side would be broader than the routing.

## `harness_hooks.py` § verbs: what the write matcher covers, and what it must not

Two corrections are folded into the pattern, both measured against real tool
names rather than reasoned about.

**The server name.** The pattern used to begin `^mcp__.*__`, which matched any
MCP server: `mcp__claude_ai_Supabase__create_project`, `Supabase__delete_branch`,
`Figma__create_new_file` and `Google_Drive__create_file` were all measured
against an Appian task's `allowedObjects` — and inconsistently, since
`Notion__notion-create-pages` escaped because the verb has to follow the
separator. Requiring `appian` in the server name keeps the gate on the
environment it reasons about.

**The runtime verbs.** The verb list described the design catalogue and said
nothing about the runtime, so `mcp__appian__appian_invoke_process_model` — which
starts a real process and writes real data in a shared environment — passed with
no gate at all, as did `appian_invoke_agent` and `appian-dev__testProcessModel`.

Those runtime verbs are spelled out rather than matched as a bare
`invoke|run|test` prefix, and the precision is the point: an expression rule has
no side effects, so `invoke_expression_rule` and `testRule` are reads, and
`runAllInterfaceTestCases` replays stored cases, which is what a verification
step should be free to do. Gating those would put friction on discovery and on
verification — the two things this harness most wants to be cheap.

The `appian` runtime server prefixes every tool with `appian_`, so the verb is
not where a reader expects it: the tool is `appian_invoke_process_model`, not
`invoke_process_model`. The corpus in `test_matcher_parity.py` is the real
catalogue for that reason.

## `harness_hooks.py` § object keys

Preferring one key over the others is wrong against the real schemas.
`updateInterface` takes a `uuid` and usually carries no `name`;
`addRecordTypeField(uuid, fieldName)` has no `name` at all; and
`updateProcessModelNode(processModelUuid, nodeId, name)` has a `name` that
belongs to the *node*, not to the object the task scoped. Reading only `name`
made most post-create writes compare a string that was never going to be in
`allowedObjects`, and ask.

## `harness_hooks.py` § official skill

Writing to Appian through the design MCP requires the official Appian skill
(github.com/appian/dev-mcp-skills), which carries what the tool schemas cannot
express: naming conventions, both sides of a relationship, the order objects
must be created in, and real UUIDs versus invented ones. None of that is
anything this plugin's gates measure — they check the contract, atomicity and
the presence of a verdict — so a write issued without it fails in a way nothing
here would catch.

A hook cannot see whether a skill is in an agent's context. What it can open is
a file, so the requirement is enforced the way the design audit already is: the
build records the load per task, and the gate reads the record. The record does
not prove the skill was loaded; it removes the silent case.

## `harness_hooks.py` § the three links

The chain is design MCP → official Appian skill → documentation MCP, checked at
session start rather than one failure at a time, because each link fails in a
way that looks like something else:

- **No design MCP** and every hook fires on nothing. The plugin installs, its
  tests pass, and it gates absolutely nothing.
- **No official skill** and objects get written with invented names and UUIDs,
  one-sided relationships and the wrong creation order.
- **No documentation MCP** and the official skill's function-availability checks
  come back empty, which reads as "the function does not exist" rather than as
  "nothing was checked".

## `harness_hooks.py` § what satisfies a gate

`validate_verdict` answers the document-shape question, plus the one thing shape
alone cannot answer: whether the document is about the work whose gate is
opening it. Both gates assemble the path from a task id and a phase, so both can
say what they are opening. Without that check, a verdict reading
`{"task": "TASK-999", "phase": "qa"}` satisfied every one of the four filenames,
and one audit copied four times was indistinguishable from four independent ones.

A phase audit satisfies a gate only on `PASS`, or on `NOT_MEASURED` with
`notMeasuredClass == DEFERRED` — which `validate_verdict` already guarantees
carries an owner and a closing condition. `FAIL` never satisfies.
`NOT_MEASURED/BLOCKING` never satisfies either: DEFERRED is the sanctioned,
owned, named escape; BLOCKING is the harness saying it could have measured this
and did not, which is a process failure, not a limitation.

Missing, structurally invalid, and valid-but-not-passing are three different
messages on purpose: "the audit exists and says FAIL" is not the same news as
"there is no audit".

## `harness_hooks.py` § verdict staleness

Nothing tied a verdict to a version of the thing it judged. A review coming back
FAIL, the agent fixing it, and only `phase=review` being re-run left the pre-fix
`implementation` and `qa` verdicts still satisfying the closure gate — two
PASSes certifying an artifact that no longer existed. With one builder that is
an occasional slip; unattended, or with several builders, it is the normal case.

Keying the check on `CLOSURE_PHASES` was wrong in the one place it could least
afford to be: `risk` is not in that tuple — it is appended for high-risk tasks —
so the fourth verdict, bought precisely because a mistake there is expensive,
was the only one that never expired. Stating the exemption as `design` instead
means a phase added later is checked by default and has to argue its way out.

The recorded date is read from the verdict's `recordedAt`, not from `getmtime`.
mtime is not a claim anyone made: `touch` cleared an expiry without re-running a
single audit, and a clone, a copy or a restore from backup rewrote every mtime
at once, so freshness did not survive moving the project. mtime stays as the
fallback, deliberately — verdicts written before the field existed are on disk
without it, and an unparseable value must not buy a pass it could not buy by
being absent.

Equal timestamps count as fresh: the log has one-second resolution, and a
verdict written in the same second as the write it judges is the normal case.

## `harness_hooks.py` § null config keys

`config.get(k, DEFAULT)` returns the DEFAULT only when the key is ABSENT. A
project whose `.claude/appian-harness.json` says `"evidenceDir": null` — what a
half-filled template looks like — got `None`, and `os.path.join(None, ...)`
raises.

The crash was survivable; where it landed was not. `main()` catches everything
and its answers are asymmetric by design: the scope gate turns an exception into
a loud `ask` and the closure gate into a `block`, but the two logging hooks emit
`{}` and exit 0. So one null stopped the operations log and the evidence-write
log **silently**, while a person hand-approved a stream of "harness hook error"
prompts. An empty write log then reads to `_staleness_error` as "this task never
wrote", which quietly makes every stale verdict look fresh.

Fail-closed held for the gates and the audit trail failed open, which is the
wrong way round: the gates announce their own failure, the logs are what nobody
is watching.

## `harness_hooks.py` § tool_response

`PostToolUse` delivers what the tool returned as `tool_response`, not
`tool_result` — confirmed against the hooks reference
(code.claude.com/docs/en/hooks, *PostToolUse input*), whose payload example
carries `tool_response`. `tool_result` is read as a fallback so the log stays
correct under either name: reading only the absent one would record every write
as "ok", and a write log that lies is worse than none, because it gets trusted.

## `harness_hooks.py` § run authorization

`appian-build` used to carry `disable-model-invocation: true`, so every task in
a twenty-task plan needed a human keystroke to start. That put the human gate on
*starting work* — high friction, almost no value — rather than on what is
irreversible or on a judgement that failed. Authorization moved to **per run,
granted once and bounded**, and `_run_authorization_errors` checks it rather
than trusting it, so removing the frontmatter flag does not become "the model
may now write whenever it likes".

Three spellings of a malformed budget used to walk past the check, and every one
of them widened the grant while leaving the file looking bounded:

| spelling | why it passed |
|---|---|
| no `maxTasks` | nothing to spend, so nothing ever spent |
| `"tasksCompleted": null` | `.get(k, 0)` returns `None`, not `0`, so the isinstance guard skipped the comparison |
| `"maxTasks": "5"` | same skip, from the other side |

## `harness_hooks.py` § the closure gate and its debt register

Before appian-build stopped deleting the active task file at STOP, nothing was
left in flight and this gate approved every nominal session without checking a
thing.

The debt entry used to read "closed via a repeated Stop", and it never was a
close: `activeTask` is re-read on every invocation, so a task that had really
closed would have approved at the top of `closure_gate` and never reached the
register. Arriving there *means* the task is still in flight.

It also appended unconditionally, so a task sitting in flight across sessions —
waiting on a human decision, the normal reason — got one identical line per
session. Measured on a real project: eleven entries, ten of them the same
sentence, burying the only one that carried an owner and a closing condition.
Repeats of the same omission are skipped; a *different* set of missing phases is
new information and is still appended. Nothing is deduplicated in place — the
register is append-only, and rewriting history to keep it tidy is the failure
mode it exists to prevent.

## `harness_hooks.py` § failure notice: writes only

The hook used to give write advice to every failed call. Both halves of the
matcher were wrong: the JSON routed a bare `mcp__.*`, so a failed call to any
MCP server in the session — Figma, Supabase, Drive — came back described as an
Appian write, and nothing on the Python side asked whether the name was a write
at all.

A failed READ announced as a failed write hands the agent a remedy that is
actively wrong for one: there is nothing to have persisted, nothing partial to
record, and "do not retry" is the opposite of the fix — a read that failed on a
stale table name wants exactly one thing, to be issued again with the name
corrected.

## `harness_hooks.py` § reads must not enter the write log

`log_write` used to log whatever the JSON matcher handed it. Three
`appian_invoke_expression_rule` calls made during an unrelated investigation
were recorded as writes of the task that happened to be in flight, which expired
all three of its verdicts and left its closure gate unsatisfiable: the task
could not close without re-running audits against an artifact nobody had
touched.

Narrowing the JSON matcher is the wrong fix — it is the net that keeps a real
write from escaping the scope gate, and `test_the_write_log_receives_them_too`
holds that direction. The line is drawn in `WRITE_TOOL_RE` instead.

## `harness_hooks.py` § the gates' own inputs

The list in `_evidence_write_target` has to grow whenever the gates learn to
read something new, and once it did not: the run authorization and the lease
register arrived as gate inputs while the function still knew about three files.
An agent could add `{"authorizedAll": true}` to the run file, or drop another
task's lease, and the edit left no line — unlike the same edit to the config,
which is no more sensitive.

## `harness_hooks.py` § deciding is not recording

`_risk_tier` once wrote the downgrade register from inside itself, which made a
*query* produce a file — and with an empty config that file landed on a relative
`evidence/` path in whatever the current directory happened to be. A unit test
asking "which phases does trivial require?" created a directory in the plugin's
own checkout, the exact plugin/project contamination this repository has a CI
step to prevent.

## `harness_hooks.py` § leases are the half a worktree cannot cover

A worktree gives each builder its own files — its own active task file, evidence
tree and SAIL sources — and two builders in two worktrees calling
`createRecordType` still write to the same Appian. The worktree isolates the
recoverable half and none of the other one.

The lease rule is one-sided on purpose: a lease held by a DIFFERENT task blocks,
and no lease at all does not. Requiring a lease would break every
single-builder project, which is the default and the common case. Protection
holds as long as one of two colliding builders claimed the object, and
`appian-build` claims.

---
## `validate_verdict.py` § what a citation check proves

A hook cannot see a subagent's transcript, so it cannot check that an auditor
loaded a skill. What it can check is the trail: the verdict must name the
reference sections it applied, and every one of them must resolve to a real
file and a real heading inside this plugin. A fabricated citation fails here.

This does not prove the auditor read the section. It proves the section exists
and is locatable by a third party — which is the failure mode that actually
occurs: the plausible citation that turns out not to exist.

The module's own exit codes are 0 (the document validates), 1 (errors printed)
and 2 (usage). It has no 3; the third outcome belongs to the checkers that
measure something, not to a document validator.

## `validate_verdict.py` § the risk phase

`risk` is the fifth phase and it is not a stricter `review`. Review asks "does
this meet its contract"; risk asks "how does this fail" — a different premise,
which is the only thing that makes a fourth opinion worth its cost. It is
required only for tasks the plan declared high-risk, so the adversarial pass
arrives where a mistake is expensive and nowhere else.

## `validate_verdict.py` § N/A at finding level

`N/A` is legal for one finding and never for the whole verdict. At finding
level it is the decision that a gate never came into play for this object,
made before the three outcomes become relevant
(`10-quality-gates.md#how-its-recorded`). That is why `FINDING_VERDICTS`
extends `VERDICTS` instead of `VERDICTS` carrying the value.

## `validate_verdict.py` § the closed list

`DEFERRABLE_CRITERIA` is *the* closed list, and it lives in code, in one place.
`10-quality-gates.md` and the auditor point at these ids rather than restating
them, and a test parses the document's copy and asserts it matches this tuple —
a list hand-copied into three files is exactly the drift this plugin keeps
finding in itself.

What makes the list mean anything is that a DEFERRED verdict must name which
entry it is invoking. Without that field the closed list is unenforceable by
construction: nothing in the document says which criterion is being deferred,
so "an agent cannot declare a criterion deferrable in order to unblock itself"
is a sentence with no mechanism under it, and DEFERRED is an unconditional
unlock.

The five entries: `screen-reader-testing`, `design-guidance-warnings`,
`row-and-field-level-security-with-a-real-user`,
`contrast-against-theme-supplied-colors`, `process-model-connection-routing`.

## `validate_verdict.py` § DEFERRED is rejected

A DEFERRED verdict with no `owner` is refused and the gate stays shut. Nothing
degrades anything: rewriting an agent's document into a class it did not write
would be worse than refusing it, because the record would then say something
nobody claimed. Prose that describes an ownerless deferral as "degrading to
BLOCKING" describes a behaviour this code does not have.

## `validate_verdict.py` § the process-excuse tripwire

`PROCESS_EXCUSE` is a tripwire, not a semantic judgement. The document requires
an `N/A` to be justified by what the OBJECT does or does not expose, "never a
justification about the process, the schedule or the time available" — and that
distinction cannot be decided by a regular expression. What the pattern can do
is catch the handful of phrasings the excuse actually arrives in, which is
enough to stop it passing *silently*. A false positive costs one rewording; the
false negative it replaces costs a gate.

## `validate_verdict.py` § case-exact paths

NTFS and APFS are case-insensitive by default and ext4 is not, so
`practices-QA.json` satisfies `os.path.isfile(".../practices-qa.json")` on a
laptop and not in CI — the same evidence tree closing a task in one place and
blocking it in the other. The documentation is unambiguous (the shape under
`evidenceDir` is fixed, and a verdict named `practices-QA.json` is one the gate
reports as missing), so the strict reading is the one implemented, everywhere.
A harness that behaves differently in two places is worse than either behaviour
consistently.

`root` bounds how much of the path is held to that standard: every component
*below* root must match on case, while root itself and everything above it are
taken as given — they are the project's own configured paths, not something an
agent chose. With no root, only the final component is checked.

## `validate_verdict.py` § paths outside root

A path outside `root` is `False`, not a softer check. Falling back to comparing
the basename — on the reasoning that a root which does not contain the path is
a configuration oddity rather than an answer — is a hole: a verdict citing
`../../../README.md#the-gates` resolves cleanly, because `README.md` does
exist, one directory up from where citations are allowed to point. Worse, an
agent can write its own markdown anywhere, name a heading in it, cite it by a
relative path and have both gates accept it as resolved doctrine. The whole
claim this function underwrites is that a citation names something inside this
plugin, so leaving root is a refusal.

Different drives raise `ValueError` from `os.path.relpath`, which is the same
answer: it cannot be under root.

## `validate_verdict.py` § citable filenames

A reference is `<file>.md#<anchor>` where `<file>` sits directly in
`references/`. Anything with a directory separator, a parent-directory
component or a drive letter is trying to leave, and a citation that leaves is
not a citation to this plugin's doctrine.

The shape is checked before touching the filesystem, and reported as its own
error, because "does not exist" would be the wrong message for a file that
exists somewhere it is not allowed to be cited from. This is defence in depth
with `isfile_exact`'s root bound: `_is_citable_filename` rejects the shape,
`isfile_exact` rejects the resolved location.

## `validate_verdict.py` § the slug rule

`_slug` is deliberately not documented as "GitHub's rule", which it is not:
GitHub keeps runs of separators, so `a / b` anchors as `a--b` there and `a-b`
here. Twenty-one of this plugin's own reference headings differ between the
two, so anyone copying an anchor out of a rendered table of contents would be
rejected by a validator claiming to use the same rule.

The rule that matters is this function, because this function is what
`anchors_of` derives the accepted set with — an anchor is correct when it
matches what `_slug` produces for a heading that really exists.

`check_readme_claims._fragment_key` deliberately uses a looser rule (letters
and digits only) and its docstring cites `_slug` as the reason there is no
strict slug rule to borrow. The two answer different questions: `_slug` defines
what an agent must WRITE into a verdict, so one exact rule is the contract; a
markdown link is read by whatever renders the page, so the renderer is the
authority there.

## `validate_verdict.py` § expected task and phase

`expected_task` and `expected_phase` are what the caller was opening this path
*for*. A gate always knows both — it assembled the path from them — and passing
them is what makes the document a claim about a particular piece of work rather
than a claim about nothing in particular. Without them the only question asked
of `phase` is whether it is one of the listed values, which one audit copied
into four filenames answers four times over.

They stay optional because the standalone CLI use is real: the auditor
validates its own verdict before any gate has opened it. The usage text says
the same: give TASK and PHASE and the document has to agree with them; omit
them to check the document's shape alone.

## `validate_verdict.py` § recordedAt

`recordedAt` is checked for shape, not for presence. Every verdict written
before the field existed is on disk without one, and the closure gate falls
back to the file's mtime for those on purpose. What must not happen is a value
that LOOKS like a timestamp and silently falls back anyway — that is a verdict
claiming a freshness nothing enforces. The accepted spelling is exactly
`YYYY-MM-DDThh:mm:ssZ`, UTC.

## `validate_verdict.py` § bare N/A in evidence

`"evidence": "N/A"` restates the verdict instead of justifying it, and the
document is explicit that a bare N/A does not count. `_strip_na` removes
leading `N/A` / `not applicable` tokens and their punctuation, repeatedly, so
what is left is the part that was supposed to be about the object. If nothing
is left, there was no justification.

## `validate_verdict.py` § validating findings

`findings[]` unvalidated leaves the per-gate "N/A: didn't get to it" alive
inside the one field nobody looks at — the exact hatch the three-outcomes
section exists to close. Unlike the top-level verdict, `N/A` *is* legal here:
it is the decision that a gate never applied to this object. What it needs is a
justification about the object, and that is what gets checked — non-empty
evidence, something beyond the letters N/A, and no process excuse.

## `parallel_safety.py` § worktrees do not isolate Appian

A git worktree isolates files. It does not isolate Appian. Two builders in two
worktrees calling `createRecordType` write to the same environment, so the
worktree protects the half of the problem that was already recoverable and none
of the half that is not. This module is the other half.

## `parallel_safety.py` § the four refusal reasons

The tool answers one question — "can these run at the same time?" — and refuses
for reasons that are facts about the tasks rather than judgements about them:

1. **Shared objects.** Two tasks whose `allowedObjects` intersect are two
   writers on one object. Nothing downstream can tell whose change a review is
   looking at.
2. **Dependency edges.** A task that depends on another cannot start beside it.
   The platform imposes an order — data source before record type, record type
   before the query, constants before the interfaces that call them — and "in
   parallel" does not suspend it.
3. **Destructive operations.** A deletion is the one action whose blast radius
   is not bounded by `allowedObjects`: it can break objects nobody listed. It
   runs alone, or not at all.
4. **Objects everything touches.** The application, a security group, a shared
   constant. Formally these are just objects, but a task that modifies one is a
   task every other task depends on without saying so.

Exit codes match the plugin's other checkers, including the one that matters:
**3 is NOT MEASURED, not a pass.** A plan this cannot read is a plan nobody
checked, and saying "OK" to it is exactly the vacuous green this harness argues
against everywhere else.

## `parallel_safety.py` § shared-object hints

`SHARED_OBJECT_HINTS` names objects whose modification is felt by tasks that
never name them. They are matched case-insensitively against a substring of the
object's name, because a plan writes names and not types. This is a heuristic
that produces a finding to be argued with, never a silent pass. The same holds
for `DESTRUCTIVE_HINTS`, which carries Spanish verbs (`borrar`, `eliminar`)
alongside the English ones.

## `parallel_safety.py` § tasks_of

The plan's tasks are read however the project spelled the container: a bare
list, `{"tasks": [...]}` or `{"plan": [...]}`, keeping only dicts that carry an
`id`. It returns `[]` when nothing recognisable is there, and the caller turns
that into NOT MEASURED rather than into a pass.

## `parallel_safety.py` § the transitive closure

Direct edges are not enough, and the gap is not theoretical: given
T-1 <- T-2 <- T-3, nothing connects T-1 and T-3 directly, so a pairwise check
on direct edges alone happily runs them together — starting T-3 before T-2 has
even begun. The order the platform imposes is transitive, so the check has to
be.

A fixed point rather than a recursive walk, and that is not a style choice: a
recursive version cuts each cycle short and then *caches* the truncated answer,
so in T-1 <-> T-2 it reports that T-1 depends on itself and T-2 does not.
Relaxing until nothing changes has no such order dependence — sets only grow
and are bounded by the task count, so it terminates, and every member of a
cycle ends up containing itself.

A cycle is a broken plan rather than a safe one, so it is recorded (see
`dependency_cycles`, which returns the tasks that end up depending on
themselves) instead of being followed forever.

## `parallel_safety.py` § check_pair without the closure

`closure` is the transitive dependency map over the WHOLE plan. Without it
`check_pair` falls back to direct edges only, which is weaker: a pair can look
independent while a chain connects them through a task neither one mentions.
Callers that hold the plan should always pass it. A dependency reached only
through the closure is reported with " (through a chain)" so the reader can
tell the two cases apart.

## `parallel_safety.py` § deduplicated findings

`check_group` deduplicates because a destructive task in a group of four
reports the same fact once per pair, and a list that repeats itself gets
skimmed.

## `parallel_safety.py` § greedy grouping

`safe_groups` is greedy on purpose: the goal is a defensible answer a person
can read, not the theoretical maximum. A bigger group found by a cleverer
search would still need the same human sign-off, and it would be harder to
argue with.

## `parallel_safety.py` § cycles

A plan whose dependencies loop cannot be executed in any order at all,
concurrent or otherwise, so the cycle is reported on its own and the run stops
there rather than being folded in with the pairwise findings.

## `parallel_safety.py` § groups are not a schedule

The printed order looks like a schedule and is not one. The output answers "who
may run TOGETHER", never "who runs first" — the plan's dependency order still
governs that, and a group whose predecessors have not closed is not ready no
matter how safe it is. The note is printed explicitly for that reason.

## `n2_interface_tree.py` § why the evaluated tree

A rendered-interface test returns the component tree already evaluated with
resolved data — including colours that came out of the database and appear
nowhere in the source (field experience). A linter over the source can never
see them. That is the whole reason this checking level exists.

## `n2_interface_tree.py` § platform traps

Both field experience, and both about getting a usable tree in the first place:

- The default response size cap truncates a real screen. Raise it, and trust
  the truncation flag rather than the byte count.
- Some API surfaces fail to serialize certain component types. Pick the surface
  that answers correctly, not the one that answers first.

## `n2_interface_tree.py` § the checked-type vocabulary

`CHECKED_TYPES` is *the* vocabulary: the `#t` values whose type this checker
knows how to judge. One constant, and the usage text is built from it rather
than restating it, so the list a user reads is the list the code applies.

Why it has to exist at all: a walk that accepts any shape and reports `OK` when
nothing matched makes a tree of types this checker does not judge
indistinguishable from a screen that was checked and found clean — the same
vacuous pass `lint_skills.py` closed when it stopped saying "All skills passed"
over zero files. `main` reports that case as NOT MEASURED and exits 3.

Types outside this list are not guessed at or aliased onto it. If a real tree
comes back NOT MEASURED, the honest answer is that this checker does not know
those components — not that the screen is fine. Unrecognised types are named in
the output so the gap is visible rather than assumed to be empty.

## `n2_interface_tree.py` § type_census

`check_tree`'s contract is documented as returning findings, and every caller
iterates that list. Whether the run measured anything is a question about
coverage rather than a finding, so it is answered by `type_census` and acted on
by `main` — the NOT MEASURED distinction is a CLI-level contract, not a new
return shape for the importable API.

## `n2_interface_tree.py` § no recognised types

Findings can still exist when no recognised type was found — contrast does not
care what type a node is — and they are printed, because they are real. But a
run that judged none of the types it exists to judge has not measured that
screen, and saying OK would be the vacuous pass. The exit code is 3 even with
findings printed above it.

## `n3_process_layout.py` § coordinates only

Field experience, and an honest limit: the API exposes node coordinates but
neither node dimensions nor connection waypoints. The thresholds are therefore
a proxy for "these do not overlap", not a proof, and the checker tells you
where every node sits — never where any arrow goes. A clean run is not a clean
diagram.

## `n3_process_layout.py` § the thresholds

`MIN_DX = 150` and `MIN_DY = 100` are the proxy for non-overlap. Two nodes at
identical coordinates are C1; two nodes closer than both thresholds are C2,
which reports the actual dx/dy against the required ones so the reader can see
how near the line it is.

## `n3_process_layout.py` § the C4 gap

The check ids jump from C3 to C5, and that gap is deliberate rather than an
omission to be filled later. C4 was to be a lane check — "the nominal path sits
on one y, branches get their own" — and nodes plus edges do not carry enough to
decide it: nothing here says which path is nominal, and any rule guessing it
from coordinates would only be re-asserting whatever layout it was given. A
constant for it (`LANE_DY`) sat unused while the README advertised the check;
both are gone. Lanes are a judgement made by looking at the diagram, which is
N5.

## `n3_process_layout.py` § back edges

C3 says flow goes left to right. Loops are legitimate in a process model, so
the edges that close a cycle — found by DFS in `_back_edges` — are exempt from
it rather than reported as backwards flow.

## `n3_process_layout.py` § no nodes is not measured

Nodes are what get measured. A layout naming none of them — with or without
edges — compared nothing, and reporting that as clean is the vacuous pass this
plugin argues against everywhere else. It is the narrow form of what
`n2_interface_tree.py` guards with `CHECKED_TYPES`, and it exits 3.

`_shape_errors` exists so a malformed layout is rejected with a named reason
instead of letting `check_layout` raise a `TypeError` three frames down.

## `exit_codes.py` § the contract

Every checker in this plugin reports three outcomes rather than two, and 3 is
the third: nothing was inspected, which is neither a pass nor a finding. The
scale is 0 clean, 1 findings, 2 usage, 3 NOT MEASURED.

3 is distinct from 1 on purpose, and it is 3 rather than any other free number
because that is what `CONTRIBUTING.md` and the README already tell a reader to
expect. A run that checked nothing and a run that checked something and found
problems are different results; collapsing them is how an absence gets read as
a pass, and 3 is the code a caller is most likely to wave through.

## `exit_codes.py` § why a file of its own

Six files typed the literal out separately — `lint_skills`,
`n2_interface_tree`, `n3_process_layout`, `check_evals`,
`check_manifest_agreement` and `check_package_integrity` — which is one rule
written six times, the same defect `hooks/test_matcher_parity.py` exists to
catch wearing another hat, and it shipped in the release that wrote the rule
against it into `CONTRIBUTING.md`.

It gets a file of its own rather than a home in whichever checker looks senior,
because the number is also asserted in prose: `CONTRIBUTING.md` states the
assignment and the README twice states the 0/1/2/3 scale. A copy that drifted
would leave the suite green — each checker agreeing with itself is the whole of
what a unit test of that checker can see — while the documentation described a
code the tree no longer returns. Nothing importable would have noticed, which
is why the parity now has a file to be about.

`scripts/test_exit_codes.py` holds the line by scanning the source text of
every `.py` in the tree for a re-typed assignment and asserting exactly one
file matches. A comment or docstring elsewhere that spells that assignment out
at the start of a line would fail that test.

## `exit_codes.py` § one value, no behaviour

One constant, and deliberately nothing else. Behaviour here would make this a
module six checkers depend on for more than a value, and a shared dependency
that can take all six down at once is worth more scrutiny than a number is. The
hooks do not import it, so it does not belong in
`check_package_integrity.REQUIRED_AT_RUNTIME` either. Keep it a value.

`lint_agents` takes `EXIT_NOT_MEASURED` from `lint_skills`, which re-exports it
from here; that two-step is asserted by `test_exit_codes.py` as well, so
`lint_skills` dropping the name in favour of a bare `exit_codes.` reference at
each use site would break a second linter without touching its file.

---
## `check_package_integrity.py` § why this file exists

Every test in this repository imports `harness_hooks.py` directly. That proves
the program is correct and proves nothing about whether Claude Code can start
it: `hooks.json` names a path, and a hook whose command cannot be found does not
ask and does not block — **it does not run**. The plugin installs, looks
healthy, and enforces nothing. That is the same failure `run_hook.sh` was
written to prevent one layer further in, and no amount of unit-testing the
module can see it.

So this file walks the declarations and checks the referents:

- every path a hook command names exists, matched case-exactly, in the manifest
  Claude Code would actually load — the one `plugin.json` points at, not the
  conventional one, when those differ;
- every component directory `plugin.json` declares exists;
- every `skills/<dir>` holds a `SKILL.md`, and every `.md` under `agents/` and
  `commands/` leads to a file inside the package that decodes as text;
- a `commands/` that ships files registers at least one of them as a command.

## `check_package_integrity.py` § a physical inventory, not a semantic one

The questions are: does the referent exist, is it spelled the way the
declaration spells it, does it lead anywhere, is where it leads still inside the
package. What a file *means* once opened belongs to the linters —
`lint_agents.py` owns the frontmatter of an agent, including which skills it may
name.

This file held that frontmatter rule too for a while. The two copies had already
drifted into disagreeing about block-style YAML before anyone noticed, which is
the defect `test_matcher_parity` exists to catch wearing a different hat. The
boundary is now a rule: one checker per question about the tree.

## `check_package_integrity.py` § hook path form

`${CLAUDE_PLUGIN_ROOT}/a/b` is the only path form a hook command may use,
because it is the only one Claude Code substitutes. A bare relative path in a
hook command resolves against the session's cwd, not the install — it works on
the author's machine and nowhere else.

Forward slash only, and not because Windows is being ignored: these strings are
handed to `sh`, where a backslash is an escape character rather than a
separator. A command written with backslashes is broken on every platform, and
matching it here would report it as fine.

## `check_package_integrity.py` § `DRIVE_PREFIX` instead of `os.path.isabs`

`os.path.isabs` answers differently on Windows and POSIX, and has changed its
mind about `\foo` across releases. A checker whose entire premise is giving the
same answer on every platform cannot ask a question that does not, so `C:` and
friends are matched by an explicit pattern.

## `check_package_integrity.py` § `COMPONENT_FIELDS`

These are the fields through which `plugin.json` may point Claude Code at
somewhere other than the conventional directory. Declaring one and shipping
nothing at it does not error at load time: the components are simply not there,
which from inside a session is indistinguishable from never having written them.

## `check_package_integrity.py` § runtime list

`REQUIRED_AT_RUNTIME` is the rest of the boot chain. `hooks.json` names
`run_hook.sh` and stops; what `run_hook.sh` starts, and what that in turn
imports, no manifest mentions — so a package can lose either one and every
declared path still resolves.

Written out rather than derived, for the direction a mistake takes — the same
argument `check_readme_claims` makes for `DERIVED_CONFIG_KEYS`. Deriving would
mean being right about two more languages: shell, for the `$PLUGIN_ROOT/...`
that `run_hook.sh` names, and Python imports, for what `harness_hooks.py` pulls
out of `scripts/`. Wrong about either and the miss is silent, which is precisely
the failure this list exists to end. A stale entry fails loudly on the next run
and is fixed in a minute.

The entries are THIS package's files. Like `lint_skills.SECTION_EXEMPT`, the
dict is meant to be edited by whoever adopts the file, not inherited unread.

What each entry buys, in the words the finding uses:

- `hooks/harness_hooks.py` is the program every hook command starts.
  `run_hook.sh` probes an interpreter and execs it against this path; with the
  file gone Python exits with `can't open file` and writes nothing to stdout, so
  the scope gate returns no decision and the write it was gating proceeds.
- `scripts/validate_verdict.py` is imported at module level by
  `hooks/harness_hooks.py`, so losing it is not a degraded closure gate — it is
  an `ImportError` before any subcommand runs, which takes down all the hooks at
  once and just as quietly.

## `check_package_integrity.py` § case

Every component is matched against the directory listing instead of being handed
to the filesystem, because NTFS and APFS are case-insensitive and ext4 is not:
`Run_Hook.sh` satisfies `os.path.isfile()` on the author's laptop and is simply
not there in CI. A checker that inherits the filesystem's opinion passes on the
machine where the mistake is invisible and fails on the machine where it bites,
which is the asymmetry rather than a check of it.

`_resolve_exact` answers about spelling only. Whether the name leads anywhere,
and whether where it leads is still inside the package, are separate questions
`_referent_problem` asks after it — a listing is evidence that a name was
written correctly and evidence of nothing else.

## `check_package_integrity.py` § check order

`_referent_problem` asks in the order the answers stop being informative in: a
malformed declaration first, then spelling, then whether the name leads
anywhere, then whether where it leads is still in the package, then what kind of
thing it is. Escape is reported before file-ness because "points outside the
install" is the useful half of "points outside the install at something that is
not a file".

## `check_package_integrity.py` § absolute paths

An absolute path in a manifest is rejected rather than reinterpreted, and the
choice is not obvious. `/hooks/hooks.json` could be split into components and
looked up under the plugin root, which quietly turns a broken declaration into a
working one and reports OK.

Whether Claude Code accepts an absolute path there is a question whose two
answers both end in "say something": if it does, the path leaves the install and
the containment rule refuses it; if it does not, the declaration is malformed.
Neither answer ends in silently rewriting it, which would have this file conceal
the exact class of defect it exists to find.

## `check_package_integrity.py` § dangling links

`os.listdir` lists the *name*, and a dangling link has one. Reading presence out
of the listing alone — which is what this file did until a reviewer pointed at
it — counts a link to nothing as a file that is there, increments the tally,
emits no finding and can exit 0. Hence the explicit `os.path.exists` step.

A `hooks/run_hook.sh` that is a link to somewhere else on the author's disk
satisfies every spelling check and ships as a package whose launcher is not in
it, which is why `_escape_reason` puts both ends through `realpath` and requires
the target to land under the root. Different drives on Windows are not
comparable, therefore not inside.

## `check_package_integrity.py` § the deleted wrappers and the `isfile_exact` name collision

Two wrappers used to live between `_referent_problem` and its callers,
`isfile_exact` and `exists_exact`, each returning `_referent_problem(...) is
None`. Both are gone.

`check()` never called them — it calls `_referent_problem` directly, because it
wants the reason and not the bool. So they were public surface with one caller
between them, that caller being their own test.

The trap worth remembering: `isfile_exact` is already the name of a *different*
function, in `validate_verdict.py`, with the arguments the other way round —
`isfile_exact(path, root=None)` against `isfile_exact(root, relative)`. Two
strings in, a bool out, both times, so importing the wrong one does not fail: it
answers wrongly and says nothing. The one the rest of this repository means by
that name is `validate_verdict`'s; `hooks/harness_hooks.py` imports it to decide
whether a verdict file exists, which is the gate that closes a task.

A name collision costs nothing until somebody reaches for it. Deleting the
unused half was cheaper than making the two halves agree.

## `check_package_integrity.py` § both hook command spellings

A hook may carry its command as a string under `command` or as an argv list
under `args`. Reading only the first meant an exec-form hook contributed no
referents *and* no warning: the recursion descended into the list, every element
was a bare `str`, and a `str` node yields nothing. A typo in the path of an
exec-form hook was invisible — not even the "names no path under
`${CLAUDE_PLUGIN_ROOT}`" notice fired, because no command string was ever seen
to notice it about.

Argv elements are joined rather than yielded one by one, so a path split across
several of them still reads as one command to the caller, and so the
no-placeholder notice judges the whole invocation.

## `check_package_integrity.py` § `_path_values` and inline configuration

Every component field accepts a single path or a list of them, and `hooks` and
`mcpServers` additionally accept the configuration inline as an object. An
object declares no path, so it contributes nothing to `_path_values` —
`_hook_manifests` reads it instead.

## `check_package_integrity.py` § which hooks manifest to open

Which file to open is not a detail. `plugin.json` may point `hooks` at a path of
its own, and walking `hooks/hooks.json` regardless would validate a manifest
Claude Code never loads while the one it does load goes unread — a green run
about the wrong file. When nothing is declared, Claude Code falls back to the
conventional path, so that is the one whose absence means "this plugin ships no
hooks" rather than "this plugin is broken".

## `check_package_integrity.py` § orphaned hooks

A tree where no manifest declares a single hook is legitimate — plenty of
plugins ship none — so it is only a finding when the package contradicts itself: `hooks/` full of code and
no manifest naming any of it. A plugin with no hooks has no `hooks/` directory;
one with the launcher, the program and no `hooks.json` installs, looks healthy
and invokes none of it, which is this file's own subject pointed one level up.

Measured, not imagined: deleting `hooks/hooks.json` from a copy of this
repository made `check()` return `(0, [])`. The hooks left the package and the
checker whose subject is hooks that never run said nothing. What did fail the
build was `check_readme_claims`, by raising `FileNotFoundError`, because the
README happens to state a hook count — coverage that exists by accident of the
prose and arrives as a traceback rather than as a finding.

The rule is deliberately not keyed on `plugin.json`'s `hooks` field: this repo
does not declare one, hooks are discovered at the conventional path, so a rule
about the declaration would be a no-op on the very tree the gap was measured in.

## `check_package_integrity.py` § the tally

Opening a manifest is deliberately NOT counted as an inspection — only a
referent that actually resolved is. A `hooks.json` declaring `{"hooks": {}}`
would otherwise buy a clean "OK every declared path resolves" for having been
opened and found to declare nothing, which is the vacuous green this plugin
spends a README arguing against.

Zero referents resolved is not an intact package, it is an uninspected one, and
the two must not share an exit code — hence `EXIT_NOT_MEASURED`.

The `and not msgs` guard is not belt-and-braces. NOT MEASURED outranking a
finding is the worst answer this file can give: it would report "nothing was
checked" about a defect it has already found and is holding in its hand, and
exit 3 is the code a caller is most likely to wave through. Findings win.

## `check_package_integrity.py` § one finding per path

Referents are collected first and reported once per path rather than once per
command. All the hooks in this plugin go through the same launcher, so a single
missing file printed once per hook reads as that many separate problems and
buries whatever else the run found.

## `check_package_integrity.py` § runtime gate

The `REQUIRED_AT_RUNTIME` sweep is gated on a hook command having *named* a path
under the plugin root — named, not resolved. Naming one is what makes this a
package that runs hooks, and it stays true when the file it names is the missing
one, so a tree that lost both `run_hook.sh` and the program behind it reports
both.

It is not gated on "a manifest was walked", which was the first shape and the
wrong one: `{"hooks": {}}` walks a manifest and declares nothing, and the gate
would have turned that from NOT MEASURED into a finding about files a package
with no hooks has no reason to carry.

## `check_package_integrity.py` § commands

`commands/` joins `agents/` in this loop, and before it existed nothing looked
at `commands/` at all: `lint_skills` walks `skills/`, `lint_agents` walks
`agents/`, and the one component a user invokes by name had no reader in any CI
step.

What the loop closes is the file being there, leading somewhere inside the
package, and decoding. It does NOT close "the README promises `/appian-init` and
no such file exists": that is a claim about prose, it belongs to
`check_readme_claims`, and the boundary is the same one drawn for the hooks
manifest — a package that ships no commands legitimately has no `commands/`
directory at all.

The tree is walked rather than listed, because `commands/<namespace>/<name>.md`
is how a command gets a namespace. A top-level-only scan reads a package whose
commands all live one level down as a package with none, which would make the
"registers nothing" finding fire on a perfectly good tree.

The "ships files and registers nothing" rule is the only rule in this file about
something being ABSENT, and it is narrow on purpose: shipping no commands is a
normal thing for a plugin to do, so the finding is not "`commands/` is missing"
but "`commands/` is there, holds files, and Claude Code takes nothing out of
it". It is the same contradiction as a `skills/<dir>` with no `SKILL.md`.

A name ending in `.md` that turns out to be dangling still counts as registered
for that purpose. It has already been reported precisely, one step earlier, and
adding "and nothing registers" on top would be the same file reported twice
under two descriptions.

The rule is asked of `commands/` only, and not for lack of symmetry:
`lint_agents` already answers it for `agents/`, exiting 3 over an `agents/` that
holds no `.md` file. Restating it here would be a second checker with an opinion
about the same tree, which is how this file's agent frontmatter rule and
`lint_agents`' drifted apart the first time.

## `check_package_integrity.py` § junctions

What gets inspected is decided by the NAME, never by `os.walk`'s verdict on it.
A dangling junction keeps its directory attribute after the target is gone, so
Windows hands `appian-init.md` back in `subdirs` and a loop over `entries` alone
never sees it — measured here, and it is the same blind spot in a new place: the
name is in the listing, ends in `.md`, and resolves to nothing. Such a name is
judged and then not descended into, since whatever sits under a name that cannot
itself register is not registering either.

Every `.md` referent goes through `_referent_problem` like every other referent
in the file, rather than the `os.path.isfile(...) or continue` this loop used to
open with. That guard answered `False` for a dangling link and moved on in
silence — a name in the listing, ending in `.md`, resolving to nothing — which
is the precise defect a reviewer had already found in `exists_exact`, and which
these two directories reintroduced by being added after the fix.

## `check_package_integrity.py` § read, not parsed

The `.md` files are read, not parsed. What the frontmatter says is
`lint_agents.py`'s subject; what this file establishes is that the bytes are
there and decode — a file Claude Code cannot read is one it does not register,
silently, exactly like a hook command it cannot find.

The read is wrapped rather than allowed to propagate: a traceback out of a
checker is a broken checker to whoever reads the CI log, and this is a finding
about the package, which is what the run is for.

## `check_package_integrity.py` § the success line

The success line says what was established and not a word more. "Every skill and
agent resolves" was true when this file read agent frontmatter; it now checks
that the files are there and readable, and a success line that keeps claiming
the larger thing is exactly the drift this repository has a checker for.

## `check_readme_claims.py` § why this file exists

Counts in prose drift. This plugin's drifted three times in one working session
— hook count, skill count, test totals — and a reader caught it every time, a
check caught it never. Which is the same argument the plugin makes about Appian
evidence, turned on the plugin: a claim nobody can check is a claim that quietly
stops being true.

So anything the prose asserts about its own repository becomes a fact a machine
holds: the number of hook entries `hooks.json` declares, the test totals for the
two suites, the size of every directory the prose enumerates (programs, skills,
domain reference files, judging agents, and eval cases split by routing and
safety), every config key the hooks read being documented, every skill, program
and agent being named, every append-only log the code writes being listed, and
every relative link resolving, section included.

## `check_readme_claims.py` § the document set

Claims are read across a **set** of documents, not one file: `README.md`, plus
every `docs/*.md` when that directory exists. A README that states every count
is a README nobody finishes, so those sections move out of it — and a checker
that only ever opened `README.md` would then report every moved claim as
deleted, which is the right answer to a deletion and the wrong one to a move. A
claim in none of the documents is still a failure; that half is the point.

`docs/` being absent is not a finding. Labels are relative and slash-separated
so a message names the same file on Windows and Linux, which is where these runs
are compared.

## `check_readme_claims.py` § two document sets

The link set is a **second, wider set** than the claim set, and the two must not
be merged. The claim set answers "where may a claim about the tree live"; the
link set answers "whose links have to resolve", and every document in the
package has that duty, including the skills and the eval cases, which state no
count at all.

Widening the claim set would pull in `CHANGELOG.md`, whose `0.4.0` entry states
a program count that was correct for that release. Reading history as a claim
about today would fail the build for being accurate.

Dot-directories and `__pycache__` are tool state rather than authored documents:
`.pytest_cache` ships a `README.md` nobody wrote.

## `check_readme_claims.py` § deliberately narrow

It checks claims with a **mechanical referent** and says nothing about whether
the prose is any good — that needs a reader, and pretending otherwise would be
the vacuous green this plugin argues against.

## `check_readme_claims.py` § no exit 3

Nothing here exits 3, and the omission is deliberate rather than inherited. Its
siblings need NOT MEASURED because a tree can declare nothing for them to
inspect; this file counts every fact against the tree whether or not the
directory is there, so an `agents/` that has gone missing reports "the prose
states a number, the tree has none" instead of counting nothing and calling it
agreement. Every referent it cannot read becomes a finding for the same reason:
silence is the one answer it must never give.

## `check_readme_claims.py` § link pattern

`LINK` matches an inline-link target, which is every inline link and every
image. Reference-style definitions (`[label]: target`) are not read, and the
repository has none — if one appears, this stays quiet about it rather than
guessing.

Inline code is not special-cased either: a link written inside backticks as an
example gets resolved like any other. That is a deliberate limit rather than an
oversight — telling them apart needs a markdown parser, this repository has
none, and the alternative to being occasionally too strict would be a rule that
also skips real links which happen to sit near code.

## `check_readme_claims.py` § `SCHEME`

A URI scheme means "not a path in this repository": http, https, mailto, and
anything else somebody writes. Two characters minimum before the colon is what
keeps `C:/Users/...` out of it — a drive letter would otherwise read as a scheme
and a link that only works on the machine it was written on would be waved
through as somebody else's problem.

## `check_readme_claims.py` § `NUMBER`

`WORDS` exists because the prose writes small numbers as words, which reads
better and is exactly as checkable once you say so.

The older claim patterns capture with `(\w+)` and get away with it because each
anchors on a phrase that occurs once. The newer ones cannot: a loose pattern for
the skill count also matches "The skills orchestrate" several sections down, and
a loose pattern for the agent count matches "the agents" and two other phrasings
in three more places. Loose, every one of those reads as a count this file then
declares unreadable — a checker inventing findings about sentences that were
never claims. Digits stay in the alternation: the test totals are written as
digits.

The `\b` is the whole of the left anchor and it is not decoration. The noun
anchors the right side; with nothing on the left, "standalone modules" ends in
"one" and reads as a claim of a single program, so a sentence that was never a
count becomes a finding against a tree that holds many. The older `(\w+)`
patterns need no such guard — each is anchored by a literal that a word cannot
run into.

## `check_readme_claims.py` § derived keys

`DERIVED_CONFIG_KEYS` names the keys the hooks compute for themselves rather
than read out of a project's config file. Everything else a `config.get("...")`
names is a key a person writes, and therefore a key the documented list has to
contain.

Written out rather than derived from `_build_config`'s dict literal, and the
direction of a mistake is why. Forget one here and the check reports a derived
key as undocumented — noise, loud, fixed in a minute. Derive the set instead and
it silently excuses `maxAllowedObjects`, which appears in both places, which is
the bug this list exists to have caught.

## `check_readme_claims.py` § config key pattern

Both spellings are matched, because a key read through a helper is still a key
the hooks read. `maxAllowedObjects` arrives as
`_max_allowed_objects(project_config)`, and inside that helper the parameter is
called `config` — so a pattern anchored on `project_config` could not see it,
and this file reported agreement while one of the documented keys was outside
its reach. It was documented by luck, not by check.

## `check_readme_claims.py` § reads never raise

Every read in this file goes through `_read_text`, and the reason is the one
`check_package_integrity.py` wrote down when it wrapped its own: a traceback out
of a checker reads in a CI log as "the checker is broken", not as "the package
has a problem" — which is the finding, and the whole output the run existed to
produce. It also collapses the 0/1/2 vocabulary every caller here is written
against into an unhandled exception, which is none of the three.

Measured rather than imagined. Deleting `hooks/hooks.json` from a copy of this
repository made `check()` raise `FileNotFoundError` on the `json.load` that
counted hook entries, and that traceback — not a finding — was what failed the
build.

`UnicodeDecodeError` joins `OSError` because a file that does not decode is a
file Claude Code does not read either, and the two arrive as the same fact:
there is no text, so whatever it was holding is unheld.

Losing `hooks/harness_hooks.py` is called out separately: both the config-key
list and the evidence table are derived from that file, so losing it leaves two
checks holding nothing rather than one, and neither of them would have said so.

## `check_readme_claims.py` § hook-count shape

`_hook_count` checks the shape rather than trusting it. An array under `hooks`
decodes as valid JSON and turns the sum into an `AttributeError` — the same
crash as a missing file wearing a different exception type, and worth exactly as
little to whoever is reading the log.

## `check_readme_claims.py` § borrowed definitions

`_is_case_dir` is imported from `check_evals` rather than reimplemented here,
private name and all: it encodes that `results/` is where the runner writes
scores and that dot- and dunder-prefixed directories are tool artefacts. A
second copy of that list would be free to drift from the file that decides what
actually runs, and this checker would then hold the prose to a count of cases
nobody executes — the same argument `check_evals` makes for borrowing
`lint_skills`' frontmatter parser instead of writing a second one.

## `check_readme_claims.py` § fragment keys

`_fragment_key` keeps letters and digits and nothing else, so a heading holding
a backticked filename and the anchor `#the-hooksjson-file` meet. It is
deliberately looser than any real slug rule, and this repository is the reason
there is no strict one to borrow: `validate_verdict._slug` exists, and its own
docstring records that it is NOT GitHub's rule — GitHub keeps runs of
separators, so `a / b` anchors as `a--b` there and `a-b` here, and twenty-one of
this plugin's reference headings differ between the two.

That function is right for what it does, which is a different question from this
one. It defines what an agent must WRITE into a verdict, so one exact rule is
the contract. A markdown link is read by whatever renders the page, so the
authority is the renderer — and picking either rule here would report links
written for the other as broken. Both survive dropping the punctuation, which is
why it is dropped.

`_anchor_keys` numbers repeats the way renderers number them: a second
`## Fixed` is reachable as `#fixed-1`, a third as `#fixed-2`. `CHANGELOG.md` has
four such headings per release, so without this the only honest options would be
reporting a working link as broken or not checking fragments at all.

## `check_readme_claims.py` § links

A link is the shortest checkable claim a document can make — "it is over there".
Every relative link in every markdown file the package ships has to resolve to
something that exists, spelled the way the link spells it, resolved against the
file holding the link. That last clause is the defect the README split actually
caused: a link to `CHANGELOG.md` travelled into `docs/`, where it means
something else, and a person reading found it. This check is that reader, minus
the remembering. Where a link names a section, the section has to be in the
target.

`_link_target` handles both forms markdown allows for a title — `path "Title"`
and `<path with spaces>` — because the alternative is reporting a link with a
title as a path that contains one, which is a finding about the parser rather
than about the document.

Joining uses `posixpath` and not `os.path`: labels are slash-separated whatever
the platform, and a link is written the same way on both. Joining with `os.path`
would produce `docs\..\CHANGELOG.md` on Windows and compare it against
slash-separated labels.

Targets are matched case-exactly through `check_package_integrity`'s own
resolver rather than handed to the filesystem. NTFS and APFS say
`Troubleshooting.md` is there and ext4 and GitHub say it is not, so asking the
filesystem passes on the machine where the mistake is invisible and fails where
a reader meets it.

A fragment on a target with no headings is not judged: `#L42` on a source file
is a line anchor the renderer invents, and a directory has no headings at all —
neither is a claim this can judge.

## `check_readme_claims.py` § `count_tests`

`count_tests=False` skips the two suite spawns, and only this file's own tests
pass it: they build tiny broken trees to prove this checker can fail, and
counting tests in a three-file fixture costs an interpreter start per case to
learn nothing. Left on, this checker's own tests added seven seconds to the edit
loop — the kind of cost this repository now goes looking for.

`_ran_count` skips the slow launcher subprocess tests, and that does not move
the total: skips still count in unittest's "Ran N".

`APPIAN_HARNESS_IN_README_CHECK` breaks a recursion that is easy to create and
hard to see. `_ran_count` spawns `unittest discover` against the scripts suite,
and that discovery contains this checker's own tests, one of which calls
`check()` on the real repository — which spawns the suite again, forever. The
nested run sees the marker and skips that one test.

Where a suite directory does not exist there is no claim to check. Spawning
`unittest discover` against a directory that is not there costs an interpreter
start to learn nothing, and would then report "could not read a test count"
about a suite the repository never had — a finding that is not about the prose
at all.

## `check_readme_claims.py` § every occurrence, not the first

`claim()` checks every occurrence in every document, not the first one found.
The README already states the domain-reference count twice — in the table and
again several sections down — and `re.search` held only the first, so the second
was as unchecked as if it were in another file. Which, once these sections move
into `docs/`, some of them will be. A duplicate that has gone stale is exactly
the defect this file exists for, and stopping at the first match is how it
survives.

Where nothing is to be read at all, `check()` returns early: reporting a dozen
claims as missing from a file that is not there says one fact twelve times and
buries it. The joined `prose` string serves the "is this name mentioned
anywhere" checks, which ask about presence and not about which document holds
it.

## `check_readme_claims.py` § counting against the tree

The "What is in the box" table states a size for every directory it lists, and
for a long time not one of those numbers was held by anything — in the very
release that codified "an assertion in prose brings the check that sustains it".
Add one more program and CI stays green while the table lists one fewer.

Counts are taken against the tree with no "does the directory exist" guard, on
purpose. A missing `agents/` makes the count 0 and the finding reads "the prose
states a number, the tree has none", which is true and useful; guarded, the
claim would go unchecked precisely when it had become most wrong.

Test files are not programs here. The prose lists the programs, and states their
suites' totals separately, as tests rather than as files.

The domain-reference count uses the one explicit path rather than a glob over
every skill's `references/`: the sentence being held is about
`appian-best-practices`' references specifically, so a second skill growing a
`references/` of its own would turn a true sentence into a failure and teach
whoever hits it to loosen the check.

The agent count anchors on "judging agents", never "agents" on its own. The
README talks about the agents doing the judging one section later, and about a
pair of them in the paragraph on review — both of them prose about how the
agents are used rather than a count of what ships. A pattern loose enough to
reach the table row reaches those too and calls one of them wrong.

The eval suite gets three claims and not one. Swapping a safety case for a
routing case keeps the total unchanged while the sentence describing the suite
stops being true, and the split is the half that says what the suite covers.

## `check_readme_claims.py` § counts versus enumeration

The counts say how many; the name loops say which. A table that enumerates can
be wrong in two ways, and one number covers only one of them — a count that
matches while one listed name is not the program that exists passes any count
and is still a table that sends a reader to a file that is not there.

## `check_readme_claims.py` § the failure line

The failure line said "The README disagrees" until the claims could live in
`docs/` too. A success or failure line that keeps naming one file when the check
reads several is the same drift this file exists to catch, one level up.

---
## `lint_agents.py` § shared rules

The three agents are as much the product as the skills. An agent's
`description` decides whether it is ever dispatched — the same job a skill
description does, judged by the same rule — so `has_trigger` is imported from
`lint_skills` rather than restated. Two copies of one rule is the defect
`test_matcher_parity` exists to catch, and writing the matcher again here would
be that defect under a new name. `MAX_DESCRIPTION` and `EXIT_NOT_MEASURED` come
across for the same reason: a limit raised in one file and not the other is two
linters disagreeing about one contract.

This file owns what an agent's frontmatter MEANS — `name`, `description`,
`skills`, `tools`. `check_package_integrity.py` owns the physical inventory and
does not interpret frontmatter.

## `lint_agents.py` § read-only whitelist

`appian-reviewer` holds Read/Grep/Glob because a reviewer that can edit what it
reviews is not an independent reviewer. Every blacklist form of that rule fails
open, because asking what is FORBIDDEN only ever protects against what its
author thought of. These are the spellings measured walking past one:

- A parser plus a list of four write tools: `tools: [Write]` passes, because
  comma-splitting the folded value yields `"[Write]"`, not `"Write"`.
- Brackets handled: `tools: Read, Write # temporary` passes.
- Comments handled: six more YAML spellings pass — a comment line inside a
  block sequence, a blank line inside a block sequence, a flow sequence wrapped
  across lines, a nested sequence, a duplicate key, a block scalar.
- Raw search for the forbidden words: `tools: Read, Grep, Glob, Skill, Bash`
  passes, because `Bash` writes any file in the repository with a redirection
  and was not one of the four words. `Task` and every MCP write tool were open
  too.

So both halves are inverted. The region is read RAW, which no spelling can hide
inside, and what may be in it is a WHITELIST — `READ_ONLY_TOOLS`. Any other
name is a finding, including the ones nobody has invented yet. A blacklist
fails open on everything its author did not enumerate; a whitelist fails closed
on everything it does not permit, and that is the only direction a prohibition
may be wrong in.

## `lint_agents.py` § READ_ONLY_TOOLS

Everything a read-only agent may hold. Adding a name widens what a reviewer can
do to the thing it is reviewing, so it is a design decision with an argument
attached, not a way to make a red build go green.

The list is not "the write tools, negated", and what is absent says why:
`Bash` writes any file with a redirection, `Task` delegates to an agent that
can write, `WebFetch` reaches the network, and every MCP server spells its
write tools differently — `mcp__appian-dev__createRecordType` and another
server's equivalent share no substring worth matching on. None of those can be
enumerated. What a reviewer needs can.

## `lint_agents.py` § READ_ONLY_AGENTS

Agents whose independence depends on not being able to write, each mapped to
the reason. An entry here is a claim the README makes about the verification
pyramid; removing one is a design decision, not a lint fix.

The finding message names the route out and its price: if a listed name is
genuinely read-only, it is added to `READ_ONLY_TOOLS` with the reason written
down. A set that grows without an argument attached is the blacklist this
replaced, wearing the other polarity. The message says what to do and not only
what is wrong, because a finding that reads "not permitted" leaves the reader
two options, and the one they reach for under time pressure is deleting the
tool they needed.

## `lint_agents.py` § declarations

A region runs from the `key:` line to the next top-level key, so it holds the
inline value AND every continuation line — block sequence entries, the tail of
a flow sequence that wrapped, comment lines, blank lines, the body of a block
scalar. Whatever the spelling, the names it grants are in there somewhere. A
key at the start of a line ends the previous key's declaration; anything
indented, blank or commented belongs to the key above it.

Every declaration is returned, not the first. YAML resolves a duplicate key to
the last one, so a reader that returns at the first match reads a declaration
the loader discards: `tools: Read` followed by `tools: Read, Write` is a grant
of Write that stopping early reports as read-only.

## `lint_agents.py` § skills vs tools

`skills:` is deliberately NOT read as a raw region. It is a whitelist already —
each name has to resolve against `skills/` — so a spelling the reader misreads
produces a name that does not resolve and gets printed. Under `tools:` the same
misreading produced a token that is not a forbidden word, which is a clean pass
on an agent holding write access. Same misparse, noisy under one key and silent
under the other. That asymmetry is why two keys in one frontmatter are read two
different ways, and anyone tempted to unify them should read this entry first.

## `lint_agents.py` § not a YAML parser

A quoted entry containing a comma (`["a,b"]`) is split in two, and an anchor or
alias is taken literally. Both surface as a complaint about a name nobody
wrote, which is a bad message rather than a missed finding — acceptable here
only because this path feeds a whitelist.

A flow sequence may wrap across lines and a block sequence may be interrupted
by a comment or a blank line. Collecting the two shapes separately and then
splitting both on commas reads all of them: the scalar half rejoins a wrapped
`[a,\n b]`, and the item half no longer stops at the first line that is not an
entry. Stopping there dropped every name after a comment silently, which under
a whitelist is the one failure that does not print anything.

## `lint_agents.py` § comments in tools

Comments ARE stripped before the whitelist test, and the reasoning is the
reverse of what it was under the blacklist this replaced. There, dropping a
comment risked dropping a grant. Under a whitelist a comment's words are not
grants, and keeping them makes every documented tools line a false alarm —
`tools: Read # nothing that writes` would be refused for the word "nothing".
What survives the strip is the declaration itself, which is exactly what the
loader sees.

A prohibition is not enforced by parsing: every spelling a parser fails to
understand becomes a token that does not match, and a token that does not match
is a silent pass. So the region is read whole and each word-like token in it is
tested against `READ_ONLY_TOOLS`.

## `lint_agents.py` § TOOL_TOKEN

The pattern is deliberately greedy about `_` and `-` so an MCP name arrives
whole: `mcp__appian-dev__createRecordType` is one token that is not on the
whitelist, rather than several fragments that individually look harmless.

It is not `\b[A-Z][A-Za-z]*\b`, which is the obvious spelling and was proposed
for this. Built-in tool names are capitalised but MCP tool names are not, and
there is no `\b[A-Z]` anywhere in `mcp__appian-dev__createRecordType` — the
capital R sits between two word characters, so no boundary precedes it. That
pattern harvests `Read` and `Grep` from the line and nothing else, and reports
an agent granted every Appian write tool as clean. Measured, not reasoned
about.

## `lint_agents.py` § empty tools line

An agent with no `tools` line inherits every tool in the session. So does one
whose `tools` line is punctuation and comments, which is why emptiness is
judged after stripping both rather than by the presence of the key.
`PUNCTUATION_ONLY` covers whitespace, list punctuation and block-scalar
indicators: everything a `tools:` declaration can be made of while naming no
tool at all.

## `lint_agents.py` § utf-8-sig

`utf-8-sig`, not `utf-8`: an editor that writes a BOM produces a file whose
first character is not `-`, so the frontmatter is not recognised and every
field reads as missing. The result is four findings about a well-formed agent,
none of them the actual problem.

## `lint_agents.py` § checkers do not raise

A read error is caught rather than allowed to propagate, for the reason
`check_package_integrity` gives: a traceback out of a checker is a broken
checker to whoever reads the CI log, it takes the other agents' results down
with it, and it collapses the 0/1/3 vocabulary the whole design rests on into
"it crashed".

## `lint_agents.py` § stale read-only entries

The failure this check exists for is silent in the worst direction. Rename
`agents/appian-reviewer.md` and its `name:` together and every per-file check
still passes — name matches filename, tools are declared — while the
restriction simply stops applying to anything. Nothing prints, because a rule
that matches no agent has no agent to complain about.

`lint_skills` carries the same phantom-entry hazard for `SECTION_EXEMPT`, but
that one over-permits LOUDLY: a stale exemption skips a section check on a
skill that is right there in the output. A stale restriction under-protects in
silence, which is the worse of the two directions, so it is checked rather than
commented about.

What this cannot see: an agent that SHOULD be read-only and was never added.
`appian-second-reviewer.md` with `tools: *` passes, and no fact about the tree
distinguishes it from an agent legitimately allowed to write. That is a
judgement about intent; this is a check about names.

## `lint_agents.py` § exit 3

No `agents/` directory, and `agents/` holding no `.md` file, both report exit
3. Reporting either as a finding would say something was checked and failed,
and the whole point of the third code is that those two stop being one signal.
"All agents passed" is trivially true of nothing.

The stale-entry check is skipped when zero agents were checked, rather than
firing: against a tree with no agents at all it would report every guarded name
as missing, which is true of the tree and says nothing about the rule.

## `lint_skills.py` § shared exit code

The value is imported rather than restated, and re-exported rather than used
through the module name, because `lint_agents.py` does
`from lint_skills import EXIT_NOT_MEASURED` alongside `MAX_DESCRIPTION` and
`has_trigger`, and that import is what a test holds. The comment this line
replaced claimed the value was "shared with `n2_interface_tree` and
`n3_process_layout`" while all three typed it out separately — shared by
assertion, not by construction.

## `lint_skills.py` § trigger phrasings

A description must say WHEN the skill fires, not only what it is. Both the
imperative house style ("Use when...") and the third-person form
`plugin-dev:skill-development` prescribes ("This skill should be used
when...") count: rejecting the latter would refuse a skill written exactly as
the official guidance recommends. `plugin-dev:skill-reviewer` found that the
phrasing choice itself does not affect triggering quality — only the
specificity of the stated conditions does — so both forms are accepted on equal
footing rather than one being treated as a fallback.

## `lint_skills.py` § negation window

"Do not use when...", "Not for use when...", "should not be used when..." and
the like describe an exclusion, not a trigger. The negation word can sit a few
words away from "use"/"used" ("Not for use when...") rather than directly
adjacent to it ("Do not use when..."), so the pattern matches a negation word
followed, within the same sentence, by "use" or "used" — a 30-character window
bounded by `[^.!?]`.

## `lint_skills.py` § per-sentence judgement

The negation test is applied per sentence, and that is the whole point of it.
Applied to the description as a whole it rejected "Use when X. Do not use when
Y." — a description with a perfectly good trigger and an exclusion after it,
which is the commonest real shape there is. A trigger and an exclusion are two
different statements, and a skill that states both is better documented than
one that states only the trigger; judging them together means the better
description is the one that gets rejected.

An earlier comment claimed sentence punctuation protected that case. It does
not. What `[^.!?]` protects is a negation placed BEFORE the trigger ("Not
applicable to legacy skills. Use when...") which the window cannot reach
across. A negation AFTER the trigger sits in its own later sentence and matched
perfectly well.

The exclusion sentence still cannot serve as the trigger on its own — it is
skipped, not accepted — so a description carrying only "Do not use when..."
fails exactly as before.

## `lint_skills.py` § sentence split

Splitting on sentence-ending punctuation followed by whitespace. A description
is one or two sentences of prose, so this does not need to survive "e.g." or an
abbreviation mid-clause — and if it mis-split one, the result is a sentence
with no trigger, which the next sentence covers.

## `lint_skills.py` § SECTION_EXEMPT

Exemptions live here, not in skill frontmatter, so a skill cannot bypass the
validator by editing its own file. Every entry needs a documented reason.

`SECTION_EXEMPT` maps a skill name to a documented reason, and it is empty:
every skill this plugin ships carries the required sections, so nothing is
exempt. The mechanism stays because a router skill — one that only lists other
skills, with no procedure to rationalize about — would legitimately need it.

It held one entry for `using-appian-harness`, a skill that does not exist here.
A live exemption for a phantom would silently exempt whatever took that name
later, which is not what a file whose exemptions are meant to be unbypassable
should do.

## `lint_skills.py` § exit 3

Zero skills checked is NOT a pass: "All skills passed" would be trivially true
of nothing. This harness exists to keep "verified" from being confused with
"not measured", so the run says NOT MEASURED explicitly and fails — with exit
3, which every checker in this plugin uses for that condition, kept distinct
from 1 so "nothing was checked" and "something was checked and failed" stop
being one signal.

## `check_evals.py` § scope

`claude plugin eval` is in early access and does not respond on the account
this plugin is developed on — neither `init` nor the runner. So the suite here
has never been executed, and the honest response to that is two things: say so
in `evals/README.md`, and check mechanically what can be checked without the
runner.

What can, and fails a build: that every directory under `evals/` is a case with
a prompt, that every case has a grader, and that the grader says something a
judge could apply. What can only be guessed at, and therefore warns: whether a
grader is a retyped copy of its prompt, and whether a prompt is built out of
the phrases its target skill advertises. What cannot be checked here at all:
whether the skills actually pass. Nothing in this file claims that.

The line is: shape fails, judgement warns. Whether a file exists, has content
and says something applicable is a fact; whether two texts are "the same claim"
is an opinion held by an uncalibrated number.

## `check_evals.py` § WARNING_PREFIX

Findings fail the build; warnings are printed and do not. Severity is carried
on the message itself, via `WARNING_PREFIX`, rather than in a second list
beside it, so severity has one home instead of two that can fall out of step,
and `check(root)` keeps returning `(exit_code, messages)`.

The comment here used to say this was "the shape its three siblings have". Two
of the four expose a `check()` at all, and one of those returns a bare list — a
count of its own family, wrong, in the file that argues counts in prose go
stale. So the shape is described and not tallied.

## `check_evals.py` § similarity thresholds

Two ways of asking "is this grader just its prompt again", both warnings,
neither a gate.

The sequence ratio was a build failure until it was measured against the thing
it claims to stop. A verbatim copy scores 1.00 and is caught; the same copy
with one sentence added drops to 0.72 on the sequence and 0.64 on the
vocabulary, which is clean past both thresholds (0.9 and 0.8). So the hard
branch stopped byte-for-byte paste and nothing else — the least likely form of
the defect — while advertising protection against the whole of it. A metric
that catches only the careless case has a place; a build gate that promises
more than it delivers does not.

Both are blunt. The vocabulary overlap compares SETS, blind to order,
frequency, negation and morphology: a grader reading exactly
`ALPHA BETA GAMMA` against a prompt asking for exactly that output scores 100%
and is perfectly legitimate.

One message rather than two, because two similarity numbers firing on one file
is one finding reported twice.

## `check_evals.py` § WORD

`!` was in the word class once, and it weakened the metric silently:
`evidence!` was a token that could never match `evidence` in its prompt, while
`evidence.` matched fine, because `.` was never in the class. The asymmetry had
no reason behind it, and its effect was that emphatic graders read as less
similar to their prompts than they are.

SAIL names survive the removal: `a!queryRecordType` becomes `a` (a stopword)
and `queryrecordtype` on both sides of the comparison, so the pair still meets.

## `check_evals.py` § empty vocabulary

A grader with no scorable vocabulary used to pass through two different doors.
`"the response should not"` is entirely stopwords — including `not`, the word
carrying the criterion — and the empty word set was skipped rather than failed.
`"!!!"` survived as a "word" that overlapped with nothing. Both die in the same
branch now: an empty vocabulary is a finding.

## `check_evals.py` § _significant

A token has to carry a letter to count: `Score 1` and `Score 0` would otherwise
contribute `1` and `0`, and a grader holding nothing but digits would read as
having said something. Punctuation is out one step earlier now that `!` has
left `WORD` — `"!!!"` yields no tokens at all — but the letter test is what
keeps a numeric grader from passing for vocabulary.

`_normalized` is the other half: the text as an ordered list of bare words,
punctuation and case gone. Ordered on purpose, because that is the half of the
check a set cannot do.

## `check_evals.py` § phrase calibration

A phrase is three words, and it has to carry two that mean something before a
match counts — "the task is" is grammar, "run the gates" is a trigger.

Three rather than a tuned number: measured against the six shipped prompts it
found one echo and no false positives, and the one it found was real. That is
thin calibration, which is exactly why this side of the check warns and never
fails.

## `check_evals.py` § NOT_A_CASE

Directories under `evals/` that are not cases are named one by one, and the
closed list is the point. "Anything without a `prompt.md` is not a case" is
exactly what let a half-written case disappear from the count: a directory
holding `graders/` and no `prompt.md` was skipped, not failed, because the
guard read it as "not a case". Alone it produced exit 3, the code a caller
skips; beside one valid case it produced exit 0 and the broken directory
vanished. So a directory under `evals/` is a case by default, and what is NOT a
case is enumerated.

`results` is where the runner writes its scores; dot- and dunder-prefixed
directories are tool artefacts (`.pytest_cache`, `__pycache__`), never authored
content.

## `check_evals.py` § trigger echo

The axis this file was not watching. It was written to catch a grader that
copies its prompt, and the same defect one layer earlier — a prompt built out
of the words a skill advertises — went unchecked:
`routing-verify-not-review` asked for "run the gates", which `appian-verify`'s
description names as one of its four trigger phrases, in a prompt of thirteen
words. A router doing nothing but substring matching scored that case, so the
case measured nothing about routing.

A prompt reads better as the situation the user is in than as the words the
skill advertises.

## `check_evals.py` § one frontmatter parser

Skill descriptions are read through `lint_skills.parse_frontmatter` rather than
a second parser written here. The frontmatter rule has one definition in this
repository and this file is not going to become its second.

## `check_evals.py` § the OK line

Similarity and phrase echoes warn, so claiming in the success line that no
grader copies its prompt would be this file asserting the half of its own
output it deliberately does not enforce.

## `check_manifest_agreement.py` § the drift

`.claude-plugin/marketplace.json` sat at 0.2.1 while `.claude-plugin/plugin.json`
said 0.2.4 — stale across three consecutive releases. Nothing broke, and that
is precisely why it survived: plugin.json wins at install time and the entry
version is silently ignored.

What does read the entry is `claude plugin tag`, probed on a throwaway
repository carrying exactly this drift. It exits 1 rather than tagging, and
says so in the plugin's own terms:

```
Version mismatch: plugin.json says "0.2.4" but marketplace.json
plugins[0].version says "0.2.1". plugin.json wins at install time, so
update the marketplace entry to "0.2.4" (or remove it) before tagging.
```

So the drift was one release away from blocking the thing it was invisible to.

## `check_manifest_agreement.py` § changelog gate

Until 0.6.0 the changelog was the one place nothing compared. CONTRIBUTING's
release procedure said "add the CHANGELOG entry" as step 2 — the only step of
the four with no check behind it, in a repository whose CHANGELOG opens by
saying it is the *only* announcement a gate that stops firing ever gets. A
release whose CHANGELOG has no entry ships behaviour nobody was told about, so
a `CHANGELOG.md` that exists must carry a `## <version>` heading for the
version the manifests declare.

## `check_manifest_agreement.py` § heading boundary

`## <version>` followed by a boundary, not merely a prefix: the entry for
0.5.10 must not satisfy a release of 0.5.1. Anchored to `## ` so a version
mentioned in a paragraph — every entry here cites earlier releases in prose —
cannot stand in for the heading a reader scans for.

## `check_manifest_agreement.py` § missing CHANGELOG

Deliberately not reported here. The shipped documents link to it
(`docs/troubleshooting.md` for one), so its absence breaks the cross-document
link check in `check_readme_claims.py`. Reporting it here too would be the
restated-check drift `ci.yml` argues against.

## `check_manifest_agreement.py` § what a pass does not promise

The same probe showed `claude plugin tag` also refuses on a dirty working tree,
which belongs to the release procedure and not to this file.

## `check_manifest_agreement.py` § not plugin validate

CI does not have the CLI, and a check that only runs where the CLI happens to
be installed is the same absent-gate problem the launcher exists to prevent.

## `check_manifest_agreement.py` § JSON_SHAPE

Python's type names are not the ones the file is written in. A reader staring
at `[...]` in a `.json` is looking at an array, and telling them it is a "list"
sends them to translate before they can act.

## `check_manifest_agreement.py` § _read_manifest

`json.load` raising means the file will not parse; a file that parses to an
array is perfectly readable and still cannot be asked for a name. That second
case used to leave as an `AttributeError` — in a step CONTRIBUTING places
immediately before `claude plugin tag`, where a traceback halts a release
without naming which of the two manifests is malformed. That is the one
question this file exists to answer, and it already answered it for the
unparseable case, so crashing on the other was an asymmetry rather than a
boundary. `_read_manifest` returns `(mapping, problem)` with exactly one of the
two `None`.

## `check_manifest_agreement.py` § both fields first

A `plugin.json` missing its version reads as `None`, an entry that also omits
one reads as `None`, and the run passes having compared two absences —
agreement about nothing. So `name` and `version` are both required up front.

A marketplace.json that is absent altogether is exit 3, not a pass: a plugin
distributed only through someone else's marketplace has nothing here to agree
with, and nothing was compared.

## `check_manifest_agreement.py` § plugins is null

A missing key means no entries, which the "declares no entry" branch reports
properly. A key present and holding `null` is a different thing — someone wrote
it and got it wrong — and `get`'s default never fires for it, so it reached the
loop as `None` and raised there. Hence the explicit type check, and the same
for entries that are not objects.

## `check_manifest_agreement.py` § no-entry message

The usual cause is a rename that landed in one manifest only, and "no entry
named X" sends the reader to open the file for something this check already
read. So the message lists the names the marketplace does declare.

---

---

## `test_documented_probe.py` § executed, not linted

A published liveness probe is run against a real `sh`, not pattern-matched.
A lint was tried first and the corpus refuses it: `${CLAUDE_PLUGIN_ROOT}`
appears legitimately in eight places across `skills/` and `agents/`, where the
surrounding text already tells the reader to resolve it by hand, and once in
`docs/troubleshooting.md` where the recipe assigns it. A rule that flags those
is a rule people learn to scroll past — the argument `ci.yml` makes against
restating checks.

Four defects fall out of executing rather than inspecting, each confirmed by
putting it back and watching the test go red:

- **A published block has to spell out the paths it expands.**
  `$CLAUDE_PLUGIN_ROOT` is substituted by Claude Code *inside* `hooks.json`
  and is empty in a reader's shell, so a block using it becomes
  `sh /hooks/run_hook.sh` and exits 127.
- **`$PWD` is not a usable `cwd`.** Under Git Bash it renders `/c/...`, an
  MSYS path the gate cannot resolve, so on Windows the probe answers
  "not configured" for every project including a governed one.
- **The payload has to be one the gate classifies as a write.** A `tool_name`
  whose server segment does not name Appian answers `allow` / `not a write
  tool`, so the `ask` case cannot be reached.
- **The launcher has to be named absolutely.** `hooks/run_hook.sh` relative
  resolves only from inside the checkout, not from where a reader stands with
  a project to ask about.

## `test_documented_probe.py` § spaces in paths

Both sides of every probe are handed a directory whose name contains a space,
on purpose. An unquoted probe splits on the first space, and a GitHub runner
checks out to `/home/runner/work/appian-harness/appian-harness` — space-free —
so the defect passes on CI forever. It surfaced on the author's checkout under
`Proyecto Claude Code Cowork`; `C:/Users/you/My Documents/…` is an ordinary
place to keep one. The test supplies what the runner cannot.

## `test_documented_probe.py` § the number that went unmeasured

466 tests passed while the broken README probe shipped, because not one of
them ran a command out of the documentation. The two-block recipe in
`docs/troubleshooting.md` promised two answers and, followed exactly, produced
neither — invisible to every reader for four releases and to 468 tests, for
the same reason: nobody ran it.

## `test_matcher_parity.py` § the real tool catalogue

The tool names are real, taken from the catalogue of the two Appian MCP
servers as a live session lists them, plus every other MCP server in that
session whose tool name carries a write verb. Measured sizes at the time of
writing: 166 Appian tools, 12 foreign-server tools, 4 case variants. The last
two defects in the matcher were both found by measuring against the real
catalogue and neither by reasoning about it.

## `test_matcher_parity.py` § the dead-verb regression

`appian_invoke_process_model` was added to the Python half alone and was dead
in production while every test passed, because the tests call `scope_gate`
directly and never touch the JSON matcher. The invariant had been stated in a
comment in `harness_hooks.py` since, and until this file nothing enforced it.

## `test_matcher_parity.py` § the failure-notice matcher was the last to narrow

The pattern is spelled out verbatim in three `hooks.json` entries and JSON has
no way to say it once. The `PostToolUseFailure` entry was a bare `mcp__.*`
until 0.2.4 — broader, not narrower, which is why nothing caught it.

## `test_matcher_parity.py` § "on both sides" once checked only one side

`test_reads_and_replays_stay_free_on_both_sides` checked `WRITE_TOOL_RE` only.
`log_write` never asked it, and recorded three expression-rule invocations as
writes of a task that was merely in flight, expiring every one of its verdicts.

## `test_end_to_end_honest_task.py` § why the walk exists

Six checks were added to the write path in one session, and any of them could
have made an ordinary build ask for permission at a step where nothing was
wrong. Unit tests check each gate in isolation, which is how a harness ends up
correct in the small and unusable in the large: each check defensible, the
sequence unlivable.

## `test_end_to_end_honest_task.py` § the citation resolves at run time

An earlier draft hard-coded a plausible-sounding reference anchor that did not
exist, and the validator refused it — the mechanism working, demonstrated by
accident. `a_real_citation()` resolves a real heading instead.

## `test_risk_proportionality.py` § why the tiers exist

The doctrine graduated by risk from the start — the calibration table in
`appian-best-practices`, the entry threshold in `appian-review` — while the
gates applied one ceremony to everything. A text fix cost four verdicts, and
the escape people take from that is to stop declaring tasks at all, which
loses the record entirely. Cheaper-but-recorded beats expensive-and-avoided.
`high` earns its fourth opinion only by asking a different question: "how does
this fail?" rather than "does this meet the contract?".

## `test_risk_proportionality.py` § a query that wrote files

`_required_closure_phases` logged from inside itself, so asking "which phases
does trivial need?" with an empty config wrote an `evidence/` directory into
whatever the current directory happened to be — including the plugin's own
checkout, the contamination CI has a step to prevent.

## `test_run_hook_launcher.py` § measured cost of the subprocess tests

On Windows: ~3.8s per starved invocation and ~8.5s with an interpreter, nearly
all of it Git Bash and Python startup rather than anything the module does.
Across the cases that is minutes. Default is to run them (a suite that skips
by default rots); the opt-out is `APPIAN_HARNESS_SKIP_SLOW=1`, which CI never
sets.

## `test_run_hook_launcher.py` § the 180s subprocess timeout

180s, not 60s. At 60s a loaded CI runner turned the Git Bash spawn plus
interpreter probe into two spurious errors in a run that passed when the
module ran alone. A timeout that fires under load measures the machine, not
the launcher.

## `test_run_hook_launcher.py` § finding `sh` on Windows

`shutil.which("sh")` is not enough: Git for Windows puts `git.exe` on PATH via
`Git\cmd` and leaves `sh.exe` in `Git\bin` and `Git\usr\bin`, neither usually
on PATH. Candidates probed: `C:\Program Files\Git\bin\sh.exe`,
`C:\Program Files\Git\usr\bin\sh.exe`, `C:\Program Files (x86)\Git\bin\sh.exe`,
`/bin/sh`. A test that gave up there would skip precisely on the platform
whose failure mode the launcher exists to survive — which is how the one
untested component stayed untested.

## `test_run_authorization.py` § why per-run replaced per-keystroke

`appian-build` carried `disable-model-invocation: true`, so every task in a
twenty-task plan needed a human keystroke to start. That put the human gate on
*starting work* — high friction, almost no value — instead of on what is
irreversible or on a judgement that failed. Removing the flag only makes sense
because something now checks that a run was actually authorized.

## `test_run_authorization.py` § the budget shapes

Three ways of writing `tasks/run.json` walked straight past the budget, each
reading as a *wider* grant than the file appears to make, and each silent
because the run keeps working:

- no `maxTasks` at all, so there is nothing to spend;
- `"tasksCompleted": null` — `.get(k, 0)` returns `None`, not `0`, so
  `isinstance(done, int)` is False and the comparison is skipped entirely;
- `"maxTasks": "5"` — the same skip from the other side.

A fourth is a Python quirk rather than a JSON one: `isinstance(True, int)` is
True, so `"maxTasks": true` reads as a budget of one unless booleans are
excluded explicitly.

## `test_logging_and_handoff_debt.py` § the three claims, found together

Found on a project where a task sat in flight for two days, and all three
survived 167 passing tests because none of them is a crash: the write log said
an expression-rule invocation was a write; the debt register said a task closed
when it had not; the staleness check said a verdict was recorded when the file
was last modified.

## `test_logging_and_handoff_debt.py` § freshness must not be mtime

Staleness measured with `os.path.getmtime` makes the file's mtime *the claim*.
Two consequences: `touch` clears an expiry without re-running anything (the
rubber stamp the gate exists to prevent), and a clone, copy or restore
rewrites every mtime, so freshness does not survive moving the project. The
verdict carries its own `recordedAt`; mtime stays as the fallback for verdicts
already on disk without one.

## `test_logging_and_handoff_debt.py` § the failure path is the louder half

`log_write` was taught to ask `_is_write_tool` before recording; the failure
path was not. The write log is a file someone reads later, while the failure
notice speaks directly into the agent's context in the same turn. It told a
session that two reads were failed writes and told it not to retry them — for
a read whose only defect was a stale table name, precisely backwards. It also
used to substitute the string "unknown tool" into a sentence asserting a write
had failed.

## `test_logging_and_handoff_debt.py` § duplicate debt entries

Ten copies of one sentence buried the only entry in the register that carried
an owner and a closing condition, which is why the debt path deduplicates.

## `test_verdict_freshness.py` § the gap a verdict closes

Nothing tied a verdict to the artifact it judged. A review comes back FAIL,
the agent fixes it — more writes — and re-runs only `phase=review`; the
pre-fix `implementation` and `qa` verdicts still satisfied the closure gate,
so the task closed on two PASSes certifying an artifact that no longer
existed. With one builder that is an occasional slip; unattended, or with
several builders, it is the normal case.

## `test_verdict_freshness.py` § why `risk` was the exempt tier

The staleness check was keyed on `CLOSURE_PHASES`, and `risk` is not a member
of that tuple — it is appended to it for high-risk tasks. So the tier that
buys a fourth opinion because a mistake there is expensive was the one tier
whose extra verdict never expired. The exemption belongs to `design` alone,
for a reason about *when* the phase runs, not about which tuple it lives in.

## `test_destructive_guard.py` § deletion used to share the update path

`delete` shared a code path with `update`, so a deletion in a shared
environment was measured only for scope and atomicity.

## `test_destructive_guard.py` § `updateRecordData` is destructive

Caught by an outside reading. The premise separating destructive from ordinary
— "an update is versioned and recoverable" — is true of design objects and
false of record data: a row has no version history, so overwriting one is
exactly as irreversible as deleting it, and just as unbounded by
`allowedObjects`. Grouping it with `updateInterface` because both are spelled
"update" was reasoning from the verb rather than from what the verb does.

## `test_destructive_guard.py` § a null config key crashed silently

A key present-but-null used to crash, and *where* it crashed was the problem.
`main()` turns a scope-gate exception into a loud `ask` and a closure-gate
exception into a `block`, but the two logging hooks emit `{}` and exit 0. So
one `"evidenceDir": null` stopped the operations log silently — and an empty
write log reads to the staleness check as "this task never wrote", quietly
making every stale verdict look fresh.

## `test_destructive_guard.py` § the test that contaminated the checkout

The first version of `test_a_null_evidence_dir_does_not_crash_the_write_log`
wrote `evidence/operations.jsonl` into the plugin's own checkout on every run:
the exact plugin/project contamination CI has a step to catch, introduced by
the test for a fix against contamination. The null falls back to the DEFAULT,
which is the *relative* path `evidence` — correct in production, a landmine in
a test whose working directory is the repository.

## `test_destructive_guard.py` § `_build_config` and the fast-loop blind spot

A typo in `_build_config` — `project__evidence_dir`, from a careless bulk
rename — survived a green fast loop and was caught only by a clean-room run
with the slow tests on, because only the launcher subprocess tests reached the
function. It now has direct coverage.

## `test_harness_hooks.py` § why any-identifier matching

The rule and the schemas that force it are in `harness_hooks.py § object keys`.
What the test adds: the resulting noise was misread in the README as evidence
of oversized tasks, so the wrong thing nearly got "fixed".

## `test_harness_hooks.py` § the deferred-debt register was a sentence

`10-quality-gates.md` said a deferral "goes into the project's deferred-debt
register with task, criterion, reason, owner and closing condition". Nothing
wrote it there, so a deferral was a permission and the register was prose.

## `test_harness_hooks.py` § one audit in four filenames

Until the gates told the validator *which* task and phase they were opening,
the document could say anything: one audit copied into four filenames
satisfied the whole four-phase guarantee.

## `test_harness_hooks.py` § `practices-QA.json` on a case-insensitive disk

`practices-QA.json` is documented as a verdict the gate reports missing. On
NTFS and APFS it was found and the task closed, so the harness behaved
differently on a laptop than in CI.

## `test_harness_hooks.py` § `Write`/`Edit` were neither gated nor logged

Every input the gates read is writable by the agent they constrain, and until
the evidence-write log existed an agent could author its own passing verdict
and leave no trace of having done it. Logging does not stop that; it makes it
visible. `tasks/run.json` joined the watched list later than the active task
file, which is why the list has to grow with the gates rather than be written
once.

## `test_harness_hooks.py` § the two directions the write matcher was wrong

Both directions, with the tool names each one let through, are in
`harness_hooks.py § verbs`. The test's own point is narrower: a matcher can be
wrong in two opposite directions at once, so a corpus has to exercise both.

## `test_check_package_integrity.py` § the case-sensitivity test is meant to disagree with its filesystem

The case-sensitivity case runs on Windows, where the filesystem itself
disagrees with the assertion, and that is the entire point: if `isfile_exact`
ever degrades to `os.path.isfile`, that test goes green in CI and red on the
author's machine, and the plugin quietly becomes author-machine-only. NTFS and
APFS resolve `Run_Hook.sh` to `run_hook.sh`; ext4 does not.

## `test_check_package_integrity.py` § symlink vs junction on Windows

`link_to()` tries `os.symlink` first and falls back to a Windows junction
(`mklink /J`): `os.symlink` needs a privilege an ordinary account does not
have, `mklink /J` needs none, and both produce the condition under test — a
name that appears in a directory listing whether or not anything is on the
other end. Falling back rather than skipping is deliberate: a test that skips
on the developer's platform and runs only in CI is the absent gate again, and
these are precisely the cases an author cannot reason about from their own
machine, which is how they survived review.

## `test_check_package_integrity.py` § measured integrity failures

Both measured on a copy of this repository, not reasoned about:

- delete `hooks/harness_hooks.py` → `check()` returns `(0, [])`. `run_hook.sh`
  execs an interpreter against that path, Python exits `can't open file`
  writing nothing to stdout, and a scope gate that emits no decision does not
  gate.
- delete `hooks/hooks.json` → `check()` returns `(0, [])`. Six hooks leave the
  package and the checker whose whole subject is hooks that never run says
  nothing.
- an argv-form hook (a list rather than a `command` string) produced no
  referent AND no warning: the recursion reached the list, every element was a
  bare `str`, and a `str` node yields nothing → `(0, [])`.
- `harness_hooks.py` imports `validate_verdict` at module level, so its
  absence is an ImportError before any subcommand runs — all six hooks down at
  once, not a degraded closure gate.

## `test_check_package_integrity.py` § `commands/` had no reader

`lint_skills` walks `skills/` and `lint_agents` walks `agents/`; nothing in
the nine CI steps had ever opened `commands/`. The readability loop selected
`.md` files, so a `commands/` holding a renamed or half-converted file
contributed nothing to check and nothing to report. `os.path.isfile` answers
False for a dangling link, and the command/agent directories were the one
exception routed around `_referent_problem` — for no reason but that they were
added last.

## `test_check_package_integrity.py` § `exists_exact` never asked the filesystem

`os.listdir` reports the name of a link whose target does not exist, so a
declared component directory pointing at nothing counted as present, raised
the tally, emitted no finding, and the checker could exit 0 over it. Found by
a reviewer.

## `test_check_readme_claims.py` § a raising checker has reported nothing

Measured: deleting `hooks/hooks.json` from a copy of this repository made
`check_readme_claims` raise `FileNotFoundError` on the `json.load` that counts
hooks, and that traceback — not a finding — was what failed the build. It also
collapses the 0/1/3 vocabulary every caller is written against into an
unhandled exception, which is none of the three.

## `test_check_readme_claims.py` § the counting claims that were prose only

The README stated its inventory in prose — how many checker modules, how many
skills, how many domain references, how many judging agents, how many eval
cases and their split. All true when written, none held by anything: adding one
more checker left CI green while the README kept the old figure. They arrived with the rule "a claim in prose
brings the check that holds it".

## `test_check_readme_claims.py` § the link that broke on the split

Splitting the README into `docs/` carried the changelog link along unchanged.
It was written to resolve from the repository root, and from inside `docs/` it
does not resolve at all. It was found by a
person reading. The word-boundary case ("standalone modules" ending in "one")
is a false-positive guard for connective prose the docs/ sections will carry.

## `test_check_readme_claims.py` § the vacuous-green guard on the document walk

The cross-document link test would pass just as happily if the walk returned
nothing at all — zero documents inspected reported as agreement. The corners
are pinned instead: a root document, a `docs/` page, a skill and an eval case
are four different depths, and `.pytest_cache` ships a `README.md` that no one
in this repository wrote.

## `test_check_manifest_agreement.py` § the drift itself

`marketplace.json` sat at 0.2.1 while `plugin.json` had moved on to 0.2.4.
`0.5.10` contains `0.5.1`, so an unanchored changelog search would let the
entry for a newer release vouch for an older one forever.

## `test_check_manifest_agreement.py` § the CHANGELOG step had no gate

CONTRIBUTING said "add the CHANGELOG entry" and nothing verified it — the only
step of the four with no gate behind it, in a repository whose changelog opens
by saying it is the only announcement a gate that stops firing ever gets.

## `test_check_manifest_agreement.py` § the two vacuous-agreement branches

Written as `if entry_version and entry_version != version`, a marketplace
entry that simply omits the field agrees with every release forever. Without
the name/version guard both sides read as `None`, `None == None`, and the run
passes having compared two absences.

## `test_exit_codes.py` § the constant that sat in six places

`assertEqual(module.EXIT_NOT_MEASURED, 3)` across every importer passes just as
happily when each one types the number out itself — which is what CI reported
for four releases while the literal sat in half a dozen places. They all
agreed, every test was green, and one of them changing its mind would have
stayed green. `lint_agents` takes the value from `lint_skills`, which
re-exports it from `exit_codes`; that two-step is the thing worth an
assertion.

## `test_exit_codes.py` § prose is not importable

`CONTRIBUTING.md` says `EXIT_NOT_MEASURED = 3` and the README twice states the
0/1/2/3 scale. The literal is spelled out once in the tests, on purpose,
because nothing else in the repository can notice the day the constant and the
sentences describing it stop agreeing.

## `test_lint_agents.py` § why the corpus, not hand-written cases

The last several defects in this file were each one more *spelling*, found by
measuring against a list and not by reasoning about a parser. The first six
were caught by successive patches to a parser; the rest were not, and are why
the rule stopped going through a parser at all. A reader who adds a spelling
adds a row.

## `test_lint_agents.py` § the spellings that got through

- `tools: [Write]` — valid YAML; splitting on commas yields the single token
  `"[Write]"`, which is not the string `"Write"`. The read-only rule satisfied
  by two square brackets.
- `Write # temporary` — YAML allows a comment after a scalar, so this is a
  grant of Write, and a reader that keeps the comment compares a token that is
  not `"Write"`. A temporary grant is exactly the one written this way and
  then left.
- a comment line inside a block sequence — an item-by-item reader stops there
  and everything below it disappears, so a bad name is not read *at all*
  rather than read wrongly.
- a duplicate key — YAML resolves to the last one, so a reader returning at
  the first match reads the declaration the loader throws away.
- `tools: Read, Grep, Glob, Skill, Bash` — passed a blacklist enumerating four
  forbidden names. Found by an independent review after three rounds of
  spelling patches, and the reason the rule is a whitelist now.

## `test_lint_agents.py` § `Bash` and the whitelist argument

`Bash` is the one that got through by name: a reviewer holding it writes any
file in the repository with a redirection, and it is not a write tool by name.
The MCP rows are the argument for a whitelist by themselves, since no two
servers spell their write tools alike. `Frobnicate` is nobody's tool and has
to be refused for the same reason as `Bash` — not because it is known to
write, but because it is not known to be safe.

## `test_lint_agents.py` § the regex that harvests nothing from an MCP name

`\b[A-Z][A-Za-z]*\b` was proposed as the tool-name harvester: built-in tool
names are capitalised, but there is no `\b[A-Z]` anywhere in
`mcp__appian-dev__createRecordType` — the capital R sits between two word
characters, so no boundary precedes it. That pattern harvests `Read` and
`Grep` from the line and reports an agent holding every Appian write tool as
clean.

## `test_lint_agents.py` § `MAX_DESCRIPTION` was restated after being imported

The first draft of the module imported `has_trigger` from `lint_skills` and
then wrote `MAX_DESCRIPTION = 1024` again. A limit raised in one file and not
the other is two linters disagreeing about one contract.

## `test_lint_agents.py` § `frontmatter_list` returned two empty answers

It returned `None` for an absent key and `[]` for an empty one, defended in a
docstring, and no caller ever told them apart.

## `test_lint_agents.py` § renaming an agent silently unprotects it

Rename the file and its `name:` together and every per-file check still passes
— name matches filename, tools are declared — while `READ_ONLY_AGENTS` now
restricts nothing, and nothing is printed, because a rule that matches no
agent has no agent to complain about.

## `test_lint_skills.py` § the negation check and sentence punctuation

The commonest real description shape states when the skill fires and then
states when it does not. Sentence punctuation only ever protected a negation
placed BEFORE the trigger; a negation in its own later sentence was still
fatal to the whole-description search. `plugin-dev:skill-development`
prescribes a third-person form that must not be rejected either.

## `test_lint_skills.py` § `SECTION_EXEMPT` ships empty

The exemption is injected by the test rather than naming a real skill: the
mechanism is what is under test, and a live entry for a skill that does not
exist would exempt whatever took that name later.

## `test_check_evals.py` § measured grader-theatre thresholds

A grader that rewards the vocabulary of the prompt scores high while the task
goes undone. Measured: the same copy with one sentence appended scores 0.72 on
the sequence ratio and 0.64 on the vocabulary overlap — clean past both
thresholds. Reported, not fatal: a gate that stops verbatim paste and nothing
else promises more than it delivers. The fuzzy overlap metric compares SETS,
so it cannot see order, frequency, negation or morphology, and it has never
been calibrated against labelled examples.

## `test_check_evals.py` § measured eval-shape failures

- a directory holding `graders/` and no prompt was read as *not a case at all*
  rather than a malformed case, so the run ended NOT MEASURED — the code a
  caller skips — with the broken directory still in the tree;
- one valid case beside it was enough to carry the run to exit 0;
- `_significant("the response should not")` is empty, and the empty set was
  skipped rather than failed. "not" is a stopword and it is the word carrying
  the criterion;
- `"!!!"` survived `_significant` as a word, overlapped with nothing, and
  passed.

## `test_check_evals.py` § the routing axis nobody was watching

The checker was built to catch a grader copied from its prompt, while a prompt
copied from the skill's own description went unchecked.
`routing-verify-not-review` asked to "run the gates" — one of the four phrases
`appian-verify` advertises — so substring matching alone scored the case and
nothing measured routing. The prompts were then rewritten to describe the
user's situation rather than the vocabulary of the skill meant to catch them.

## `test_n2_interface_tree.py` / `test_n3_process_layout.py` § the vacuous pass

A tree whose component types the checker does not judge came back `OK`, exit 0
— indistinguishable from a screen that was checked and found clean. The same
vacuous pass `lint_skills.py` fixed when it stopped claiming "All skills
passed" over zero files. N3's narrower form: a layout naming no nodes had
nothing to check and said `OK`, exit 0.

## `test_parallel_safety.py` § what a worktree cannot isolate

A worktree gives each builder its own files and its own active task file, and
two builders in two worktrees calling `createRecordType` still write to the
same Appian. Worktrees isolate the recoverable half. Transitive ordering was
originally got wrong: given T-1 ← T-2 ← T-3, nothing joins T-1 and T-3
directly, so a pairwise check on direct edges alone runs them together and
starts T-3 before T-2 has begun. A destructive task in a group of three
reported the same fact twice, and a list that repeats itself gets skimmed.

## `test_validate_verdict.py` § DEFERRED was an unconditional unlock

While the schema had no field naming *which* criterion was deferred, the
document's rule — an agent "cannot declare a criterion deferrable in order to
unblock itself" — was unenforceable by construction: `owner: "me"` and
`closingCondition: "eventually"` opened a gate. The document also used to say
an ownerless deferral "degrades to blocking"; nothing degraded it, it was
refused, and the message had to be corrected to describe what the code does.

## `test_validate_verdict.py` § `findings[]` went unvalidated

The per-gate "N/A: didn't get to it" that the three-outcomes section exists to
close survived inside `findings[]`. N/A is legal at finding level — unlike at
verdict level — but the document requires a justification about the OBJECT,
never about the process, the schedule or the time available.

## `test_validate_verdict.py` § citations escaping `references/`

`isfile_exact` fell back to comparing the basename whenever the path left its
root, so a reference resolving outside `references/` was accepted:
`../../../README.md#the-gates` validated cleanly, and so did a markdown file
the agent wrote itself with a heading it chose. On a case-insensitive
filesystem `06-SECURITY.md` resolves and on a case-sensitive one it does not,
so the same verdict passes on a laptop and fails in CI.

## `test_validate_verdict.py` § the `recordedAt` degradation

The dangerous case is not a missing `recordedAt` — verdicts written before the
field existed are on disk without one and fall back to mtime legitimately — it
is a value that *looks* like a timestamp and silently degrades to mtime, a
verdict claiming a freshness nothing enforces.
