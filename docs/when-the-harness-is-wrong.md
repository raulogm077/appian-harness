# When the harness is wrong

> Part of the [appian-harness](../README.md) documentation.

It will be, eventually. A gate will name a defect that is not there, or a
register will state something that did not happen. This section exists because
what someone does in that moment decides whether the problem stays a bug or
turns into a divergence nobody can see.

### The boundary: a project consumes this plugin, it never modifies it

**Do not edit your installed copy.** Not to unblock yourself, not "just this
once". `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` is a **copy**
made at install time, one directory per version — not a link to anything. An
edit there works, right up until the next update replaces the directory and
silently reverts it. Nothing records that the edit existed, nothing records that
your project ever depended on it, and the behaviour you were relying on vanishes
between one session and the next.

That is worse than the original defect, because a defect is at least the same
for everyone. A patched copy makes one machine behave differently from every
other machine running the same declared version — and the declared version is
the only thing anyone can compare.

The same applies to per-project forks. If a project needs this plugin to behave
differently, that is a change to the plugin, released as a version, or it is not
a change at all.

### You are not blocked, and that is on purpose

No gate here refuses. The scope gate **asks**; the closure gate blocks once and
approves on the repeat, recording the omission as debt. So a defect in this
plugin costs you a confusing message and possibly a wrong line in a register —
never your afternoon, and never a reason to reach for the cache.

That is the design constraint the boundary forces: a tool its users cannot patch
must never hard-block, and must be conservative about what it asserts. If you
ever find a gate that traps you with no way through, **that is the bug**, and it
outranks whatever you were doing when you found it.

### What to record while you wait for a fix

In your own project's evidence, never in the plugin:

- what the harness claimed,
- what you did instead, and
- **the version it happened on**.

The third is the one people skip, and it is the one that matters. Without it a
workaround outlives its cause: nobody can tell whether it is still needed, so it
stays forever.

### Which version is actually running?

The line this plugin writes at session start begins with it — `appian-harness
0.2.4: …`. That is the **loaded** version, which is not the installed one: the
component inventory is fixed when the process starts, so an update applies only
after a restart, and a plugin can be installed, enabled and validated while the
running session has never heard of it. Every check on disk can be green while
the answer to "is the fix in?" is no.

To update:

```
claude plugin marketplace update <marketplace>
claude plugin update <plugin>@<marketplace>   # qualified; the short name is not found
```

then **restart Claude Code**. The marketplace is a git clone of the published
repository, so a fix that has not been pushed cannot arrive this way.

### Reporting

<https://github.com/raulogm077/appian-harness/issues>

Include the version from the session-start line, the hook's message verbatim,
and the relevant lines of whichever register looks wrong
(`evidence/operations.jsonl`, `evidence/deferred-debt.jsonl`,
`evidence/gate-decisions.jsonl`). Those three are usually enough to locate a
hook defect without any access to your project.

