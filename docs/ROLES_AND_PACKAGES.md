# Roles and packages usability

## Part A — Roles

The API supplies eleven locked staff presets, their actual DB grants, copyable permissions, allowed assignments, scope descriptions, and grouped action metadata. Custom copies exclude sensitive grants and actions the creator does not own. The editor provides simple group choices, Advanced controls, a live summary, editable custom roles, assignment counts and impact confirmation. Staff Add/Edit access forms show preset and custom-role choices. Assignment validates actor permissions, active roles, department requirements and lodge ownership. Invitations apply custom roles before their transaction commits. Deactivation restores the previous preset and retains history rather than hard-deleting roles.

Scope descriptions reflect endpoint behavior; maintenance is a workshop pool and finance is not a universal money-only filter. Migration 0014 makes three narrow existing administrator capabilities explicit for strict preset-copy/delegation checks. RLS and sensitive custom-role blocks are unchanged.

Validation: 453 API tests, production build and targeted browser flows passed. Preset → custom copy → edit → staff assignment → deactivate is covered. Optional per-lodge preset editing is intentionally not implemented; presets stay locked.

## Part B — Packages

Super Admin can edit each active database plan's working feature grants. The review step shows the affected lodge count; the API checks both the plan revision and count before committing an audited change. Changes apply dynamically through existing entitlement checks, while lodge exceptions remain in force. Plans and their descriptions now populate registration and subscription choices, with a shared comparison table.

One server catalogue describes and groups implemented capabilities separately from coming-soon capabilities. AI, external integrations, live tracking and telemetry cannot be enabled as usable access. Existing future plan associations are retained as roadmap information only. Lodge exceptions require a reason, display plan/default/exception/final access separately, and record the reason in the audit log. Locked screens query actual database plans and can create a private access-review notification for active Super Admin recipients, with daily request deduplication. They do not grant access. Existing subscription write restrictions apply. Optional email delivery follows recipient preferences and configured delivery settings; the in-app notification does not require an email provider.

Migration 0015 adds plan descriptions, revisions, ordering and exception reasons. No RLS policy is removed. Validation: 462 API tests, production frontend build, static guard audit and browser checks for registration, affected-lodge confirmation and locked navigation. No requested Part B work remains; unfinished product capabilities remain explicitly marked coming soon, rather than being implemented by this access-management change.

## Part C — Form and regional polish

Registration uses a searchable time-zone combobox, defaults to the browser zone, supports arrow keys/Enter/Escape and rejects unknown zones inline. API validation messages distinguish email, date, number, range, option and time-zone errors without exposing raw validation details. Shared forms show a summary and focus the affected field; registration field names now match API field names so errors attach correctly.

Migration 0016 changes only the currency default to PKR. Existing lodge values are not updated; all prior currency choices remain available. Tests exercise both ORM and database defaults and preserve an explicitly selected ZAR currency. New UI copy remains in the shared English catalogues for future translation.

Validation: 463 API tests, the production frontend build, all 35 browser checks and the static guard audit pass. Browser coverage includes login, activation, MFA, custom-role copy/edit/assignment/deactivation, package impact confirmation, registration errors and time-zone selection, guest creation, and responsive accessibility checks at 375, 768, 1366 and 1440 px in both themes. The combobox handles Escape before its enclosing Radix/Vaul drawer, and opens again on click after selection. Package panel spacing was reviewed in desktop dark and mobile light views.

Nothing required in Part C remains undone. Optional per-lodge preset editing remains unimplemented by design. Unbuilt capabilities remain coming soon. Migrations were verified on temporary test databases; updating an installation through the existing Docker Compose migration service applies migrations 0014–0016. Existing lodge currency choices are preserved.

## South Africa release default

Currency settings, monetary fuel and maintenance fields, cost summaries, and the existing external-payment wording are restored. The South Africa launch uses ZAR as the ORM, database and display fallback for new lodges. Migration 0017 changes only the database default; it does not rewrite existing lodge choices. All supported currencies remain selectable. Existing payment handling stays outside SafariOS; this restoration adds no payment gateway. Accounting integrations remain explicitly coming soon.

Restoration validation: 464 API tests, the production frontend build, six relevant browser checks and the static guard audit pass. Tests cover restored fuel and parts costs, report totals, ZAR database/ORM defaults, selectable currencies, and preservation of explicitly selected currencies. Responsive registration remains checked in both themes at 375, 768, 1366 and 1440 px.
