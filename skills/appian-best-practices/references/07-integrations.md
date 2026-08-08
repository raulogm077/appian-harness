# Best practices — Integrations and connectivity

> Official Appian doctrine for connecting your applications to external systems: connected systems, integration objects, Web APIs, use in processes and interfaces, record types over web services, and automation (RPA / AI). Each rule is anchored to official Appian documentation. Links use `/suite/help/latest/`, which always redirects to the latest published version. (Exception: **Appian RPA** pages are published under their own product version — `…/latest/rpa-9.25/…` —; that is their canonical path within `/latest/`, not a platform version pin.)

Convention: ✅ = do this · ❌ = anti-pattern. Each block closes with **Source:**.

---

## 1. Connected systems: separate credentials from the integration object

The connected system is where the connection lives (base URL + authentication); the integration object only describes the specific call. Never mix the two.

✅ **Centralize credentials and the base URL in a connected system, not in the integration.** A connected system is "a centralized location to manage credentials" and lets "multiple integrations that connect to the same external service" share configuration. That way you deploy different configurations per environment (Dev, Test, Prod) without touching the integration.
**Source:** [Connected System Object](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)

✅ **For an API key, ALWAYS configure it in the connected system, never in loose headers/parameters of the integration.** Literal quote: "the only way to securely configure an API key for an integration is by using the connected system object". The `Value` field is **Sensitive**: it is masked and must be treated as a password.
**Source:** [Authentication Types — API key properties](https://docs.appian.com/suite/help/latest/connected_system_authentication.html)

✅ **Trust that `Sensitive` fields don't leak.** "All fields marked Sensitive will never be logged as part of HTTP request/response logging for integrations or exported in an import customization file". That's why, when promoting between environments, secrets have to be **re-entered by hand** (they don't travel in the export).
**Source:** [Authentication Types](https://docs.appian.com/suite/help/latest/connected_system_authentication.html) · [Connected System Object — import/export](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)

⚠️ **Don't turn on HTTP request/response logging when sensitive data travels through the integration.** Masking protects **only** the fields marked `Sensitive`: the **body, headers and query params** of the request and response are logged in **plain text**. This becomes critical as soon as the solution moves data subject to confidentiality (compensation, health, personal, or field-level-security-protected data): it must not pass through an integration with logging enabled. Turn it on only to debug, with non-sensitive data, and turn it off when done.
**Source:** [HTTP request/response logs](https://docs.appian.com/suite/help/latest/Logging.html) · [Web APIs](https://docs.appian.com/suite/help/latest/Web_APIs.html)

❌ **Don't put username/password or tokens in the URL, parameters or body of the integration.** Those values aren't masked, can be seen, and get exported. If the external system forces "None" authentication, upload the client/server certificate in the Admin Console instead of embedding secrets.
**Source:** [Authentication Types — None](https://docs.appian.com/suite/help/latest/connected_system_authentication.html)

✅ **Restrict who can use the connected system with object security.** Its role map controls who can **reference the credentials** from an integration; limit it to the designers who need it instead of leaving it open. The credentials are masked, but the object wrapping them is still a point of access.
**Source:** [Connected System Object — security](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)

✅ **For non-sensitive values that change between environments (variable endpoint/base URL, username, flags), use constants marked "Environment Specific" + the Import Customization File (ICF).** Mark the constant as *Environment Specific* and set its value per environment in the deployment's ICF, instead of editing the integration by hand after every promotion. Credentials and the connected system still go through the `Sensitive` field / manual re-entry (above), never through a constant.
**Source:** [Constants](https://docs.appian.com/suite/help/latest/Constants.html) · [Application Deployment Guidelines — rules](https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html)

---

## 2. Connected system types and authentication

✅ **Choose the connected system type according to the destination.** Standard: **HTTP** (REST) and **OpenAPI** (from an OpenAPI specification). Database: **data source** (supported databases: Aurora MySQL, PostgreSQL, Oracle, SQL Server…) and **custom JDBC** for unsupported ones. Streaming: **Apache Kafka**. Third-party templates: Salesforce, Microsoft Dynamics 365, DocuSign, Google Drive, Snowflake, MCP…
**Source:** [Connected System Object](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)

✅ **Use the supported authentication method that fits.** For HTTP/OpenAPI, the dropdown offers: **None**, **API Key**, **Basic**, **OAuth 2.0: Authorization Code Grant**, **OAuth 2.0: Client Credentials Grant**, **AWS Signature Version 4** and **Google Service Account**. Appian officially supports the **authorization code** and **client credentials** grant types of OAuth 2.0 (RFC 6749).
**Source:** [Authentication Types](https://docs.appian.com/suite/help/latest/connected_system_authentication.html) · [OAuth 2.0: Client Credentials Grant](https://docs.appian.com/suite/help/latest/oauth_client_credentials.html)

✅ **Client Credentials for system-to-system calls; Authorization Code when each user acts on their own behalf.** Client Credentials "is used when access is being requested on behalf of an application, not a user". Authorization Code requires giving the user a way to authorize (authorization link).
**Source:** [OAuth 2.0: Client Credentials Grant](https://docs.appian.com/suite/help/latest/oauth_client_credentials.html) · [OAuth 2.0: Authorization Code Grant](https://docs.appian.com/suite/help/latest/Oauth_connected_system.html)

✅ **Let Appian manage the OAuth token lifecycle.** With Client Credentials, when a call returns `401`, `403` or `404`, Appian treats the token as revoked/expired, requests a new one from the token endpoint, and **automatically retries** the integration. Don't implement the refresh yourself.
**Source:** [OAuth 2.0: Client Credentials Grant — Access token expiration](https://docs.appian.com/suite/help/latest/oauth_client_credentials.html)

✅ **Certificates and proxy are platform configuration, not code.** Mutual SSL / client certificates and trusted server certificates (self-signed/internal) are uploaded in the **Admin Console**; the HTTP proxy is also enabled there.
**Source:** [Authentication Types — None](https://docs.appian.com/suite/help/latest/connected_system_authentication.html) · [Design Considerations](https://docs.appian.com/suite/help/latest/restrictions-and-limitations.html)

---

## 3. Integration object: query vs modify, timeout, errors

✅ **Correctly classify each integration as "query data" or "modify data".** This choice isn't cosmetic: it determines **where** it can be called and protects against duplicate changes. Official rule:

| Location | Query Data | Modify Data |
|---|---|---|
| Expression or rule | ✔ | |
| `saveInto` of an interface component | ✔ | ✔ |
| Web API (GET) | ✔ | |
| Web API (POST, PUT, DELETE) | ✔ | ✔ |
| Process Model (Call Integration Smart Service) | ✔ | ✔ |

**Source:** [Call an Integration — Querying vs Modifying Data](https://docs.appian.com/suite/help/latest/Call_an_Integration.html)

❌ **Don't mark an integration with side effects as "query".** Appian's canonical example: processing a card charge is "modify"; if marked "query" and called twice, "the customer would be charged twice for the same purchase". An operation with side effects must go through a smart service, saveInto or Web API POST/PUT/DELETE — never in an expression/rule that could be re-evaluated.
**Source:** [Call an Integration](https://docs.appian.com/suite/help/latest/Call_an_Integration.html) · [Functions with side effects](https://docs.appian.com/suite/help/latest/functions-side-effects.html)

✅ **Configure the integration timeout.** It is "the time, in seconds, after which an integration should time out and throw an integration error if a response hasn't been returned", and it covers the entire runtime (prepare + execute + transform). If you leave it blank, execution can hang indefinitely waiting for a response.
**Source:** [Integration Object](https://docs.appian.com/suite/help/latest/Integration_Object.html)

✅ **Always handle the response of a query integration.** It returns a dictionary with `success` (Boolean), `result` (HttpResponse), `error` (IntegrationError) and `connectedSystem`. Branch on `success` before using `result`:
```
a!localVariables(
  local!externalQuery: rule!GetUnsettledTransactionList(),
  local!value: if(local!externalQuery.success,
    local!externalQuery.result,
    local!externalQuery.error
  )
)
```
**Source:** [Call an Integration — Query Data](https://docs.appian.com/suite/help/latest/Call_an_Integration.html)

✅ **Customize errors with `a!integrationError()`.** The IntegrationError has `title` (summary), `message` (specific message) and `detail`. Return useful messages instead of the generic one.
**Source:** [Integration Object](https://docs.appian.com/suite/help/latest/Integration_Object.html)

⚠️ **Respect the size limits.** JSON/XML request body: 5 MB (up to 75 MB in base64). Response-to-Appian-document conversion: up to 250 MB. Design with pagination (see §7) if you expect large responses.
**Source:** [Integration Object](https://docs.appian.com/suite/help/latest/Integration_Object.html)

✅ **Test the integration with "Test Request" before wiring it into processes or interfaces.** The designer shows the HTTP Request / HTTP Response tabs and the per-phase timings (prepare / execute / transform), so you validate auth, headers and mapping without building anything around it. Watch out: in that view **the response body is truncated to 10 KB** — for large responses validate the structure, not the volume (that's covered by the pagination in §7).
**Source:** [Create an Integration — Test the integration](https://docs.appian.com/suite/help/latest/Create_an_Integration.html)

---

## 4. Synchronous calls (interface/rule) vs asynchronous calls (process)

✅ **Query external data synchronously only when the user needs the result on screen; always write/modify from a process.** "Modify" integrations can't even be called in expressions: they go through the Call Integration Smart Service. This separates reading (cheap, retryable) from writing (with effects).
**Source:** [Call an Integration](https://docs.appian.com/suite/help/latest/Call_an_Integration.html) · [Call Integration Smart Service](https://docs.appian.com/suite/help/latest/Call_Integration_Smart_Service.html)

✅ **For slow external systems in an interface, load asynchronously with `a!asyncVariable()`.** Official recommendation: use it for data that takes more than **500 ms**; "This allows users to interact with the rest of the interface while waiting for the external system".
**Source:** [Call an Integration to Query Data — Tip](https://docs.appian.com/suite/help/latest/Call_an_Integration.html) · [Asynchronous Loading](https://docs.appian.com/suite/help/latest/async_loading.html)

❌ **Don't overuse `a!asyncVariable()`: 7 per interface maximum.** "Limit the number of async variables to 7 per interface for the best performance". Each one consumes server resources; start with the slowest and don't apply it to data that already loads fast.
**Source:** [Asynchronous Loading — Performance considerations](https://docs.appian.com/suite/help/latest/async_loading.html)

❌ **Don't fire integrations inside an interface loop (e.g. one call per row in an `a!forEach`).** Every interface evaluation would re-launch all the calls, hurting performance; Appian's performance guidance insists on not re-executing expensive queries on every evaluation and on moving heavy work to cached local variables. If you need N calls, make them in a process (batched/parallel), not in the interface.
**Source:** [Asynchronous Loading — Performance and resource considerations](https://docs.appian.com/suite/help/latest/async_loading.html) · [SAIL Design — Local Variables](https://docs.appian.com/suite/help/latest/SAIL_Performance.html) *(anti-pattern inferred from the performance guidance; Appian does not publish a literal rule "no integrations in interface loops")*

⚠️ **The query result cache only lives within a single expression evaluation.** If you call twice with the same parameters within the same expression, only one request is made and the result is reused; but it does **not** persist across evaluations or across different expressions. Don't rely on it as an application-level cache.
**Source:** [webservicequery() — Usage considerations](https://docs.appian.com/suite/help/latest/fnc_scripting_webservicequery.html)

---

## 5. Integrations inside processes: errors, timeouts and retries

✅ **Handle failure with the `Success`/`Error` outputs of the Call Integration Smart Service.** Key point: "This node does not pause by exception if an integration error occurs" and "does not automatically retry failed requests". In other words, an integration error does **not** stop the flow by exception nor retry itself: you decide the path (escalation, notification, etc.).
**Source:** [Call Integration Smart Service — Node outputs](https://docs.appian.com/suite/help/latest/Call_Integration_Smart_Service.html)

⚠️ **Account for the 90-second-per-node limit.** "All nodes time out after 90 seconds". Verify in testing that no external call comes close to that limit.
**Source:** [Autoscale Patterns and Best Practices — Avoid long-running calls](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

✅ **Build explicit retries with a timer + counter pattern when the external system is unreliable.** The official pattern: an XOR checks whether the expected response arrived; if not, a **timer event** waits (e.g. 30 s), a script task increments a retry counter, and after several failed attempts it **notifies the administrator** to investigate. Don't retry in an infinite loop.
**Source:** [Autoscale Patterns — retry loop with timer](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)

ℹ️ **Distinguish platform-automatic retry from the retry you design yourself.** Some operations retry on their own after transient time-out errors **only when no data has been modified** (safeToRetry): for example, the **Call Web Service Smart Service** retries on 503/408, with intervals that double (32 s, 64 s, 127 s…). The **Call Integration Smart Service does NOT** enter that mechanism. Don't mix up the two mental models.
**Source:** [Automatic Error Handling](https://docs.appian.com/suite/help/latest/Automatic_Error_Handling.html)

---

## 6. Web APIs exposed by Appian: design, security, versioning

✅ **Keep the logic in expression rules and let the Web API only orchestrate and return `a!httpResponse()`.** A Web API "are created much like expression rules" and **all of them must return an HTTP Response**. Reuse testable rules instead of writing the logic inside the endpoint.
**Source:** [Web APIs](https://docs.appian.com/suite/help/latest/Web_APIs.html) · [Create Web APIs](https://docs.appian.com/suite/help/latest/Designing_Web_APIs.html)

✅ **Authenticate with an API key (service account) for system calls; never with a session from outside.** There are five methods: **API key**, **Basic**, **OAuth 2.0 Client Credentials**, **mTLS** and **session-based** — and "If you wish to invoke an Appian Web API from another system, you cannot use session-based authentication". Advantages of the API key: random (not usable to log in), "up to 10x faster" than username/password, and it doesn't expire on its own.
**Source:** [Web API Authentication](https://docs.appian.com/suite/help/latest/Web_API_Authentication.html)

✅ **Prepare service accounts to promote permissions between environments.** Each API key is tied to a service account that must have access to the Web API via groups. Create them with the **same username** and in the **same groups** in every environment; API keys are **per environment** (they are not promoted).
**Source:** [Web API Authentication — Service Accounts](https://docs.appian.com/suite/help/latest/Web_API_Authentication.html)

✅ **Return correct HTTP codes, including error ones.** You can set the response status code ("return a `404` code if data that does not exist is requested"). Remember: a non-existent endpoint or one without viewer permission gives `404`; an evaluation error or a response that isn't an HTTP Response gives `500`.
**Source:** [Web APIs — HTTP status codes](https://docs.appian.com/suite/help/latest/Web_APIs.html)

✅ **In write Web APIs (POST/PUT/DELETE/PATCH), use the smart service's `onSuccess`/`onError`.** Every executable smart service inside a Web API expects an `a!httpResponse()` in `onSuccess` and another in `onError`: 200 with the body on success, 500 with an error message on failure.
**Source:** [Create Web APIs — Executing a smart service](https://docs.appian.com/suite/help/latest/Designing_Web_APIs.html)

⚠️ **Configure CORS carefully: exposing an origin disables CSRF protection for write methods.** Allowed origins are declared in the Admin Console; "For POST, PUT, DELETE, and PATCH web APIs, adding a website to the allowed origins list will also exempt that website from Appian's built-in cross-site request forgery (CSRF) protection". Add only trusted origins.
**Source:** [Web APIs — Cross-origin requests](https://docs.appian.com/suite/help/latest/Web_APIs.html)

✅ **Version by convention in the endpoint (e.g. `/myapi/v1/...`).** The method + endpoint combination must be unique across the whole system, and the endpoint "will be seen by end users and in log files". Appian doesn't offer a native versioning mechanism for the Web API object, so versioning is managed by naming endpoints and keeping the old one alive while there are still consumers.
**Source:** [Create Web APIs](https://docs.appian.com/suite/help/latest/Designing_Web_APIs.html) *(versioning in the path is a design convention; Appian does not document formal Web API versioning — verify case by case)*

✅ **Pay attention to the Web API editor's design guidance.** **Warnings** cannot be dismissed and "should always be addressed"; recommendations can be dismissed one by one if they don't apply. It also shows up in the Health Dashboard.
**Source:** [Web APIs — Design guidance](https://docs.appian.com/suite/help/latest/Web_APIs.html)

---

## 7. Record types over external services and pagination

✅ **To expose web service data as a record type, build: connected system → integration → record data source (expression rule).** The record data source is an expression rule that calls the integration and returns the `body`. Requirements: cast to List of Map / Dictionary / CDT and **every row must have a non-null Number(Integer) field as its primary key**.
**Source:** [Connect a Record Type to a Web Service](https://docs.appian.com/suite/help/latest/configure-record-data-source.html)

❌ **Don't use query functions inside the record data source.** "The expression does not use plug-ins or any of the following functions: `a!query`, `a!queryEntity`, `a!queryProcessAnalytics`, `a!queryRecordType`". The data source only transforms the integration's response.
**Source:** [Configure Record Data Source](https://docs.appian.com/suite/help/latest/configure-record-data-source.html)

✅ **Prefer Optimized Data Access (synced) for most cases.** It syncs the data as a cache ("Appian only has to execute queries against your synced data instead of the external source") and enables relationships, smart search and analytics in Process HQ. Row limits depend on the tier (Standard 4M, Advanced 20M, Premium with no fixed limit). Use **sync filters** to avoid pulling in unnecessary data.
**Source:** [Data Access for Record Types — Optimized data access](https://docs.appian.com/suite/help/latest/about-data-sync.html)

✅ **Paginate large responses with batching; by default only 1,000 rows are synced.** Choose the method based on how the external API paginates: **sequential values** (`batchNumber`, with `startIndex = 1 + ((batchNumber - 1) * batchSize)`), **cursor/token** (`nextPageUri` + `a!pageResponse()`), or **full URL/URI**. Increase the per-page `limit` to reduce the total number of calls.
**Source:** [Batch by sequential values / cursor or token](https://docs.appian.com/suite/help/latest/configure-record-data-source.html) · [Service-Backed Record Tutorial](https://docs.appian.com/suite/help/latest/Service-Backed_Record_Tutorial.html)

✅ **End pagination cleanly and handle the "out of range" case.** Use `a!defaultValue()` to pass null when there is no next page (so the sync stops), and handle `statusCode` 416 by returning an empty list to end the sync instead of propagating the error.
**Source:** [Batch by cursor or token](https://docs.appian.com/suite/help/latest/configure-record-data-source.html)

---

## 8. RPA (robotic tasks) and AI at a high level: when to integrate

✅ **RPA only for systems WITHOUT an API.** Official rule: "Use the robotic task for interacting with third party systems that don't have APIs" (logins, navigation, reading/writing in the third-party app) and "Use Appian expressions and process models for anything else, including... interacting with systems that have APIs". Rule of thumb: if something can be done low-code in Appian (expression/process), do it that way; if not, RPA.
**Source:** [Design Patterns (Appian RPA)](https://docs.appian.com/suite/help/latest/rpa-9.25/design-patterns.html)

✅ **Orchestrate RPA from the process and pull business logic out into expression rules.** Start the robotic task with the **Execute Robotic Task smart service** (synchronous, saves outputs into process variables); inside the task, run calculations and validations via the **Evaluate expression** action calling an expression rule (reusable and testable), not inline.
**Source:** [Design Patterns (Appian RPA)](https://docs.appian.com/suite/help/latest/rpa-9.25/design-patterns.html)

✅ **AI: synchronous calls by default; asynchronous only for parallelizable work.** For AI agents, "For most scenarios, use a synchronous AI agent call... For tasks that can run in parallel... asynchronous calls reduce wait time". Also, offload programmable tasks outside the agent and query data with expression rules (less consumption, more reliable).
**Source:** [AI Agents FAQ — synchronous vs asynchronous](https://docs.appian.com/suite/help/latest/ai-agents-faq.html)

---

## 9. Secret hygiene (applies to keys of any integration)

✅ **Never hardcode keys or commit them to version control; rotate them periodically.** Official guidance (RPA management APIs, general principle): "Never hardcode API keys in scripts or commit them to source control", store them in a secrets manager, inject them at runtime, and "Rotate the API key on a regular schedule". In Appian, the equivalent is the connected system's Sensitive field (§1).
**Source:** [Integrate RPA Management APIs with External Tools](https://docs.appian.com/suite/help/latest/rpa-9.25/how-to-integrate-rpa-apis.html)

✅ **Use a dedicated service account for automation, not a personal one.** "Avoid using a personal user account — if that account is deactivated, your automation will break".
**Source:** [Integrate RPA Management APIs with External Tools](https://docs.appian.com/suite/help/latest/rpa-9.25/how-to-integrate-rpa-apis.html)

---

## Sources

- [Connected System Object](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)
- [Authentication Types (connected systems)](https://docs.appian.com/suite/help/latest/connected_system_authentication.html)
- [OAuth 2.0: Client Credentials Grant](https://docs.appian.com/suite/help/latest/oauth_client_credentials.html)
- [OAuth 2.0: Authorization Code Grant](https://docs.appian.com/suite/help/latest/Oauth_connected_system.html)
- [Connected System Plug-in — Design Considerations](https://docs.appian.com/suite/help/latest/restrictions-and-limitations.html)
- [Integration Object](https://docs.appian.com/suite/help/latest/Integration_Object.html)
- [Create an Integration (Test the integration)](https://docs.appian.com/suite/help/latest/Create_an_Integration.html)
- [Call an Integration (query vs modify)](https://docs.appian.com/suite/help/latest/Call_an_Integration.html)
- [Functions with side effects](https://docs.appian.com/suite/help/latest/functions-side-effects.html)
- [Call Integration Smart Service](https://docs.appian.com/suite/help/latest/Call_Integration_Smart_Service.html)
- [Autoscale Patterns and Best Practices](https://docs.appian.com/suite/help/latest/autoscale-patterns-practices.html)
- [Automatic Error Handling](https://docs.appian.com/suite/help/latest/Automatic_Error_Handling.html)
- [Asynchronous Loading (a!asyncVariable)](https://docs.appian.com/suite/help/latest/async_loading.html)
- [SAIL Design / Performance — Local Variables](https://docs.appian.com/suite/help/latest/SAIL_Performance.html)
- [webservicequery() — Usage considerations](https://docs.appian.com/suite/help/latest/fnc_scripting_webservicequery.html)
- [Web APIs](https://docs.appian.com/suite/help/latest/Web_APIs.html)
- [Create Web APIs](https://docs.appian.com/suite/help/latest/Designing_Web_APIs.html)
- [Web API Authentication](https://docs.appian.com/suite/help/latest/Web_API_Authentication.html)
- [a!httpResponse()](https://docs.appian.com/suite/help/latest/fnc_system_a_httpresponse.html)
- [Data Access for Record Types (data sync)](https://docs.appian.com/suite/help/latest/about-data-sync.html)
- [Connect a Record Type to a Web Service](https://docs.appian.com/suite/help/latest/configure-record-data-source.html)
- [Service-Backed Record Tutorial](https://docs.appian.com/suite/help/latest/Service-Backed_Record_Tutorial.html)
- [Design Patterns (Appian RPA)](https://docs.appian.com/suite/help/latest/rpa-9.25/design-patterns.html)
- [Integrate RPA Management APIs with External Tools](https://docs.appian.com/suite/help/latest/rpa-9.25/how-to-integrate-rpa-apis.html)
- [AI Agents FAQ](https://docs.appian.com/suite/help/latest/ai-agents-faq.html)
- [Logging (HTTP request/response logs)](https://docs.appian.com/suite/help/latest/Logging.html)
- [Constants (Environment Specific)](https://docs.appian.com/suite/help/latest/Constants.html)
- [Application Deployment Guidelines](https://docs.appian.com/suite/help/latest/Application_Deployment_Guidelines.html)
