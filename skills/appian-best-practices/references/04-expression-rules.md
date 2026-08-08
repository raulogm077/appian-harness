# Best Practices — Expression Rules and SAIL Logic

> Official Appian doctrine for writing SAIL logic: reusable, single-responsibility expression rules, functional patterns (`a!localVariables`, `a!match`, looping), null-safety, separating query from presentation, expression performance, testing with test cases, and constant governance. Each rule is anchored to `docs.appian.com/.../latest/...`.

Links use the `latest` alias, which Appian redirects to the most recently published release (the no-pinning-versions rule). The behaviors cited were verified against the 25.4 / 26.3 / 26.6 pages, which are identical to one another.

---

## 1. Rule design: reusability and single responsibility

**⚠️ An expression rule has NO side effects and does not mutate data: it only computes and returns a value.** None of the functions Appian ships have side effects (a side effect is any change to the system beyond the returned value). To write or modify data, use **smart services** — in a process, or in a component's `saveInto` — **never** a standalone expression or a rule. Also, neither the **order** nor the **number of evaluations** of the parts of an expression is guaranteed: a part can be evaluated multiple times, never, or in parallel.
*Why:* the engine optimizes, parallelizes and retries evaluations (e.g. after a transient error, or when re-evaluating an interface on each interaction); any logic that assumes a fixed order or that "something runs exactly once" is non-deterministic and breaks intermittently.
*Anti-pattern:* expecting `a!save()` or a smart service to "run" when invoked inside an expression rule.
Source: [Functions and Side Effects](https://docs.appian.com/suite/help/latest/functions-side-effects.html)

**✅ Extract any logic that appears in more than one place into an expression rule.**
An expression rule is a stored expression with a name, description and definition, reusable from any expression field. Changing the rule propagates the change to all its consumers.
*Why:* eliminates duplication, centralizes maintenance and makes the app more consistent.
*Anti-pattern:* copying the same formula (e.g. "most recent event") into three different interfaces.
Source: [Expressions Best Practices — Save expression as expression rules](https://docs.appian.com/suite/help/latest/expressions-best-practices.html)

**✅ One rule, one responsibility.** Design small, composable rules (one computes, another queries, another formats) instead of a monolithic rule that does everything.
*Why:* small rules are easy to test, read and reuse; a monolithic one gets copied whole when only a piece was needed. This granularity is what enables automatic parallelism (§7) and reusable rules that wrap components.
Source: [Reusing Interfaces — Reusability / Creating reusable custom components](https://docs.appian.com/suite/help/latest/using_interfaces_in_appian.html#reusability)

**✅ Name the rule inputs of a reusable component `value` and `saveInto`.** When wrapping a component (e.g. a `dollarField`), the input that maps to `saveInto` must be an array of type *Save*, and by convention the inputs are called `value` and `saveInto`.
*Why:* lets other developers use `a!save()` on your component just as they would on a native one.
Source: [Reusing Interfaces — Creating reusable custom components](https://docs.appian.com/suite/help/latest/using_interfaces_in_appian.html#reusability)

**❌ Don't leave unused rule inputs or local variables.** The designer flags "Unused rule input" and "Unused local variable" as recommendations: dead inputs complicate maintenance, and dead variables can run unnecessary queries.
Source: [Appian Design Guidance — Expression design guidance](https://docs.appian.com/suite/help/latest/appian-recommendations.html#expression-design-guidance)

---

## 2. Rule inputs: typing and passing by keyword

**✅ Type each rule input with the specific type it expects** (don't leave everything as *Any Type* unless you need deliberate indirection). Each input has Name, Description, Type and an Array flag.
*Why:* the type documents the contract, enables early validation and improves generated test cases.
Source: [Expression Rules — Properties (Rule Inputs)](https://docs.appian.com/suite/help/latest/Expression_Rules.html)

**✅ Fill in the Description of every rule input and of the rule itself.** The test case Copilot and other developers use the name, description, commented definition and input descriptions to understand intent.
*Why:* rich descriptions improve the quality of auto-generated test cases and maintainability.
Source: [Expression Rule Testing — Generate test cases with AI (Tips)](https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html)

**✅ Always pass arguments by keyword** (`myRule(input: value)`), not by position, whenever the rule or constructor has more than one input.
*Why:* protects against compatibility breaks if inputs are added, reordered, renamed or removed in the future. The designer flags this as "Missing keyword syntax".
*Anti-pattern:* `myRule(a, b, c)` — breaks silently if a new input is inserted tomorrow.
Source: [Appian Design Guidance — Missing keyword syntax](https://docs.appian.com/suite/help/latest/appian-recommendations.html#expression-design-guidance)

**❌ Don't use `Array` when the value is single, or vice versa.** The input's Array flag must reflect the real cardinality; name it in the plural if it's a list (solution convention).
Source: [Expression Rules — Properties](https://docs.appian.com/suite/help/latest/Expression_Rules.html) · plural convention in [Connected Underwriting — Naming conventions (Variables and Rule Inputs)](https://docs.appian.com/suite/help/latest/cu/connected-underwriting-architecture-overview.html) *(verify: the CU solution doc mandates the plural; the general standard doesn't explicitly require it)*

---

## 3. Naming, documentation and organization

**✅ Follow Appian's standard object naming:**
- **Expression rule / Decision:** application prefix + Pascal case, no spaces or special characters, unique across the environment. E.g. `HRO_ComputeBaseSalary`, `HRO_GetEmployeeOnboardingTasksStatus`.
- **Constant:** application prefix + ALL UPPERCASE, no spaces. Optionally a type prefix for grouping. E.g. `HRO_IMG_CAREER_HISTORY_ICON`.
Source: [Standard Object Names — Rule objects](https://docs.appian.com/suite/help/latest/Standard_Object_Names.html#rule-objects)

**✅ Organize rules into folders (rule folders) with a standard name per purpose.** Application prefix + title case with spaces; use standard names across apps for folders that serve the same purpose (`HRO Expression Rules`, `HRO Constants`, `HRO Interfaces`). A rule folder's name must be unique across the environment.
*Why:* a predictable folder structure speeds up finding and governing objects.
Source: [Standard Object Names — Content-management objects (Folder)](https://docs.appian.com/suite/help/latest/Standard_Object_Names.html#content-management-objects)

**✅ Comment non-obvious logic with `/* ... */`.** Everything between `/*` and `*/` is ignored during evaluation.
*Why:* comments explain intent to other developers and feed the test case Copilot.
Source: [Parts of an Expression — Comments](https://docs.appian.com/suite/help/latest/parts-of-an-expression.html#comments)

**✅ Use the *Format expression* button and the editor's indentation guides** to keep SAIL readable before saving.
Source: [Expression Editor — Toolbar actions](https://docs.appian.com/suite/help/latest/expression-editor.html#toolbar-actions)

**❌ Don't use reserved names** from process report metrics for rules (`Completion`, `Lag`, `Work`, `process_status`, `task_status`, etc.).
Source: [Expression Rules — Reserved names](https://docs.appian.com/suite/help/latest/Expression_Rules.html)

**❌ Don't use unsupported/undocumented functions.** The designer flags "Unsupported function detected": their behavior can change or break in an upgrade.
Source: [Appian Design Guidance — Unsupported function detected](https://docs.appian.com/suite/help/latest/appian-recommendations.html#expression-design-guidance)

---

## 4. Functional patterns: local variables, match, if/choose

**✅ Use `a!localVariables()` to declare local variables; it's the replacement for `load()` and `with()`.** It does everything they did, adds refresh behaviors, and by default updates only when its dependencies change (not on every evaluation), and supports `saveInto`.
*Why:* simplifies the design and improves performance compared to `with()` (which recalculates on every interaction) and `load()` (which forces you to duplicate the update logic).
*Anti-pattern:* continuing to write `load()`/`with()` in new objects.
Source: [Updating Expressions to Use a!localVariables](https://docs.appian.com/suite/help/latest/Updating_Expressions_to_Use_a_localVariables.html) · [a!localVariables() Function](https://docs.appian.com/suite/help/latest/fnc_evaluation_a_localvariables.html)

**✅ Use `a!match()` to evaluate a value against several conditions** instead of nesting `if()` inside `if()`. It supports `equals`/`then` pairs (literal value) and `whenTrue`/`then` pairs (boolean expression, with `fv!value`), plus a mandatory `default`. The keywords are mandatory.
*Why:* flattens the decision tree; `a!match()` short-circuits evaluation as soon as it finds the first match and skips the rest (including `default`).
*Anti-pattern:* `if(x=1, a, if(x=2, b, if(x=3, c, d)))` — use `a!match(value: x, equals: 1, then: a, ...)`.
Source: [a!match() Function — Usage considerations (Configuring / Evaluation order)](https://docs.appian.com/suite/help/latest/fnc_logical_match.html#usage-considerations)

**✅ Reserve `if()` for a single condition and `choose()` for selecting by index.** `if` evaluates only the matching branch; `choose` evaluates only the value whose index matches.
Source: [Interface Performance — Conditional logic](https://docs.appian.com/suite/help/latest/interface-performance.html#conditional-logic)

**✅ Avoid excessive nesting.** Official doctrine sets thresholds: avoid nesting looping functions more than 2 levels deep.
Source: [Expressions Best Practices — Designing memory-efficient expressions (Limit looping iterations)](https://docs.appian.com/suite/help/latest/expressions-best-practices.html#designing-memory-efficient-expressions)

**✅ Use the Decision object (decision table) for business logic with many conditions.** When the logic is a matrix of rules (several inputs → one output) that's best **managed, read and tested as a table** and reused from any expression, interface or process, model it as a **Decision** object and call it with `rule!` just like a rule. Prefer it over nested `a!match`/`if` when the number of conditions or combinations grows, or when the people maintaining the rules are business users: the table is more readable and auditable.
*Why:* it separates the complex, shared business rule (Decision) from simple or presentation logic inside an expression (`a!match`/`if`/`choose`, §4). A 15-branch `a!match` is more fragile to maintain than an equivalent decision table.
Source: [Decisions](https://docs.appian.com/suite/help/latest/Decisions.html) · [Design Objects — Decision](https://docs.appian.com/suite/help/latest/design-objects.html#rule-objects)

---

## 5. Null-safety: nulls and empty lists

**✅ Use `a!defaultValue(value, default[, default2, ...])` to supply a default value for null or empty.** `null`, `""` and `{}` all count as null/empty; it returns the first non-null default. (Careful: a list of nulls `{null, null}` or of empty strings `{"", ""}` is **not** considered empty.)
*Why:* prevents errors when rendering dropdowns, choiceLabels, etc. when a related piece of data is missing.
Source: [a!defaultValue Function](https://docs.appian.com/suite/help/latest/fnc_informational_a_defaultvalue.html)

**✅ Check presence with `a!isNullOrEmpty()` / `a!isNotNullOrEmpty()`** instead of long combinations of `if()`+`isnull()`. Returns `true` if it's null, an empty string, or an empty list.
Source: [a!isNullOrEmpty() Function](https://docs.appian.com/suite/help/latest/fnc_informational_isnullorempty.html)

**✅ Filter nulls in queries with `applyWhen` and in arrays with `reject(a!isNullOrEmpty, ...)`.** `applyWhen: a!isNotNullOrEmpty(ri!id)` avoids applying a filter when the input is empty, making the query predictable.
Source: [How to Handle Null Values — Common scenarios](https://docs.appian.com/suite/help/latest/null-handling.html#common-scenarios)

**✅ Remember that `a!forEach()` over `null` or an empty list returns an empty list and does NOT evaluate the expression.** This is useful for null-safety, but it also means **the body of an `a!forEach` over an empty list never runs**: a broken rule can pass its tests if you only test it with empty lists (see §8).
Source: [a!forEach() Function — Using the items parameter](https://docs.appian.com/suite/help/latest/fnc_looping_a_foreach.html#usage-considerations)

**❌ Don't trust that data exists.** Design assuming missing data: you can't transform a null string, iterate a null list, or render a link with a null address. Test casts with nulls in particular (make sure they don't end up as the string `"null"`).
Source: [How to Handle Null Values in Appian — Why are nulls an issue / Casting](https://docs.appian.com/suite/help/latest/null-handling.html)

---

## 6. Separating query from presentation

**✅ Separate query logic from presentation logic.** You can query record type data to render interfaces, drive logic in rules, or route processes; extract queries into dedicated query rules (`QR`/`QE` convention) and keep interfaces focused on presenting.
Source: [Record Type Query Performance Best Practices](https://docs.appian.com/suite/help/latest/query-best-practices.html) · query prefix convention in [Connected Underwriting — Naming conventions (Querying)](https://docs.appian.com/suite/help/latest/cu/connected-underwriting-architecture-overview.html) *(verify: the QR/QE prefix is CU solution doctrine, not part of the general naming standard)*

**✅ Query in the parent interface/rule and pass the result to the child via a rule input.** Query into a `local!` at the top and pass it with `data: ri!...` to the child rule.
*Why:* besides ordering responsibilities, this is **mandatory** for offline: an offline sync only downloads the parent interface's data; querying inside the child errors out in Appian Mobile.
Source: [Offline Mobile Design Best Practices — Query data for child interfaces at the top of the parent](https://docs.appian.com/suite/help/latest/offline-mobile-design-best-practices.html)

**✅ Request only the fields you need** in the `fields` parameter of `a!queryRecordType()`; avoid `a!selectionFields()` unless you truly need every field.
*Why:* the more data you request, the longer it takes to load; pulling every field (and relationship fields) drives up load time.
*Anti-pattern:* `a!selectionFields(allFieldsFromRecordType: ...)` with `batchSize: 5000` to show 5 cards.
Source: [Query Performance Best Practices — Specify individual fields](https://docs.appian.com/suite/help/latest/query-best-practices.html) · [Query Recipes — only specify the data you need](https://docs.appian.com/suite/help/latest/Query_Recipes.html)

**✅ For generic, data-driven rules, use indirect evaluation** (`=ri!inputName()` with an *Any Type* input that receives a function/rule/partial function). Useful for reusable rules that configure a grid from a parameterizable data source.
Source: [Advanced Expression Evaluation — Indirectly evaluating arguments](https://docs.appian.com/suite/help/latest/expression-advanced-evaluation.html#indirectly-evaluating-arguments)

---

## 7. Expression performance

**✅ Cache expensive computations and queries in a local variable; don't repeat them.** Instead of `if(isnull(rule!slowQuery()), "def", rule!slowQuery())` (which runs the query twice), store it once in `local!data` and reference it.
Source: [SAIL Performance — Local Variables](https://docs.appian.com/suite/help/latest/SAIL_Performance.html#local-variables)

**✅ Put expensive computations in local variables, not in component parameters.** Every user interaction re-evaluates all component parameters; a local variable, by default, is only evaluated on load, when it's given a `saveInto`, or when a variable it depends on changes.
Source: [Interface Performance — Put expensive computations in local variables](https://docs.appian.com/suite/help/latest/interface-performance.html#local-variable-best-practices)

**✅ Let independent queries evaluate in parallel.** Appian automatically parallelizes queries that don't depend on each other: items in a list, parameters, independent local variable definitions, loop iterations. If a local variable references another, they get serialized; rewrite them so they don't reference each other.
*Why:* several queries at once take less time than in series; the bottleneck becomes the slowest one.
Source: [Parallel Evaluation of Expressions](https://docs.appian.com/suite/help/latest/expressions-parallel-evaluation.html) · [Interface Performance — evaluate in parallel](https://docs.appian.com/suite/help/latest/interface-performance.html#local-variable-best-practices)

**✅ In `and()`, `or()` and `a!match()`, put expensive computations last.** They cut off evaluation as soon as `and` finds a `false`, `or` finds a `true`, or `match` finds a match; whatever comes after is not evaluated and adds no time.
Source: [Interface Performance — put expensive computations last](https://docs.appian.com/suite/help/latest/interface-performance.html#when-using-and-or-and-match-functions-put-expensive-computations-last)

**✅ Paginate and filter queries; never use `batchSize: -1` without control.** Unbounded queries return an unpredictable amount of data (more in production than in development) and fill up `local!` memory.
Source: [Expressions Best Practices — Page and filter query results](https://docs.appian.com/suite/help/latest/expressions-best-practices.html#designing-memory-efficient-expressions)

**✅ Limit looping: avoid iterating over more than ~500 items and don't nest loops more than 2 levels deep.** Each iteration accumulates its result in memory; nested loops don't free memory until the parent finishes. Check first whether you actually need a loop (functions like `text()` or `if()` already operate over arrays).
Source: [Expressions Best Practices — Limit looping iterations](https://docs.appian.com/suite/help/latest/expressions-best-practices.html#designing-memory-efficient-expressions)

**✅ Choose the right looping function.** `a!forEach()` to transform each item; `all()`/`any()`/`none()` to reduce to a boolean; `filter()`/`reject()`/`merge()` to filter; `reduce()` when each operation uses the result of the previous one. `all/any/none/filter/reject` have short-circuit logic and can be more efficient than `a!forEach` on large lists. Use `a!forEach()` instead of the deprecated `apply()`.
Source: [Looping Recipes — For loop](https://docs.appian.com/suite/help/latest/looping.html#for-loop)

**✅ Avoid rule recursion: a rule that calls itself should not exceed a total depth of 20.** Past that threshold it degrades performance and the user experience; the risk is greater if the recursive rule has complex inputs or expressions or returns lists or CDTs. Replace recursion with a looping function (`reduce()` when each step uses the result of the previous one, `a!forEach()` to transform; official doctrine cites `apply()`/`reduce()`).
Source: [Understanding the Health Check Report — Recursive rule depth limit](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#recursive-rule-depth-limit)

**⚠️ `refreshAlways`/`with()` recalculate on every evaluation.** Use it only when the data changes fast and the user must see it updated; otherwise, leave the default refresh so it caches between evaluations.
Source: [SAIL Performance — Local Variables](https://docs.appian.com/suite/help/latest/SAIL_Performance.html#local-variables)

---

## 8. Testing expression rules

**✅ Save test cases with every rule; don't leave them as disposable, ad-hoc checks.** Test cases serve as living documentation, TDD (write them before the rule), use cases, edge cases and **regression** (run in bulk to catch unintended changes).
Source: [Expression Rule Testing with Appian — What can test cases be used for](https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html)

**✅ Choose the right assertion:**
- "passes if it evaluates without errors" (the default, most common),
- "passes if the output matches an expected output" (exact match of value and type, case-sensitive),
- "passes if an expression evaluates to true" (uses `test!output` and the `ri!` domain; e.g. `exact(index(test!output, "status", {}), "IN PROGRESS")`).
Source: [Expression Rules — Test cases (Create a test case)](https://docs.appian.com/suite/help/latest/Expression_Rules.html#test-cases)

**✅ Explicitly cover edge cases and real data, not just the happy path.** Write cases for unusual inputs that could break the rule, and test with populated data: since `a!forEach` doesn't evaluate its body on empty lists (§5), a broken rule can pass all its cases if you only test it empty. The test case Copilot is designed to surface edge cases (nulls, extreme values), but it doesn't know your domain: review and refine what it generates.
Source: [Expression Rule Testing — Edge Cases / Use Cases](https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html) · [a!forEach() Function — Using the items parameter](https://docs.appian.com/suite/help/latest/fnc_looping_a_foreach.html#usage-considerations)

**✅ Run test cases in bulk for regression** after editing rules that other objects depend on, to catch unintended impacts.
Source: [Automated Testing for Expression Rules](https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html)

---

## 9. Constants vs. hardcoded values

**✅ Extract any repeated literal into a constant** (days until a deadline, a code, a document id, a brand color) instead of writing it in multiple places.
*Why:* a single point of change; the same argument as for expression rules.
*Anti-pattern:* typing `30` (days) or a HEX value in five interfaces.
Source: [Expressions Best Practices — Save literal values as constants](https://docs.appian.com/suite/help/latest/expressions-best-practices.html)

**✅ Govern constants by name and type.** Application prefix + UPPERCASE; use a type prefix for grouping (`_IMG_`, `_TXT_`, `_REF_CODE_`, ...). Create them directly from the Expression Editor with *Create Constant*.
Source: [Standard Object Names — Constant](https://docs.appian.com/suite/help/latest/Standard_Object_Names.html#rule-objects) · [Expression Editor — Create constant](https://docs.appian.com/suite/help/latest/expression-editor.html#toolbar-actions)

**✅ Values that change per environment: mark the constant as *Environment Specific*.** For a value that differs between DEV/TEST/PROD (an endpoint, a service account, an external id), create a **constant** and enable the **Environment Specific** checkbox: from then on, its value **is not overwritten on import**. The per-environment value is set in an **import customization file** during deployment. Import rules: if the constant **does not yet exist** at the destination, the import customization file is **mandatory** for it to import; if it **already exists** and no file is supplied, the constant imports but **keeps its current value** (the rest of the attributes are updated). It can only be enabled on constants of **primitive type** or **Email Address**.
*Why:* a single object for the whole app while each environment keeps its own value, without editing it by hand after every deployment.
*Anti-pattern:* duplicating the constant once per environment, or typing the PROD endpoint directly into the SAIL.
Source: [Constant Object — Environment Specific](https://docs.appian.com/suite/help/latest/Constants.html) · [Application Deployment Guidelines — Environment specific constants](https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html#rules) · [Managing Import Customization Files](https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html)

---

## 10. Hygiene and validation before considering a rule done

**✅ Pay attention to the Expression Editor's real-time Design Guidance.** The editor flags recommendations (lightbulb) and warnings: missing keyword syntax, unsupported function, unused rule input / local variable, size limit in the styled text editor. Resolve them or dismiss them consciously.
Source: [Expression Editor — Design guidance](https://docs.appian.com/suite/help/latest/expression-editor.html#design-guidance) · [Appian Design Guidance — Expression design guidance](https://docs.appian.com/suite/help/latest/appian-recommendations.html#expression-design-guidance)

**✅ Remember the evaluation permissions context.** An expression is evaluated with the initiator's rights (or the designer's/owner's, in a process); if the user lacks access to a resource the expression requests, evaluation stops with an exception. Keep this in mind when testing sensitive logic with different roles.
Source: [Expressions Best Practices — Permissions used during evaluation](https://docs.appian.com/suite/help/latest/expressions-best-practices.html)

**⚠️ Not every function can be invoked in a process model expression.** Some functions only do something in their own context: `a!save()` **has no effect** outside a component's `saveInto`; **smart services** only execute in interfaces (and certain Web APIs), not in an expression on a process node or gateway, nor in a standalone rule — invoking their function there just returns its configuration, without executing it; and **Custom Field functions** only work inside calculated fields (real-time). Before putting a function into a process expression, check its **compatibility table** (Process Reports / Process Events, etc.): it might do nothing or throw an error.
Source: [Functions and Side Effects — Smart services](https://docs.appian.com/suite/help/latest/functions-side-effects.html) · [a!save() Function](https://docs.appian.com/suite/help/latest/fnc_evaluation_save.html)

---

## Sources

- Expressions Best Practices — https://docs.appian.com/suite/help/latest/expressions-best-practices.html
- Functions and Side Effects (no side effects, evaluation order/count, smart services in expressions) — https://docs.appian.com/suite/help/latest/functions-side-effects.html
- Understanding the Health Check Report (Recursive rule depth limit ≤20) — https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#recursive-rule-depth-limit
- Constant Object (Environment Specific: primitives and Email only) — https://docs.appian.com/suite/help/latest/Constants.html
- Application Deployment Guidelines (Environment specific constants) — https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html#rules
- Managing Import Customization Files — https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html
- a!save() Function — https://docs.appian.com/suite/help/latest/fnc_evaluation_save.html
- Appian Design Guidance (Expression design guidance) — https://docs.appian.com/suite/help/latest/appian-recommendations.html#expression-design-guidance
- Expression Rules (properties, test cases, reserved names) — https://docs.appian.com/suite/help/latest/Expression_Rules.html
- Expression Rule Testing with Appian — https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html
- Automated Testing for Expression Rules — https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html
- Standard Object Names (Rule objects / Content-management objects) — https://docs.appian.com/suite/help/latest/Standard_Object_Names.html
- Updating Expressions to Use a!localVariables — https://docs.appian.com/suite/help/latest/Updating_Expressions_to_Use_a_localVariables.html
- a!localVariables() Function — https://docs.appian.com/suite/help/latest/fnc_evaluation_a_localvariables.html
- a!match() Function — https://docs.appian.com/suite/help/latest/fnc_logical_match.html
- Decisions (Decision object / decision tables) — https://docs.appian.com/suite/help/latest/Decisions.html
- a!defaultValue Function — https://docs.appian.com/suite/help/latest/fnc_informational_a_defaultvalue.html
- a!isNullOrEmpty() Function — https://docs.appian.com/suite/help/latest/fnc_informational_isnullorempty.html
- How to Handle Null Values in Appian — https://docs.appian.com/suite/help/latest/null-handling.html
- a!forEach() Function — https://docs.appian.com/suite/help/latest/fnc_looping_a_foreach.html
- Looping Recipes — https://docs.appian.com/suite/help/latest/looping.html
- Interface Performance Best Practices (conditional logic, local variables, expensive computations last) — https://docs.appian.com/suite/help/latest/interface-performance.html
- SAIL Performance (Interface Evaluation Lifecycle — Local Variables) — https://docs.appian.com/suite/help/latest/SAIL_Performance.html
- Parallel Evaluation of Expressions — https://docs.appian.com/suite/help/latest/expressions-parallel-evaluation.html
- Record Type Query Performance Best Practices — https://docs.appian.com/suite/help/latest/query-best-practices.html
- Recipes for Querying Records — https://docs.appian.com/suite/help/latest/Query_Recipes.html
- Offline Mobile Design Best Practices — https://docs.appian.com/suite/help/latest/offline-mobile-design-best-practices.html
- Advanced Expression Evaluation (Indirectly evaluating arguments) — https://docs.appian.com/suite/help/latest/expression-advanced-evaluation.html
- Reusing Interfaces (Reusability) — https://docs.appian.com/suite/help/latest/using_interfaces_in_appian.html
- Parts of an Expression (Comments) — https://docs.appian.com/suite/help/latest/parts-of-an-expression.html
- Expression Editor (Toolbar actions / Design guidance) — https://docs.appian.com/suite/help/latest/expression-editor.html
- Connected Underwriting — Architecture Overview (solution naming conventions, marked "verify") — https://docs.appian.com/suite/help/latest/cu/connected-underwriting-architecture-overview.html
