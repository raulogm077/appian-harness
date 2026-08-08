# Best practices — Security

> Official Appian doctrine for designing an application's security: the group model, object security, the five security layers of the record type, credential management, least privilege and governance. Every rule is anchored to the official documentation (`docs.appian.com/.../latest/...`). Product focus, not tooling.

Version note: the links use the `latest` alias, which redirects to the latest monthly release. The doctrine on this page has been stable from 25.4 through 26.6; recent naming changes (e.g. *Default Filters* → *Security Expressions*) are flagged where they apply. (The linked **Appian RPA** pages carry their own product version — `…/latest/rpa-9.25/…` —: that is their canonical path, not a platform pin.)

---

## 1. Group model and role maps

Object security in Appian is two coupled concepts: **groups** and **role maps**. A role map associates groups (or users) with a permission level on an object; **every object has exactly one role map**.

✅ **ALWAYS configure security with groups, never with individual users.**
You control access by changing group membership, without touching the object's role map. Also, not every user exists in every environment: using groups guarantees that permissions travel correctly when objects are promoted to higher environments.
Anti-pattern: adding `john.smith` directly to an interface's role map. Appian flags it with the warning *"Individual user detected"*.
Source: [Object Security — Groups and role maps](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps) · [Warnings](https://docs.appian.com/suite/help/latest/object-security.html#warnings)

✅ **Create a group for every business role in the organization and assign permissions to the group, not the user.**
Appian's literal recommendation: "instead of assigning rights to each user, create a custom group for each role in your organization, assign rights by group, and add the users of that role to the group".
Source: [Manage user rights and security](https://docs.appian.com/suite/help/latest/User_Management.html#manage-user-rights-and-security)

✅ **Use group types to classify groups and share attributes across them.**
A group type (e.g. "Region") organizes groups by category and can require common attributes (e.g. "Regional VP"). Only a System Administrator can create group types.
Source: [Creating Groups — Overview](https://docs.appian.com/suite/help/latest/Creating_Groups.html) · [Group objects](https://docs.appian.com/suite/help/latest/design-objects.html#group-objects)

✅ **Understand that administration and membership propagate in opposite directions through the group hierarchy.**
**Membership flows upward**: a member of a subgroup is a member of the parent group. **Administration flows downward**: the administrator of a group administers its subgroups, but not its parent. Design with this in mind so you don't grant excess visibility when nesting groups.
Source: [Group Administration Versus Group Membership](https://docs.appian.com/suite/help/latest/Creating_Groups.html#main_content)

❌ **Do not duplicate a group or user within the same role map.**
Appian warns with *"Duplicate entries detected"*. If duplicates exist, the highest permission always applies. A user who is a member of several groups in the role map receives **their highest permission** (Administrator beats Viewer).
Source: [Object Security — Groups and role maps](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps) · [Warnings](https://docs.appian.com/suite/help/latest/object-security.html#warnings)

---

## 2. Permission levels and the Deny permission

✅ **In practice, configure only two levels: Administrator and Viewer.**
Appian: "in most cases you'll only need Administrator and Viewer". Administrator can edit/delete the object; Viewer can use it as an end user (Tempo, sites, embedded). The set of available levels depends on the object type: rule folders accept Viewer/Editor/Administrator/Deny; process models add **Initiator** and **Manager**; record types use Viewer/Editor/Administrator plus **Data Steward** (which does not show the record type in sites/Tempo, only enables it as a Process HQ dataset — see §5).
Source: [Permission levels in role maps](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps)

✅ **Assign every object at least one Administrator group and at least one Viewer/Editor group.**
Without an administrator group, no basic user will be able to administer it (warning *"Missing administrator group"*). Without a viewer/editor group, nobody but administrators and system administrators will be able to see it (*"Missing viewer or editor group"*).
Source: [Warnings](https://docs.appian.com/suite/help/latest/object-security.html#warnings)

✅ **Use Deny only to revoke access inherited from a nested group.**
Deny is equivalent to not being in the role map, except that it **overrides any other permission** the group would otherwise have through nesting. This is the only legitimate case: group A must not have access, but is nested inside group B which does — mark A with Deny.
Source: [Deny permission level](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps)

❌ **Do not set Default (All Other Users) to Administrator.**
This grants administration to every user in the role map who lacks an explicit Deny. Appian flags it (*"Default set to administrator"*) and recommends giving Administrator to specific groups.
Source: [Warnings](https://docs.appian.com/suite/help/latest/object-security.html#warnings)

---

## 3. Security inheritance

✅ **Set security on top-level objects (knowledge centers and rule folders) and let nested objects inherit it.**
Appian's literal recommendation: doing so keeps security consistent and easy to manage in large applications. A rule folder's security is inherited by default by every interface, constant, expression rule, decision and integration it contains; a knowledge center's security is inherited by its folders and documents.
Source: [Security inheritance](https://docs.appian.com/suite/help/latest/object-security.html#security-inheritance)

✅ **Know the inheritance behavior per object type before you design the folder structure.**
There are five categories: *always inherit* (documents, process reports), *inherit if a parent is specified* (groups, knowledge centers), *inherit by default but editable* (constants, decisions, expression rules, integrations, interfaces, rule folders...), *never inherit* (applications, record types, process models, sites, connected systems, web APIs, data stores...) and *have no security* (CDTs, group types). Record types, process models and sites **never inherit**: their security must be set explicitly.
Source: [Security inheritance by object type](https://docs.appian.com/suite/help/latest/object-security.html#security-inheritance-by-object-type)

✅ **Resolve security warnings on the parent object, not on each child.**
The warning *"Parent has security warnings"* is fixed on the root parent; the fix propagates to every object that inherits from it.
Source: [Warnings](https://docs.appian.com/suite/help/latest/object-security.html#warnings)

---

## 4. Application security

✅ **Configure the security of the application object itself, in addition to the security of every object it contains.**
Updating the application's security (including via import) requires Administrator. Editor can update content but not security; Viewer can only see feeds/actions and export. System administrators always have access, regardless of the application permission.
Source: [Application security](https://docs.appian.com/suite/help/latest/application-settings.html#prodlink-security)

✅ **Take advantage of default security groups: when groups are generated at app creation, Appian pre-populates the role maps with the Viewer group and the Administrator.**
If no groups are generated, the creator remains the sole Administrator of every object they create — a single point of failure. Configure default security groups so new objects are born with correct security.
Source: [Application security](https://docs.appian.com/suite/help/latest/application-settings.html#prodlink-security) · [Editing object security](https://docs.appian.com/suite/help/latest/object-security.html#editing-object-security)

---

## 5. The five security layers of the record type

Appian applies record type security in layers, from broadest to most granular. Each layer stacks on top of the previous one. **Every layer applies automatically everywhere** the record type is used (lists, queries, grids, charts, related data), with the exception of Process Insights (see §6).

| Layer | What it controls |
|---|---|
| Object security | Who can view/modify the record type |
| Record-level security | Which rows each user sees |
| Field-level security | Which fields each user sees |
| Record view security | Which views each user sees |
| Record action security | Which actions each user sees |

Source: [Secure Your Data Fabric — How security layers work together](https://docs.appian.com/suite/help/latest/secure-your-data-fabric.html)

✅ **Always start with the record type's object security: it is mandatory and it is the entry gate.**
By default, any user with **Viewer** permission on the record type sees **all** rows and **all** fields. The granular layers only restrict from there.
Source: [Secure Your Data Fabric — Where to start](https://docs.appian.com/suite/help/latest/secure-your-data-fabric.html) · [Record-Level Security — About](https://docs.appian.com/suite/help/latest/record-level-security.html)

✅ **Set `Default (All Other Users)` to `No Access` on every record type; use the `Data Steward` level only for Process HQ.**
Official best practice: configure the record type's object security with **`Default (All Other Users) = No Access`**, so that only the groups you explicitly grant access to can see the data. **Watch out for service accounts:** they count as "users" for that Default, so a `Default = Viewer` exposes the record type to **every** service account (including web APIs and portals) — Appian flags it with *"Default set to viewer"*. The **Data Steward** level is specific to the record type: it does **not** allow viewing it in sites/Tempo or viewing its object security, it only allows using it as a **dataset in a Process HQ process**; reserve it for data governors.
Source: [Record Type Object Security — permission levels](https://docs.appian.com/suite/help/latest/record-security.html#main_content) · [Secure Data for Process HQ — Default No Access](https://docs.appian.com/suite/help/latest/secure-data-for-process-hq.html#show-record-types-as-datasets) · [Warnings — Default set to viewer](https://docs.appian.com/suite/help/latest/object-security.html#warnings)

⚠️ **Restricting a record type's object security does NOT protect the underlying table.**
Preventing a user from seeing the record type does not secure its data source: if **another object connects to the same table** (a CDT, an integration, another record type, a data store entity), the user can still see that data through that other path. Securing the data requires securing **every** object that touches the source, not just the record type. Apply this with special care to financial/compensation data and any sensitive field.
Source: [Record Type Object Security — source security](https://docs.appian.com/suite/help/latest/record-security.html#source-security)

### 5.1 Record-level security

✅ **Use Security Rules (guided experience) instead of Security Expression whenever you can.**
Security Rules are **inherited** from related record types (you keep the logic in one place), are **tested** by toggling rules on/off within the record type itself, and Appian manages their **performance** automatically. A Security Expression has to be configured on each record type, is not inherited, requires testing by logging in as another user, and its performance is the designer's responsibility.
Source: [Record-Level Security — Options / Security Rules vs Security Expression](https://docs.appian.com/suite/help/latest/record-level-security.html#record-level-security-options)

✅ **Reserve the Security Expression for complex conditions, and build it with `a!queryFilter()` / `a!queryLogicalExpression()`.**
Each filter must evaluate to *true* for the row to appear; with multiple filters, the row must satisfy **all** of them (implicit AND). For OR logic use `a!queryLogicalExpression(operator:"OR", ...)`.
Source: [Use a security expression](https://docs.appian.com/suite/help/latest/record-level-security.html#use-a-security-expression)

❌ **Do not combine Security Rules and Security Expression on the same record type, and do not expect a Security Expression to be inherited.**
They are mutually exclusive per record type, and expressions are not inherited between related record types. Available only on record types that are **synced (Optimized Data Access)** or **Direct Data Access with features enabled**; **not** on legacy record types.
Source: [Security expression limitations](https://docs.appian.com/suite/help/latest/record-level-security.html#use-a-security-expression) · [Supported record types](https://docs.appian.com/suite/help/latest/record-level-security.html#main_content)

### 5.2 Field-level security

✅ **Protect sensitive fields (salary, national ID, SSN, rate) with field-level security, restricting them to specific groups.**
By default every Viewer of the record type sees every field. With field-level security, "only users in these groups" see the field. Configurable on any field **except the primary key**.
Source: [Field-Level Security — What is it](https://docs.appian.com/suite/help/latest/field-level-security.html) · [Configure field-level security](https://docs.appian.com/suite/help/latest/field-level-security.html)

✅ **Know the exact behavior when the user does NOT have access to the field (it is not intuitive):**
- **Interface components:** the field is displayed, but with a **null** value (it does not disappear on its own).
- **Queries** (`a!queryRecordType`, `a!queryRecordByIdentifier`): the field is **not** returned in the output.
- **Filters and sorts:** **error** when trying to view a query or interface that filters or sorts by that field.
- **User filters:** the user filter is hidden.
- **Search:** the field cannot be searched on.

Source: [Field-level security in applications](https://docs.appian.com/suite/help/latest/field-level-security.html#field-level-security-in-applications)

✅ **Actively hide components with `a!doesUserHaveAccess()` in their `showWhen`.**
Since the field does not disappear on its own (it shows as null), use `a!doesUserHaveAccess(fields: recordType!X.fields.sensitiveField)` in the `showWhen` of the column/KPI to hide it from anyone without access. This avoids showing confusing empty cells.
Source: [a!doesUserHaveAccess()](https://docs.appian.com/suite/help/latest/fnc_system_doesUserHaveAccess.html)

❌ **Never use a protected field inside a sync-time custom record field without hiding the data.**
**Sync-time custom record fields bypass field-level security**: the field still shows with its visible values. If `revenue` is sensitive, create the custom field to show a range (high/medium/low), not the raw value. (By contrast, **real-time** custom fields do show null and are hidden from the Process HQ dataset.)
Source: [Field-level security in applications — custom record fields](https://docs.appian.com/suite/help/latest/field-level-security.html#field-level-security-in-applications)

❌ **Do not trust Appian Designer to validate field-level security: it is not applied there.**
The designer sees every field. The only valid test is to **log in as a user of each role** in the actual application and check the behavior. The same criterion applies to testing Security Rules/Expressions (§5.1) and record view security.
Source: [Field-level security in Appian Designer](https://docs.appian.com/suite/help/latest/field-level-security.html#main_content)

✅ **Account for common fields in relationships.**
Protecting a common field does not affect the security of the related record type: if the user can reach the related record's fields through another path, they will see them even though the common field is hidden.
Source: [Field-level security in applications — common fields](https://docs.appian.com/suite/help/latest/field-level-security.html#field-level-security-in-applications)

### 5.3 Record view and record action security

✅ **Restrict sensitive views and actions with Security Rules; use Security Expression only for complex or legacy logic.**
A view is only shown if its Security Expression evaluates to *true* for the user. For "NOT a member of a group" conditions use `not(a!isUserMemberOfGroup(...))`. As with record-level security, test it by switching users.
Source: [Record View Security — Security expression](https://docs.appian.com/suite/help/latest/record-view-security.html#security-expression) · [Secure Your Data Fabric](https://docs.appian.com/suite/help/latest/secure-your-data-fabric.html)

✅ **Remember that seeing a record action requires `Initiator` on the underlying process model, in addition to the action's Security Rule/Expression.**
Appian only shows a record action if all three conditions hold at once: the action's Security Rule/Expression includes the user, the user has **Initiator** on the process model the action starts, and — for related actions — the user can see the row (record-level security). The process model's security is edited from the record type itself (**Views and Actions Security → Actions**). If an action doesn't appear and the Security Rule is correct, check the process model's **Initiator**.
Source: [Record Action Security — About](https://docs.appian.com/suite/help/latest/record-action-security.html#about-record-action-security) · [Configure Record Actions — Record action security](https://docs.appian.com/suite/help/latest/record-actions.html#prodlink-record-action-security)

---

## 6. Data security in Process HQ and Data Fabric

❌ **Do not assume record type security protects Process Insights: it is not applied there.**
Record-level and field-level security apply everywhere **except in Process Insights**, which aggregates rows from multiple record types. There, data is protected by **access to the process itself**. The data steward must **remove sensitive fields beforehand**, before granting access to the process.
Source: [Record-Level Security — Where is it applied](https://docs.appian.com/suite/help/latest/record-level-security.html#main_content) · [Field-level security in Process HQ](https://docs.appian.com/suite/help/latest/field-level-security.html#field-level-security-in-applications)

✅ **The Appian MCP Server does respect field-level security in data fabric queries.**
Hidden fields are excluded both from results and from the schema response (`appian_data_fabric_metadata`), with the same behavior as an interface. (Note: this applies to the data fabric; Process Insights remains the exception noted above.)
Source: [Appian MCP Server Security — Field-level security](https://docs.appian.com/suite/help/latest/mcp-server-security.html#field-level-security)

---

## 7. Data security: service accounts, credentials and secrets

✅ **Store third-party credentials in the Secure Credentials Store, never in constants, expressions or code.**
The Secure Credentials Store encrypts the **values** (the attributes remain in cleartext) and stores them in Appian's data source. A System Administrator manages them on the *Third-Party Credentials* page of the Admin Console. A plug-in can only access them if it is explicitly added to that credential's list of authorized plug-ins.
Source: [Secure Credentials Store](https://docs.appian.com/suite/help/latest/Secure_Credentials_Store.html) · [Handling credentials securely](https://docs.appian.com/suite/help/latest/Custom_Smart_Service_Plug-ins.html#handling-credentials-securely)

✅ **Centralize authentication and the base URL in a connected system object; parameterize per environment.**
This way a password is updated only once even if 10 integrations use it, and each environment uses its own connection without touching the objects. Data source connected systems are additionally protected with object-level security to restrict sensitive data in development.
Source: [Connected System Object — Overview](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)

✅ **Consciously choose between site-wide (system-wide) and per-user credentials.**
- **Site-wide:** Appian presents itself as a single "integration user". Use these if users don't have their own login in the external system, or if a standard set of privileges applies to everyone.
- **Per-user:** each user authenticates with their own credentials and their own privileges in the external system. Use these if everyone has their own login, if each person's own permissions must apply, or to split rate limits.
- **Trap:** per-user credentials are **not available for users who authenticate via SAML**, and in smart services they require the service to be attended or activity-chained and executed by the user themself.
Source: [Connectors — System-wide vs. per-user authentication](https://docs.appian.com/suite/help/latest/Connectors.html#main_content) · [Secure Credentials Store — Per-User Credentials](https://docs.appian.com/suite/help/latest/Secure_Credentials_Store.html)

✅ **Reference the external system key (`scsExternalSystemKey`) via a Text-type constant, not a literal.**
The System Administrator creates the credential, notes the auto-generated key and stores it in a constant; designers use the constant. This avoids scattering the key across the code.
Source: [Connectors — Authentication](https://docs.appian.com/suite/help/latest/Connectors.html#main_content)

✅ **For integrations that consume infrastructure APIs: a dedicated service account, secrets kept out of code, HTTPS and rotation.**
Appian's API security doctrine (RPA context, applicable to any automation): use a dedicated service account with the **minimum privilege** required; store API keys in a secrets manager (Vault, AWS/Azure Secrets Manager), **never in scripts, configs or version control**; always use **HTTPS**; **rotate** keys periodically; retrieve passwords from environment variables or the secrets manager at runtime; and **never log password values**.
Source: [API security for infrastructure management](https://docs.appian.com/suite/help/latest/rpa-9.25/security-rpa.html#api-security-for-infrastructure-management) · [RPA security best practices](https://docs.appian.com/suite/help/latest/rpa-9.25/automate-rpa-infrastructure.html#security-best-practices)

✅ **Authenticate incoming Web APIs with an API key or OAuth 2.0 Client Credentials on a service account, never with a person's username/password.**
An external call to an Appian Web API authenticates against a **service account** (a role of the *Service Accounts* system group), not against a named user. Two mechanisms, both managed by a System Administrator in **Admin Console → Authentication → Web API Authentication**:
- **API key:** a random key tied to a service account; it cannot be used to log in, runs ~10x faster than basic auth, and does not expire. It travels in the `Appian-API-Key` header (or `Authorization: Bearer`). Appian shows it only once: store it outside Appian.
- **OAuth 2.0 Client Credentials Grant:** the industry standard for machine-to-machine, with token expiration/refresh; preferable when possible. Reuses the same service account as the API key (no need to touch object security).
The service account must be in a **group with permission to call that Web API** (otherwise the call returns **404**) and must be created with the **same username and the same groups in every environment** so that permissions promote correctly. Members of the *SAML* and *Service Accounts* system groups **cannot** use basic auth.
Source: [Web API Authentication](https://docs.appian.com/suite/help/latest/Web_API_Authentication.html#authentication) · [Admin Console — Web API Authentication](https://docs.appian.com/suite/help/latest/admin-web-api-authentication.html#api-keys) · [Service account role](https://docs.appian.com/suite/help/latest/User_Roles.html#service-account-role)

---

## 8. Least privilege, user types and environment separation

✅ **Reserve the System Administrator type for what is strictly necessary; everything else is Basic Users with roles.**
System Administrator is the highest level of rights and accesses every object regardless of its role map. A Basic User needs specific roles (e.g. the **designer role** to enter Appian Designer). Design for least privilege: nobody has more rights than their function requires.
Source: [Manage user rights and security](https://docs.appian.com/suite/help/latest/User_Management.html#manage-user-rights-and-security)

✅ **Apply least privilege to service accounts as well.**
If a service account only needs to rotate credentials, it should not have broader administrative access than required. The **Deploy As** account in the deployment configuration must be in the **service account** role.
Source: [API security — Authentication and authorization](https://docs.appian.com/suite/help/latest/rpa-9.25/security-rpa.html#api-security-for-infrastructure-management) · [Deploy to Target Environments — Security](https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html#security)

✅ **Separate development, test and production environments; change control between them is the customer's responsibility.**
Appian Cloud assumes the customer manages their non-production environments for testing, and reviews/approves changes affecting security, availability or confidentiality before promoting them. Data classification and who accesses it are also the customer's responsibility.
Source: [Appian Cloud User Control Considerations](https://docs.appian.com/suite/help/latest/Appian_Cloud_User_Control_Considerations.html)

✅ **Deploy security with an `<App>_Administrators` group present in both environments.**
Official best practice: create the group in the source environment, export it in the application package before the app itself (so Appian recognizes it as the same group in both environments), add it with Administrator to every role map, temporarily add the importer to the group and remove them after importing. Remember: on deployment, **individual users in a role map are dropped** if they don't exist (or are disabled) in the target; groups only survive if they are in the package or already exist in the target — another reason to use groups, not users.
Source: [Deploy to Target Environments — Security / Deploying security role maps](https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html#security)

✅ **Harden platform authentication in the Admin Console: MFA, session timeout and SSO/SAML.**
Beyond object security, the access surface is governed in **Admin Console → Authentication**: require **MFA** (a code from an authenticator app such as Google/Microsoft Authenticator), set **session timeouts** (with different values for administrators and users) and delegate identity to **SSO/SAML** when the organization uses it. These are System Administrator settings, not designer settings, but they condition the whole application's security.
Source: [Admin Console — Appian Authentication (MFA, session timeout)](https://docs.appian.com/suite/help/latest/admin-appian-authentication.html#multi-factor-authentication) · [Authentication (SSO/SAML)](https://docs.appian.com/suite/help/latest/Authentication.html)

---

## 9. Portal and external user security

✅ **Control what an external portal user sees through service accounts: they only reach the objects and data that the service account grants.**
Portals are **public** yet secure: the end user does not log in and only reaches what you expose through the portal's service account. Treat that service account with least privilege.
Source: [Portal Object — Portal security](https://docs.appian.com/suite/help/latest/portal-object.html#portal-security) · [Portals service accounts](https://docs.appian.com/suite/help/latest/portals-service-accounts.html)

❌ **Do not use a portal for account-level access or for data personalized per user.**
Portals are for **public, unauthenticated** cases (starting a workflow, submitting a form, viewing a public dashboard, self-registration). If the user needs to see their own cases/invoices/history, that requires **login with a user account**, not a portal.
Source: [Appian Portals — When to use a portal](https://docs.appian.com/suite/help/latest/portals-home.html#when-to-use-a-portal)

✅ **Harden the portal: reCAPTCHA against fraudulent activity and extra care with plug-ins.**
Enable reCAPTCHA to monitor malicious activity. Because the portal is exposed to the open internet, component plug-ins have a larger attack surface and the load coming from the internet can be **unbounded**: prefer **connected system plug-ins** (they have protections/throttling that shield logged-in users from traffic spikes) over component plug-ins that call external systems without them, and do load testing.
Source: [Keep your sensitive data secure / reCAPTCHA](https://docs.appian.com/suite/help/latest/portals-home.html#main_content) · [Develop Component Plug-ins for Portals](https://docs.appian.com/suite/help/latest/component-portals.html#main_content)

✅ **If the environment uses inbound access over VPN or PrivateLink, enable dual inbound access and trusted IPs before publishing the portal.**
Appian Portals is only supported on Appian Cloud; with inbound over VPN/PrivateLink you must configure dual inbound access and trusted IPs.
Source: [Appian Portals — Overview (note)](https://docs.appian.com/suite/help/latest/portals-home.html#main_content)

### 9.1 Custom external front end over Appian

If, instead of the Portal object, the project exposes its own application (SPA, mobile or server) that consumes Appian via Web API, integration or the MCP server, it inherits the portal model above, but **the custom layer adds responsibilities it cannot delegate to the platform**. Apply this section to any front end that is not Appian.

✅ **Apply row-level (record-level) security so the external user sees ONLY THEIR OWN data.**
The service account the front end connects with counts as a "user" for security purposes: without record-level security it sees **all** rows of the record type. Configure a Security Rule/Expression that filters by the external user's identifier (their email, account, or the key that identifies them) so that each one reaches only their own data, never anyone else's. This layer is the ultimate safety net.
Source: [Portals service accounts — access to the right data](https://docs.appian.com/suite/help/latest/portals-service-accounts.html#making-sure-your-service-account-has-access-to-the-right-data) · [Record-Level Security](https://docs.appian.com/suite/help/latest/record-level-security.html)

✅ **Use non-guessable identifiers in portal URLs and payloads (anti-IDOR).**
A portal is public: if a record's ID is sequential (1, 2, 3…), anyone can iterate and request someone else's (*Insecure Direct Object Reference*). Expose opaque tokens/UUIDs, not the numeric primary key, and **verify in Appian** that the requested record belongs to the portal's user — never trust that the ID "can't be seen". The record-level security above backstops this check in case an identifier leaks.
Source: [Portal Object — Portal security](https://docs.appian.com/suite/help/latest/portal-object.html#portal-security) · [Portals service accounts](https://docs.appian.com/suite/help/latest/portals-service-accounts.html)

✅ **Protect public forms with anti-bot measures (reCAPTCHA) and give the portal's service account least privilege.**
Enable **reCAPTCHA** on public submission forms against spam/fraud (see §9), and grant the portal's service account **only** the record types, documents and processes the front end actually uses — nothing more. The portal only exposes what an interface directly calls, but least privilege is the defense in depth if something is referenced by mistake.
Source: [reCAPTCHA / keep your sensitive data secure](https://docs.appian.com/suite/help/latest/portals-home.html#main_content) · [Portals service accounts — least privilege](https://docs.appian.com/suite/help/latest/portals-service-accounts.html)

---

## 10. Access auditing and governance

✅ **Review the security of the entire application with the Security Summary before every deployment.**
The Security Summary shows the security of every object in a site, groups them by identical role map, **highlights objects with warnings** and allows editing security **in bulk**. Use it to find objects without security and to review a whole package before deploying it.
Source: [Object Security — Security Summary](https://docs.appian.com/suite/help/latest/object-security.html#security-summary) · [Editing object security](https://docs.appian.com/suite/help/latest/object-security.html#editing-object-security)

⚠️ **Remember that the same permission level means different things depending on the object.**
The Security Summary groups by role map, but "Viewer" is not the same everywhere: executing a web API requires Viewer, while **anyone can evaluate an expression rule** if it's invoked by an interface or process that is already using it. Do not infer the real exposure from the level alone.
Source: [Security Summary — Role Maps (note)](https://docs.appian.com/suite/help/latest/object-security.html#security-summary)

✅ **Treat security changes as auditable events.**
Editing an object's security **does not create a new version**, but it **is recorded as an update** (Last Modified By + design logs). Application Server logs can be audited by the customer as frequently as needed; review them to detect unexpected activity.
Source: [Editing object security (tip)](https://docs.appian.com/suite/help/latest/object-security.html#editing-object-security) · [Appian Cloud User Control Considerations](https://docs.appian.com/suite/help/latest/Appian_Cloud_User_Control_Considerations.html)

✅ **Own the control responsibilities that Appian Cloud leaves to the customer.**
User account management, data classification, change control between environments, approval of changes affecting security, and notifying Appian of suspicious activity or breaches — all of this is the customer's responsibility, not the platform's.
Source: [Appian Cloud User Control Considerations](https://docs.appian.com/suite/help/latest/Appian_Cloud_User_Control_Considerations.html)

---

## Sources

All URLs use the `latest` alias (redirects to Appian's latest monthly release).

**Object, group and role map security**
- [Object Security — Groups and role maps / Deny / Permission levels](https://docs.appian.com/suite/help/latest/object-security.html#groups-and-role-maps)
- [Object Security — Security inheritance](https://docs.appian.com/suite/help/latest/object-security.html#security-inheritance)
- [Object Security — Security inheritance by object type](https://docs.appian.com/suite/help/latest/object-security.html#security-inheritance-by-object-type)
- [Object Security — Warnings](https://docs.appian.com/suite/help/latest/object-security.html#warnings)
- [Object Security — Editing object security / Security Summary](https://docs.appian.com/suite/help/latest/object-security.html#security-summary)
- [Application Settings — Application security / Security summary](https://docs.appian.com/suite/help/latest/application-settings.html#prodlink-security)
- [Creating Groups](https://docs.appian.com/suite/help/latest/Creating_Groups.html) · [Group objects](https://docs.appian.com/suite/help/latest/design-objects.html#group-objects)

**Record type / data fabric security**
- [Secure Your Data Fabric — layers](https://docs.appian.com/suite/help/latest/secure-your-data-fabric.html)
- [Record Type Object Security — permission levels / Data Steward](https://docs.appian.com/suite/help/latest/record-security.html#main_content) · [source security](https://docs.appian.com/suite/help/latest/record-security.html#source-security)
- [Secure Data for Process HQ — Default No Access](https://docs.appian.com/suite/help/latest/secure-data-for-process-hq.html#show-record-types-as-datasets)
- [Record-Level Security](https://docs.appian.com/suite/help/latest/record-level-security.html) · [options and expression](https://docs.appian.com/suite/help/latest/record-level-security.html#record-level-security-options)
- [Field-Level Security](https://docs.appian.com/suite/help/latest/field-level-security.html) · [where it applies](https://docs.appian.com/suite/help/latest/field-level-security.html#field-level-security-in-applications)
- [a!doesUserHaveAccess()](https://docs.appian.com/suite/help/latest/fnc_system_doesUserHaveAccess.html)
- [Record View Security — Security expression](https://docs.appian.com/suite/help/latest/record-view-security.html#security-expression)
- [Record Action Security — About](https://docs.appian.com/suite/help/latest/record-action-security.html#about-record-action-security) · [Configure Record Actions — Record action security](https://docs.appian.com/suite/help/latest/record-actions.html#prodlink-record-action-security)
- [Appian MCP Server Security — Field-level security](https://docs.appian.com/suite/help/latest/mcp-server-security.html#field-level-security)

**Credentials, service accounts and integrations**
- [Secure Credentials Store](https://docs.appian.com/suite/help/latest/Secure_Credentials_Store.html)
- [Connected System Object](https://docs.appian.com/suite/help/latest/Connected_System_Object.html)
- [Connectors — System-wide vs. per-user authentication](https://docs.appian.com/suite/help/latest/Connectors.html#main_content)
- [Handling credentials securely (smart service plug-ins)](https://docs.appian.com/suite/help/latest/Custom_Smart_Service_Plug-ins.html#handling-credentials-securely)
- [API security for infrastructure management](https://docs.appian.com/suite/help/latest/rpa-9.25/security-rpa.html#api-security-for-infrastructure-management)
- [Web API Authentication (API key / OAuth 2.0 Client Credentials)](https://docs.appian.com/suite/help/latest/Web_API_Authentication.html#authentication) · [Admin Console — Web API Authentication](https://docs.appian.com/suite/help/latest/admin-web-api-authentication.html#api-keys)
- [Service account role](https://docs.appian.com/suite/help/latest/User_Roles.html#service-account-role)

**Users, environments, deployment and governance**
- [Manage user rights and security](https://docs.appian.com/suite/help/latest/User_Management.html#manage-user-rights-and-security)
- [Deploy to Target Environments — Security](https://docs.appian.com/suite/help/latest/Deploy_to_Target_Environments.html#security)
- [Admin Console — Appian Authentication (MFA, session timeout)](https://docs.appian.com/suite/help/latest/admin-appian-authentication.html#multi-factor-authentication) · [Authentication (SSO/SAML)](https://docs.appian.com/suite/help/latest/Authentication.html)
- [Appian Cloud User Control Considerations](https://docs.appian.com/suite/help/latest/Appian_Cloud_User_Control_Considerations.html)

**Portals and external users**
- [Appian Portals — home / when to use](https://docs.appian.com/suite/help/latest/portals-home.html#when-to-use-a-portal)
- [Portal Object — Portal security](https://docs.appian.com/suite/help/latest/portal-object.html#portal-security)
- [Portals service accounts (least privilege / access to the right data)](https://docs.appian.com/suite/help/latest/portals-service-accounts.html)
- [Develop Component Plug-ins for Portals](https://docs.appian.com/suite/help/latest/component-portals.html#main_content)
