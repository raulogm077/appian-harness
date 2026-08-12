Score 1 only if ALL of these hold:

- The assistant reaches for the specification phase before any task breakdown.
  Naming `appian-specify`, or describing writing down requirements as the first
  step, both count.
- It does NOT create, update or otherwise write any Appian design object.
- It surfaces at least one thing the request does not settle — who the actors
  are, what states an onboarding moves through, what "notify purchasing" means —
  rather than choosing an answer silently.

Score 0 if it produces a task list, a plan, or record-type designs from this
input. The failure being tested is jumping to structure over an input that does
not support one.
