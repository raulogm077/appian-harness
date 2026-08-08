---
name: appian-specify
description: Turns a vague Appian request into a written specification before any object is created. Use when starting a new Appian application, module or feature, or when the requirements exist only as conversation, email or meeting notes. Use before planning or building anything.
---

## Overview

This skill is the **SPECIFY** phase of the lifecycle `SPECIFY → PLAN → BUILD → VERIFY → REVIEW → CLOSE`.
Its job is to turn "build me a thing that does X" into a written specification, before a single
record type, interface, or process model exists. The output is consumed by the `appian-plan` skill,
which breaks it into buildable, dependency-ordered tasks — so the specification is not a formality,
it is the contract the rest of the lifecycle is built against.

Appian's design tools make it fast to start creating objects straight from a rough idea: a record type
in a few clicks, a form a few minutes after that. That speed is exactly why specification has to happen
first and on paper. A record type built around the wrong entity boundary, a relationship whose
cardinality was assumed rather than confirmed, or a field's sensitivity discovered only after it has
already been exposed in three listings — these are not typos to fix later. They are data-model and
security decisions that get more expensive the more objects are built on top of them. Catching them in
a conversation costs a question. Catching them after BUILD costs a rebuild.

The artifact this skill produces has six sections, in this order: **Actors**, **Entities and
relationships**, **States and transitions**, **Authorization matrix**, **Volume and growth**, **Out of
scope**. This is a fixed contract — `appian-plan` reads these section names, so all six must be present
even when an answer is "none" or "not applicable," and that answer should be written down rather than
the section omitted. Where the specification should be saved (a file, a ticket, a section of an
existing document) is a decision for the project this skill is running in, not something this skill
assumes.

## When to Use

- Starting a new Appian application, module, or feature and no written specification exists yet.
- The requirements exist only as conversation, a chat thread, an email, or meeting notes — nothing
  that names entities, states, or who is allowed to do what.
- Before running `appian-plan` or creating any design object. If a specification already exists and
  covers the six sections, re-run only the sections a new request actually changes rather than
  starting over.
- Not needed for a small, well-understood change to an object that is already fully specified (for
  example, adding one more value to an existing dropdown). It **is** needed the moment a change
  introduces a new entity, a new actor, a new state, or touches a field that was not previously
  classified as sensitive or not — those are exactly the changes that quietly outgrow the existing
  specification.

## Procedure: One Question at a Time

Ask one question, get an answer, then ask the next. Do not hand over all six sections as a form to
fill in at once. Interview style surfaces gaps as they appear — an answer about relationships often
reveals an actor nobody had mentioned yet — where a form just gets filled in with whatever was already
in the requester's head, gaps included.

For each question below, say why it matters *in Appian specifically*, not only what information is
wanted. The person answering usually has a business answer ready; they do not usually know which of
their answers determines a data-model decision until it is pointed out.

### 1. Actors

Ask who acts on the system, one at a time: "Besides the people you've already named, is there anyone
who only reads this data? Anyone outside your organization who touches it? Anyone who acts on it
automatically, without a person involved?" Distinguish internal users (who belong to an Appian group)
from external ones (who would reach the system through a portal or a public-facing interface) — the
distinction changes which security and navigation model applies from the start, not as an afterthought.

### 2. Entities and Relationships

For every noun that comes up, ask: **"Is this its own business entity, or is it an attribute of
something you've already named?"** In Appian, one record type is meant to model one entity. Getting
this wrong is not a naming problem — it is a data-model problem, and it is usually discovered only
once interfaces and processes already assume the wrong shape.

For each entity confirmed, also ask **what uniquely identifies one record of it** — an entity with no
clear key is not actually specified yet, whatever it is called.

Then ask about **relationships, in both directions and with cardinality**: "Can one expense report
have more than one expense line? Can one expense line belong to more than one report?" Ask it both
ways, even when one direction seems obvious — the obvious direction is rarely the one that turns out
to be wrong.

For every attribute of every entity, ask: **"Is this field sensitive — would you want it hidden from
some of the actors you named in section 1?"** This question cannot wait: which fields are sensitive
determines record-level and field-level security, and that security in turn constrains which fields
can appear in a listing, be filtered on, or be sorted by, for each role — it shapes the data model and
the screens, it is not a policy layer applied on top of a finished design (field experience: field-level
security restrictions are also not evaluated while browsing data inside Appian Designer, so a "does
this look right" check from the design environment will not catch a missing restriction — it has to be
verified by signing in as a user who actually holds each restricted role).

### 3. States and Transitions

For every entity that has a lifecycle, ask: **"What counts as a distinct state here, and for each
state, which other states can it move to — and who or what makes that transition happen?"** Push for
transitions explicitly; a state that is only ever entered and never exited is either a dead end or a
transition nobody has named yet. A "status" that is really just a combination of other flags is not a
state of its own — ask what actually changes about what the entity can do when it enters it.

### 4. Volume and Growth

Ask, per entity: "About how many of these exist today, and how many would you expect a year from now?
Is this queried interactively by users, pulled into reports, or read by other systems?" This is not a
tuning question to revisit once something feels slow — expected volume and query pattern decide
whether a record type should be sync-enabled against Appian's own data store or left query-time
against its source, and that choice is made when the record type is modeled, not adjusted afterward
without rebuilding it.
Source: [Choose a Data Source](https://docs.appian.com/suite/help/latest/configure-record-data-source.html) · [Use synced record types (best practice)](https://docs.appian.com/suite/help/latest/build-best-data-fabric.html#use-synced-record-types)

### 5. Authorization Matrix

Build the matrix directly from the previous answers: every actor from section 1, crossed with every
entity (and, for sensitive fields, every field) from section 2, crossed with every action relevant to
its states from section 3 — create, read, update, delete, and each named transition. For every cell,
get an explicit answer, including the negative ones: "Can this role see this field at all? If not,
does it need to know the field exists but not its value, or not know the field exists at all?" A blank
cell is not a "no," it is an unanswered question.

### 6. Out of Scope

The specification is not complete without an explicit **Out of scope** section.
Half of all misalignment is silent disagreement about what is *not* being built.

Ask directly: "What might someone reasonably assume is included here that actually isn't?" A generic
"nothing else" is not an answer — push for the specific adjacent things a reasonable person might
assume are in scope (a related report, a notification, an integration, a second language) and record
each one that was considered and excluded, not just the ones nobody thought of.

### Output Template

```markdown
## Actors
## Entities and relationships
## States and transitions
## Authorization matrix
## Volume and growth
## Out of scope
```

## Common Rationalizations

| Thought | Why it's wrong |
|---|---|
| "We can define security later, once the screens exist." | Field-level and record-level security decide which fields a listing may even display, filter, or sort by for a given role. Deciding it after the screens are built means rebuilding the screens, not configuring a layer on top of them. |
| "The volume is small, we don't need to think about this yet." | Sync-enabled versus query-time is a modeling decision made when the record type is created. Changing it later is not a settings toggle — it is rebuilding the record type and everything that queries it. Source: [Choose a Data Source](https://docs.appian.com/suite/help/latest/configure-record-data-source.html) · [Use synced record types (best practice)](https://docs.appian.com/suite/help/latest/build-best-data-fabric.html#use-synced-record-types) |
| "It's obviously one entity, we don't need to ask." | "Obviously one entity" is exactly the assumption that turns out wrong once two attributes need independent histories, independent security, or independent volume — by then it's a migration, not a rename. |
| "The actors are just 'the user' and 'the manager,' that's clear enough." | Real systems almost always have more distinct actors than the first two named — a read-only auditor, an approver who isn't the line manager, an external party, a scheduled process acting without a human. Each one changes the authorization matrix. |
| "We'll figure out the states as we build." | A state discovered mid-build forces rework on every interface's available actions and every process model branch that already assumed a smaller set of states. |
| "Out of scope is implied — we only talked about what we want." | Silence is not a scope decision anyone can point back to. Without a written exclusion, "we assumed X was included" and "we assumed X wasn't" are both consistent with the same conversation. |

## Red Flags

- An entity with no field that uniquely identifies one of its records.
- A state with no transitions in, no transitions out, or neither — likely a dead end or an
  unrecorded transition.
- A sensitive field with no named owner for who may see or edit it.
- A relationship stated in only one direction ("an order has line items") with no cardinality
  confirmed in the other direction (can a line item belong to more than one order?).
- Two actors described with identical permissions in every row of the authorization matrix — often a
  sign they are really one actor, or that a real distinction between them hasn't been asked about yet.
- A specification with no `Out of scope` section, or one that only says "nothing else" without
  naming what was considered and excluded.

## Verification

Before handing the specification to `appian-plan`, confirm:

- [ ] **Actors** — every distinct role is listed, including read-only, external, and automated actors,
      not just the two or three named first.
- [ ] **Entities and relationships** — every entity has an unambiguous key; every relationship states
      its cardinality in both directions; every attribute has been asked about for sensitivity.
- [ ] **States and transitions** — every state has at least one documented transition in or is
      explicitly marked as an initial state; every state has at least one documented transition out or
      is explicitly marked as terminal.
- [ ] **Authorization matrix** — complete: every actor × every entity (and every sensitive field) ×
      every relevant action, with explicit "not permitted" answers recorded, not left blank.
- [ ] **Volume and growth** — current and expected volume recorded per entity, with the sync versus
      query-time consequence written down rather than left implicit.
- [ ] **Out of scope** — present, and specific enough that someone who disagreed with an exclusion
      could point to the exact line and say so.
- [ ] Every field flagged sensitive has a named owner for its access rules.
- [ ] The six sections exist as one handed-off document, not scattered across separate notes.
