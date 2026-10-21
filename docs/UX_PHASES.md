# SafariOS UX implementation phases

## Phase 1 — Errors and accessibility

Implemented shared `ApiError`/`formatApiError` handling, safe server-error messages, field-level Pydantic validation, shared `Form`, `Field` and password controls. Drawer/modal forms use the shared primitives; client validation is inline, labels connect to controls, required fields and helper/error descriptions are exposed, contact fields have appropriate semantics. Icon close controls are named; the existing Radix/Vaul focus trap and Escape handling remain, with explicit restoration to the opening control. Login, activation and reset include password visibility and live 12-character guidance. Existing security headers, cookies and checks remain unchanged.

Validation: **435 API tests passed**, **production build passed**, **22 browser checks passed**, including new login error/visibility and guest-drawer validation/focus checks. Existing activation and branding checks passed. Browser API responses are fixtures; these do not replace API integration tests.

Remaining across later phases: dedicated full registration and MFA browser flows, navigation/onboarding, MFA recovery, content/preferences, and final responsive visual checks. Existing English labels are preserved; new validation copy is collected in `lib/strings/forms.ts` for later localization. Full localization is not included.

## Phase 2 — Onboarding and navigation clarity

Added a permission/feature-aware setup checklist with progress and one next primary action; empty new workspaces suppress zero metrics/charts while operational activity remains visible. Role-authorized modules now appear locked when unavailable, open an access-review screen without mounting protected content, and preserve the requested URL. Sidebar, mobile navigation and command search indicate locks. This supersedes the earlier hidden-module policy; disabled subfeatures remain hidden and backend enforcement is unchanged. Single-lodge users no longer see a selector duplicating their lodge identity. Housekeeping jobs, maintenance tickets and assets use the shared drawers with sticky action footers. Super Admin activation guidance explains mandatory authenticator setup and console access.

Validation: **435 API tests passed**, **production build passed**, **24 browser checks passed**. Updated the static CSRF/credentials source assertion to accept formatting/quote changes without changing its security expectations. Added fresh-lodge and maintenance-drawer browser checks; locked-feature tests confirm no disabled endpoint request occurs.

Remaining: access review provides administrator/provider instructions rather than sending a support message (no support contact configured). Setup progress uses existing authorized list endpoints; no new aggregate API or customer data is introduced. Security recovery and final content/visual work follow below.

## Phase 3 — Security UX

Added locally generated authenticator QR images, ten one-time recovery codes at enrollment, private text downloads, password-plus-fresh-TOTP regeneration, and a recovery-code login option. Codes contain 80 random bits, are stored only as account-bound SHA-256 hashes, never returned by account reads, and are consumed under the existing account row lock. Regeneration replaces old codes; disabling MFA clears them; authenticator replay prevention remains. Added migration `0012_mfa_recovery_codes`. Its narrowly scoped INSERT-only audit policy permits only the authenticated account’s own named MFA events; existing audit read isolation and append-only protection are retained. Failed MFA attempts contribute to the existing account lockout.

Lodge Admin MFA reminders are optional/dismissible. Read-only Rooms controls and Stays/Requests auxiliary lookups now honor both feature and permission checks; housekeeping/maintenance lookups use the same restriction.

Validation: **441 API tests passed**, **production build passed**, **27 browser checks passed**, **151-route guard audit passed (0 issues)**. Integration tests verify hashed/private codes, one-time and concurrent consumption, password/CSRF requirements, replacement, cross-account rejection and disable cleanup. Browser checks exercise QR rendering, code download, regeneration, one-time display, recovery login and forbidden-lookup prevention.

Remaining: already-enrolled accounts must use Security settings to generate their first recovery codes. Recovery codes are intentionally unrecoverable after closing/reloading; regenerate them if lost while authenticator access remains. Operators must apply the new migration before running the updated API. No real email or external QR service is used by tests.

## Phase 4 — Content and polish

Centralized readable status/event copy, display descriptions, package summaries and formatting helpers. Status pills, options, delivery messages, operational history and platform audit presentation no longer expose raw status/event keys. Successful mutations name the affected record/action. Each sidebar module has its own icon. Registration has a searchable native time-zone dropdown with browser default, local-calendar start/+one-year expiry defaults, a styled existing logo preview/upload and package summaries. Guest nationality is an ISO country picker using localized display names. Fixed duplicate cleaning states, enlarged housekeeping stat labels, improved action spacing and repaired the lodge-search input alignment.

Added migration `0013_lodge_display_preferences`, guarded read/write APIs, a dedicated administrator permission and audited date-format/currency settings. Ordinary roles cannot edit another lodge’s preferences; CSRF and subscription write checks remain. Date/time and amount displays use viewer locale and lodge preferences; date-only values do not move to the preceding day in western time zones. Currency selection does not perform currency conversion and the form explains this. Registration validates time zones on the API.

Validation: **449 API tests passed**, **production build passed**, **30 browser checks passed**, **date-only/legacy-zone/event-label edge-case test passed**, **153-route static guard audit passed**. Dedicated registration, guest creation and preference-saving browser flows pass. The prior raw `pending_activation` browser expectation was updated to its readable equivalent.

Remaining for the final pass: three secondary HR/service-date captions, full requested-width visual checks, token/contrast/focus polish. Supported currencies are the 34 common lodge/business currencies listed by the API and picker; no payment processing or currency conversion is introduced. Full translation into other languages is not included; the new catalogues and Intl-based helpers prepare the copy/display layer for it.

## Phase 5 — Shared visual style and final verification

Added shared material, radius, spacing and shadow tokens in `app/design-system.css`, mapped through the existing reference palette and Tailwind. Cards use 24px corners, controls 12px, dialogs 28px, and glass uses 32px blur with restrained inset highlights/shadows. Kept the owner’s exact `#363636` canvas and `#171717` sidebar, existing olive accents, dark default and saved light preference. Input boundaries and focus rings have stronger contrast; solid surfaces remain available without backdrop filtering and reduced-motion behavior remains. Removed a legacy inner drawer scroll/animation layer that clipped focus rings and blocked sticky action footers. Corrected mobile radius overrides and the nested lodge-search input border.

Finished secondary HR/service-date formatting and explicit confirmation-dialog focus restoration. The final form audit also connected guest-profile editing to shared inline validation, made profile opening keyboard-accessible and protected read-only controls. Setup progress counts invited staff accounts rather than profiles without login access.

Validation: **449 API tests passed**, **production build passed**, **33 browser/unit checks passed**. After the last checklist-only adjustment, the setup browser check passed again against a fresh production build. The browser suite checks 375, 768, 1366 and 1440px in light/dark themes, including dialog containment, focus trapping, visible sticky actions, overflow, material tokens and automated WCAG A/AA checks on representative registration/guest flows. Existing login, activation, MFA, branding, account isolation, role/feature gating, notifications and group flows pass. **153-route guard audit: 0 issues. Production dependency audit: 0 vulnerabilities.** Screenshots for all requested width/theme combinations are in `docs/screenshots/`.

Remaining: real-device Safari/Firefox review and production deployment/email delivery verification have not been performed. Browser checks use Chromium and controlled API fixtures; PostgreSQL integration tests cover the API separately. The access-review action provides administrator/provider instructions because no support destination is configured. Full language translations and currency conversion remain outside this change; supported display options are documented in Phase 4. These results are not a blanket production certification.

## Updating an existing local checkout

The release includes Alembic migrations `0012_mfa_recovery_codes` and `0013_lodge_display_preferences`. From the repository root, use the existing environment file:

```sh
git pull origin main
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

The Compose migration service applies `alembic upgrade head` before the API starts. Existing MFA users can generate their first recovery codes in Account Security using their current password and authenticator. New enrollments receive codes during confirmation. Lodge/Group Admins can change date/currency presentation in Account Security → Lodge preferences.
