---
name: appian-best-practices
description: Official Appian best practices and quality gates for design, implementation, review and debugging. Use when creating, changing, reviewing or debugging record types, data models, relationships, sync, custom fields, SAIL interfaces, expression rules, process models, integrations, sites, security, performance or test cases — through an MCP server or in Appian Designer. Use before calling any write operation against an Appian environment, and before declaring an object finished.
---

# Appian development best practices

Official Appian doctrine anchored to `docs.appian.com/.../latest/`, plus the **quality gates** that
separate "the object exists" from "the object is professional." It is tool-agnostic: it applies the same
way through an MCP server as it does in Appian Designer.

## Overview

**This skill supplies the HOW (how to work well in Appian). The project supplies the WHAT** (which app is
being built, which objects exist, which conventions it uses, which requirements it has). Do not mix the
two planes: if you need a fact about the project, discover it (see Discovering Project Context below); do
not assume it or invent it.

## When to Use

The most expensive mistake in a quality guide is applying it in full to everything. Calibrate:

| The change… | Procedure |
|---|---|
| Is cosmetic or local and touches no data, permissions or queries (text, spacing, a label) | Cardinal Rules (see below) + the correctness gate. Do not open the reference docs. |
| Creates or modifies an object without exposing new data or changing authorization | Open **the doc for its domain** + the applicable gates (`references/10-quality-gates.md`). |
| Creates or modifies objects that **write data, expose information, change permissions, or query at volume** | The domain docs + **10** + **11** (reliability) and the full verification. |
| Is architecture design, a new data model, or integration with an external system | Add the high-risk documentary validation (see Tools below). |

When in doubt between two rows, go up one. What is **never** graded down: an invalid reference, an
authorization gap, and a non-idempotent write are blocking in any change.

**Do not launch subagents by default.** A normal Appian task is done inline. Delegate only when there is
genuinely parallel, independent work (e.g. several static validators over the same file, or reviewing
unrelated modules). If you delegate write work, the subagent needs its own instructions: it does not
inherit what you have loaded.

## Routing by Domain

Paths relative to this skill. **Open only what the change touches**; do not load the whole set.

| You are going to touch… | Read |
|---|---|
| Tables, record types, relationships, sync, custom fields, CDTs, documents | `references/01-data-model-records.md` |
| Interfaces, SAIL, forms, grids, charts, layouts, on-screen queries | `references/02-interfaces-sail.md` |
| Process models, subprocesses, tasks, exceptions, MNI, email, activity chaining | `references/03-processes.md` |
| Expression rules, logic, null-safety, `a!match`/`a!forEach`, Decision, constants | `references/04-expression-rules.md` |
| Anything with a performance impact (queries, grids, processes, limits) | `references/05-performance.md` |
| Groups, object security, record/field-level security, service accounts, portals | `references/06-security.md` |
| Connected systems, integrations, web APIs, external calls | `references/07-integrations.md` |
| Naming, app structure, packages/deployment, testing, methodology | `references/08-alm-testing-naming.md` |
| Sites, pages, navigation, branding | `references/09-sites-navigation.md` |
| **Definition of Done: quality gates for any object** | `references/10-quality-gates.md` |
| **Reliability: concurrency, idempotency, retries, observability, rollback** | `references/11-reliability-operations.md` |

A typical change touches 1–3. **10** applies to anything declared finished; **11**, to anything that
writes data, calls an external system, or reaches production.

## Discovering Project Context

These rules are generic; the project governs its own territory. Before creating or modifying anything,
find out **only what the task needs**, in this order, stopping as soon as you have an answer:

1. **What is already in context** (what the user has told you, files already read). Do not re-query it.
2. **Project instructions and documentation**, if they exist: `CLAUDE.md`/`AGENTS.md`, README,
   specification, architecture decisions, functional docs. Do not assume they exist or that they are
   named that.
3. **The real objects**, when the implementation matters more than the documentation (see Tools below).

What you almost always need to know before creating an object: **the naming convention** and **where it
fits** (app, folder, prefix). If it is not documented, infer it from existing objects of the same type.
A reasonable local convention **overrides the generic preference of these docs** — consistency within an
app is worth more than canonical style. If it conflicts with security or platform validity, say so
instead of perpetuating it.

❌ **Do not explore the entire application "for context."** Modifying an interface does not justify
inventorying every record type, process and integration. Widen the context when a real dependency shows
up, not before.

## Tools

Check what is available in the session; do not invent tools or assume they exist.

**Design MCP (e.g. `appian-dev` or equivalent) — "how is this actually implemented?"**
Inspect and modify real objects, dependencies, validate against the environment. Ask for **the specific
objects** you need; do not list the whole application to find one. Do not repeat a call whose response you
already have. Before modifying an existing object, check its **dependents**.
If there is no MCP, the work is the same, describing the changes for Designer instead: the rules and the
gates do not depend on the tool.

**Documentation MCP (e.g. `appian-docs` or equivalent) — "how does Appian work?"**
Syntax, functions, parameters, components, limits, version-specific behaviour. It is the source of truth
for a concrete doubt, **not a mandatory step for every task**.

Before consulting it, the operative question is: **"is there a concrete doubt whose answer would change
what I am about to write?"** If not, do not consult it. If there is, make the **minimal** query ("does
this component accept this property?", not "everything about SAIL") and stop as soon as you can decide.
Proportionality: known capability → do not consult; doubtful parameter or unusual function → one query;
architecture, security, performance, integration or platform-limit decision → verify.

If there is no documentation MCP, consult `docs.appian.com/suite/help/latest/…` by whatever means you
have; if there is none at all, **say explicitly what you were not able to verify** instead of asserting it
from memory.

⚠️ **Do not invent Appian.** `a!` functions, parameters, components, properties, smart services and
capabilities: either you know them with certainty, or you verify them. The typical failure is carrying
syntax from other languages or frameworks into SAIL as if the platform had it.

**Version:** the environment can lag behind `latest` (Appian Cloud upgrades are monthly and opt-in). If
something depends on the version, confirm it against the environment's version, not only against
`latest`.

## Cardinal Rules

The ones that almost never have an exception. For a small, low-risk change these may be enough; as soon
as the change creates, writes or exposes something, also open the doc for its domain, which carries the
detail and the source.

- **Query with `a!queryRecordType`, asking only for the fields you use.** Never inside a loop; page any
  potentially large collection; do not repeat the same query — cache it.
- **One record type = one business entity.** Model relationships instead of duplicating; any
  denormalization needs a documented reason.
- **Reuse.** One rule per responsibility, typed rule inputs, keyword arguments. Complex business logic →
  a Decision object, not a giant `a!match`.
- **An expression has no side effects**, and no guaranteed order or number of evaluations. Writing data is
  the job of smart services.
- **Always null-safe.** Null, empty list and "does not exist" are different states; an empty list keeps
  its type and **`a!forEach` does not evaluate its body** — which is why *testing with empty tables is
  not testing*: a broken screen passes every one of its test cases.
- **Short, decoupled processes.** Logic that does not persist belongs in a rule or record action, not in
  a process. **Activity chaining is not a transaction.**
- **Security by role, data and action.** Permissions to groups, least privilege. **Hiding UI does not
  authorize**: authorization lives in the layer that executes. Test one authorized role and one NOT
  authorized role; row/field-level security **does not apply in Designer**, so test it with a real user
  of each role.
- **Credentials live in the connected system**, never in the integration; handle timeouts and errors; no
  integration inside an interface loop.
- **Idempotency** on every write that could be retried, and **optimistic locking** for concurrent editing.
  **Versioning ≠ rollback.**
- **Name by the current convention and deploy with packages** (Dev→Test→Prod, paired by UUID); never edit
  Production by hand.
- **Measure before optimizing** (Health Check / Performance Details). Design Guidance *warnings* are
  always resolved; *recommendations* can be dismissed, but consciously.

## Before Calling It Finished

An object is not done because it exists and saves. Run it through the applicable gates in
`references/10-quality-gates.md` (platform correctness · behaviour with data, empty values, nulls and
errors · security by role · complete interface · performance · maintainability · deployment), and through
the operational-readiness gate in **11** if it reaches production.

Meeting the requirements demonstrates **functional** acceptance; the gates demonstrate **technical**
quality. Both are needed, and a FAIL blocks closing. If something is left unverified, **say so** — do not
wave it through in silence.

## When Doctrine and Official Documentation Conflict

These docs are stable, but Appian publishes every month. If the official documentation contradicts what a
`references/` doc says:

1. **The official documentation wins** (for the environment's version). Do not apply the stale rule
   blindly.
2. **Flag the discrepancy**, citing both statements with their source.
3. **Propose the change, do not make it:** updating the doc is the user's decision; do not rewrite the
   doctrine mid-development.

The limits table is audited against the official source: do not change its numbers on intuition, only
with documentation that contradicts them.

---

*Sources: each doc in `references/` cites its own (`docs.appian.com/suite/help/latest/…`, release notes,
the Appian Playbook, Appian Community). Links use the `/latest/` alias, which redirects to the current
release and never expires.*

## Common Rationalizations

| The thought | Why it is wrong |
|---|---|
| "It validates, so it is finished" | Validation proves the platform accepts it, not that it is correct or well designed. |
| "The tables are empty but the screen works" | The body of `a!forEach` over an empty list is never evaluated. A broken screen passes every test case against empty data. |
| "The test case is green" | A test that never exercises the path proves nothing. A search box is tested by typing something. |
| "The field came back null, so the restriction works" | A null does not travel in the response. Absence is indistinguishable from a restriction that was never applied. Put a real value in before you look. |
| "I only hid the button" | Hiding UI does not authorize anything. Authorization lives in the layer that executes the action. |
| "The API returned 200" | Some surfaces silently downgrade an unrecognized value and still answer 200. Read back what was actually stored. |
| "This query only returns a few rows today" | Current volume does not remove the obligation to page or bound. |
| "The validator reported an error, so I must fix it" | Run it first. A rule with no inputs that queries data reports an error and works perfectly; adding a fake input to satisfy the validator pollutes its signature. |

## Red Flags

- A query inside a loop, or the same query repeated instead of cached.
- A reference to a rule or constant that was never verified to exist. `rule!Name` alone validates clean; only `rule!Name(param: null)`, with parentheses, proves it exists.
- A gate marked PASS whose evidence does not cover the gate's criterion.
- A destructive action whose confirmation sits on a component that ignores it.
- A screen whose only path to its data is a chart.
- A title rendered as styled rich text instead of a heading component.
- A grid without a label or a row header.
- Business validation drawn as a card with the submit button silently disabled.
- A colour used as the sole carrier of meaning.
- A write that is not idempotent, or a retry issued before checking whether the first attempt persisted.
- A skill, hook or gate whose exemption can be edited by whoever it constrains.

## Verification

Before calling the work finished, confirm each of these and record the outcome:

- [ ] Every applicable gate in `references/10-quality-gates.md` has PASS, FAIL, or NOT MEASURED with its class.
- [ ] Every PASS names the evidence that produced it.
- [ ] Every NOT MEASURED · DEFERRED has an owner and a closing condition, and its criterion is on the closed deferral list.
- [ ] Behaviour was exercised with populated data, not only with empty tables.
- [ ] If the change touches data, permissions or actions, one authorized and one unauthorized role were both tested.
- [ ] Nothing was changed outside the agreed scope; anything noticed and left alone is stated explicitly.
