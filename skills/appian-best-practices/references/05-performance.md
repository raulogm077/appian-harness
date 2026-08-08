# Best practices — Performance and scalability

> Official Appian doctrine for applications to load fast and scale: fetch only the data you need, don't recompute, keep processes lightweight, and measure before optimizing. Every rule is anchored to `docs.appian.com/suite/help/latest/`. The links use `latest` (an alias that redirects to the latest release; they never expire).

Cross-cutting rule that runs through the whole document: **the cheapest work is the work you don't do.** Every field you don't query, every row you don't fetch, every re-evaluation you avoid, and every process instance you archive is performance gained without writing code.

---

## 1. Methodology: measure before optimizing

✅ **Measure with diagnostic tools before touching anything.** Every object has its own instrument: `Performance Details` in interfaces, `Query Performance` in the Monitor, the optimization process reports in processes, and Health Check at the environment level. Optimizing by intuition wastes effort on something that isn't the bottleneck.
Source: [Interface Performance Best Practices](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **Test with production data volumes, not development ones.** Performance in your development environment will differ from production; for a realistic assessment, replicate production volumes in the test environment. A screen that runs fine with 10 rows can collapse with 100,000.
Source: [Asynchronous Loading — Identifying slow-loading components](https://docs.appian.com/suite/help/latest/async_loading.html)

❌ **Anti-pattern:** declaring "it's fast" after testing with tables that are nearly empty. The real cost only shows up with data.

---

## 2. Record type queries

How you retrieve data directly impacts your application's speed and responsiveness. Guiding principle: **only fetch the data you need.**

✅ **Specify the exact fields in the `fields` parameter; don't use `a!selectionFields()` in production.** The more data you query, the longer it takes to load. `a!selectionFields()` fetches all fields, including those of related record types, driving up load time. Reserve it for when you genuinely need every field.
Source: [Record Type Query Performance Best Practices](https://docs.appian.com/suite/help/latest/query-best-practices.html)

⚠️ **Trap:** if you leave `fields` empty in `a!queryRecordByIdentifier()`, only the base record type's primary key is returned. It's a silent failure: the query "works" but brings back nothing useful.
Source: [a!queryRecordByIdentifier() — Using the fields parameter](https://docs.appian.com/suite/help/latest/fnc_system_a_queryrecordbyidentifier.html)

✅ **Exclude expensive fields from high-volume queries:** *real-time custom record fields* and *Extra Long Text fields*. They're costly to return and penalize large grids and listings.
Source: [Query Performance Best Practices — Best practice checklist](https://docs.appian.com/suite/help/latest/query-best-practices.html)

✅ **Always paginate with `a!pagingInfo(startIndex, batchSize)` and filter to narrow the result set.** Returning 5,000 rows to display 5 wastes resources.
Source: [Query Performance Best Practices](https://docs.appian.com/suite/help/latest/query-best-practices.html)

❌ **Don't query inside a loop (N+1 pattern).** `a!queryRecordByIdentifier()` **should not be used inside a loop**: if you need more than one base record or more than 100 related records, query the related record type separately in a single query.
Source: [a!queryRecordByIdentifier() — Usage considerations](https://docs.appian.com/suite/help/latest/fnc_system_a_queryrecordbyidentifier.html)

✅ **Know the ceiling of each query function.** `a!queryRecordByIdentifier()` returns **one** base record and up to **250** related records per relationship (automatic batching). `a!queryRecordType()` returns one or several and up to **100** related records per relationship (manual batching with `a!pagingInfo`). Choose based on what you need: `byIdentifier` for single-record detail views; `queryRecordType` for listings.
Source: [a!queryRecordByIdentifier() versus a!queryRecordType()](https://docs.appian.com/suite/help/latest/fnc_system_a_queryrecordbyidentifier.html)

✅ **On UNsynced record types, apply filters and sorts on the base record type, not on related ones.** For complex filtering or sorting on unsynced data, consider a database view instead of resolving it in the query.
Source: [Query Performance Best Practices — Best practice checklist](https://docs.appian.com/suite/help/latest/query-best-practices.html)

⚠️ **5,000-row ceiling on record-type-powered components.** Every records-powered component (grid, chart, dropdown, checkbox…) displays a maximum of **5,000 rows**, and you shouldn't get close to that number: paginate, filter, or aggregate. It's a platform limit, not a target.
Source: [Row limit for records-powered components](https://docs.appian.com/suite/help/latest/records-powered-components.html)

✅ **Filter by indexed fields.** Filtering and sorting by columns indexed in the source database is what keeps the query fast at volume. *(The existence of the index is guaranteed at database design time; see the data model document.)*
Source: [Query Performance Best Practices](https://docs.appian.com/suite/help/latest/query-best-practices.html)

---

## 3. Interfaces: evaluation cost

Principle: **every user interaction re-evaluates the entire interface** (entering a value, pressing a button, changing a filter). Everything inside a component parameter is recomputed on every re-evaluation.

✅ **Put expensive computations in local variables, not in component parameters.** A local variable is only re-evaluated when the interface loads, when it's updated via `saveInto`, or when another local variable it references changes; a parameter is recomputed on every interaction.
Source: [Interface Performance — Local variable best practices](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **Design independent queries so they evaluate in parallel.** If a local variable holding a query references another local variable holding a query, they evaluate serially (one waits for the other). Rewrite them so they don't depend on each other and they'll evaluate at the same time, reducing total time.
Source: [Interface Performance — Set them up to evaluate in parallel](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **Defer loading slow data with asynchronous loading.** Use `a!asyncVariable()`, or the `loadDataAsync` parameter on read-only grids, charts, and KPIs powered by record data. The user sees and can interact with the rest of the screen while the slow data loads (with skeletons). Rule of thumb: apply it to any data that takes **more than 500 ms**.
Source: [Asynchronous Loading — When to enable async loading](https://docs.appian.com/suite/help/latest/async_loading.html)

❌ **Don't overuse async.** Every `a!asyncVariable()` consumes additional server resources; overusing it degrades the environment. **Recommended limit: 7 async variables per interface.** Don't apply it to data that's already fast (<500 ms): the skeleton flicker is more annoying than an instant load.
Source: [a!asyncVariable() — Performance considerations](https://docs.appian.com/suite/help/latest/fnc_evaluation_a_asyncvariable.html)

✅ **In interfaces that display a lot of data (reporting dashboards), reduce user interactions.** Every filter or editable field triggers a full re-evaluation with all its queries. Fewer interactions = less waiting.
Source: [Interface Performance — Don't add a lot of user interactions](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **In `and()`, `or()`, and `match()`, put expensive computations last.** These functions short-circuit: if a cheap earlier condition already decides the result, the expensive one never runs.
Source: [Interface Performance — Put expensive computations last](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **Don't wrap text in `a!richTextItem()` if you're not going to style it.** It's evaluation cost for nothing.
Source: [Interface Performance — Don't wrap text in a!richTextItem()](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **In grids with conditional columns, use the `fields` parameter of `a!recordData()`** to specify which fields to query and when, instead of fetching them all.
Source: [Query Performance Best Practices — Verify Grid Logic](https://docs.appian.com/suite/help/latest/query-best-practices.html)

✅ **Use `rv!identifier` in record views and related actions with dynamic start forms** to avoid over-fetching record data.
Source: [Query Performance Best Practices — Best practice checklist](https://docs.appian.com/suite/help/latest/query-best-practices.html)

✅ **`if()`, `choose()`, and `showWhen: false` don't evaluate the hidden branch or component.** This is the main lever for not paying for what isn't shown: the false branch of an `if()`/`choose()` and any component with `showWhen: false` are skipped entirely during evaluation. Break large forms (multi-step wizards) so each step is wrapped in a `choose()` or `showWhen`, so only the visible step is computed instead of the whole screen at once.
Source: [Interface Performance — Conditional logic](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **Control when a piece of data re-evaluates with `a!refreshVariable()` instead of reloading everything.** Its parameters (`refreshAlways`, `refreshInterval`, `refreshOnReferencedVarChange`, `refreshOnVarChange`, and `refreshAfter: "RECORD_ACTION"`) set exactly what triggers that variable's re-evaluation, avoiding recomputing expensive queries on every interaction. In grids and charts powered by record data, also use their refresh parameters to control when they re-query.
Source: [Interface Performance — Local variable best practices](https://docs.appian.com/suite/help/latest/interface-performance.html) · [Local Variables — a!refreshVariable()](https://docs.appian.com/suite/help/latest/Local_Variables.html)

✅ **Write memory-efficient expressions.** Three rules that bound memory consumption during evaluation: **never use `batchSize: -1`** (it fetches the result with no limit and can blow up memory — always paginate); **keep loops (`a!forEach`) under ~500 items**; and **don't nest more than 2 levels** of functions that iterate over arrays. Prefer array functions (`a!forEach`, `filter`, `reduce`) over iterating with indexes.
Source: [Expressions Best Practices — Designing memory-efficient expressions](https://docs.appian.com/suite/help/latest/expressions-best-practices.html)

---

## 4. Processes: memory footprint and scalability

Official Appian Efficiency Tip: **keep processes short-lived.** Reducing instance lifespan significantly improves memory usage and scalability.
Source: [Analyzing Process Model Performance](https://docs.appian.com/suite/help/latest/analyzing-process-model-performance.html)

✅ **Configure aggressive archiving/deletion policies for completed instances.** Completed processes that aren't archived or deleted keep occupying engine memory. Memory is only freed on engine restart, so prevention (automatic cleanup) is key.
Source: [KB-2011 How to address high memory usage in Appian Cloud](https://community.appian.com/support/w/kb/1574/kb-2011-how-to-address-high-memory-usage-in-appian-cloud-environments)

✅ **Put a timer on processes users rarely complete.** Without one, those instances live in memory forever. An `Intermediate Event - Timer` that closes the process after a deadline prevents accumulation.
Source: [KB-2011 High memory usage](https://community.appian.com/support/w/kb/1574/kb-2011-how-/to-address-high-memory-usage-in-appian-cloud-environments)

✅ **Keep process variables few and small.** Appian recommends **≤ 100 process variables** per model (more complicates maintenance and drives up memory consumption). Each version of a large PV is saved in the history and grows over time. Convert PVs into *activity class parameters* where applicable, or split into subprocesses.
Source: [Appian Design Guidance — Too many process variables](https://docs.appian.com/suite/help/latest/appian-recommendations.html)

✅ **Split large models into subprocesses.** Appian recommends **≤ 50 nodes** per model; beyond that it complicates maintenance, raises memory consumption, and lengthens completion time.
Source: [Appian Design Guidance — Too many nodes](https://docs.appian.com/suite/help/latest/appian-recommendations.html)

✅ **Remove unused process variables.** They add nothing and clutter memory and maintainability.
Source: [Appian Design Guidance — Unused process variable](https://docs.appian.com/suite/help/latest/appian-recommendations.html)

✅ **Factors that bloat a process's footprint** (review them when redesigning): the model definition and each node's, the number and **value** of process variables, the length of the process history, and any notes/attachments the instance carries. Watch them in the Monitor → *Process Model Metrics*.
Source: [Monitor View — Monitoring process model AMU](https://docs.appian.com/suite/help/latest/monitoring_view.html)

### Autoscale (advanced/premium tier)

✅ **With Autoscale, keep process variables under 5 MB.** Test with the largest data volume you expect. Prefer more small models whose PVs hold less, over a few complex models with large PVs.
Source: [Autoscale Patterns and Best Practices — Keep process variables small](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

✅ **Dynamically scale data fabric queries** to support the query load of autoscaled processes (avoids manual scaling). Requested via a support case.
Source: [Autoscale Patterns and Best Practices — Query throughput](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

⚠️ **Platform limits under Autoscale:** nodes **time out at 90 seconds**; processes start up to a maximum of **700 per minute** (above that they go to a queue of up to **1 million**; if the queue fills up, the Start Process node fails). Use batching in web API calls that start processes.
Source: [Autoscale Patterns and Best Practices](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

---

## 5. Data and records: sync vs. direct access

✅ **Prefer synced record types (Optimized Data Access)** when you want automatic performance optimization and full access to data fabric capabilities. Sync caches the data in Appian's data service, giving fast queries regardless of source complexity.
Source: [Record Type Data Access](https://docs.appian.com/suite/help/latest/about-data-sync.html)

✅ **Use Direct Data Access only** when you need real-time data modified outside Appian and syncing is impractical. It queries the source directly and depends on its native performance.
Source: [Record Type Data Access](https://docs.appian.com/suite/help/latest/about-data-sync.html)

⚠️ **Platform limits for sync (by capability tier):**

| Tier | Maximum synced rows per record type |
|---|---|
| Standard | **4 million** |
| Advanced | **20 million** |
| Premium | No fixed limit |

Additionally, **every record type supports up to 100 fields**, including custom record fields. If you expect to exceed your tier's limit, use **sync filters** or switch to direct access.
Source: [Record Type Data Access — row limits & field limit](https://docs.appian.com/suite/help/latest/about-data-sync.html)

✅ **Add sync filters to your largest synced record types** so only the data the application needs gets synced. It's the main lever for maintaining performance at high volume.
Source: [Configure Sync Options](https://docs.appian.com/suite/help/latest/records-data-sync.html)

✅ **Schedule full syncs outside peak hours**, and if you have several synced record types, stagger their full syncs at different times for optimal performance.
Source: [Configure Sync Options](https://docs.appian.com/suite/help/latest/records-data-sync.html)

✅ **Enable "Keep data available at high volumes" on your fastest-growing record types** (histories, audit logs). It's the sync option designed for high-growth record types: it sustains query performance as volume grows over time. Check its status in the record type's monitoring details.
Source: [Configure Sync Options — Keep data available at high volumes](https://docs.appian.com/suite/help/latest/records-data-sync.html) · [Records Monitoring Details](https://docs.appian.com/suite/help/latest/Records_Monitoring_Details.html)

✅ **Calculated custom record fields: sync-time vs. runtime.** *Real-time custom record fields* are computed on every query and are expensive: exclude them from high-volume queries (see §2). Sync-time calculated fields are materialized once per sync and are cheap to read, but they bypass field-level security. Choose based on cost and security.
Source: [Query Performance Best Practices — Best practice checklist](https://docs.appian.com/suite/help/latest/query-best-practices.html)

⚠️ **Write throughput under Autoscale:** if your autoscaled processes write to synced record types above **15,000 transactions per minute** (summed across all apps), apply the incremental-write guidance to work around the limit. (Don't confuse this with the "30,000/min" figure from older release notes, which was the data fabric's **general** write capacity, not this specific autoscale threshold.)
Source: [Autoscale Patterns — Write throughput considerations](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

✅ **Database indexes.** For unsynced record types, filtering/sorting by columns indexed at the source is what sustains the query at volume; for complex logic, materialize it in an indexed database view instead of in the query. *(Index design lives in the database layer.)*
Source: [Query Performance Best Practices — unsynced record types](https://docs.appian.com/suite/help/latest/query-best-practices.html)

---

## 6. Integrations

✅ **Always configure an explicit timeout on the HTTP integration.** The *Timeout (sec)* field covers the full runtime (prepare + execute + transform). **If you leave it blank, the integration runs indefinitely** until it responds or the connection fails — a hung source can block resources forever.
Source: [Integration Object — HTTP integration definition](https://docs.appian.com/suite/help/latest/Integration_Object.html)

✅ **Asynchronous loading for slow integrations in interfaces.** Async loading (§3) is designed precisely for "slow external systems you don't control": the user isn't blocked waiting on a third party.
Source: [Interface Performance Best Practices](https://docs.appian.com/suite/help/latest/interface-performance.html)

✅ **In processes, protect external calls with retries and avoid long-running ones.** In automated processes, nodes time out at 90 s; build a retry pattern with a timer + counter for unreliable sources instead of leaving the node waiting.
Source: [Autoscale Patterns — Avoid long-running calls to external systems](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

⚠️ **Size limits on the HTTP integration body:** the request body cannot exceed **5 MB** (the size of documents sent doesn't count toward this limit); base64 files, up to **75 MB** combined; binary files, recommended to keep them under **250 MB**.
Source: [Integration Object — Body size limitations](https://docs.appian.com/suite/help/latest/Integration_Object.html)

✅ **Synchronous by default, asynchronous for what's parallelizable.** A synchronous call guarantees the step finishes before continuing and gives consistent output; reserve async for tasks that can run in parallel (e.g., confirming by email while other processing continues). *(The doctrine is written for AI agent calls, but the sync-vs-async criterion is cross-cutting.)*
Source: [AI Agents FAQ — synchronous versus asynchronous](https://docs.appian.com/suite/help/latest/ai-agents-faq.html)

---

## 7. Diagnostic tools

✅ **Interfaces → Performance Details.** Run an evaluation and review *Parameters and Direct Children* to locate the slowest local variables or components. Watch out: async variables always show up as `<1 ms`, it doesn't measure their real time.
Source: [Asynchronous Loading — Identifying slow-loading components](https://docs.appian.com/suite/help/latest/async_loading.html)

✅ **Queries → Monitor's Query Performance tab.** Monitor your queries as you build them and identify which ones to improve.
Source: [Query Performance Best Practices](https://docs.appian.com/suite/help/latest/query-best-practices.html)

✅ **Processes → optimization process reports + Monitor.** `Default Process Model Optimization Metrics` (average lag and completion) and `Default Process Optimization Metrics` (actual lag and completion) flag bottlenecks per node. The Monitor → *Process Model Metrics* shows memory (AMU), instance count, and % completion.
Source: [Analyzing Process Model Performance](https://docs.appian.com/suite/help/latest/analyzing-process-model-performance.html)

✅ **Environment → Health Check.** Run it regularly on every environment, **including Production**. It monitors server metrics (CPU, heap, disk), detects design and performance risks, and tracks capacity trends. Available to system administrators in the Admin Console; reports are managed from MyAppian.
Source: [Health Check](https://docs.appian.com/suite/help/latest/health-check.html) · [Monitoring Applications](https://docs.appian.com/suite/help/latest/monitoring-applications.html)

✅ **Log analysis.** During data collection, Health Check generates a zip with Appian's logs plus information on design patterns, configurations, and objects — a starting point for performance log analysis.
Source: [Monitoring Applications](https://docs.appian.com/suite/help/latest/monitoring-applications.html)

---

## 8. Actionable summary (KPIs and limits)

**Performance KPIs to watch:** interface evaluation time (Performance Details), query time (Query Performance), per-node lag/completion (process reports), process AMU and % completion (Monitor), environment CPU/heap/disk (Health Check).

**Platform limits cited** (all with sources above).

> Note the distinction the table blurs: **hard limits** (technical ceilings the platform enforces)
> versus **recommended thresholds** — marked *(recommended)* — from Appian Design Guidance and Health
> Check. The latter are design indicators, not barriers: exceeding them **warns, it doesn't block**, and
> splitting an object purely to comply with them can hurt traceability. Tier limits and platform
> limits **change between releases**: if a decision depends on the exact number, confirm it for
> your environment before designing around it.

Other limits live in their own domain doc with their source: calculated fields per record type, text
lengths and unique fields (doc 01), record type query timeout (doc 02), MNI and Write Records per node
(doc 03), default sync for a web service source (doc 07).

| Scope | Limit | Source |
|---|---|---|
| Synced rows / record type | 4 M (Standard) · 20 M (Advanced) · no limit (Premium) | about-data-sync |
| Fields per record type | 100 (incl. custom fields) | about-data-sync |
| Related records per query | 100 (`queryRecordType`) · 250 (`byIdentifier`) | queryRecordByIdentifier |
| Rows in records-powered component (grid/chart/dropdown…) | 5,000 | records-powered-components |
| Async variables per interface | 7 (recommended) | async_loading |
| Threshold for async loading | > 500 ms | async_loading |
| Nodes per process model | 50 (recommended) | appian-recommendations |
| Process variables per model | 100 (recommended) | appian-recommendations |
| Process variable size (Autoscale) | 5 MB | autoscale-patterns-practices |
| Node timeout (automated processes) | 90 s | autoscale-patterns-practices |
| Process starts (Autoscale) | 700/min · queue of 1 M | autoscale-patterns-practices |
| Writes to synced record (Autoscale) | 15,000 transactions/min | autoscale-patterns-practices |
| HTTP integration body | 5 MB (body) · 75 MB (base64) · 250 MB (binary, recommended) | Integration_Object |

---

## Sources

- [Record Type Query Performance Best Practices](https://docs.appian.com/suite/help/latest/query-best-practices.html)
- [Row limit for records-powered components (5,000 rows)](https://docs.appian.com/suite/help/latest/records-powered-components.html)
- [a!queryRecordByIdentifier() Function](https://docs.appian.com/suite/help/latest/fnc_system_a_queryrecordbyidentifier.html)
- [Interface Performance Best Practices](https://docs.appian.com/suite/help/latest/interface-performance.html)
- [Local Variables (a!refreshVariable())](https://docs.appian.com/suite/help/latest/Local_Variables.html)
- [Expressions Best Practices (memory-efficient expressions)](https://docs.appian.com/suite/help/latest/expressions-best-practices.html)
- [Asynchronous Loading](https://docs.appian.com/suite/help/latest/async_loading.html)
- [a!asyncVariable() Function](https://docs.appian.com/suite/help/latest/fnc_evaluation_a_asyncvariable.html)
- [Analyzing Process Model Performance](https://docs.appian.com/suite/help/latest/analyzing-process-model-performance.html)
- [Monitor View — Process Model Metrics](https://docs.appian.com/suite/help/latest/monitoring_view.html)
- [Appian Design Guidance (Recommendations)](https://docs.appian.com/suite/help/latest/appian-recommendations.html)
- [Autoscale Patterns and Best Practices](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)
- [Record Type Data Access (about-data-sync)](https://docs.appian.com/suite/help/latest/about-data-sync.html)
- [Configure Sync Options (records-data-sync)](https://docs.appian.com/suite/help/latest/records-data-sync.html)
- [Records Monitoring Details](https://docs.appian.com/suite/help/latest/Records_Monitoring_Details.html)
- [Integration Object](https://docs.appian.com/suite/help/latest/Integration_Object.html)
- [AI Agents FAQ](https://docs.appian.com/suite/help/latest/ai-agents-faq.html)
- [Health Check](https://docs.appian.com/suite/help/latest/health-check.html)
- [Monitoring Applications](https://docs.appian.com/suite/help/latest/monitoring-applications.html)
- [KB-2011 How to address high memory usage in Appian Cloud environments](https://community.appian.com/support/w/kb/1574/kb-2011-how-to-address-high-memory-usage-in-appian-cloud-environments)
