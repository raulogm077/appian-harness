# Quality gates — Definition of Done for an Appian object

> These gates **complement** the functional criteria of the project's approved requirements (its
> specification, user stories or acceptance criteria). An object is only **done**
> when it meets that functional criteria **and** the applicable gates in this document: the requirements
> demonstrate **functional** acceptance, the gates demonstrate **technical** quality. Both are needed.

## Apply the gates in proportion to the change

**"Applicable" does not mean "all, always."** A gate applies when the change can break what
that gate protects. Fixing a text literal does not need a role matrix or a performance measurement;
creating a record type that exposes compensation data does. The practical rule: **always run through
the list of gates** (it's cheap) and **thoroughly execute the ones the change could break** (that's
the expensive part). A new object that writes data or exposes information touches almost all of
them; a layout tweak, two or three.

What **never** scales down: an invalid reference, an authorization gap and a non-idempotent write
are FAIL in any change, no matter how small.

## How it's recorded

For each applicable gate, record a result:

- **PASS** — checked, with evidence (UUID, validator output, test result, screenshot).
- **FAIL** — blocks closure. Work is not marked "done" with a FAIL.
- **N/A** — the gate does not apply to this object at all: the condition it protects against isn't
  present here (e.g., a field-level security gate on an object that carries no fields with protected
  data). Requires **a concrete justification about the object** ("N/A: the object does not expose
  data") — **never** a justification about the process, the schedule or the time available. A bare
  "N/A" does not count.

A gate that **does** apply but that nobody checked is not N/A — it's `NOT MEASURED`, defined below.
Conflating the two is the exact escape hatch this document exists to close: "N/A: I didn't get to
it" is not a legitimate outcome under any name.

Leave the evidence wherever the project tracks progress (its status file, the ticket or the PR). A
FAIL or an omitted gate without justification blocks closing the work.

## Three outcomes, not two

These three outcomes cover a gate that **applies** to the object under review. `N/A`, above, is not
a fourth outcome tacked onto this list — it's the decision that a gate never came into play for this
object at all, made *before* the three outcomes below become relevant.

- **PASS** — checked, with evidence.
- **FAIL** — blocks closure.
- **NOT MEASURED** — the gate applies, and no evidence covers it — including a gate you simply didn't
  check. This is not a pass, and it is never recorded as N/A.

`NOT MEASURED` has two classes:

| Class | What it is | Effect |
|---|---|---|
| `NOT MEASURED · BLOCKING` | The harness could have measured it and did not | Blocks the task. It is a process failure, not a limitation |
| `NOT MEASURED · DEFERRED` | The criterion structurally requires a human or a capability the API does not expose | Does not block the task. **Blocks phase closure and deployment** until it has an owner and a due condition |

A deferral is not a permission, it is a named debt: it goes into the project's
deferred-debt register with task, criterion, reason, **owner and closing
condition**. A deferral **missing any of those is rejected** — the verdict does
not stand and the gate it was meant to open stays shut. It is not quietly
rewritten into `NOT MEASURED · BLOCKING`: a record that says something nobody
claimed is worse than a record that refuses an incomplete claim.

**Only these criteria may be deferred.** This list is closed and lives in the
plugin, not in the task: an agent cannot declare a criterion deferrable in
order to unblock itself. Each one has an id, and a deferral **names the id it
is invoking** — a deferral that names none, or names something not on this
list, is rejected.

- `screen-reader-testing` — screen reader testing.
- `design-guidance-warnings` — Design Guidance warnings (not exposed by the API).
- `row-and-field-level-security-with-a-real-user` — row-level and field-level security tested with a real user per role.
- `contrast-against-theme-supplied-colors` — contrast against theme-supplied colors.
- `process-model-connection-routing` — process model connection routing (waypoints are not exposed by the API).

> **These ids are a copy, and the plugin holds the original.** The list that
> decides what a gate accepts is `DEFERRABLE_CRITERIA` in
> `scripts/validate_verdict.py`; the bullets above exist so the list can be
> read in context, and a test parses them and fails if the two ever disagree.
> Adding a deferrable criterion means editing the constant — editing only this
> document changes nothing except this document.

---

## 1. Platform correctness

- ✅ The object **saves and validates without errors**. With MCP `appian-dev` available: `validateDesignObject`, and for interfaces `validateExpression` **with `isInterface: true`** (without that flag a correct interface fails with *"Could not find variable 'env!features'"*). Without MCP: save in Designer without errors and review its Design Guidance.
- ✅ Expressions, references, constants, record fields and rule inputs **exist and are of the expected type**. Known blind spot: object validation **does not see a nonexistent rule invoked inside an `a!forEach` over an empty list** — catch it by evaluating the call to that rule separately, with its parentheses.
- ❌ No **invented UUIDs, names, fields or references** remain. Identifiers come from reading the environment or the project's documentation, never from memory or from another environment.
- ✅ No broken dependencies or duplicate objects. If you **modify** an existing object, check its **dependents** first (`getObjectDependents` via MCP, or Designer's dependencies panel) and confirm they still work.

## 2. Functional behavior

Test, when applicable, these paths — not just the happy one:

- ✅ nominal path with **populated representative data** (the project's minimum dataset; if it doesn't exist, create it — it's the only way for the test to mean anything);
- ✅ **empty set** and **null values** (use an identifier that deliberately does not exist);
- ✅ invalid input and boundary values;
- ✅ dependency/integration error;
- ✅ **repeated** operation (detect duplicates / lack of idempotency).

> The key blind spot: the body of an `a!forEach` over an empty list **is not evaluated**, so a broken screen or rule **passes all its test cases with empty tables**. The case with real data **is not optional**.

Test data: representative, controlled, **no personal data or production secrets**.

> **Test case quality, not just its existence:** each case tests **only your logic** (not the platform), with **one per expected result**, no trivial *"tests 1=1"* and **no embedded queries or dates** (use controlled inputs, not `now()`/`today()` or a live query). Transactional rules are not tested. A fragile or tautological case does not count as coverage.
> Source: [Expression Rule Testing — general guidance](https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html#general-guidance)

## 3. Security (by role, data and action)

If the change exposes objects, data or actions, define/update a **matrix**:

| Role/group | Visible objects | Accessible data | Allowed actions | Expected result |
|---|---|---|---|---|

- ✅ Permissions to **groups**, least privilege; review the **Application Security Summary**.
- ✅ Check separately: object security · **row-level** (record-level) and **field-level** security · **action** authorization · access to processes/tasks/reports/integrations · **site/navigation** security.
- ❌ **Hiding a button or component in SAIL authorizes nothing.** Authorization lives in the layer that executes the action/query.
- ✅ Test **at least one authorized role and one NOT authorized** (and a partial one if the model covers it). Row/field security **does not apply in Appian Designer**: test it by logging in with a real user for each role.
- ⚠️ Field with **field-level security**: arrives **null** in the interface / **is not returned** in a query / filtering or sorting by it errors out / **sync-time** custom fields **skip it**. Do not put user filters on a protected field. And watch out when testing it: if the column is empty, the null you see is the data's, not the security's — it's a **false positive**.

Detail: doc **06-security**.

## 4. SAIL interfaces (full gate)

Every new or modified interface passes, **in order**:

1. **Syntax validation** — `validateExpression` with `isInterface: true` (or save in Designer without errors).
2. **Static analysis**, if the environment offers SAIL validators (agents, linters or plugins covering schema/parameters, icon keys and structural review). These are a separate layer from environment validation and apply **in addition**, not instead. If no validators are available, manually review what they cover: existing functions and parameters, valid icon keys, correct enumerations.
3. Fix **every blocking finding** and re-validate what you touched.
4. **Render** (`testInterface` or open the interface).
5. **Two** interface test cases: one with **null data / nonexistent identifier** and another with **populated real data**. The second is not optional — see the `a!forEach` blind spot in gate 2.

> **Why two layers of validation:** the environment's validation checks that the expression evaluates;
> static analysis catches what evaluating doesn't uncover — an invalid icon key, a nonexistent `color`
> in rich text or a misspelled enumeration can pass validation and break (or render wrong) at runtime.

And a **manual review** (syntax validation does not replace it):

- ✅ **loading, empty, error and success** states with a useful message and next step;
- ✅ visual hierarchy, spacing, density and legibility; consistency with the rest of the app;
- ✅ accessible labels/instructions/validations; **contrast** and **not relying on color alone** (WCAG 2.2 AA);
- ✅ behavior at the **screen sizes** the requirements demand;
- ✅ **confirmation** on destructive/irreversible actions;
- ❌ no UUIDs, indexes or technical text visible to the user.

> **Accessibility is TESTED, not just reviewed.** For critical screens, verify it as its own activity
> with **screen reader + keyboard navigation** (focus, reading order, error messages, zoom/reflow), not
> just by checking the SAIL. Source: [DevOps with Appian — accessibility testing](https://docs.appian.com/suite/help/latest/devops-with-appian.html) · [Building accessible applications](https://docs.appian.com/suite/help/latest/building_accessible_applications.html)

> Design Guidance is a gate, not an aesthetic recommendation, and its two types of alert **do not** get treated the same: **warnings (yellow triangle) CANNOT be dismissed** and must **always be resolved** (they flag patterns that cause errors or unexpected behavior at runtime); only **recommendations (lightbulb) allow *dismiss***, and dismissing one is a conscious decision that gets justified. Never close an interface with open warnings.
> Source: [Design guidance — warnings vs. recommendations](https://docs.appian.com/suite/help/latest/appian-recommendations.html#warnings-vs-recommendations)

Detail: docs **02-interfaces-sail**, **04-expression-rules**, **05-performance**.

## 5. Performance

- ✅ Queries request **only the fields needed**; every potentially large collection is **paginated or bounded** (remember the 5,000-row cap for records-powered).
- ❌ No query **inside a loop** (N+1); no expensive expression/query repeated — cache it in a local variable.
- ✅ Refresh and SAIL re-evaluations **justified** (expensive work in `a!localVariables`, not in parameters).
- ✅ Don't invent a performance threshold: use the agreed requirement or record a **baseline measurement** (Performance Details / Health Check). Document sync, volume and concurrency risks if relevant.

Detail: doc **05-performance**.

## 6. Maintainability

- ✅ **Naming** conforms to the current convention: the project's if it's documented, or the one existing objects already follow; failing that, the official standard (Standard Object Names, doc 08).
- ✅ **Typed** rule inputs with clear names; each rule, **one responsibility**.
- ❌ No duplicated business logic or embedded environment values (use constants; complex logic → Decision object).
- ✅ Comments that explain **non-obvious decisions**, not that repeat the code. Errors turned into controlled results/messages.

Detail: docs **04-expression-rules**, **08-alm-testing-naming**.

## 7. Operations and deployment

- ✅ Dependencies and per-environment configuration **identified**; the package contains the expected objects and **no accidental changes**.
- ✅ **Inspect the package before deploying (Inspect Deployment).** Review **security warnings**, **failing test cases** and **missing precedents**. Distinguish: warnings alert but let you continue; **deployment errors block** the deployment (references to deleted objects or invalid record fields). Don't deploy with deployment errors.
  Source: [Inspect deployment packages](https://docs.appian.com/suite/help/latest/inspect-deployment-packages.html) · [Deploy to target environments — inspect the package](https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html#inspect-the-package)
- ✅ **Compare the package against the target (Compare Deployment Packages)** before deploying: which objects **exist, change or conflict** in the target (including test values), so you don't overwrite someone else's changes or introduce silent regressions in a shared environment.
  Source: [Prepare the Deployment — Comparing across environments](https://docs.appian.com/suite/help/latest/prepare-deployment.html#comparing-across-environments) · [Prepare deployment packages](https://docs.appian.com/suite/help/latest/prepare-deployment-packages.html)
- ✅ **Full regression before a major deployment:** run **all** the application's expression-rule/interface test cases (Start Rule Tests → Applications/All) and confirm they pass. A major deployment does not close with red test cases.
  Source: [Automated Testing for Expression Rules](https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html) · [Expression Rule Testing](https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html)
- ✅ **Watch coverage, not just the result:** use **Manage Test Cases** to find rules **without** a test and prioritize the reused/critical ones; for critical business flows, consider **UI automation** (FitNesse/Cucumber or the Appian Selenium API) in addition to rule/interface test cases.
  Source: [Expression Rule Testing — test case management](https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html#test-case-management) · [Testing Applications — UI testing](https://docs.appian.com/suite/help/latest/testing-applications.html#user-interface-ui-testing)
- ✅ Processes and integrations with **exception handling** matched to their impact; defined **which operations are safe to retry** (idempotency).
- ✅ If a build is left **partial**, document **what was created** and **how to resume it without duplicating** objects.

> **Health Check as a cadenced gate, not just a one-off measurement:** run it **at least once per sprint** and review its **four areas** (Infrastructure, Configuration, Design, UX), not only when chasing a specific performance number.
> Source: [Continuous improvements to your application](https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html) · [Health Check](https://docs.appian.com/suite/help/latest/health-check.html)

> **Operational readiness (doc 11).** Before considering the object or delivery closed, also apply the **operational readiness gate** from doc **11-reliability-operations**: monitoring and **tested alerts** (not just configured), a recovery **runbook**, a rehearsed **rollback/roll-forward** plan and **sign-off from the operational owner** (not just the functional one). This layer complements these seven gates and also gates closure.

Detail: docs **03-processes**, **07-integrations**, **08-alm-testing-naming**, **11-reliability-operations**.

---

## Quick gates by object type

Specific minimums, in addition to the 7 cross-cutting gates:

- **Record type / data model:** keys, relationships and cardinality defined; tested with an existing record, a nonexistent one and an empty relationship; record-level security, sync, volume and refresh reviewed; no duplication without a documented reason.
- **Expression rule:** typed inputs; nominal/null/empty/invalid/boundary cases; no repeated or looped queries; stable output contract documented for its use; test cases saved.
- **Process model:** success/exception/cancellation/retry paths where applicable; reusable logic **outside** the process; start/tasks/escalation security; a re-run **does not** duplicate effects.
- **Integration:** credentials only in the connected system; timeout, remote error, empty and invalid response handled; no secrets/sensitive payloads in user-facing messages; normalized input/output contract for its consumers.
- **Site / navigation:** visibility and access by role; consistent navigation with no unreachable pages; initial state and empty-data routes tested; no display name with a long-running query.

---

## Hierarchy when requirements conflict

When two requirements clash, this is the order (a higher layer is not overridden by a lower one):

1. **Security, privacy and platform validity** (an invalid reference or a security gap is never justified by a functional requirement).
2. **The project's approved requirements and acceptance criteria** (if its specification has several versions or annexes, the **most recent** prevails per its version control).
3. **Recorded architecture decisions** and the project's established conventions.
4. **Best practices** (these docs).
5. **Implementation preferences.**

If a requirement clashes with level 1, **don't silently reinterpret it**: document the conflict and ask for a decision.

> **Project conventions vs. best practices (levels 3 and 4).** A reasonable local convention
> —prefixes, folder organization, constant patterns, interface structure— **overrides
> the generic preference of these docs**: consistency within an app matters more than
> canonical style. Before creating objects, look at how existing ones are named and organized and follow
> that pattern. That said, if the local convention clashes with **level 1** (e.g. a pattern that leaves
> a sensitive field unprotected), flag it instead of perpetuating it.
