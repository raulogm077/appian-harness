# Best practices — Interfaces and SAIL

> Official Appian doctrine for designing interfaces with SAIL: structure, data querying, responsive layouts, forms, grids, rich text, accessibility and performance. Every rule is anchored to official Appian documentation (`docs.appian.com/suite/help/latest/…`). The links use the `latest` alias, which always redirects to the most recently published release.

Convention: ✅ = recommended practice · ❌ = anti-pattern. Each block closes with **Source**.

---

## 1. Interface structure

### 1.1 Expensive calculations and queries go in `a!localVariables`, not in component parameters
- ✅ Put every function or rule that takes time to evaluate (a query, an aggregation) inside a local variable with `a!localVariables()`.
- ❌ Don't put it directly in a component parameter (`value`, `data`, etc.).
- **Why:** every time an evaluation fires (the user types, clicks a button…) **all** components are re-evaluated, so whatever lives in a parameter gets recalculated on every interaction. A local variable, by default, is only re-evaluated when the interface loads, when it is updated in a `saveInto`, or when another local variable it references changes.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#local-variable-best-practices

### 1.2 Never put a component inside a local variable
- ❌ Don't use a component (`a!textField(...)`, `a!cardLayout(...)`) as the **value** of a local variable.
- ✅ To reuse a component, define it in a **new interface** (an interface rule) and invoke it.
- **Why:** it doesn't throw a visible error, but produces unexpected or inconsistent behavior.

Source: https://docs.appian.com/suite/help/latest/Local_Variables.html#components-in-local-variables

### 1.3 Split into reusable interfaces and custom components
- ✅ Extract repeated fragments into reusable interfaces; a change is reflected instantly in every object that calls them.
- ✅ When wrapping an input component in a generic rule (e.g. a `dollarField`), use a `value` rule input and a `saveInto` one; the one that maps to `saveInto` must be of type **array of Save**, so `a!save()` can be used.
- **Why:** it reduces redundant expressions, eases maintenance, and enforces a consistent design standard and UX. Naming the rule inputs `value` and `saveInto` is the convention that helps others configure the component correctly.

Source: https://docs.appian.com/suite/help/latest/using_interfaces_in_appian.html#reusability

### 1.4 Give each local variable a unique name
- ✅ Name every local variable uniquely, including those inside loop functions (`a!forEach()`).
- **Why:** renaming from the Local Variables grid in design mode can, through a name collision, affect variables defined inside loops, causing unintended changes.

Source: https://docs.appian.com/suite/help/latest/interface_object.html#local-variables

### 1.5 In children, query at the top and pass through a rule input
- ✅ Query the data in a local variable in the **parent interface** and pass it to the child through a rule input (`ri!`).
- ❌ Don't query data inside a child interface or a rule called from the parent.
- **Why:** in offline synchronization only the parent's data is downloaded; querying in the child causes an error in Appian Mobile. Also, typing the rule inputs correctly makes the component's data contract explicit.

Source: https://docs.appian.com/suite/help/latest/offline-mobile-design-best-practices.html#query-data-for-child-interfaces-or-rules-at-the-top-of-the-parent-interface

---

## 2. Querying data in interfaces

> **Where the depth lives.** Query mechanics —fields, paging, filters, aggregations, relationships and
> their ceilings— are specified once for this plugin in **`05-performance.md` § 2**, and in full by the
> official Appian skill in `references/query-record-type-patterns.md` (1.463 lines). **This section
> keeps only what is specific to querying *from an interface*, and must not restate the rest.**

### 2.1 Choose the query function for the case
- ✅ List of records from a **record type** → `a!queryRecordType()`.
- ✅ A **single** record (and its related ones) for summary views or related actions → `a!queryRecordByIdentifier()`.
- ✅ Grid or chart fed by a record type (including aggregations) → `a!recordData()` in the component's `data` parameter.
- ✅ List or aggregation from a **data store entity** (not a record type) → `a!queryEntity()` with `a!query()`.
- **Why:** if the data lives in a record type, `a!queryRecordType()` / records-powered components are the preferred route; `a!queryEntity()` is left for entities without a record type.

Source: https://docs.appian.com/suite/help/latest/about-queries.html#how-to-query-data · https://docs.appian.com/suite/help/latest/fnc_system_a_queryrecordbyidentifier.html#usage-considerations

### 2.2 Fields, paging and the N+1: the rules live in `05-performance.md` § 2

Specify the exact `fields`, page with `a!pagingInfo()`, never run an unbounded query, and never query
inside a loop. Those four rules, their ceilings and their traps —the empty-`fields` trap on
`a!queryRecordByIdentifier()` among them— are stated once in **`05-performance.md` § 2**. They are not
repeated here, because the same rule written twice drifts into two versions of itself.

What is specific to an interface, and only lives here:

- **An interface re-evaluates.** A query inside an interface runs again on every interaction that
  touches its variable, so an expensive query costs once in a rule and costs *per click* here. This is
  why § 1.1 puts queries in `a!localVariables` and § 8.3 limits interactions on data-heavy screens.
- **The 65-second timeout is reached sooner from a screen** than from a rule, because the render adds
  its own work on top. Reduce the batch, the fields, or tighten the filters.

### 2.3 For slow data, load asynchronously
- ✅ Use `a!asyncVariable()`, or the `loadDataAsync` parameter on read-only grids, charts and KPIs fed by records, when the data is slow to load.
- **Why:** it's one of the most effective ways to improve perceived performance: the user interacts with the rest of the screen while the slow data loads behind a placeholder (skeleton). Note: in offline mobile and portals, async data loads together with everything else, not in the background.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#use-asynchronous-loading-for-slow-data

---

## 3. Responsive layouts and mobile design

### 3.1 `a!isPageWidth()` and `stackWhen` are the responsiveness tools
- ✅ Use `a!isPageWidth()` (with `if`) to change sizes, spacing or layout based on page width, and the `stackWhen` parameter of `a!columnsLayout()` / `a!sideBySideLayout()` to control when they stack.
- ❌ Don't use `a!isNativeMobile()` for responsive layout decisions.
- **Why:** `a!isNativeMobile()` only detects whether the user is in the Appian Mobile app or a browser, not screen size; reserve it for app-specific functionality. Breakpoints: `PHONE` ≤480px, `TABLET_PORTRAIT` 481-768, `TABLET_LANDSCAPE` 769-1024, `DESKTOP_NARROW` 1025-1280, `DESKTOP` 1281-1680, `DESKTOP_WIDE` ≥1681.

Source: https://docs.appian.com/suite/help/latest/responsive_design.html

### 3.2 Don't fix the width of every column
- ❌ Don't give a fixed width to every column of an `a!columnsLayout()`.
- ✅ Use relative widths, or combine empty `AUTO` columns on the sides to center the content; check that any fixed width fits every target screen size.
- **Why:** not every user has the same screen; fixed widths don't fit all of them. Mind the negative space: more content isn't better — avoid filling the whole screen if it doesn't add value.

Source: https://docs.appian.com/suite/help/latest/sail/ux-columns-layout.html#style-guidelines

### 3.3 Design "small screen first" and touch-friendly
- ✅ Stack columns on narrow screens, limit horizontal scrolling and ensure comfortable touch targets.
- **Why:** on mobile, columns stack by default; the interface must stay usable at the smallest width it supports.

Source: https://docs.appian.com/suite/help/latest/responsive_design.html

---

## 4. Forms

### 4.1 Requiredness with `required`; cross-field validation at the form/section level
- ✅ Mark required fields with `required: true`.
- ✅ When the rule isn't about a single field (e.g. "phone **or** email"), use the `validations` parameter of `a!formLayout()` (or `a!sectionLayout()`) with `a!validationMessage()`.
- **Why:** setting `required` on two fields that are alternatives is incorrect; form-level validation expresses the actual rule. With `validateAfter: "SUBMIT"` the message only appears on submit.

Source: https://docs.appian.com/suite/help/latest/recipe-showing-validation-errors-that-arent-specific-to-one-component.html · https://docs.appian.com/suite/help/latest/sail/ux-form-layout.html#behavior-configurations

### 4.2 Conditional requiredness with `validationGroup`
- ✅ To make fields required only if the user clicks a certain button, assign the same `validationGroup` to those fields and to the button; use `requiredMessage` for a custom message.
- **Why:** it defers validation (required and `validations`) until the group is triggered. The `validationGroup` value **cannot contain spaces** (use underscore: `"Future_Hire"`).

Source: https://docs.appian.com/suite/help/latest/recipe-configure-buttons-with-conditional-requiredness.html

### 4.3 `saveInto` with `a!save()` to transform the saved value
- ✅ Use `a!save(target, value)` in `saveInto` when you need to transform the input before saving it (e.g. `todecimal(save!value)`).
- **Why:** it lets the consuming designer always work with the correct type; `save!value` is the value the user entered.

Source: https://docs.appian.com/suite/help/latest/using_interfaces_in_appian.html#reusability

### 4.4 `showWhen` to show/hide at no cost
- ✅ Use `showWhen: false` to conditionally hide layouts or components.
- **Why:** when `showWhen` is false the component is hidden **and not evaluated**, saving work.

Source: https://docs.appian.com/suite/help/latest/Columns_Layout.html#main_content

### 4.5 In scrolling dialogs, fix the title bar and buttons
- ✅ Enable "Fix title bar when scrolling" and "Fix buttons to bottom" on long forms, and consider "Automatically focus on first input" to speed up typing.

Source: https://docs.appian.com/suite/help/latest/sail/ux-form-layout.html#behavior-configurations

### 4.6 Choose the form layout based on the flow
- ✅ Single-screen form → `a!formLayout()`; **sequential multi-step** form → `a!wizardLayout()`, which provides a progress bar (milestone), step navigation, a fixed footer and per-step validation.
- ✅ Prefer `a!wizardLayout()` over building a "wizard" by hand with sections toggled by `showWhen`: the native wizard gives you, for free, the progress, navigation and per-step validation that are expensive and fragile to reproduce by hand.
- ✅ With **more than 5-6 steps**, use the **vertical/side** orientation of the step bar instead of the horizontal one.
- ✅ Group related fields with `a!sectionLayout()`; use `a!tabLayout()` when the content consists of **parallel** views, not sequential steps.
- ❌ Don't leave "Auto" height on an `a!wizardLayout()` inside a dialog (it produces size jumps when changing steps).
- **Why:** each layout is built for a different way of moving through the form; picking the right one saves code and gives a consistent UX.

Source: https://docs.appian.com/suite/help/latest/sail/ux-wizard-layout.html · https://docs.appian.com/suite/help/latest/sail/forms.html

### 4.7 Progressive disclosure: in sequential flows, disable — don't hide
- ✅ In a **sequential** flow (one step enables the next), show fields that aren't yet available as **disabled** (`disabled: true`), not hidden.
- ✅ Reserve `showWhen` for **conditional** visibility (the field applies or not depending on another answer), not for sequential progression.
- ❌ Don't use `showWhen` to hide steps the user can't fill in yet: it loses the preview of what's coming and how much is left.
- **Why:** seeing disabled fields communicates the structure of the flow; `showWhen` is for conditions, not for order.

Source: https://docs.appian.com/suite/help/latest/sail/ux-progressive-disclosure.html

---

## 5. Grids

### 5.1 Read-only vs. editable: choose by use case
- ✅ Tabular read-only data → read-only grid (`a!gridField()`), which supports search, filter, selection, sort and **pagination**.
- ✅ Fast inline editing of a few records → editable grid (`a!gridLayout()`).
- ❌ Don't use an editable grid for large volumes: **it doesn't support pagination**.
- **Why:** to edit large datasets, use a read-only grid with a per-row link, or a record action that edits each record.

Source: https://docs.appian.com/suite/help/latest/Editable_Grid_Component.html#using-the-editable-grid-component

### 5.2 Performance of large editable grids
- ❌ Don't put too many cells in an editable grid.
- ✅ Reduce the number of components; if you use `a!queryEntity()` as the source, set `fetchTotalCount: true` so `totalCount` is valid (otherwise it can come back as -1).
- **Why:** performance depends on the number of components in the interface; many cells make it feel slow.

Source: https://docs.appian.com/suite/help/latest/Editable_Grid_Component.html#using-the-editable-grid-component

### 5.3 Use the record type as the grid's source
- ✅ Feed the grid from a record type to take advantage of the search field and user filters already defined on the object; apply a logical order that shows what matters most at the top.
- ❌ Don't show long blocks of text in a grid, and don't format cells in the same column differently.
- **Why:** grids exist to scan and decide; consistent per-column formatting maximizes readability.

Source: https://docs.appian.com/suite/help/latest/sail/ux-grids.html

### 5.4 Actions in grids: one per cell, or a toolbar above
- ❌ Don't put several related actions inside a single cell.
- ✅ Use the Record Action component in a column (in "Icon Only" style), or show the actions in "Toolbar" style above the grid when it's backed by a record type.

Source: https://docs.appian.com/suite/help/latest/sail/ux-grids.html

### 5.5 Every grid needs a row header (accessibility)
- ✅ Configure a row header on every grid; the first column with text is usually the right choice.
- **Why:** it's an accessibility requirement so screen readers can associate each row.

Source: https://docs.appian.com/suite/help/latest/Editable_Grid_Component.html#grid-height-and-headers

---

## 5A. Charts

### 5A.1 Choose the chart type by the story the data tells
- ✅ **Parts of a whole** → pie (a single category), stacked bar/column (several categories), stacked area (parts of a whole over time).
- ✅ **Distribution** → column (positive and negative values), bar (many categories), scatter (comparing two measures).
- ✅ **Trend over time** → column or line (few intervals), line or area (many intervals).
- ✅ **Comparing categories** → column, line or area (small datasets), line (large datasets).
- ❌ Don't force the data into your preferred chart type: the type is dictated by the data's story, not by taste.
- **Why:** each type is optimized for a different reading; choosing the wrong one hides the pattern you meant to show. A line chart with more than 5 lines is unreadable (use column instead); an area chart stops making sense with more than 3 series.

Source: https://docs.appian.com/suite/help/latest/sail/ux-charts.html

### 5A.2 Minimize series, categories and colors; short labels
- ✅ Design the chart with the minimum number of dimensions and data points needed; use short labels (long ones shrink the plot area and some get hidden).
- ❌ Don't use more than 5 colors in a chart, and don't leave series/category labels undefined when hiding the axes; group small-value categories into an "Other" bucket.
- ⚠️ A pie with many slices, especially thin ones, hides labels: if you can't avoid it, **enable tooltips** so values show on hover.
- **Why:** simple charts are understood faster and load quicker; include a legend only when there are several series.

Source: https://docs.appian.com/suite/help/latest/sail/ux-charts.html · https://docs.appian.com/suite/help/latest/Tempo_Report_Design.html#usability

### 5A.3 Charts with many data points → single-column layout
- ✅ A chart with **more than 7 data points** looks better in a single-column layout; reserve the two-column layout for small charts being compared side by side.
- **Why:** line and column charts with many data points force horizontal scrolling on the user; giving them the full width avoids that. Keep the same layout (one or two columns) across every section of the dashboard for a balanced result.

Source: https://docs.appian.com/suite/help/latest/Tempo_Report_Design.html#usability

### 5A.4 Records-powered: 5,000-row cap and a 65-second timeout
- ✅ Feed charts and aggregations from the record type with `a!recordData()`; for totals and counts use aggregation (`a!aggregationFields()`), not raw rows.
- ❌ Don't try to render all 5,000 rows: records-powered components show **at most 5,000 rows**, and displaying all of them degrades performance.
- ⚠️ Queries against record types (synced or not) **time out after 65 seconds**, just like grids: if you get a timeout, reduce the batch, the fields, or tighten the filters.
- **Why:** a chart is meant for reading a pattern at a glance; thousands of points are neither readable nor performant.

Source: https://docs.appian.com/suite/help/latest/Column_Chart_Component.html#usage-considerations

### 5A.5 Asynchronous loading and background matched to the card
- ✅ Set `loadDataAsync: true` on records-powered charts that are slow to load: the interface displays without waiting for the chart, which shows a placeholder while it loads in the background (see 2.5).
- ✅ When placing a chart inside a colored card, its background takes on the card's color; text and lines adjust automatically over dark backgrounds.
- ⚠️ In offline mobile and portals, async data does **not** load in the background: it arrives together with the rest of the interface.

Source: https://docs.appian.com/suite/help/latest/Column_Chart_Component.html#usage-considerations

> Chart accessibility (a requirement, not optional): every chart needs an equivalent text/grid representation — see 9.5.

---

## 6. Rich text, icons and styles

### 6.1 Only the styles rich text supports exist (there is no HTML)
- ✅ Format text with `a!richTextItem()` / `a!richTextIcon()` using the supported styles: bold, italic, underline, strikethrough, color, safe links, icons and web images.
- ❌ Don't try to inject HTML or arbitrary styles: SAIL doesn't support them; only each component's enumerated parameters and values exist.
- **Why:** the rich text editor only applies that set of styles; any other formatting must be achieved through the component's parameters (`style`, `size`, `color`).

Source: https://docs.appian.com/suite/help/latest/Rich_Text_Component.html#usage-considerations · https://docs.appian.com/suite/help/latest/Styled_Text_Component.html#main_content

### 6.2 Use valid icons and valid colors
- ✅ The `icon` parameter must be a key from the official "Available Icons" list; `color` accepts hex or the enumerated values `STANDARD`, `ACCENT`, `POSITIVE`, `NEGATIVE`, `SECONDARY` (and `WARN` in recent releases); `size` accepts `STANDARD`/`SMALL`/…/`EXTRA_LARGE`.
- ❌ Don't invent icon keys or color values: an invalid `color` in rich text is not caught by `validateExpression`.
- **Why:** out-of-enum values or nonexistent icons break or silently degrade the screen.

Source: https://docs.appian.com/suite/help/latest/Styled_Icon_Component.html#main_content

### 6.3 Don't overuse "Positive"/"Negative", and don't use color as the only channel
- ✅ Reserve Positive (green) and Negative (red) colors for values with **business meaning** (gain/loss, success/failure).
- ❌ Don't use them as arbitrary decoration, and ensure sufficient contrast over colored backgrounds (billboard, card).
- **Why:** colorblind users or those with low vision don't perceive the difference; critical information must be in the words, not only in the color.

Source: https://docs.appian.com/suite/help/latest/sail/ux-rich-text.html#positive-and-negative-colors

### 6.4 Don't wrap text in rich text if you're not going to style it
- ❌ Don't put text in `a!richTextItem()` if you're not applying any style to it.
- ✅ Limit the number of rich text items, and bulleted and numbered lists per screen.
- **Why:** each item increases server evaluation time, client rendering and transmission; showing many components at once slows things down.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#dont-wrap-text-in-arichtextitem-if-you-dont-need-to-style-it · https://docs.appian.com/suite/help/latest/Rich_Text_Component.html#reducing-render-time

---

## 7. UX: consistency, loading states and empty states

### 7.1 Don't overload the page
- ✅ Favor larger text, more white space and fewer elements; before adding content, check that its visual cost pays off.
- **Why:** less cluttered pages feel more modern and usable.

Source: https://docs.appian.com/suite/help/latest/sail/employee-home-pages.html#best-practices-for-employee-home-pages

### 7.2 Preserve layout consistency as data changes
- ✅ Set an upper limit on the number of items per section and a minimum card height.
- ❌ Don't let a card change height sharply depending on how many items it shows.
- **Why:** layout jumps when the data changes are disorienting.

Source: https://docs.appian.com/suite/help/latest/sail/employee-home-pages.html#best-practices-for-employee-home-pages

### 7.3 Show an empty-state message, not an empty list
- ✅ When there's no data, show an "empty list" message and keep a minimum height that balances the page.
- ❌ Don't leave an empty gap without explanation.
- **Why:** it tells the user there are no items (not that something failed) and keeps the layout balanced.

Source: https://docs.appian.com/suite/help/latest/sail/employee-home-pages.html#best-practices-for-employee-home-pages · https://docs.appian.com/suite/help/latest/sail/lists.html#full-page-empty-state-message

### 7.4 Loading states: automatic placeholders
- ✅ Rely on asynchronous loading (section 2.5): components waiting on async data show skeletons automatically.
- **Why:** the user knows content is loading without the rest of the screen being blocked.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#use-asynchronous-loading-for-slow-data

### 7.5 Organize with cards to reduce visual noise
- ✅ Use `a!cardLayout()` to group related content.
- ❌ Don't use it where it isn't allowed: inside a read-only grid, an editable grid, or a side-by-side.

Source: https://docs.appian.com/suite/help/latest/card_layout.html#main_content

---

## 8. Performance anti-patterns (actionable summary)

### 8.1 In `and()`, `or()`, `match()`, put the expensive part last
- ✅ Place expensive computations as the last argument of `and()`, `or()` and `match()`.
- **Why:** these functions short-circuit; if a cheap condition already decides the result, the expensive one is never evaluated.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#when-using-and-or-and-match-functions-put-expensive-computations-last

### 8.2 Independent queries → parallel evaluation
- ✅ If a query in a local variable references another query in another local variable, rewrite so they **don't** depend on each other.
- **Why:** variables that reference each other are evaluated in series; independent ones are evaluated in parallel, reducing total time.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#for-expensive-queries-that-rely-on-each-other-set-them-up-to-evaluate-in-parallel

### 8.3 Limit interactions on data-heavy interfaces
- ❌ Don't add lots of user interactions (filters, inputs) to dashboards with many queries.
- ✅ Use record action components to update data, and a "MENU" when there are many actions.
- **Why:** every interaction re-evaluates the **entire** interface; with many queries that means repeated waits.

Source: https://docs.appian.com/suite/help/latest/interface-performance.html#dont-add-a-lot-of-user-interactions-to-complex-interfaces-that-display-a-lot-of-data

### 8.4 Don't store large volumes in local variables
- ✅ Page/filter before saving into a local variable; remember that variables with a refresh setting other than `refreshAlways` persist in memory across every evaluation of the interface.
- **Why:** storing a lot of data in a variable keeps it in memory for as long as the variable is alive.

Source: https://docs.appian.com/suite/help/latest/expressions-best-practices.html#designing-memory-efficient-expressions

### 8.5 The number of visible components is the factor that weighs most on rendering
- ✅ Reduce the number of components shown at once: page lists, apply dynamic behavior (show detail on demand), and split large screens into steps/tabs.
- ✅ Wrap alternate branches in `if()` / `choose()` (or `showWhen: false`) so hidden components **aren't evaluated**.
- **Why:** the Health Check measures "SAIL interface size" for exactly this reason: the more visible components, the more server evaluation time, client rendering and transmission. It's the dominant factor in a screen's performance, ahead of the number of queries.

Source: https://docs.appian.com/suite/help/latest/SAIL_Performance.html#phase4 · https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html#sail-interface-size

---

## 9. Accessibility

> **Where the depth lives.** The official Appian skill carries 602 lines across
> `references/accessibility-audit.md`, `component-checks.md` and `accessibility-reference.md`: the
> audit procedure and the per-component checks. **This section keeps the criterion and what closes the
> gate, and must not grow.** What the harness adds and nobody else does is that accessibility is
> *gated*: the automatable part is checked by the interface-tree script, and the part that needs a
> person to look at the screen is recorded as an owned residue instead of being quietly skipped.
> **Without that skill installed**, the platform sources cited under each rule are what it is built
> from.

### 9.1 Always a text equivalent
- ✅ Give `altText` to meaningful images and icons; for critical data and controls, express them in text.
- ✅ In read-only grids with conditional background color, add accessibility text explaining the meaning of each color.
- **Why:** screen readers don't read what is purely visual; an image with text only reaches a user who can see the screen.

Source: https://docs.appian.com/suite/help/latest/sail/ux-accessibility.html#always-provide-a-text-equivalent

### 9.2 Don't rely on color to communicate
- ❌ Don't use instructions like "click the red button".
- ✅ Reinforce color with text or icons.
- **Why:** users with low vision or colorblindness can't distinguish the color.

Source: https://docs.appian.com/suite/help/latest/sail/ux-accessibility.html#avoid-relying-on-color-to-communicate-information

### 9.3 Describe inputs explicitly
- ✅ Use `label`, `instructions` and `validations` on every input; if you don't want to show the label, use `labelPosition: "COLLAPSED"` so the screen reader still reads it.
- ✅ Use "Accessibility Text" for extra context (e.g. which section a field belongs to).
- **Why:** accessibility is automatically optimized by using label/instructions/validations; visual proximity isn't enough for a screen-reader user.

Source: https://docs.appian.com/suite/help/latest/sail/ux-accessibility.html#explicitly-describe-form-inputs · https://docs.appian.com/suite/help/latest/sail/ux-accessibility.html#use-accessibility-text-to-provide-supplemental-information

### 9.4 Reference standard: WCAG 2.2 AA / Section 508
- ✅ Design against WCAG 2.2 Level AA and Section 508; test with the recommended browser+reader combinations (Chrome/JAWS, Edge/JAWS, Firefox/NVDA, Safari/VoiceOver).
- **Why:** these are the standards Appian validates its product against; testing accessibility requires doing it with a real screen reader, not just reviewing the SAIL.

Source: https://docs.appian.com/suite/help/latest/building_accessible_applications.html#main_content

### 9.5 A chart is only visual: always offer the same information as a grid
- ✅ Every chart needs an equivalent text representation a screen reader can read; the recommended pattern is a **chart↔grid toggle** showing exactly the same data.
- ✅ Implement it with a boolean local variable (e.g. `local!showAsGrid`) and an `a!dynamicLink` that flips it with `not()`; an `if()` decides whether the chart or the grid is rendered.
- ❌ Don't leave a chart as the **only** way to access the data.
- **Why:** charts are built for users who can see the screen; a screen reader doesn't interpret a chart. It's an accessibility requirement, not an optional extra.

Source: https://docs.appian.com/suite/help/latest/recipe-configure-a-chart-to-grid-toggle.html · https://docs.appian.com/suite/help/latest/Tempo_Report_Design.html#usability

### 9.6 Headers with real heading tags (H1–H6), not enlarged rich text
- ✅ Structure headers with **section headers** and **heading fields** (`a!headingField()`), setting their level with the "Accessibility Heading Tag" parameter (`labelHeadingTag` on sections, `headingTag` on `a!headingField()`), not with an `a!richTextItem()` with a larger `size`/`color` that only *looks* like a title.
- ✅ Respect the hierarchy and **correct the default mapping** when nesting: the default tag depends on the label size (Extra Large / Large Plus / Large → H1; Medium Plus / Medium → H2; Small → H3; Extra Small → H4), so a "Large" section nested under an "Extra Large" one must have its heading tag moved from **H1 to H2** (avoid two H1s on the same screen).
- ❌ Don't imitate headers with large colored text: the screen reader doesn't announce it as a header, and the user loses heading-based navigation.
- **Why:** screen readers move through the page by jumping between headings and only recognize them if they carry the semantic heading tag; an enlarged rich text is visually a title but semantically plain text.

Source: https://docs.appian.com/suite/help/latest/sail/ux-accessibility.html#use-accessible-headers · https://docs.appian.com/suite/help/latest/sail/content-structure.html

---

## Sources

All of the doctrine above comes from official Appian documentation (`docs.appian.com/suite/help/latest/…`, aliased to the latest release). Reference pages:

- Interface Performance Best Practices — https://docs.appian.com/suite/help/latest/interface-performance.html
- Local Variables — https://docs.appian.com/suite/help/latest/Local_Variables.html
- Interface Object (rule inputs and local variables) — https://docs.appian.com/suite/help/latest/interface_object.html
- Reusing Interfaces — https://docs.appian.com/suite/help/latest/using_interfaces_in_appian.html#reusability
- Offline Mobile Design Best Practices — https://docs.appian.com/suite/help/latest/offline-mobile-design-best-practices.html
- About Queries — https://docs.appian.com/suite/help/latest/about-queries.html
- a!queryRecordByIdentifier() — https://docs.appian.com/suite/help/latest/fnc_system_a_queryrecordbyidentifier.html
- a!queryRecordType() — https://docs.appian.com/suite/help/latest/fnc_system_queryrecordtype.html
- a!queryEntity() — https://docs.appian.com/suite/help/latest/fnc_system_a_queryentity.html
- Recipes for Querying Records — https://docs.appian.com/suite/help/latest/Query_Recipes.html
- Record Type Query Performance Best Practices — https://docs.appian.com/suite/help/latest/query-best-practices.html
- Expressions Best Practices — https://docs.appian.com/suite/help/latest/expressions-best-practices.html
- Responsive Design — https://docs.appian.com/suite/help/latest/responsive_design.html
- Columns Layout — https://docs.appian.com/suite/help/latest/Columns_Layout.html · Design guidance: https://docs.appian.com/suite/help/latest/sail/ux-columns-layout.html
- Form Layout (design) — https://docs.appian.com/suite/help/latest/sail/ux-form-layout.html
- Forms (design) — https://docs.appian.com/suite/help/latest/sail/forms.html
- Wizard Layout (design) — https://docs.appian.com/suite/help/latest/sail/ux-wizard-layout.html
- Progressive Disclosure (design) — https://docs.appian.com/suite/help/latest/sail/ux-progressive-disclosure.html
- Recipe: Conditional Requiredness — https://docs.appian.com/suite/help/latest/recipe-configure-buttons-with-conditional-requiredness.html
- Recipe: Validation Errors not specific to one component — https://docs.appian.com/suite/help/latest/recipe-showing-validation-errors-that-arent-specific-to-one-component.html
- Editable Grid Component — https://docs.appian.com/suite/help/latest/Editable_Grid_Component.html
- Grids (design) — https://docs.appian.com/suite/help/latest/sail/ux-grids.html
- Charts (design) — https://docs.appian.com/suite/help/latest/sail/ux-charts.html
- Column Chart Component (usage considerations) — https://docs.appian.com/suite/help/latest/Column_Chart_Component.html
- Tempo Report Design (usability) — https://docs.appian.com/suite/help/latest/Tempo_Report_Design.html
- Recipe: Chart-to-Grid Toggle — https://docs.appian.com/suite/help/latest/recipe-configure-a-chart-to-grid-toggle.html
- Rich Text Display Component — https://docs.appian.com/suite/help/latest/Rich_Text_Component.html
- Rich Text Item — https://docs.appian.com/suite/help/latest/Styled_Text_Component.html
- Rich Text Icon — https://docs.appian.com/suite/help/latest/Styled_Icon_Component.html
- Rich Text (design) — https://docs.appian.com/suite/help/latest/sail/ux-rich-text.html
- Card Layout — https://docs.appian.com/suite/help/latest/card_layout.html
- Lists (empty state) — https://docs.appian.com/suite/help/latest/sail/lists.html
- Employee Home Pages (design) — https://docs.appian.com/suite/help/latest/sail/employee-home-pages.html
- Accessibility (design) — https://docs.appian.com/suite/help/latest/sail/ux-accessibility.html
- Content Structure (design) — https://docs.appian.com/suite/help/latest/sail/content-structure.html
- Building Accessible Applications — https://docs.appian.com/suite/help/latest/building_accessible_applications.html
- SAIL Performance — https://docs.appian.com/suite/help/latest/SAIL_Performance.html
- Understanding the Health Check Report (SAIL interface size) — https://docs.appian.com/suite/help/latest/understanding-the-health-check-report.html
