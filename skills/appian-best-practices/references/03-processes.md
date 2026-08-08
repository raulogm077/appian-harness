# Best practices — Processes (BPMN)

> Official Appian doctrine for designing process models that are robust, maintainable and
> scalable. Every rule is anchored to official documentation (`docs.appian.com/.../latest/...`)
> or the Appian Community. Links use the `latest` alias, which always redirects to the
> latest release. Claims without a clean official source are marked **(verify)**. (The linked
> **Appian RPA** pages carry their own product version — `…/latest/rpa-9.25/…` —: that is their
> canonical path within `/latest/`, not a platform version pin.)

---

## 1. Process design and size

**✅ Keep processes short: a maximum of ~50 nodes.**
Appian Design Guidance raises the *"Too many nodes"* recommendation once you go past **50
nodes**: more nodes complicate maintenance, raise memory consumption and lengthen completion
time. Combine nodes or split into subprocesses.
- ❌ Anti-pattern: a single monolithic process model with 80 nodes that handles an entire
  onboarding flow.
- Source: [Appian Design Guidance — Process model design guidance](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance)

**✅ A single Start Event per process model.**
A process model admits only **one Start Event**; every model has one Start and one End Event.
Multiple entry points connect to the same start node.
- Source: [Start Event](https://docs.appian.com/suite/help/latest/Start_Event.html)

**✅ Formally terminate the process at End nodes.**
It is best practice to mark **Terminate Process** on End Events. A process remains *active*
until **all** active flows reach an end node; without Terminate, a forgotten parallel flow
keeps the instance alive in memory forever. Mark Terminate on most end nodes unless the
process genuinely expects multiple simultaneous active flows.
- ❌ Anti-pattern: unterminated end nodes in a process with AND branches that never close.
- Source: [Process Modeling Tutorial — Configure the end nodes](https://docs.appian.com/suite/help/latest/Process_Modeling_Tutorial.html#configure-the-end-nodes) · [Troubleshooting — process does not complete at end node](https://docs.appian.com/suite/help/latest/Testing_and_Debugging_Problems_with_Process_Models.html#the-process-does-not-complete-when-it-reaches-an-end-node)

**✅ One process = one responsibility.**
Appian recommends processes that are "clear and focused, doing a single job." Split when the
flow involves several users, contains timers/wait rules, or reuses standard operations.
Deterministic logic (validations, calculations, conditional flows) belongs inside the process;
delegate only orchestration to subprocesses.
- Source: [Prepare process models for AI agent tools](https://docs.appian.com/suite/help/latest/create-and-configure-ai-agent.html#before-you-begin-prepare-your-tools-and-actions) (applies the "focused process, single task" doctrine)

---

## 2. Subprocesses and reuse

**✅ Reuse shared functionality as a subprocess.**
Appian recommends using subprocesses for any functionality shared across models. The
Subprocess node links parent and child and transfers data between them.
- Source: [Subprocess](https://docs.appian.com/suite/help/latest/Sub-Process_Activity.html)

**✅ Choose synchronous vs. asynchronous with judgment.**
- **Synchronous**: the parent waits for the child to finish; allows passing data in both
  directions and **activity chaining** into the child.
- **Asynchronous**: the parent does not wait; data only travels parent→child (it does not come
  back) and it does **not** support activity chaining. Use it when the activities don't need to
  communicate back.
- Source: [Subprocess — synchronous / asynchronous](https://docs.appian.com/suite/help/latest/Sub-Process_Activity.html)

**✅ To launch MANY processes, use Start Process, not the Subprocess node.**
Subprocesses run on the **same execution engine** as the parent: there is no load balancing.
Starting a large number via the Subprocess node concentrates the load on a single engine and
degrades performance. The **Start Process smart service** spreads the load across engines.
Design Guidance flags this explicitly (*"Asynchronous subprocess"*) when an asynchronous
subprocess sits inside a loop or is configured with MNI.
- ❌ Anti-pattern: an asynchronous Subprocess node with MNI of 10,000 instances.
- Source: [Design Guidance — Asynchronous subprocess](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance) · [Start Process Smart Service](https://docs.appian.com/suite/help/latest/Start_Process_Smart_Service.html)

**✅ Don't pass a CDT by reference into a subprocess; use input/output variables.**
Active processes keep using the version of the CDT they started with, but a subprocess always
starts with the **latest** version of the CDT. If the parent passes a CDT **by reference** and
the type is updated in the meantime, the parent **breaks** when it reaches the Subprocess node.
Pass the data through input and output variables instead.
- Source: [Design Guidance — Data types passed by reference](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance)

**✅ Don't overuse "wrapper models".**
A model that only wraps a simple smart service (e.g. a single write) plus a gateway degrades
throughput in exchange for a minimal reuse benefit. Configure simple smart services directly in
the relevant process. It is worth wrapping smart services with complex configuration (Send
Email, Document Generation, Stored Procedure) or integrations you expect to replace.
- Source: [Health Check — Simple wrapper process model](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#simple-wrapper-process-model)

---

## 3. Process variables and memory footprint

**✅ Minimize the number of process variables: threshold 100, high risk 300+.**
Design Guidance warns (*"Too many process variables"*) past **100 PVs**; the Health Check marks
100 as medium risk and **300 or more as high risk**. Every PV reserves memory for the
**entire life of the process**, even once completed and unarchived. Convert PVs into
**activity class parameters** (node parameters) where you can, or split into subprocesses.
- Source: [Design Guidance — Too many process variables](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance) · [Health Check — Max process variables per model](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#maximum-number-of-process-variables-per-process-model)

**✅ Remove unused process variables.**
They complicate understanding and maintenance. (Watch out: the check does not see whether the
PV is used by a *process report*; confirm that before deleting.)
- Source: [Design Guidance — Unused process variable](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance)

**✅ Keep PVs small; CDTs and lists multiply the cost.**
The memory risk is higher when PVs are CDTs or lists: there is a multiplier effect per CDT
field or list element, made worse if they change frequently. Prefer **more, smaller models**
with PVs that hold less data, rather than a few complex models with large PVs.
- Source: [Health Check — Max process variables per model](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#maximum-number-of-process-variables-per-process-model) · [Autoscale Patterns and Best Practices — Keep process variables small](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

**✅ Never store large payloads in PVs.**
Avoid large strings (Base64, bulky JSON/XML) in PVs or node inputs: the execution engine's
memory is retained even for completed, unarchived processes. Store large content in a
**document, database table or external storage** and reference the pointer.
- ❌ Anti-pattern: storing an entire PDF as Base64 in a PV.
- Source: [KB-1248 — High memory usage: Memory impact of process variables](https://community.appian.com/support/w/kb/463/kb-1248-how-to-address-high-memory-usage-in-self-managed-appian-environments#engines)

**✅ Hard limit of 5 MB per PV in autoscale processes.**
With autoscale, each PV has a size limit of **5 MB**; test in development with the largest
volume you expect. The way out: more models, each holding less data.
- Source: [Autoscale Patterns and Best Practices — Keep process variables small](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

---

## 4. Writing data (smart services)

**✅ Use Write Records for database-backed record types with data sync.**
Write Records inserts/updates at the source and syncs the change into Appian automatically. It
requires the record type to use a **database as its source** and have **data sync enabled**.
Limit: **50,000** records + related records + events combined per node. The user running the
node needs **Viewer** permission on every record type being written (otherwise the node fails
and pauses the process with an exception).
- Source: [Write Records Smart Service](https://docs.appian.com/suite/help/latest/Write_Records_Smart_Service.html)

**✅ These smart services sync on their own: Write Records, Write to Data Store Entity, Write to Multiple Data Store Entities, Delete Records, Delete from Data Store Entities.**
When used in processes, interfaces or rules, Appian syncs the change and it is available
instantly on the record type. For data changed by *other* smart services or external systems,
use **Sync Records**.
- Source: [Configure Data Sync Options — Smart service syncs](https://docs.appian.com/suite/help/latest/records-data-sync.html#smart-service-syncs)

**✅ Write to Data Store Entity: fill in EVERY field of the CDT.**
If you leave a field blank, **null** is written to that column. Capture every needed value
before the node and cast to the correct type with `cast()` if required.
- Source: [Write Records Smart Service](https://docs.appian.com/suite/help/latest/Write_Records_Smart_Service.html) · [Troubleshooting — Unable to write data](https://docs.appian.com/suite/help/latest/Testing_and_Debugging_Problems_with_Process_Models.html#unable-to-write-data)

**✅ Guard the write from the form, not from the database.**
Add validations on the start form (not-null, max length) so you don't reach the node with data
the column rejects (null in a not-null field, length overflow, a PK without auto-increment). A
failed write against the source of a synced record type leaves the data **unavailable until the
next full sync**.
- Source: [Troubleshooting — Unable to write data](https://docs.appian.com/suite/help/latest/Testing_and_Debugging_Problems_with_Process_Models.html#unable-to-write-data)

**✅ One "action tool" process, one write.**
For processes that create/update data, avoid multiple Write Records nodes for different record
types in the same model. One node, one record type, one purpose.
- Source: [Prepare process models for AI agent tools](https://docs.appian.com/suite/help/latest/create-and-configure-ai-agent.html#before-you-begin-prepare-your-tools-and-actions)

---

## 5. MNI, parallelism and gateways

**✅ Use MNI for nodes that do NOT accept lists; for the ones that do, pass the list.**
Multiple Node Instances (MNI) repeats an activity N times. It is recommended for nodes that
**don't** accept lists of values. Using MNI on nodes that already accept lists (e.g. **Write to
Data Store Entity**) produces unwanted results; pass the list to it directly instead.
- ❌ Anti-pattern: MNI over Write to Data Store Entity to insert N rows.
- Source: [Looping Recipes — Multi-node instances](https://docs.appian.com/suite/help/latest/looping.html#multi-node-instances)

**✅ Know the limits of MNI.**
Subprocess MNI and robotic task MNI each have a limit of **150,000 instances**; loops have no
static limit, but iterating over large volumes consumes a lot of memory. Apply a *circuit
breaker* to cap iterations. If the evaluated number of instances is empty, null or zero, the
process **pauses with an exception**: plan for that case.
- Source: [Looping Recipes — Multi-node instances](https://docs.appian.com/suite/help/latest/looping.html#multi-node-instances)

**✅ Route multiple outgoing flows with a gateway, never at random.**
With several outgoing flows and activity chaining, Appian picks one **at random** — which is
not what you want. Standard practice is a gateway:
- **AND** (Parallel Fork/Join): activates every branch; on join, waits for all of them to arrive.
- **XOR** (Exclusive): a single path based on a condition.
- **OR** (Inclusive): one or several paths based on conditions.
- **Complex**: accepts/restricts incoming paths and evaluates outgoing rules.
- Source: [Common Recipes — Configuring multiple outgoing flows](https://docs.appian.com/suite/help/latest/Process_Model_Recipes.html#configuring-multiple-outgoing-flows) · [Gateways](https://docs.appian.com/suite/help/latest/Gateways.html)

**✅ A looping gateway with multiple incoming flows → precede it with a Script Task that merges the flows.**
A gateway with several incoming flows lets the first flow through but waits for **all** the
incoming flows to arrive before executing what follows; inside a loop that can hang the process
indefinitely. Place a script task in front to merge the incoming flows.
- ❌ Anti-pattern: a loop that re-enters directly into an AND gateway with two incoming flows.
- Source: [Design Guidance — Gateway nodes with multiple incoming flows](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance) · [Gateways — Usage considerations](https://docs.appian.com/suite/help/latest/Gateways.html)

**✅ In parallel/MNI flows, enable "Keep process variables synchronized".**
When a node runs multiple instances or the flow loops, each copy reads/writes the same PVs and
one instance can **overwrite** another's value. Check *Keep process variables synchronized
across this flow* on the connector's Flow Properties to protect values from being overwritten.
- Source: [Common Recipes — Using process variables in parallel flows](https://docs.appian.com/suite/help/latest/Process_Model_Recipes.html#using-process-variables-in-parallel-flows)

---

## 6. Exceptions, timers and robustness

**✅ Capture the result in a variable and route the exception; don't let the process die.**
The official resilience pattern: save the result (success/failure, error message) in an output
variable and use a gateway to route retry, human escalation or logging. It applies to Execute
Robotic Task (the `Success` variable), Execute AI Agent and, by extension, any smart service
with a status output.
- Source: [Design Patterns (RPA) — Handling unplanned exceptions](https://docs.appian.com/suite/help/latest/rpa-9.25/design-patterns.html#handling-unplanned-exceptions)

**✅ Watchdog timer: a parallel branch with a timer for processes that hang.**
For activities that can take longer than acceptable, run the activity in one branch and a
**timer event** in a parallel branch with the maximum tolerable duration. If the activity
doesn't finish in time, the timer triggers an orderly escalation (human queue, log, fallback).
- Source: [Design Patterns for Production AI Agents — Watchdog timer](https://docs.appian.com/suite/help/latest/agent-studio-design-patterns.html#error-handling-and-resilience)

**✅ Set a timer to close processes users never complete.**
Incomplete processes stay in memory forever. Add an Intermediate Event Timer that terminates
the process if it isn't completed within a certain window.
- Source: [KB-2011 — High memory usage in Appian Cloud](https://community.appian.com/support/w/kb/1574/kb-2011-how-to-address-high-memory-usage-in-appian-cloud-environments) · [Intermediate Event - Timer](https://docs.appian.com/suite/help/latest/Intermediate_Event_-_Timer.html)

**✅ Send error alerts to a specific application GROUP, never to the default or to individual users.**
The system default only notifies process/model/system administrators, who differ between
environments. And a specific user may not exist in every environment. Use a constant or
expression that points to a **group** in the application, on the Alerts tab.
- ❌ Anti-pattern: error alerts left on "system default" or pointed at a named user.
- Source: [Design Guidance — Misconfigured error alerts](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance)

**✅ Task escalations: configure them on the attended node's Escalations tab.**
There is a dedicated official recipe (*"Escalating a task"*), so you don't need to model the
escalation by hand. An escalation is configured on any **attended node**; when its timer fires
it runs one of **four actions**: **reassign** the task to another user or group, **raise/change
the priority**, **alert** a user or group, or **notify another process** (Send Message Event).
You can **chain several levels**: level 2's timer (and beyond) doesn't start until the
previous level fires. To have the deadline respect the working calendar (excluding weekends),
set the timer with `a!addDateTime(startDateTime: now(), days: N, useProcessCalendar: true)`.
- ❌ Anti-pattern: an approval task that expires without reassigning or alerting anyone because
  no escalation was configured for it.
- Source: [Common Recipes — Escalating a task](https://docs.appian.com/suite/help/latest/Process_Model_Recipes.html#escalating-a-task) · [Process Node Properties — Escalation tab](https://docs.appian.com/suite/help/latest/Process_Node_and_Smart_Service_Properties.html#escalation-tab) · [a!addDateTime()](https://docs.appian.com/suite/help/latest/fnc_date_and_time_adddatetime.html)

**✅ The node's Exceptions tab: interrupts the activity and reroutes it by condition.**
The **Exceptions** tab (present on every node except events and gateways) creates alternate
flows: a **Receive Message**, a **Timer** or a **Rule Event** which, once satisfied,
**interrupts/cancels** the activity in progress and diverts the flow down the exception branch
(skipping the rest of the node). Only **one** exception flow is allowed per activity even if it
has several events. Two limits: it does **not** support activity chaining on the exception
branch, and it is **incompatible with autoscale** (you cannot configure Exceptions if the model
has autoscale enabled — with autoscale, a rule-based exception on an unattended node leaves the
node in *Skipped* state).
- Source: [Process Node Properties — Exceptions tab](https://docs.appian.com/suite/help/latest/Process_Node_and_Smart_Service_Properties.html#exceptions-tab)

**✅ Know what each error type does: an unattended node does NOT pause the process; an attended task does.**
Error on an **unattended node** (system logic): the process **does not pause**, parallel
branches keep running and an alert is sent with a link to the Monitor view — which is why a
failed write can go unnoticed if nobody is watching the alerts (send them to a group, not the
default; see above). Error affecting an **attended task**: the **entire process pauses** with
status **"Paused by Exception"** and only a Process Administrator can resume it after fixing the
node. **Transient** errors (`safeToRetry`, no data changed): they don't alert immediately, they
**retry** on their own and only alert once retries are exhausted.
- Source: [Process Errors](https://docs.appian.com/suite/help/latest/Process_Errors.html)

**✅ Automatic retry: exponential backoff up to 18 h, but Query Database is not retried.**
For a `safeToRetry` error (only when data has **not** been modified) Appian retries at
intervals that roughly double: **32 s → 64 s → 127 s → 4.5 min … → 18 h** (12 attempts); if the
last one fails there are no more and the activity ends up *canceled by exception*. Internal
smart services, Call Web Service (503/408) and Send E-Mail (connection error) are retried;
**Query Database is NOT retried**, so you are responsible for its robustness (capture the
result and route it, the pattern above). An Activity Execution Exception is not `safeToRetry`:
it cancels without retrying.
- Source: [Automatic Error Handling — Retry intervals](https://docs.appian.com/suite/help/latest/Automatic_Error_Handling.html)

---

## 7. User tasks

**✅ Dynamic task name.**
The display name of a User Input Task should include a variable or expression (an ID, an
entered value) so the user can tell instances of the same task apart in Tempo and in task
reports. A static name makes them indistinguishable.
- ❌ Anti-pattern: a literal display name `"Review request"` across 300 open tasks.
- Source: [Design Guidance — Task display name not dynamic](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance)

**✅ Expose the process to the user as a Record Action or Application Action.**
For users to start processes (create a request, close a ticket, add a document), expose the
model as a **record action** (an action on a record or list) or an **application action**
(a Site page or the Tempo Actions tab). Application actions require interaction, so they only
work with **non-autoscale** models.
- Source: [Ways to Start a Process — from Tempo or sites](https://docs.appian.com/suite/help/latest/Ways_to_Start_a_Process_From_a_Process.html#starting-a-process-from-tempo-or-sites)

**✅ Process model security: its own role map (it does NOT inherit), by groups, minimum Initiator to start it.**
The process model **does not inherit** security from its parent folder: you must set it on each
model individually. Use **groups, not users** (so you control access by moving group
membership, not by re-editing the role map). To **start** the process — including via the Start
Process smart service or a record action — **Initiator** is enough. The role map's six roles:
**Initiator** (start only; cannot see the model or reports), **Viewer** (view model/reports and
reassign their own tasks), **Manager** (also reassign others' tasks and update PVs), **Editor**
(also edit/save/complete others' tasks), **Administrator** (everything: security, deletion,
in-flight changes, publishing) and **Deny** (blocks everything, useful for excluding a group
nested inside another group that has access).
- ❌ Anti-pattern: granting permissions to named users in the role map, or leaving the model on
  inherited security expecting the folder to cover it (it doesn't).
- Source: [Process Model Object — Process model security](https://docs.appian.com/suite/help/latest/process-model-object.html#process-model-security) · [Object Security — Groups and role maps](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps)

---

## 8. When NOT to use a process

**✅ Pure business logic → expression rule, not a process model.**
A model that contains only **script tasks and gateways** should be replaced with an expression
rule (unless you need to audit the logic). The division of labor: **processes for
orchestration, rules for business logic**. Rules run much faster and with much less overhead
than processes, and support *unit tests*. The risk rises if the model has many nodes or sits on
a critical or high-volume path.
- Source: [Health Check — Process model that could be replaced by a rule](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#process-model-that-could-be-replaced-by-a-rule)

**✅ Avoid chains of script tasks in series.**
Three or more chained script tasks can usually be a rule. Two, for readability, is acceptable
(low risk). The risk spikes if they sit inside a loop or at a performance-sensitive point where
the user is waiting. Use the Script Task's Inputs and Outputs tabs to reduce their number, and
move complex expressions into testable rules.
- Source: [Health Check — Sequential script tasks](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#sequential-script-tasks)

**✅ To read data, use an expression rule; to modify it, use a process model.**
Platform doctrine: use an expression to **read** (query, business logic) and a process model to
**modify** (write to the database, generate documents).
- Source: [Design Patterns (RPA) — Leveraging the low-code power of Appian](https://docs.appian.com/suite/help/latest/rpa-9.25/design-patterns.html#robotic-task-design-patterns)

---

## 9. Performance, archiving and monitoring

**✅ Every process lives in memory until it's archived or deleted.**
The execution engine's memory is proportional to the **total number of instances**: running,
completed, stale and unarchived. Set an aggressive retention policy on the model's **Data
Management** tab.
- Source: [Process Model Object — Data Management tab](https://docs.appian.com/suite/help/latest/process-model-object.html#data-management-tab) · [KB-1248 — Process Execution Engines](https://community.appian.com/support/w/kb/463/kb-1248-how-to-address-high-memory-usage-in-self-managed-appian-environments#engines)

**✅ Auto-archive by default (7 days); auto-delete only if the data will never be needed.**
Auto-archive: for processes whose data isn't needed after completion, with the option to
unarchive if regulation requires it (default 7 days, configurable; `0` archives instantly).
Auto-delete: only for processes that will never need their data/metadata viewed afterward — no
trace remains, maximum savings. **Subprocesses do not inherit** the parent's configuration.
- Source: [Considerations for Archiving Processes](https://docs.appian.com/suite/help/latest/Archiving_Processes.html)

**✅ Archiving frees memory but breaks reporting.**
Data from an archived process **stops being available** for process reports. If you need
historical KPIs, map that data to a **separate reporting process** or export it to an RDBMS
table: don't rely on process archiving for business reporting.
- Source: [Considerations for Archiving Processes — Policy / Historical data](https://docs.appian.com/suite/help/latest/Archiving_Processes.html)

**✅ Identify memory consumers with the Health Check and monitor with the Monitor view.**
The Appian Health Check (*Sizing* section) flags which models generate large instance volumes
or have a large footprint. The **Monitor view / Process Activity** gives visibility into which
processes consume the most and lets you archive/delete ad hoc.
- Source: [KB-2011 — Optimize process models](https://community.appian.com/support/w/kb/1574/kb-2011-how-to-address-high-memory-usage-in-appian-cloud-environments) · [Monitoring view](https://docs.appian.com/suite/help/latest/monitoring_view.html)

**✅ High volume from outside Appian → Web API + `a!startProcess()`, with batching.**
The best way to start autoscale processes from an external system is a **web API** calling
`a!startProcess()`. Frequent calls load the server; use **batching**. The autoscale process
queue accepts a maximum of **700/minute** (the overflow is queued up to 1 million).
- Source: [Autoscale Patterns and Best Practices — Starting large numbers of autoscaled processes](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

---

## 10. Email and notifications

> Applies when the solution sends email from the process flow (invitations, reminders, result
> notices). Everything below applies to the **Send E-Mail smart service** inside a process.

**✅ Plain text is the most predictable; rich formatting gets lost.**
**Plain text** emails are the easiest to configure and the ones that look the same across the
widest range of clients. Emails sent from Appian do **not** support: **inline images,
indentation, dividing lines or nested lists**. Design the body assuming plain text; if you need
HTML, test it in several clients before relying on it.
- ❌ Anti-pattern: laying out the invitation with an inline logo, indentation and a nested list
  of requirements.
- Source: [Working with Email — Using the Send E-Mail smart service](https://docs.appian.com/suite/help/latest/email-in-appian.html#sending-emails-from-appian)

**✅ Templates with substitution keys; base template + runtime template pattern.**
To standardize emails, use a **`.txt` or `.html`** template with substitution keys in the
**`###key###`** format: the node scans the template, populates the key grid and replaces each
one with the result of an expression (e.g. a PV). The pattern is a **base template** (the one
that gets scanned) plus a **runtime template** (an expression that returns the `docId` of the
template to use at runtime); that way a single configuration **chooses the template at
runtime**, which is the standard mechanism for **ES/EN localization**. Upload the templates to a
folder and reference them by **constant**. Every key present in the runtime template must also
exist in the base template.
- ❌ Anti-pattern: one Send E-Mail per language on separate process branches, instead of a
  runtime template that picks the template.
- Source: [Send E-Mail Smart Service — Using a template](https://docs.appian.com/suite/help/latest/Send_Email_Smart_Service.html#using-a-template)

**✅ Deliverability: custom sender + a domain with SPF/DKIM/DMARC.**
To avoid landing in spam, configure a **custom sender** and use a "from" domain you are
**authorized to use**, with valid **SPF, DKIM and DMARC** records that include your
environment's mail servers (Cloud or self-managed). **Never** use domains you don't own or
domains that don't exist: SMTP doesn't authenticate them and mail clients flag the message as
suspicious. Without *Email Sender Authentication* set up for the domain, Appian builds the
headers so the email appears sent "on behalf of" (via), precisely so it doesn't look like
spoofing.
- ❌ Anti-pattern: sending from `@gmail.com` or any domain the organization doesn't control.
- Source: [Configuring Custom Email Senders](https://docs.appian.com/suite/help/latest/Configuring_Custom_Email_Senders.html) · [Email on Appian Cloud — Deliverability / DKIM](https://docs.appian.com/suite/help/latest/Email_on_Appian_Cloud.html)

**✅ Reply-To pointed at a monitored mailbox.**
The default address of an email originating from a process is
`<process-instance>@<site-url>`, which **cannot receive replies**. Configure the **Reply To**
field to point at a real mailbox someone monitors, or recipients' replies get lost.
- Source: [Send E-Mail Smart Service — Email Configuration (Reply To)](https://docs.appian.com/suite/help/latest/Send_Email_Smart_Service.html#email-configuration-section) · [Working with Email](https://docs.appian.com/suite/help/latest/email-in-appian.html#sending-emails-from-appian)

**✅ Choose the From field with judgment; watch out for "Undisclosed Recipients".**
The **From** field accepts: **Process, Process Model, Process Initiator, Process Designer** or
**Custom Sender** (which requires a *Sender Display Name* and *Sender Email Address*). If you
send to a **Personal, Restricted or High Privacy Policy** group, the other recipients show up as
**"Undisclosed Recipients"** in the delivered email's To: field — flag that if the business
expects to see the list of recipients.
- Source: [Send E-Mail Smart Service — Email Configuration section](https://docs.appian.com/suite/help/latest/Send_Email_Smart_Service.html#email-configuration-section)

**✅ Sending is sensitive to volume; measure the spam score and add a test toggle.**
Performance depends on **volume** of emails, **size** (attachments especially) and **number of
recipients**. Test with **several email clients** to verify the formatting, measure the **spam
score** with free online tools, and add an application **toggle** to enable/disable sending in
test environments.
- ❌ Anti-pattern: leaving Send E-Mail active in the test environment, firing at real end-user
  addresses.
- Source: [Working with Email — Best practices](https://docs.appian.com/suite/help/latest/email-in-appian.html#sending-emails-from-appian)

---

## 11. Activity chaining

**✅ What it is: chains nodes so the user sees the next screen without returning to their list.**
**Activity chaining** connects two attended nodes through their flow connector (Flow Properties
→ *Enable Activity-Chaining*) so that, on completing a task, the user goes straight to the next
one **without passing through their Task Inbox**. It only chains into **synchronous
subprocesses** (asynchronous ones don't support it — see §2). By default, whoever completes the
first task gets assigned the next ones in the chain; disable that with *Override assignment* on
the connector.
- Source: [Common Recipes — Using activity-chaining to display multiple forms](https://docs.appian.com/suite/help/latest/Process_Model_Recipes.html#enabling-activity-chaining)

**✅ Exceeding the limit breaks the chain and produces stale data.**
Between two chained attended tasks, only a limited number of **unattended nodes** (without a
form) fit: `CHAINED_EXECUTION_NODE_LIMIT`, default **50**, maximum **100**, cannot be disabled.
Once you exceed it, the Health Check raises *"Activity chaining limit reached"* and three
symptoms appear:
- The user **doesn't see the next task**: they must accept it from their task list (a source of
  confusion).
- **Dashboards show stale data**, because required nodes haven't finished before the screen
  loads.
- **Web APIs that start processes return stale data**, for the same reason.

The chain also breaks if more than **10 minutes** pass between attended tasks, or in the face of
a receive message / rule / timer event. **MNI** over chained unattended nodes is the typical
cause of exceeding the limit (a separate finding, *"Number of activity chained unattended nodes
using MNI"*).
- ❌ Anti-pattern: an MNI that inserts N rows one at a time between two chained forms.
- Source: [Health Check — Activity chaining limit reached](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#design) · [Post-Install Configurations — Activity-chain limits](https://docs.appian.com/suite/help/latest/Post-Install_Configurations.html#maximum-activity-instances)

**✅ Mitigation: reduce the chained nodes in the affected processes.**
Review the flagged processes and **reduce the number of nodes with activity chaining enabled**.
Flatten operations (insert all rows at once instead of by MNI), or insert a simple
**"Continue"** form that deliberately breaks the chain before hitting the limit.
- Source: [Health Check — Number of activity chained unattended nodes using MNI](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#number-of-activity-chained-unattended-nodes-using-mni)

---

## Sources

Official documentation (`latest` redirects to the latest release, published monthly):

1. [Appian Design Guidance — Process model design guidance](https://docs.appian.com/suite/help/latest/appian-recommendations.html#process-model-design-guidance) — Too many nodes, Too many process variables, Unused process variable, Task display name not dynamic, Asynchronous subprocess, Data types passed by reference, Gateway nodes with multiple incoming flows, Misconfigured error alerts.
2. [Understanding the Health Check Report](https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html) — Max process variables per model, Process model that could be replaced by a rule, Sequential script tasks, Simple wrapper process model, Activity chaining limit reached, Number of activity chained unattended nodes using MNI.
3. [Subprocess](https://docs.appian.com/suite/help/latest/Sub-Process_Activity.html) — synchronous/asynchronous, same engine, reuse recommendation.
4. [Start Process Smart Service](https://docs.appian.com/suite/help/latest/Start_Process_Smart_Service.html) · [Ways to Start a Process](https://docs.appian.com/suite/help/latest/Ways_to_Start_a_Process_From_a_Process.html).
5. [Gateways](https://docs.appian.com/suite/help/latest/Gateways.html) · [Common Process Model Workflows and Recipes](https://docs.appian.com/suite/help/latest/Process_Model_Recipes.html) — multiple outgoing flows, parallel flows / keep PVs synchronized, using activity-chaining to display multiple forms, **escalating a task** (four actions, chained levels, `a!addDateTime` with `useProcessCalendar`).
6. [Looping Recipes — Multi-node instances](https://docs.appian.com/suite/help/latest/looping.html#multi-node-instances).
7. [Write Records Smart Service](https://docs.appian.com/suite/help/latest/Write_Records_Smart_Service.html) · [Configure Data Sync Options](https://docs.appian.com/suite/help/latest/records-data-sync.html) · [Troubleshooting Process Models](https://docs.appian.com/suite/help/latest/Testing_and_Debugging_Problems_with_Process_Models.html).
8. [Start Event](https://docs.appian.com/suite/help/latest/Start_Event.html) · [End Event](https://docs.appian.com/suite/help/latest/End_Event.html) · [Process Modeling Tutorial](https://docs.appian.com/suite/help/latest/Process_Modeling_Tutorial.html).
9. [Autoscale Patterns and Best Practices](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html).
10. [Considerations for Archiving Processes](https://docs.appian.com/suite/help/latest/Archiving_Processes.html) · [Process Model Object — Data Management tab](https://docs.appian.com/suite/help/latest/process-model-object.html#data-management-tab) · [Monitoring view](https://docs.appian.com/suite/help/latest/monitoring_view.html).
11. [Design Patterns for Production AI Agents](https://docs.appian.com/suite/help/latest/agent-studio-design-patterns.html) · [Design Patterns (Appian RPA)](https://docs.appian.com/suite/help/latest/rpa-9.25/design-patterns.html) · [Prepare process models for AI agent tools](https://docs.appian.com/suite/help/latest/create-and-configure-ai-agent.html).
12. [Working with Email](https://docs.appian.com/suite/help/latest/email-in-appian.html) · [Send E-Mail Smart Service](https://docs.appian.com/suite/help/latest/Send_Email_Smart_Service.html) · [Configuring Custom Email Senders](https://docs.appian.com/suite/help/latest/Configuring_Custom_Email_Senders.html) · [Email on Appian Cloud](https://docs.appian.com/suite/help/latest/Email_on_Appian_Cloud.html) — plain text limits, base + runtime templates with substitution keys, custom sender / SPF-DKIM-DMARC, Reply To, From options and "Undisclosed Recipients", performance and test best practices.
13. [Post-Install Configurations — Activity-chain limits](https://docs.appian.com/suite/help/latest/Post-Install_Configurations.html#maximum-activity-instances) — `CHAINED_EXECUTION_NODE_LIMIT` (default 50, max 100, cannot be disabled) and `MAX_NODE_INSTANCES`.
14. [Process Node Properties](https://docs.appian.com/suite/help/latest/Process_Node_and_Smart_Service_Properties.html) — [Escalation tab](https://docs.appian.com/suite/help/latest/Process_Node_and_Smart_Service_Properties.html#escalation-tab) (four actions, attended nodes only, chained levels) and [Exceptions tab](https://docs.appian.com/suite/help/latest/Process_Node_and_Smart_Service_Properties.html#exceptions-tab) (Receive Message / Timer / Rule, interrupts and reroutes, no activity chaining, incompatible with autoscale) · [a!addDateTime()](https://docs.appian.com/suite/help/latest/fnc_date_and_time_adddatetime.html).
15. [Process Errors](https://docs.appian.com/suite/help/latest/Process_Errors.html) — unattended node doesn't pause vs. attended task "Paused by Exception" vs. transient errors · [Automatic Error Handling](https://docs.appian.com/suite/help/latest/Automatic_Error_Handling.html) — `safeToRetry`, retry intervals 32 s→18 h, Query Database is not retried.
16. [Process Model Object — Process model security](https://docs.appian.com/suite/help/latest/process-model-object.html#process-model-security) (does not inherit from the folder, minimum Initiator, roles Initiator/Viewer/Manager/Editor/Administrator/Deny) · [Object Security — Groups and role maps](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps) (use groups, not users).

Appian Community:

17. [KB-1248 — High memory usage (self-managed)](https://community.appian.com/support/w/kb/463/kb-1248-how-to-address-high-memory-usage-in-self-managed-appian-environments).
18. [KB-2011 — High memory usage (Appian Cloud)](https://community.appian.com/support/w/kb/1574/kb-2011-how-to-address-high-memory-usage-in-appian-cloud-environments).
19. [Playbook — Advance your Process Models](https://community.appian.com/success/w/playbook/3473/advance-your-process-models) (an index of guides; the detail lives in the linked guides).
