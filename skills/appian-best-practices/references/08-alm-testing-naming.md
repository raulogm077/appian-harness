# Best practices — ALM, testing, naming conventions and development approach

> Official Appian doctrine on how to name, structure, test, version and deploy applications,
> and how to govern their quality over time. Every rule is anchored to `docs.appian.com/suite/help/latest/…`.
> Links with `latest`: an alias that redirects to the newest release, so they never expire.

---

## 1. Object naming

The official **Standard Object Names** page defines a standard per object type. It is adaptable to your
organization, but its backbone — application prefix + case convention per type — is not something to
improvise.

✅ **Give each application a short, unique prefix, and start every technical object's name with it.**
Domain initials (e.g. `HRO` for *HR Onboarding*). It's configured when creating the app and pre-fills the
name of new objects.
- **Why:** the prefix visually groups an app's objects in a shared environment and avoids
  name collisions (which must be unique across the environment for data stores, CDTs and record types).
- **Anti-pattern:** objects with no prefix mixed in with those of 458 other apps in the environment;
  impossible to tell at a glance what's yours.
- Source: <https://docs.appian.com/suite/help/latest/Standard_Object_Names.html> · <https://docs.appian.com/suite/help/latest/creating-applications.html>

✅ **Respect the case Appian prescribes for each object type:**

| Object | Convention | Official example |
|---|---|---|
| Application (unpublished) | Title Case with spaces + version suffix | `HRO HR Onboarding All Contents v1.0` |
| Data Store | Title Case with spaces | `HRO Employee Data` |
| Custom Data Type | Title Case with underscores + own namespace | `HRO_Employee_Data` (`urn:appian:hro`) |
| Record Type | Singular, descriptive | `HRO Employee` |
| Constant | UPPERCASE with underscores, optional secondary prefix | `HRO_IMG_CAREER_HISTORY_ICON` |
| Decision | PascalCase | `HRO_DetermineEligibilityStatus` |
| Expression Rule | PascalCase, optional secondary prefix | `HRO_ComputeBaseSalary` |
| Integration | PascalCase | `HRO_GetApplicationInformation` |
| Interface | PascalCase | `HRO_AddNewEmployee` |
| Process Model | Title Case with spaces | `HRO Onboard New Employee` |
| Web API | Spaces allowed | `HRO Get LinkedIn Profile` |
| Folder / Group / Site (internal) | Title Case with spaces | `HRO Process Models` |

- **Why:** the case communicates the object type before you even open it; an `HRO_ComputeBaseSalary`
  reads as a rule, an `HRO Employee Data` reads as data.
- Source: <https://docs.appian.com/suite/help/latest/Standard_Object_Names.html>

❌ **Don't put the application prefix on objects the end user sees.** Published applications,
sites (visible name), business groups, reports, actions and feeds use a descriptive, meaningful
name, without a prefix.
- **Why:** Appian uses the published app's name to group actions in Tempo; a technical prefix
  leaks straight into the user's face. Example: internal site `HRO Onboarding`, visible name `Onboarding`.
- Source: <https://docs.appian.com/suite/help/latest/Standard_Object_Names.html>

✅ **Use singular, descriptive names for record types; Appian generates the visible plural.** `HRO Employee`
→ the user sees "Employees".
- Source: <https://docs.appian.com/suite/help/latest/Standard_Object_Names.html>

✅ **Give record types a business display name, not the technical abbreviation.** Prefer
`Case Managers` / `Human Resource Employees` over `CM Employee` / `HR Employees`.
- **Why:** the display name appears in Process HQ and feeds AI features; clear business terms make
  data more usable and better for AI.
- Source: <https://docs.appian.com/suite/help/latest/build-best-data-fabric.html>

❌ **Don't change an app's prefix after creating objects expecting a mass rename.** Appian does **not**
bulk-update existing names; you have to edit every object by hand.
- Source: <https://docs.appian.com/suite/help/latest/creating-applications.html>

---

## 2. Application structure

✅ **One application per business solution.** *CRM*, *Employee Onboarding* and *Sales Opportunities* are
three apps, not one.
- **Why:** it's the unit of deployment and security; splitting by domain keeps packages
  small and dependencies clear.
- Source: <https://docs.appian.com/suite/help/latest/creating-applications.html>

✅ **Remember the app is a list of associated objects, not an exclusive container.** An object can be
associated with several apps; the **Objects** view lists them ignoring that association.
- **Why:** it shapes how you split shared objects and what you pull in when packaging.
- Source: <https://docs.appian.com/suite/help/latest/design-objects.html>

✅ **Treat shared objects (subprocesses, groups, folders, common rules) as a risk zone.**
Changing or importing them can have side effects on other apps in the environment.
- **Why:** the impact of a shared object propagates outside your app; review it with dependents
  analysis before touching it.
- Anti-pattern: editing a "common" rule for your use case and silently breaking another
  application that reuses it.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

✅ **Before any significant change, run dependents and precedents analysis (impact analysis).**
Dependents = blast radius (everything that needs to be re-tested); precedents = everything the
object references (and that you must include in the package).
- **Why:** it avoids deploying with missing precedents and breaking the target.
- Source: <https://docs.appian.com/suite/help/latest/Trace_Relationships_for_Impact_Analysis.html> · <https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html>

✅ **Generate the standard groups and folders when creating the app** (security checkbox) to organize
and secure objects from minute zero.
- Source: <https://docs.appian.com/suite/help/latest/creating-applications.html>

---

## 3. ALM / deployment across environments

### Environment model

✅ **Always promote from lower to higher: Dev → Test → Production.** Supported deployment paths
include Dev→Test, Dev1→Dev2, Break/Hotfix→Dev and Test→Prod.
- Source: <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

❌ **Never modify objects directly in Production.** Changes are born in Dev and travel by
package. The only exception is a Break/Fix (hotfix) flow, which additionally **flows back into Dev**
so the fix isn't lost.
- **Why:** a direct change in Prod isn't versioned in the pipeline and gets lost in the next
  deployment from Dev, which overwrites it.
- Source: <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

### Packages

✅ **Start a package for the application from the beginning of development** instead of deploying the
whole app every time.
- **Why:** a package scopes the change, makes deployment more agile and flexible, and enables
  incremental Compare & Deploy.
- Source: <https://docs.appian.com/suite/help/latest/creating-applications.html> · <https://docs.appian.com/suite/help/latest/prepare-deployment-packages.html>

✅ **Prefer Compare & Deploy (direct) between connected environments.** Appian offers three methods:
direct (compare and deploy), programmatic (deployment APIs, for CI/CD) and manual (export/import ZIP).
- Source: <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

✅ **Review the package with object comparison before promoting.** Compares version to version and
surfaces missing precedents.
- Source: <https://docs.appian.com/suite/help/latest/prepare-deployment.html#comparing-across-environments> · <https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html>

### Programmatic deployment — Deployment REST API (CI/CD)

✅ **For CI/CD, use the native Deployment REST API: six endpoints that automate the full
export → inspect → import cycle.** Called on `https://<domain>/suite/deployment-management/<v#>`:
1. **Export** apps/packages · 2. **Inspect** apps/packages · 3. **Get inspection results** ·
4. **Import (deploy)** · 5. **Get deployment results** · 6. **Get deployment log**. In addition,
**Application Package Details** retrieves the **package UUID** that triggers the export/import.
- **Why:** you build the pipeline once and every deployment runs the same way, without manual errors;
  it integrates with external tools (e.g. Jenkins) and triggers the post-deployment process.
- **Flow:** Appian recommends **always inspecting before deploying**; the `POST` calls distinguish
  import from export with the `Action-Type` header, and the `GET` calls (statuses, log) are available
  **always**, regardless of the Admin Console settings.
- Source: <https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html> · <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

✅ **Authenticate the API with an API key or OAuth 2.0 tied to a service account** (the same mechanism
that secures Web API objects); both are created in the Admin Console. For extra security, upload
trusted server certificates and enable **mTLS** (requests over port 8443).
- Source: <https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html> · <https://docs.appian.com/suite/help/latest/admin-certificates.html>

⚠️ **Choose the API version according to your Appian release, and enable it before using it.** There
are three: **V1** (Appian ≤ 23.2), **V2** (≤ 26.4) and **V3** (26.5+). Each version adds flexibility:
**V3** is the only one that supports **multiple packages** in a single deployment and **DB scripts
from different sources**. Endpoints are enabled in **Admin Console → Infrastructure**.
- Source: <https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html> · <https://docs.appian.com/suite/help/latest/admin-infrastructure.html>

### Import Customization File (ICF)

✅ **Use an Import Customization File (ICF) for values that change per environment or aren't
exported.** It's a `.properties` template that Appian generates (you download, edit and upload it) to
fix in the target: credentials/passwords, connected systems, integrations, environment-specific
constants and Admin Console settings. It's also used to **force the update of unchanged objects**
(`importSetting.FORCE_UPDATE=true`) and to **trigger a sync** of a record type
(`recordType.<UUID>.forceSync=true`).
- **Why:** it decouples secrets and per-environment values from the object package; the same package
  gets promoted to Test and to Prod by only changing the ICF.
- Source: <https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html> · <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

⚠️ **Watch the ICF syntax: `#` comments out (ignored), and uncommenting a valid property without
setting a value leaves it `null` in the target.** Every line of the template comes commented out by
default; uncomment only what you want to change and put the value after the `=`. **A single ICF per
deployment**, even when deploying several packages: you have to consolidate everything into one file.
Keep **one ICF per environment** in the pipeline (non-applicable properties are ignored). For
constants used as a feature toggle or counter, **leave the line commented out** so you don't overwrite
the target's value.
- Source: <https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html>

### Database scripts in deployment

✅ **Include DB scripts (`.sql`/`.ddl`) in the package and fix their execution order.** Appian runs
**all scripts before deploying any object**; if a script fails, the deployment **stops** (and rolls
back what it can) — check the deployment log. The order **within** a package is persisted in the
package; the order **between** packages is not persisted (check it on every Compare & Deploy). Keep
the DDL versioned in the repository, alongside the rest of the solution's code.
- Source: <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html> · <https://docs.appian.com/suite/help/latest/prepare-deployment-packages.html>

⚠️ **DB scripts and plug-ins are NOT exported with the object package; they're a separate step that
requires direct deployment permission.** And if the data source is a **connected system** that also
travels in the deployment, you have to **deploy the DB scripts separately from the connected system**.
If a script touches the data of a synced record type that isn't in the package, trigger the sync with
the ICF (`forceSync`).
- Source: <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html> · <https://docs.appian.com/suite/help/latest/data-source-connected-systems.html>

### Deployment gates and automation

✅ **Open the deployment gates in the target environment's Admin Console before promoting scripts or
plug-ins.** The **"Allow deployments with plug-ins"** and **"Allow deployments with database
scripts"** settings must be enabled in the target, or that content won't get in. For high
environments (Production), **require prior review/approval**: with review enabled, the app's
administrators and the reviewer group get an email and approve or reject in the **Deploy** view.
- Source: <https://docs.appian.com/suite/help/latest/admin-infrastructure.html> · <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

✅ **Lean on Appian's DevOps accelerators for the pipeline** (Application Version Manager and
version-control integration, DevOps Quick Start / Deployment Automation from Appian MAX) instead of
home-grown export/import scripts.
- Source: <https://docs.appian.com/suite/help/latest/devops-with-appian.html> · <https://community.appian.com/success/w/guide/3328/deployment-automation>

⚠️ **Environment-specific settings are NOT deployed: API keys and certificates are configured by hand
in each environment.** The ICF covers object secrets (credentials, connected systems), but these
platform settings don't travel in the package.
- Source: <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html> · <https://docs.appian.com/suite/help/latest/Appian_Administration_Console.html>

⚠️ **Validate AppMarket plug-ins BEFORE a platform upgrade, and test them thoroughly before
Production.** Plug-ins and shared components are used **at your own risk** and Appian doesn't
guarantee they work; in a **shared** cloud environment with other applications, an incompatible
plug-in after the upgrade can affect everyone.
- Source: <https://docs.appian.com/suite/help/latest/plugindisclaimer.html>

### ALM for Report and Dashboard objects

❌ **Don't deploy a report whose dataset filter or quick filter points to a user, group or document**
(nor a dashboard with a **process KPI**): inspection flags it as an **error** and blocks the
deployment, both direct and via manual export. To deploy them you must belong to the **Data
Fabric Report Creators** system group and **add the object to the application** first.
- Source: <https://docs.appian.com/suite/help/latest/deploy-to-production.html> · <https://docs.appian.com/suite/help/latest/report-and-dashboard-objects.html>

⚠️ **A report/dashboard edited by a business user in the target becomes protected: the deployment
does NOT overwrite it.** By default that version is authoritative. If your change governance requires
the source to win, force the overwrite per object in the ICF with
`report.<UUID>.forceOverrideProtection=true` / `dashboard.<UUID>.forceOverrideProtection=true`. These
objects cannot go in a post-deployment process.
- Source: <https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html> · <https://docs.appian.com/suite/help/latest/deploy-to-production.html>

### Deployment behavior rules

✅ **Trust that Appian matches objects between environments by UUID, not by name or Local ID.** If the
UUID exists in the target, it **updates**; if not, it **creates**. Same name with a different UUID =
two different objects.
- **Why:** this is why you **never invent or copy UUIDs between environments** — deployment matching
  depends on them. An invented UUID doesn't update anything: it creates a duplicate object.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

⚠️ **Import has no undo.** Once completed it cannot be rolled back; keep a backup and a stable
window.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

❌ **Don't edit the generated XML or the internal structure of the export ZIP.** It's not supported
and can break the deployment.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

✅ **Only deploy from an Appian version equal to or earlier than the target, never the other way
around.** Same release with a different hotfix is still compatible.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

❌ **Don't modify objects in the target environment while an import is in progress**, and don't
deploy onto an environment under maintenance.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

✅ **Import with a shared system administrator account, not a personal one.** A process model
configured to "run as its designer" fails if that account is deactivated.
- **Why:** decoupling deployment and execution from a specific person avoids outages when someone
  leaves the team.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

✅ **When deploying several packages together, align versions of shared objects** (you can't deploy
two versions of the same object) and use a **single ICF** per deployment.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>

✅ **Use a post-deployment process for logic that must run after a direct or external deployment**
(DB updates, refreshes). Auditable in the **Deploy** view.
- Source: <https://docs.appian.com/suite/help/latest/post-deployment-process.html> · <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

### Versioning

✅ **Lean on native per-object versioning: every save creates a version.** Compare versions to
review and debug; you can revert.
- **Why:** it's the safety net that makes an `update` reversible, unlike a delete, which isn't.
- Source: <https://docs.appian.com/suite/help/latest/Managing_Object_Versions.html> · <https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html>

⚠️ **Rollback strategy: per-object versioning and Compare & Deploy are NOT a transactional
rollback.** Reverting an object to its previous version doesn't undo the DB schema, the data, the
groups, the credentials, or the effects of processes already run; and import **has no undo**. Plan
the real reversal: **roll-forward** (a new deployment that fixes things), **N / N-1 compatibility**
between objects and schema so they can coexist during deployment, **compensating scripts** for DB
changes, and **backup/restore** — export the Production objects before promoting so you can restore
if the deployment fails.
- Source: <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html> · <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html> · <https://docs.appian.com/suite/help/latest/Managing_Object_Versions.html>

✅ **Integrate continuously: frequent, incremental changes, not one big batch at the end.**
- **Why:** it reduces the risk of conflicting changes and eases collaboration between several
  designers.
- Source: <https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html>

---

## 4. Testing

Appian recognizes three types: **unit** (rules, logic), **user-interface**, and **performance**
testing. Testing is continuous, not a final phase.

### Expression rule test cases (unit)

✅ **Write test cases for every expression rule that's important or reused across applications.**
- **Why:** rules are the smallest pieces of the app; their test cases give confidence that a logic
  change doesn't break dependent functionality, and document the expected behavior for the next
  developer.
- Source: <https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html> · <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

✅ **Cover use cases, edge cases and nulls.** Write one test per possible outcome of the rule and
another for unusual inputs that could break it.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

✅ **Test only your logic, not Appian's.** Don't verify that `sum()` adds; do verify that your rule
handles types or nulls.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html> (General guidance)

✅ **Make each test as specific as possible.** Isolate one part of the rule per test; three outcomes =
three tests, not one that checks three things.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

❌ **Avoid the "test 1=1".** If the assertion is identical to the rule's definition, you learn
nothing. A surprisingly easy mistake to make.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

❌ **Don't write brittle tests that depend on external data or the current date/time.** A query
against a transactional table can fail because of a data change unrelated to the rule's logic.
- **Why:** a failure like that doesn't reflect a defect in the rule; it poisons the regression suite's
  signal.
- **Corollary:** rules that query **transactional** data (different in every environment) don't need
  a test case.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

✅ **Consider TDD: write the test cases before the rule** and use them as the "done" criterion.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

### Interfaces

✅ **Test display and validation logic while building the interface, not at the end.** Use the live
view, ad hoc tests and test scenarios (named sets of rule inputs).
- Source: <https://docs.appian.com/suite/help/latest/interface_object.html> · <https://docs.appian.com/suite/help/latest/testing-applications.html>

✅ **Test every interface with real data AND with the empty/null path.** A newly added rule input
comes in as null; create one scenario with data and another with nulls.
- **Why:** the body of an `a!forEach` over an empty list never gets evaluated, so a broken screen can
  pass all its cases while its lists come in empty. Loading a minimal data set surfaces blockers that
  the empty path hides.
- Source: <https://docs.appian.com/suite/help/latest/interface_object.html> · <https://docs.appian.com/suite/help/latest/null-handling.html>

✅ **Handle nulls explicitly with `a!defaultValue()`, `a!isNullOrEmpty()`, `a!isNotNullOrEmpty()` and
the `applyWhen` parameter in filters.** You can't transform a null string, iterate a null list, or
show a link with a null address.
- **Why:** an unhandled null turns the app into "broken or unstable" in the user's eyes.
- Source: <https://docs.appian.com/suite/help/latest/null-handling.html>

### Regression and cadence

✅ **Run all of the app's rule test cases in bulk at the end of every sprint.** Smart Service
*Start Rule Tests (Applications)*.
- **Why:** a change to one rule can have implications elsewhere; testing just the change, in a
  less-loaded environment, gives fast feedback.
- Source: <https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html>

✅ **Regression-test ALL rules in the system after deploying to Test, before a major release.** Smart
Service *Start Rule Tests (All)*.
- **Why:** many rules are shared across apps; this surfaces impacted dependencies before Prod.
- Source: <https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html>

✅ **Run the package's test cases at least once right before deploying.** When inspecting the package
during a direct deployment, Appian reminds you of missing coverage and invites you to run the tests.
- **Why:** it's the best way to confirm the changes haven't degraded existing rules.
- Source: <https://docs.appian.com/suite/help/latest/testing-applications.html> · <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>

✅ **Watch and close coverage gaps with the Manage Test Cases dialog**, which lists rules without
tests and runs several rules' tests at once.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

✅ **Automate execution with a CI tool (e.g. Jenkins)** via the test smart services.
- Source: <https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html>

### Processes

✅ **Debug process models by starting processes in debug mode as you add nodes.** Don't wait until
the end.
- Source: <https://docs.appian.com/suite/help/latest/testing-applications.html>

---

## 5. Development approach and methodology

✅ **Follow an agile methodology (Initiate → Build → Release → Optimize).** Appian explicitly
recommends Agile and its Appian Delivery Methodology.
- Source: <https://docs.appian.com/suite/help/latest/introduction-to-application-building.html> · <https://community.appian.com/success/w/guide/2973/the-appian-delivery-methodology>

✅ **Design data-driven: model with record types and data fabric as the foundation.** Every record
type represents a business concept (Products, Orders, Customers…); relate several for a unified view.
- **Why:** it unifies, secures and optimizes the data without migrations or custom APIs, and speeds
  up development.
- Source: <https://docs.appian.com/suite/help/latest/Record_Type_Object.html> · <https://docs.appian.com/suite/help/latest/data-fabric.html>

✅ **Use synced record types whenever you can.** They unlock automatic performance optimization,
relationships, custom record fields and row-level security.
- Source: <https://docs.appian.com/suite/help/latest/build-best-data-fabric.html>

✅ **Reuse objects instead of duplicating logic.** Reference an interface from a record, a common rule
from several interfaces.
- **Why:** builds faster and is easier to maintain; fewer places to touch when something changes.
- **Trade-off:** reuse increases the dependents blast radius — hence the impact analysis (§2).
- Source: <https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html>

✅ **Do design reviews before building.** Wireframing/prototyping with SAIL, technical design
documentation, and **fix naming and structure standards as part of the design**, not after the fact.
- **Why:** Appian places "Determining coding standards" (naming, structure, documentation) within
  the design phase, before the build.
- Source: <https://docs.appian.com/suite/help/latest/introduction-to-application-building.html>

✅ **Prefer documented functions.** An unsupported/undocumented function can change or break when
Appian is upgraded (design guidance "Unsupported function detected").
- Source: <https://docs.appian.com/suite/help/latest/appian-recommendations.html>

---

## 6. Documentation and maintainability of objects

✅ **Write clear descriptions on record types (and key objects).** 1–2 sentences about the purpose,
in business language, including relevant relationships or constraints; understandable to someone
outside the app. You can generate them with AI Copilot.
- **Why:** they feed Process HQ and AI, and are the next developer's onboarding.
- Source: <https://docs.appian.com/suite/help/latest/build-best-data-fabric.html>

✅ **Use test cases as living documentation.** They describe the expected behavior and outcomes of a
rule for whoever modifies it in the future.
- Source: <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>

✅ **Pass arguments by keyword syntax to rules and data constructors.** It protects the expression
against compatibility issues if inputs get added, reordered, removed or renamed.
- Source: <https://docs.appian.com/suite/help/latest/appian-recommendations.html>

❌ **Don't leave unused local variables, rule inputs or process variables.** They complicate
understanding, debugging and maintenance (and can trigger unnecessary queries). Design guidance flags
them.
- Source: <https://docs.appian.com/suite/help/latest/appian-recommendations.html>

✅ **Name user tasks with a dynamic display name** (an ID or an entered value) to distinguish
instances in Tempo and in task reports.
- Source: <https://docs.appian.com/suite/help/latest/appian-recommendations.html>

✅ **Keep process models small:** under 50 nodes and 100 process variables; split into subprocesses
if they grow past that.
- **Why:** going beyond those thresholds complicates maintenance and consumes more memory (design
  guidance "Too many nodes" / "Too many process variables").
- Source: <https://docs.appian.com/suite/help/latest/appian-recommendations.html>

---

## 7. Continuous quality control (Health Check, design guidance, technical debt)

✅ **Attend to Appian Design Guidance in real time as you develop.** Warnings (triangle) and
recommendations (light bulb) appear on the object and in the Monitor's Health Dashboard.
- **Why:** applying these patterns improves performance and reduces runtime and maintainability
  problems; it's technical debt tackled at the source, when it's cheapest.
- Source: <https://docs.appian.com/suite/help/latest/appian-recommendations.html> · <https://docs.appian.com/suite/help/latest/devops-with-appian.html>

✅ **Schedule Health Check in every environment and review the report regularly — at least once per
sprint.** It covers four areas: **Design, User Experience, Infrastructure, Configuration**, with
high/medium/low risks and mitigation links, plus historical trends.
- **Why:** in build it catches design flaws early and cheaply; in test, functional and performance
  risks; in Prod, it monitors capacity and trends.
- Source: <https://docs.appian.com/suite/help/latest/health-check.html> · <https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html>

⚠️ **Run Health Check outside business hours in active environments.** It increases system load and
can degrade user performance (mind the time zones).
- Source: <https://docs.appian.com/suite/help/latest/health-check.html>

✅ **Also monitor at runtime: application and system performance, and logs.** Check that the app is
functional, efficient, gives a good experience and delivers business value; use logs for non-process
errors (record views, task forms) and usage analysis.
- Source: <https://docs.appian.com/suite/help/latest/devops-with-appian.html>

✅ **Automate Health Check in CI** with a Web API that calls `a!latestHealthCheck()` if you integrate
it into Jenkins.
- Source: <https://docs.appian.com/suite/help/latest/health-check.html>

---

## Sources

- **Standard Object Names** — <https://docs.appian.com/suite/help/latest/Standard_Object_Names.html>
- **Creating Applications** — <https://docs.appian.com/suite/help/latest/creating-applications.html>
- **Design Objects** — <https://docs.appian.com/suite/help/latest/design-objects.html>
- **Introduction to Application Building** — <https://docs.appian.com/suite/help/latest/introduction-to-application-building.html>
- **Application Deployment Guidelines** — <https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html>
- **Deploy to Target Environments** — <https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html>
- **Deployment REST API** — <https://docs.appian.com/suite/help/latest/Deployment_Rest_API.html>
- **Manage Import Customization Files (ICF)** — <https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html>
- **Deploy to Production (Process HQ / reports & dashboards)** — <https://docs.appian.com/suite/help/latest/deploy-to-production.html>
- **Deploy Report and Dashboard Objects** — <https://docs.appian.com/suite/help/latest/report-and-dashboard-objects.html>
- **DevOps Infrastructure (Admin Console)** — <https://docs.appian.com/suite/help/latest/admin-infrastructure.html>
- **Admin Console — Certificates (mTLS)** — <https://docs.appian.com/suite/help/latest/admin-certificates.html>
- **Data Source Connected Systems** — <https://docs.appian.com/suite/help/latest/data-source-connected-systems.html>
- **Appian Administration Console** — <https://docs.appian.com/suite/help/latest/Appian_Administration_Console.html>
- **Plug-in Disclaimer (test before production)** — <https://docs.appian.com/suite/help/latest/plugindisclaimer.html>
- **Deployment Automation (Appian MAX / Community)** — <https://community.appian.com/success/w/guide/3328/deployment-automation>
- **Prepare Deployment Packages** — <https://docs.appian.com/suite/help/latest/prepare-deployment-packages.html>
- **Prepare the Deployment — Comparing across environments** — <https://docs.appian.com/suite/help/latest/prepare-deployment.html#comparing-across-environments>
- **Post-Deployment Process** — <https://docs.appian.com/suite/help/latest/post-deployment-process.html>
- **Continuous Integration in Appian** — <https://docs.appian.com/suite/help/latest/continuous-improvements-to-your-application.html>
- **DevOps in Appian** — <https://docs.appian.com/suite/help/latest/devops-with-appian.html>
- **Trace Relationships for Impact Analysis** — <https://docs.appian.com/suite/help/latest/Trace_Relationships_for_Impact_Analysis.html>
- **Managing Object Versions** — <https://docs.appian.com/suite/help/latest/Managing_Object_Versions.html>
- **Testing Applications** — <https://docs.appian.com/suite/help/latest/testing-applications.html>
- **Expression Rule Testing** — <https://docs.appian.com/suite/help/latest/Expression_Rule_Testing.html>
- **Automated Testing for Expression Rules** — <https://docs.appian.com/suite/help/latest/Automated_Testing_for_Expression_Rules.html>
- **Interface Object (Testing interfaces)** — <https://docs.appian.com/suite/help/latest/interface_object.html>
- **How to Handle Null Values** — <https://docs.appian.com/suite/help/latest/null-handling.html>
- **Appian Design Guidance** — <https://docs.appian.com/suite/help/latest/appian-recommendations.html>
- **Health Check** — <https://docs.appian.com/suite/help/latest/health-check.html>
- **Understanding the Health Check Report** — <https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html>
- **Build Your Best Data Fabric** — <https://docs.appian.com/suite/help/latest/build-best-data-fabric.html>
- **About Record Types** — <https://docs.appian.com/suite/help/latest/Record_Type_Object.html>
- **Data Fabric** — <https://docs.appian.com/suite/help/latest/data-fabric.html>
- **Use Data Fabric in Existing Apps** — <https://docs.appian.com/suite/help/latest/use-synced-record-types-in-existing-apps.html>
- **The Appian Delivery Methodology (Community)** — <https://community.appian.com/success/w/guide/2973/the-appian-delivery-methodology>
- **The Appian Playbook — Appian Testing Essentials (Community)** — <https://community.appian.com/success/w/playbook/3474/appian-testing-essentials>
