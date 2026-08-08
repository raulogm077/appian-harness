# Best Practices — Reliability, Consistency and Operations

> The layer that separates "works in the demo" from "holds up in production." It cuts across every
> domain: concurrency, idempotency, retries, reconciliation, observability, adversarial security
> and operational readiness. Part of this is **Appian doctrine** (carries a `Source:` pointing to
> `docs.appian.com`); part is **general distributed-systems doctrine applied to Appian** (marked
> **[engineering]**): it has no official page because it isn't platform-specific, but a CoE demands
> it just the same. Don't invent platform numbers here; the limits live in docs 03/05/07 with their
> source.

---

## 1. Consistency and Concurrency

- ⚠️ **`Write Records` does not guarantee business invariants.** It writes whatever you give it; on its own it doesn't check that two users aren't stepping on the same row, nor that the state remains valid. **[engineering]**
- ✅ **Lost update → optimistic locking.** Before writing a record that several users can edit, **re-read and compare** version/status/`lastUpdated`; if it changed since it was loaded, don't overwrite it — warn and reload. Back it with a **version column** or a **uniqueness constraint** in the DB. **[engineering]**
- ✅ **Validate on the server, not just on the screen.** The process/rule that WRITES must revalidate permissions, current state and business rules; SAIL's `showWhen`/`required`/`validations` are UX, not the last line of defense. **[engineering]** — see doc 06.
- ⚠️ **Activity chaining is NOT a transaction.** Each smart service can commit its changes before a later node fails; chaining doesn't make the chain atomic. Design the **unit of work**, the **recoverable intermediate states**, and the **compensation** for when a later step fails. The process must stay correct even if the chain breaks (see doc 03, activity chaining). **[engineering]**
- ✅ **Referential integrity lives in the DB, not in the relationship.** Record type relationships don't enforce FKs: declare PK/FK and uniqueness at the source when it matters. And watch out for **cascading deletes**: `Delete Records` on the base propagates to related rows if the FK is `ON DELETE CASCADE`. Source: [Maintaining referential integrity](https://docs.appian.com/suite/help/latest/record-type-relationships.html#relationship-considerations) — detail in doc 01.

## 2. End-to-End Idempotency

- ✅ **Every operation that creates/charges/notifies needs a stable idempotent key** that travels from the UI/Web API/event all the way through the process, the integration and persistence. Before acting, check whether that key was already processed (an *inbox*/dedup table or a **unique constraint**) and, if it already exists, return the saved result instead of repeating the operation. **[engineering]**
- ❌ **Don't blindly retry a non-idempotent write.** A retry without a key duplicates payments, case files, emails or external calls. (In integrations, classify "query" vs "modify" — doc 07.)
- ✅ **Distinguish "it failed" from "I don't know whether the remote system got to process it."** The second case calls for reconciliation (§4), not an immediate retry. **[engineering]**

## 3. Governed Retries

- ✅ **Classify the error before retrying:** transient (timeout, 429, 503 → retryable) vs permanent (400/validation → not). Apply **exponential backoff with jitter**, a **maximum number of attempts**, a **total window**, and respect `Retry-After`. Once exhausted, escalate to a human/error queue. **[engineering]**
- ✅ **Know what Appian retries on its own and what it doesn't.** Automatic handling retries certain transient smart-service errors with growing backoff (roughly 32 s → 18 h) **only if no data was modified** (`safeToRetry`); e.g. `Query Database` is **not** retried. The **Call Integration Smart Service does NOT** enter that mechanism and doesn't pause on exception either: you design the failure path yourself (timer + counter). Source: [Automatic Error Handling](https://docs.appian.com/suite/help/latest/Automatic_Error_Handling.html) — see docs 03 and 07.
- ✅ **Circuit breaker:** if a dependency degrades, stop hammering it; open the circuit, queue or degrade, and retry at spaced intervals. **[engineering]**

## 4. Reconciliation and Failed Messages

- ✅ **Functional error queue / dead letter:** whatever exhausts its retries isn't lost — it goes to a reviewable state/queue, with **safe replay** (idempotent) and a **runbook** for *poison messages*. **[engineering]**
- ✅ **Periodic reconciliation** against external systems: detect "sent without a response" operations, divergences and orphans, and correct them. Don't rely solely on the synchronous happy path. **[engineering]**
- ✅ **Outbox/inbox pattern for "update data + invoke/publish."** It avoids the inconsistent *dual-write* (writing to the DB and calling another system with no guarantee both happen). Appian Process is not a durable broker: don't use it as an implicit substitute for one. **[engineering]**

## 5. Observability and Operations

- ✅ **Correlation:** propagate a `correlationId` (and, where applicable, `causationId` + idempotent key + business reference) through the process, logs and integrations, so an operation can be traced end to end. **[engineering]**
- ✅ **Measure and alert on what breaks in production, oriented to SLOs** (not just node-level alerts): integration errors, failed/paused processes, *unattended activities*, **record sync** failures/lag, queue depth/age, latency, and **credential/certificate expiration**. Add operational dashboards, **runbooks**, escalation, and **test the alerts themselves**. **[engineering]** + Health Check (doc 05/08).
- ✅ **Capacity budget:** translate the nominal limits (700/min, MNI, 5,000 rows, timeouts — doc 05) into safe concurrency using **peak rate, p95/p99, fan-out and queue growth**, tested against a real distribution, not the average. **[engineering]**
- ✅ **Sync status as operational data:** govern *freshness*, failed/partial sync, stale data, and what gets shown to the user when the synced source isn't current. Source: [Records monitoring](https://docs.appian.com/suite/help/latest/Records_Monitoring_Details.html).

## 6. Adversarial Security (test like an attacker)

- ✅ **NEGATIVE authorization tests, by role and by channel.** For each role, try to read/modify/export/invoke what it should NOT be able to, through: interface, **direct access by URL/identifier**, record action, related action, export, report, document, Web API, integration, and process execution. The success criterion is "403 / no data," not "the button is hidden." **[engineering]** + doc 06.
- ❌ **Interface security is NOT authorization.** `showWhen`, column visibility, site navigation, and hiding actions are UX. Authorization lives in object/record/field security, process model security, Web APIs and integrations — the layer that EXECUTES. Source: [Object security](https://docs.appian.com/suite/help/latest/object-security.html).
- ⚠️ **Effective execution identity (privilege laundering).** Processes, scheduled processes, record events, integrations, Web APIs and record sync can run as the designer, the *initiator*, or a **service account**. Verify that a user can't obtain, through an operation, data/actions their own identity wouldn't permit. **[engineering]**
- ⚠️ **IDOR/BOLA:** non-guessable identifiers, and per-object authorization on every access — don't rely on the ID being "unknown." Critical on any **portal or external front end** (a Portal object or a custom-built front end). **[engineering]** + doc 06.
- ⚠️ **Restricting the record type doesn't protect the underlying source:** another object connecting to the same table can still see the data; secure the source too. Source: [Record security](https://docs.appian.com/suite/help/latest/appian-records-security.html).
- ⚠️ **Leakage through logging:** HTTP request/response logging masks credentials but stores body/headers/query params in **plain text** — don't turn it on with sensitive data. Source: [Logging](https://docs.appian.com/suite/help/latest/Logging.html) — see doc 07.
- ✅ **Recertification and auditing:** periodically review privileged groups, object/app admins, service accounts, and temporary access; define which events are auditable (effective actor + requester, before/after, timestamp, correlation, outcome) and their retention. **[engineering]**

## 7. Real-World ALM: Rollback, Promotion and Per-Environment Configuration

- ⚠️ **Versioning ≠ rollback.** Object versions and Compare & Deploy do **not** revert schema, data, groups, credentials, plug-ins, or the effects of processes that already ran; the history lives in the environment where it was created and doesn't travel in the package. Source: [Application Deployment Guidelines](https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html) — see doc 08.
- ✅ **Per-change recovery strategy:** roll-forward, **N/N-1** compatibility with in-flight processes, compensating scripts, *feature flags*, applicable backup/restore, and an **abort criterion**. **[engineering]**
- ✅ **Treat data and schema as part of the release:** **idempotent** migrations, DDL→objects→data ordering, reconciliation, and compatibility with older instances. A post-deployment process on its own doesn't cover this. **[engineering]** + doc 08.
- ✅ **Governed per-environment configuration:** inventory constants, connected systems, endpoints, IDs, flags, senders, timeouts, and credentials; use **"Environment Specific" constants + an Import Customization File**; verify no Dev values are left in Prod; secrets **never travel** in packages or show up in logs/evidence. Source: [ICF](https://docs.appian.com/suite/help/latest/Managing_Import_Customization_Files.html) — see doc 08.
- ✅ **Test the deployable ARTIFACT, not just the Dev workspace:** install the same candidate package on a clean environment, apply the customization, and run **smoke E2E + regression**; this is what surfaces implicit dependencies and missing configuration. **[engineering]** + doc 10.

## 8. Platform and Extensibility Governance

- ✅ **Plug-ins (AppMarket/third-party):** prefer native components; treat plug-ins as "use-at-your-own-risk"; inventory provenance, version, permissions, support, and **validate them against the target release BEFORE every upgrade** (on Appian Cloud upgrades are monthly and opt-in: the environment may lag behind `latest`). Source: [Shared Components](https://docs.appian.com/suite/help/latest/Shared_Components.html) — see doc 08.
- ✅ **AI (when adopted):** data/PII classification, authorized providers/models, prior evaluation + regression dataset, **human-in-the-loop** scaled to risk, defense against *prompt injection*, structural validation of the output, and **authorization downstream of the model** (never execute sensitive actions on generated text alone). **[engineering]** — applies only if the solution adopts AI.
- ✅ **RPA (when adopted):** dedicated accounts + vault (Credentials object, AES-256), least privilege, robust selectors, exception queue, and PII-free evidence. Source: [RPA security](https://docs.appian.com/suite/help/latest/rpa-9.25/security-rpa.html) — applies only if the solution adopts RPA.
- ✅ **Exception and deprecation governance:** every deviation from the standard carries a reason, risk, approver, scope, and expiry; and there's a retirement policy for unused objects, old APIs, constants, and flags (with impact analysis and an observation period). **[engineering]**

---

## Operational Readiness Gate (feeds doc 10)

Before closing a phase or calling something "done" once it reaches production, add to doc 10's 7 gates:

- ✅ Monitoring and **tested alerts** for its failure modes (integration, paused process, sync, credentials).
- ✅ A **runbook** for what to do when it fails, who recovers it, and how.
- ✅ A **rollback/roll-forward** plan and compatibility with in-flight processes.
- ✅ **E2E smoke test** from the real consumer (login/site → query → operation with persistence → integration/stub → document/notification → per-role permissions).
- ✅ **Idempotency and concurrency** tested (double click, double submit, simultaneous edit).
- ✅ **Sign-off from the operational owner** (not just the functional one).

A change that doesn't pass this gate isn't "professional," no matter how cleanly it validates and renders.
