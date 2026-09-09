# Render signals — what travels instead of the tree

**Cited, not reinvented.** The signals below are the checks the official Appian skill already
specifies in `references/change-review.md § Runtime Verification`. This file says **where they are
measured and what shape they travel in**; it does not restate the rules, and if the two ever
disagree, the official reference wins.

---

## Why signals and not the tree

The evaluated tree of a medium screen is **218 KB (≈ 62 K tokens)**, and there are **942 KB ones
(≈ 268 K)**. A `Read` of one returns 2.000 lines of 15.896 — **12,6 %** — so an agent told to "judge
the rendered tree" sees an eighth of it and emits a truncated verdict that looks complete.

So the tree is **measured, never read**. What travels is the trio:

| What | Size | Produced by |
|---|---|---|
| Normalized hashes of the render pair | ~130 B | `scripts/n2_interface_tree.py` (the only place normalization is defined) |
| N2 output over both renders | ~500 B | `scripts/n2_interface_tree.py` |
| The derived signals below | ~400 B | the same script, `--record` |

Anyone who needs a fragment opens it with `offset`/`limit` and **declares in the verdict which
fragment they opened**. A verdict claiming to have judged a tree of more than 2.000 lines without
declaring that is `NOT MEASURED`, not `PASS`.

---

## The signals, and their source

Every row below is `change-review.md § Interface Checks`, in the order that reference lists them.

| Signal | The official check it is | Where it is measured |
|---|---|---|
| `error` | *"`diagnostics.error` must be null — any value means a runtime rendering failure"* | `render_record()`; a non-null error credits nothing |
| `timedOut`, `truncated` | The same rule's siblings: a render that did not finish is not a render | `render_record()` |
| `valueNodes` | *"Filtered grids must return fewer rows than total record count"* and *"Grid column data must contain strings or proper component objects"*, generalised to the one number that decides them: how many nodes carry non-empty `value` / `values` / `data` | `render_record()` |
| `findings` / `checks` | *"No `-1` values in rendered text"*, *"Alert/count cards must show non-negative integers"*, plus the accessibility checks — all of them properties of nodes, so all of them N2's | `check_tree()` |
| `categories` | Which kinds of node were present at all. A category with zero nodes did not get checked, and saying so is the difference between a clean run and an unchecked one | `category_census()` |
| `normalizedHash` | Not in the official reference: it is what makes the two guarantees of the harness's § 8.5 assertable at all | `normalized_hash()` |

## Normalization, in one place

Appian returns a fresh `_cId` per node (230 in the measured case), re-encrypts every `saveInto`
handler with a new nonce, and varies `diagnostics.durationMs`. **Two renders of an untouched screen
already have different bytes**, so comparing raw renders is a test that cannot fail.

Normalization is defined **once**, in `scripts/n2_interface_tree.py`, and it may **never** null
`value`, `text` or `values` — those are exactly what the populated/empty inequality is counted over,
so a normalization that touched them would make the guarantee vacuous.

## What the pair buys

Two guarantees and a corollary. Counting three is the mistake this section exists to prevent.

1. **Guarantee.** Two renders of the same state with the same inputs ⇒ the **same** normalized hash.
   Without this, nothing built on the hash proves anything.
2. **Corollary.** Populated and empty ⇒ **different** normalized hashes. It follows from (3), and is
   kept as a cheap sanity assertion.
3. **Guarantee.** The populated render carries **strictly more** nodes with non-empty
   `value`/`values`/`data` than the empty one. It is this inequality, not the hash, that rules out an
   `a!forEach` that never iterated.

The hook asserts all three off `checks.jsonl` rows it stamped itself, so none of them depends on a
file the constructor wrote.

## The empty path

The empty render is reached **by the mechanism that screen has** — a non-existent identifier on a
detail screen, out-of-range inputs on a dashboard — and **which mechanism was used is recorded**, as
the inputs digest of the row.

A clean empty render is **not** "I could not measure": it is a well-made empty state. It is
legitimate for an empty tree to carry no recognised signature **provided** the populated half of the
same pair did measure, and the empty one carries an empty-state message or a non-empty text node.
Without that rule the floor would penalise good design — the better the empty state, the more likely
the escalation.

---

*Sources: `change-review.md § Runtime Verification` and `§ Interface Checks` of the official Appian
skill (github.com/appian/dev-mcp-skills). Sizes and percentages: the measurement campaign recorded in
`docs/design/appian-harness-0.7-1.0.md § 8.5`.*
