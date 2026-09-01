# Contributing

## What you need

Python 3.9 or newer, `git`, and on Windows a Git Bash — the hooks are launched
through `sh`, and Git for Windows is the only thing that provides it here.

Nothing else. The test suite runs on `unittest` from the standard library and
every checker is stdlib-only, on purpose: a check that needs a package installed
is a check that does not run on a user's machine, which is the same absent-gate
problem the launcher exists to prevent.

**Python 3.9 is the floor, not 3.13.** The hooks run under whatever interpreter
the launcher finds on the machine, which is rarely the newest. So no `match`, no
`X | Y` in annotations, no `str.removeprefix`, no `dict | dict`. CI runs 3.9 and
3.13 on Ubuntu and Windows, and the Windows half is not ceremony: `isfile_exact`
exists because NTFS and APFS are case-insensitive and ext4 is not, so a verdict
named `practices-QA.json` closes a task on a laptop and blocks it in CI.

## Checking your work locally

All nine, before you push. They are what CI runs, in the order CI runs them:

```bash
python -m unittest discover -s hooks -v
python -m unittest discover -s scripts -v
python scripts/lint_skills.py
python scripts/lint_agents.py
python scripts/check_readme_claims.py
python scripts/check_manifest_agreement.py
python scripts/check_package_integrity.py
python scripts/check_evals.py
python -c "import os, sys; leaked = [p for p in (os.path.join('.claude', 'appian-harness.json'), 'evidence', 'tasks') if os.path.exists(p)]; sys.exit('harness project state leaked into the plugin: %s' % leaked) if leaked else print('plugin/project separation intact')"
```

The ninth has no script of its own — in `ci.yml` it is a `shell: python` block,
transcribed here so you can run the same check rather than discover it in CI. It
is the one that catches what *testing in a real session* leaves behind, which is
why running it locally matters more than its size suggests. See the next section.

On a POSIX machine where `python` is absent or is a Python 2, use `python3` —
the launcher makes the same substitution at runtime.

The six checker scripts do not share one calling convention, and the list above
hides that because every line runs them on this repository: the four newer
checkers take the root **positionally** (`check_evals.py ../elsewhere`), while
`check_readme_claims.py` takes `--root <path>` and exits **2** on a usage error.
Worth knowing the first time you point one at a directory that is not this one.

**Exit 3 is not a pass.** The checkers use `EXIT_NOT_MEASURED = 3` for "nothing
was inspected": zero skills linted, no marketplace entry to compare, no eval
case found. A checker that inspects nothing and prints nothing red has not
approved your change, and treating 3 as green is the exact failure this plugin
spends a README arguing against. 0 passes, 1 fails, 3 means go and find out why
there was nothing to look at.

## What a change has to bring with it

- **A new checker brings its test file**, next to it in `scripts/`, named
  `test_<module>.py`. `unittest discover` picks it up from there.
- **A claim in prose brings the check that holds it.** `check_readme_claims.py`
  exists because counts in the README drifted three times in one working
  session, and a reader caught it every time while a check caught it never.
- **A rule written twice is a rule that will diverge.** `lint_agents.py` imports
  `has_trigger` from `lint_skills.py` rather than restating it, and a test
  asserts they are the same object. `test_matcher_parity.py` holds the same line
  between the matcher in `hooks.json` and the one in `harness_hooks.py`.
- **No project state of its own.** `evidence/`, `tasks/` and
  `.claude/appian-harness.json` must never appear in this repository — a CI step
  fails the build if they do. The plugin is a layer the project consumes; a
  harness governing itself has lost the separation that makes its records worth
  reading.

## Comments, design notes and commit messages

**Comments are minimal.** A comment says, in the present tense, why the line it
sits on is the way it is — one or two lines. A comment that restates the code is
not written, and neither is one that narrates how the code got here: no "it used
to be", no dates, no account of who found what.

**The history goes somewhere, just not into the source.** Three homes, and each
answers a different question:

| file | question it answers |
|---|---|
| `docs/design-notes.md` | why is this line the way it is, and what was measured? |
| `CHANGELOG.md` | what changes for a project that upgrades this release? |
| `docs/troubleshooting.md` | what does a user do when this misbehaves? |

Nothing is deleted, it moves. When a line needs more context than two comment
lines can carry, the paragraph goes to `docs/design-notes.md` and the comment
cites it:

```python
# Case-exact on purpose: docs/design-notes.md § validate_verdict.py · case
```

Module docstrings are eight lines at most: what the module does, its usage line,
its exit codes. Function docstrings are three at most, and only where the name
and signature do not already say it.

Read `run_hook.sh` or `scripts/exit_codes.py` for the register.

Commit messages are `type(scope): lowercase phrase saying what changes`, with a
body that states the defect and the evidence. In English, like the rest of the
history.

## Testing a change in a real session

The plugin cannot be tested only by importing it. Install the working tree as
its own marketplace:

```
/plugin marketplace add "C:\path\to\appian-harness"
/plugin install appian-harness@appian-harness
```

then **restart Claude Code**. Two things bite here, both documented in the
README's *Troubleshooting*: a directory source copies the working tree as it
stands, including files `.gitignore` excludes; and the loaded version is not the
installed one, because the component inventory is fixed when the process starts.
The session-start line reports the version actually running — check it before
concluding a fix did not work.

**Drive the test session from a scratch project, not from this checkout.** The
gates only activate where `.claude/appian-harness.json` exists, so exercising
them means creating one — and `appian-init` writes it along with `evidence/` and
`tasks/`. Do that inside this repository and you have just produced the three
paths the ninth check fails on, by following these instructions. It is the
plugin governing itself, which is exactly the separation the check defends. If
you did test in place, delete `.claude/appian-harness.json`, `evidence/` and
`tasks/` before you push.

## Releasing

```bash
# 1. bump BOTH manifests to the new version
#    .claude-plugin/plugin.json and .claude-plugin/marketplace.json
# 2. add the CHANGELOG entry
# 3. align the documentation with what the release changes
# 4. verify manifests and changelog agree before tagging
python scripts/check_manifest_agreement.py
# 5. tag (validates both manifests itself, and refuses if they disagree)
claude plugin tag --dry-run
claude plugin tag --push
```

Step 1 says **both** because the marketplace entry sat three releases behind
`plugin.json` without anything noticing: nothing at install time reads it, so
the drift was invisible right up to the point where it would have blocked a
release. Step 4 is that becoming a command you can run.

Step 2 is enforced, not requested: since `0.6.0`,
`check_manifest_agreement.py` fails when `CHANGELOG.md` has no `## <version>`
entry for the version the manifests declare — it was the one step of these
with no check behind it, in a repository whose changelog opens by saying it is
the only announcement a gate that stops firing ever gets.

Step 3 is the part a check cannot do for you, so here is what it means
concretely: read the release's diff asking **which sentences in `README.md`
and `docs/` it makes false**, and fix those in the same release. The
mechanical edges are held for you — `check_readme_claims.py` pins every count
and cross-document link, and `hooks/test_documented_probe.py` executes the
commands the documentation publishes — but neither can notice that a paragraph
still describes last release's behaviour in prose. Every documented command
that changed gets run once before it ships; six of the six that had never been
run turned out to be broken (`0.5.1`–`0.5.3`), which is the entire argument.

Two refusals, both observed against a throwaway repository rather than inferred
from the documentation.

**Disagreeing manifests.** The versions below are that probe's, not this
release's. With `plugin.json` at 0.2.4 and the marketplace entry at 0.2.1,
`claude plugin tag` exits 1 and prints:

```
✘ Version mismatch: plugin.json says "0.2.4" but .claude-plugin\marketplace.json plugins[0].version says "0.2.1". plugin.json wins at install time, so update the marketplace entry to "0.2.4" (or remove it) before tagging.
```

That is why step 4 sits before step 5 and not after: it is the same check, run
where the CLI is not — on your machine before you reach for the tag, and in CI,
which has no `claude` binary at all.

**A dirty working tree.** `claude plugin tag` also exits 1 when the repository
is not clean, and the version message is gone from that failure — two untracked
scratch files were enough to make an agreeing pair of manifests look like the
mismatch case failing anyway. Commit or stash first.

With the manifests agreeing and the tree clean, `--dry-run` exits 0 and prints
the exact `git tag -a <name>--v<version>` and `git push origin refs/tags/...` it
would run, which makes it a real rehearsal rather than a formality.

So: `--dry-run` first, always. **`--push` is externally visible and hard to
retract**: it creates and pushes a tag, and anyone whose marketplace clone
updates after that gets what you pushed. A tag can be deleted, but not
un-fetched. Read the two commands `--dry-run` prints, and only then push.

## Issues and pull requests

Bug reports go through the form at
<https://github.com/raulogm077/appian-harness/issues/new/choose>. It asks for
the plugin version, your OS, the Python the launcher finds and the hook's output
because those four locate most hook defects without any access to your project.

Questions about using the plugin belong in Discussions, not issues. Security
reports go to the address in [SECURITY.md](SECURITY.md) and never to a public
issue.

Pull requests: one change per branch, the nine commands above green, and a
description that says what was broken rather than what was added.
