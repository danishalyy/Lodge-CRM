# SafariOS UX implementation phases

## Phase 1 — Errors and accessibility

Implemented shared `ApiError`/`formatApiError` handling, safe server-error messages, field-level Pydantic validation, shared `Form`, `Field` and password controls. Drawer/modal forms use the shared primitives; client validation is inline, labels connect to controls, required fields and helper/error descriptions are exposed, contact fields have appropriate semantics. Icon close controls are named; the existing Radix/Vaul focus trap and Escape handling remain, with explicit restoration to the opening control. Login, activation and reset include password visibility and live 12-character guidance. Existing security headers, cookies and checks remain unchanged.

Validation: **435 API tests passed**, **production build passed**, **22 browser checks passed**, including new login error/visibility and guest-drawer validation/focus checks. Existing activation and branding checks passed. Browser API responses are fixtures; these do not replace API integration tests.

Remaining across later phases: dedicated full registration and MFA browser flows, navigation/onboarding, MFA recovery, content/preferences, and final responsive visual checks. Existing English labels are preserved; new validation copy is collected in `lib/strings/forms.ts` for later localization. Full localization is not included.

## Phase 2 — Onboarding and navigation clarity

Added a permission/feature-aware setup checklist with progress and one next primary action; empty new workspaces suppress zero metrics/charts while operational activity remains visible. Role-authorized modules now appear locked when unavailable, open an access-review screen without mounting protected content, and preserve the requested URL. Sidebar, mobile navigation and command search indicate locks. This supersedes the earlier hidden-module policy; disabled subfeatures remain hidden and backend enforcement is unchanged. Single-lodge users no longer see a selector duplicating their lodge identity. Housekeeping jobs, maintenance tickets and assets use the shared drawers with sticky action footers. Super Admin activation guidance explains mandatory authenticator setup and console access.

Validation: **435 API tests passed**, **production build passed**, **24 browser checks passed**. Updated the static CSRF/credentials source assertion to accept formatting/quote changes without changing its security expectations. Added fresh-lodge and maintenance-drawer browser checks; locked-feature tests confirm no disabled endpoint request occurs.

Remaining: access review provides administrator/provider instructions rather than sending a support message (no support contact configured). Setup progress uses existing authorized list endpoints; no new aggregate API or customer data is introduced. Security recovery and final content/visual work follow below.
