# Best practices — Sites and navigation

> Official Appian doctrine for the **Site** object and its navigation: page types, organization into
> page groups, navigation bar layout (header bar vs sidebar), branding, secondary navigation, page width,
> and the site's own performance and security traps. Every rule is anchored to official Appian
> documentation (`docs.appian.com/suite/help/latest/…`, an alias that always redirects to the latest release).

Convention: ✅ = recommended practice · ❌ = anti-pattern · ⚠️ = trap. Each block closes with **Source**.

---

## 1. Site page types

### 1.1 Know the five page types and what each one shows
- ✅ A site supports **five** page types:
  - **Action** — shows the *start form* of a process model (starts a process).
  - **Interface** — shows an interface object.
  - **Record List** — shows the record list configured on a record type.
  - **Process HQ - Full Library** — embeds the Process HQ Reports & Dashboards library.
  - **Process HQ - Dashboard** — embeds a specific Process HQ dashboard.
- **Why:** choosing the right type avoids reinventing in an interface what the site already provides out
  of the box (a record list as a Record List, not as an interface with a hand-built grid).

Source: https://docs.appian.com/suite/help/latest/sites_object.html#pages

### 1.2 Only Interface-type pages support page groups and URL parameters
- ✅ If a page is going to live inside a **page group** or needs to receive **URL parameters** via
  `a!urlForSite()`, it must be of type **Interface**.
- ❌ Don't count on grouping or URL-parameterizing Action, Record List, or Process HQ pages.
- **Why:** it's a product restriction: *"Interface type pages are the only pages that can be added
  to page groups or use URL parameters in `a!urlForSite()`."* If you need deep-linking to an action or a
  record list, wrap it in an Interface page that invokes it.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#pages

### 1.3 Records and actions are better exposed as their own page type
- ✅ To give access to a record list use a **Record List** page (it inherits the search field, user
  filters, and views already defined on the record type); to launch a process, use an **Action** page.
- ❌ Don't replicate a record list inside an interface just to place it on a site.
- **Why:** the Record List reuses the record type's entire configuration without duplicating SAIL, and
  record views (summary, related actions) remain accessible from it.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#pages

---

## 2. Organizing navigation: number of pages and page groups

### 2.1 The hard cap is 10 items; the recommended limit is 8 (and 5 for mobile-first)
- ✅ A site (or portal) supports up to **ten** top-level pages or page groups — this is a platform
  limit.
- ✅ As a general rule, **limit the navigation bar's top-level items to eight**.
- ✅ In **mobile-first sites** (Appian Mobile only), don't exceed **five** pages or page groups.
- **Why:** an overloaded bar makes it harder to find what matters; every item needs a clear title and a
  distinct purpose to earn its place.

Source: https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#organizing-pages-and-page-groups

### 2.2 Group related pages into page groups
- ✅ Bring pages with a similar purpose together under a single title, using a **page group**.
- **Why:** the user scans a short list inside the group and finds what they're looking for faster; it also
  frees up top-level slots to respect the cap in 2.1.

Source: https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#organizing-pages-and-page-groups

### 2.3 Order pages with a logical criterion
- ✅ Order pages and groups by a criterion useful to the user: **most used to least used** or
  **alphabetical**.
- ❌ Don't leave the order to whatever sequence they happened to be created in.
- **Why:** a predictable order reduces search time.

Source: https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#organizing-pages-and-page-groups

### 2.4 Short, clear page names
- ✅ Use **clear and concise** page names.
- ❌ Don't use long names: they get truncated on screen (especially in the header bar and on mobile).
- **Why:** a concise name scans better and fits without being cut off.

Source: https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#organizing-pages-and-page-groups

### 2.5 Each page in a group needs its own title within the page
- ✅ Include a **title** at the top of every page in a page group that clearly states its purpose.
- **Why:** when navigating within a group, the user needs to know which page they're on; the group's name
  alone doesn't tell them.

Source: https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#organizing-pages-and-page-groups

### 2.6 A page group supports a maximum of 10 pages, and only of type Interface
- ✅ A **page group** fits up to **ten** pages, and **all of them must be of type Interface**
  (see 1.2).
- ⚠️ **Moving a page** into or out of a page group is not an in-place operation: it amounts to
  **deleting it and recreating it**, which loses its previous configuration. Plan the grouping before
  creating many pages.
- **Why:** knowing the cap and the real cost of reorganizing avoids late-stage navigation redesigns.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#add-a-page-group

### 2.7 Mobile and offline navigation: page groups don't carry over the same way
- ⚠️ In **Appian Mobile offline**, **page groups are not supported**: don't count on grouped
  navigation for pages marked as available offline.
- ⚠️ On **iOS**, starting from the **fifth** top-level page, the 5th and beyond collapse under a
  **"More"** item; on **Android** the bar scrolls horizontally. This is another reason to respect the
  five-page limit on mobile-first sites (see 2.1).
- **Why:** navigation that looks fine on web can get reordered or lose its groups on mobile/offline;
  design for that behavior up front.

Source: https://docs.appian.com/suite/help/latest/sail/ux-mobile-considerations.html#site-pages

---

## 3. Navigation bar layout and branding

### 3.1 Header bar vs sidebar: choose based on navigation complexity
- ✅ **Header bar** (top bar) for simple navigations with few pages; available styles:
  **Helium**, **Mercury** (default) and **Oxygen**.
- ✅ **Sidebar** (side bar) when there are many pages or navigation is complex: it scales better to a
  large number of pages, at the cost of more occupied space.
- **Why:** horizontal navigation is clean but falls short with many items; vertical navigation supports
  more pages and sub-levels.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#navigation-bar · https://docs.appian.com/suite/help/latest/sail/secondary-navigation.html#about-secondary-navigation

### 3.2 Brand the site with corporate branding, not with patches in every interface
- ✅ Configure branding at the site level: **Accent Color** (`#1d659c` by default), Loading Bar Color,
  button/input/dialog shape (Squared / Semi-rounded / Rounded), logo, and **CSS Profile**.
- ⚠️ **Typeface is NOT a per-site lever**: the site object's Typeface field is **read-only**
  ("View the current typeface…") and applies to **all** sites and portals in the environment.
  It's configured in the **Admin Console** (as of 26.6, via the environment's CSS profile), not on each
  site. The only style/typeface lever that belongs to the site itself is the **CSS Profile** field.
- **Why:** centralizing color and shape at the site level gives visual coherence to all its pages without
  having to repeat styles in every interface; but confusing the Typeface (global and read-only) with a
  per-site setting leads to expecting changes that will never happen from the site. (For corporate HEX in
  buttons and chips within an interface, see doc 02.)

Source: https://docs.appian.com/suite/help/latest/sites_object.html#branding · https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html

### 3.3 Header styles aren't just aesthetic: they change what's shown
- ✅ When choosing a header bar, take into account the **functional** differences between styles, not
  just the look:
  - **Helium** — shows the **page names next to their icons** in the bar.
  - **Mercury** (default) and **Oxygen** — designed for **a single page**: they **don't show the page
    name** in the bar.
  - **Mercury** also **doesn't show the page icon on web** (only on Appian Mobile).
- **Why:** if the site has several named pages, Mercury/Oxygen leave them unlabeled and confusing; for
  navigation with visible names, use Helium. Choose the style based on how many pages there are and
  whether you need to see their names, not on blind visual preference.

Source: https://docs.appian.com/suite/help/latest/Sites.html#navigation-bar

### 3.4 The Accent Color must be accessible, not just corporate
- ✅ Choose the Accent Color with **sufficient contrast**: a minimum of **4.5:1** against the bar's
  white background and the components that use it.
- ❌ Avoid **grays** (poor contrast) and don't rely on **green/red** as the only signal (color blindness).
- ⚠️ Also test the **dimmed hover** state: a color that passes at rest can fall below the threshold when
  lightened on hover.
- **Why:** the Accent Color tints links, buttons, and active elements across the whole site; if it doesn't
  contrast, navigation becomes hard to read for users with low vision or color blindness.

Source: https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#branding · https://docs.appian.com/suite/help/latest/sites_object.html#branding

---

## 4. Secondary navigation (splitting up a page's content)

### 4.1 When a page has a lot of content, use secondary navigation, not more top-level pages
- ✅ To split content **within a page** use secondary navigation: tab layout (`a!tabLayout()`) for
  sub-tabs, or a sidebar pattern within the page.
- ❌ Don't turn every subsection into a top-level page: you'd exhaust the bar's 8-10 item budget.
- **Why:** secondary navigation spreads a single page's content into categories without inflating the
  site's main navigation.

Source: https://docs.appian.com/suite/help/latest/sail/secondary-navigation.html#about-secondary-navigation

### 4.2 Horizontal vs vertical within the page
- ✅ **Horizontal** (tabs) when there are **fewer than 7** tabs and you want to reserve width for the
  content.
- ✅ **Vertical** (internal sidebar) when you need **more than 6** tabs, there are several levels of
  sub-navigation, or the labels are long.
- ⚠️ If you need **deep-linking to a sub-tab via URL parameter**, the standard `a!tabLayout()` isn't
  enough: you have to build the secondary navigation by hand with the official pattern (and remember URL
  parameters only work on Interface-type pages — see 1.2).
- **Why:** the right orientation for the number of tabs keeps the page readable; the manual pattern is
  only justified when you need extra functionality like a direct URL link.

Source: https://docs.appian.com/suite/help/latest/sail/secondary-navigation.html#when-to-use-vertical-vs-horizontal-navigation

---

## 5. Page width based on content

### 5.1 Match page width to the type of content
- ✅ Every page has a width: **Narrow**, **Medium**, **Wide**, or **Full**. Choose it based on the
  content: **Narrow/Medium** for short forms and centered content; **Wide/Full** for dense grids,
  dashboards, and wide tables.
- ❌ Don't leave a three-field form at **Full** width (it gets lost) or a many-column grid at **Narrow**
  (it forces horizontal scrolling).
- **Why:** the right width balances information density with readability; the whitespace on the sides of
  a short form is desirable, not a defect.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#pages

---

## 6. Performance: the site's display name

### 6.1 Never put a long-running expression (a query) in the display name
- ❌ Don't use expressions that query data to build the site's **display name**.
- ✅ Static text, or at most a lightweight expression with no queries.
- **Why (trap):** *"If you use an expression to create a display name, that expression will evaluate
  whenever sites in the environment that the user has access to load or refresh… don't use long-running
  expressions, like queries."* The display name is evaluated whenever **all** the sites the user has
  access to load or refresh, not just the current one: a query there penalizes the loading of the entire
  environment.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#display-name

### 6.2 Changing the site's display name does NOT change its URL
- ⚠️ Editing a site's **display name** (its visible name) **doesn't update the web address
  identifier** (the URL fragment): the address stays fixed once the site is created.
- ✅ If you need a specific URL, decide it when you **create** the site; renaming it later doesn't migrate
  it and doesn't generate redirects.
- **Why:** existing links and bookmarks keep pointing to the original URL even after the site is renamed;
  assuming otherwise breaks saved deep-links.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#considerations-for-configuring-sites

---

## 7. Site security

### 7.1 Sites NEVER inherit security: you must set their role map explicitly
- ✅ Always configure the site's role map by hand: in the official inheritance list by object type,
  **Site** is in the **"Never Inherit Security"** column.
- ❌ Don't assume the site takes security from the application or from a parent folder: it doesn't.
- **Why:** since it doesn't inherit, a newly created site has no "borrowed" permissions; if you don't set
  a role map, it ends up poorly protected or inaccessible. The doctrine on groups, permission levels, and
  least privilege is in **doc 06 (Security)** — this section only flags the site's particularity.

Source: https://docs.appian.com/suite/help/latest/object-security.html#security-inheritance-by-object-type

### 7.2 A user needs at least Viewer on the site and visibility of the page
- ✅ To access a site, the user needs at least **Viewer** permission on the site object **and**
  visibility of the specific pages they want to open.
- ⚠️ Access to the site **doesn't** grant access to the data it shows: each page remains subject to the
  security of the objects it invokes (record types, interfaces, processes). A user can see the site and
  still not see a list if they don't have permission on its record type.
- **Why:** site security controls the **gate** (what navigation they see), not the **content**; the two
  layers are configured separately.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#security

### 7.3 Conditional visibility of pages and page groups: distinct from the role map
- ✅ In addition to the role map, every **page** and every **page group** supports an **"Only show
  when"** condition (a boolean expression): the page/group only appears in navigation when the
  expression is true. It's a mechanism that is **native and distinct from security**: visibility hides the
  item from the bar; the role map controls the real permission on the objects the page invokes.
- ⚠️ **Group precedence over page:** if a **page group's** expression hides the group, **none** of its
  pages show, even if an individual page's condition is true. Check the group's condition before
  debugging why a page isn't appearing.
- ⚠️ **This is not security:** hiding a page with "Only show when" doesn't prevent direct URL access for
  a user with permission on the underlying object. To actually restrict access, use the role map
  (7.1/7.2); visibility is navigation UX, not an access barrier.
- ⚠️ **Performance:** these expressions are **evaluated on every load/refresh** of the site, just like the
  display name — **don't put long-running queries** in them (same trap as 6.1).
- **Why:** adapting the bar to the role or the state (showing "Approvals" only to whoever approves)
  improves UX without duplicating sites; but confusing visibility with security leaves the data accessible
  via URL.

Source: https://docs.appian.com/suite/help/latest/sites_object.html#page-and-page-group-visibility · https://docs.appian.com/suite/help/latest/object-security.html#visibility

---

## Sources

All the doctrine above comes from official Appian documentation (`docs.appian.com/suite/help/latest/…`,
an alias to the latest release). Reference pages:

- Sites (object: pages, page types, navigation, branding, width, display name, security) — https://docs.appian.com/suite/help/latest/sites_object.html
- Sites (usage guide: navigation bar and Helium/Mercury/Oxygen header styles) — https://docs.appian.com/suite/help/latest/Sites.html#navigation-bar
- Designing Sites and Portals — Organizing pages and page groups — https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#organizing-pages-and-page-groups
- Designing Sites and Portals — Branding (global read-only Typeface; Accent Color accessibility) — https://docs.appian.com/suite/help/latest/sail/ux-site-branding.html#branding
- Sites — Page and page group visibility ("Only show when", group>page precedence) — https://docs.appian.com/suite/help/latest/sites_object.html#page-and-page-group-visibility
- Object Security — Visibility — https://docs.appian.com/suite/help/latest/object-security.html#visibility
- Mobile considerations for site pages (no page groups offline, "More" on iOS, scrolling on Android) — https://docs.appian.com/suite/help/latest/sail/ux-mobile-considerations.html#site-pages
- Secondary Navigation (tabs/sidebar within a page) — https://docs.appian.com/suite/help/latest/sail/secondary-navigation.html
- Tab Layout (`a!tabLayout()`) — https://docs.appian.com/suite/help/latest/Tab_Layout.html
- `a!urlForSite()` / URL parameters — https://docs.appian.com/suite/help/latest/url-parameters.html
- Object Security — Security inheritance by object type (Site = "Never Inherit Security") — https://docs.appian.com/suite/help/latest/object-security.html#security-inheritance-by-object-type
- General object and group security — see **doc 06 (Security)** in this collection
