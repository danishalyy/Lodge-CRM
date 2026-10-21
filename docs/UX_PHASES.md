# SafariOS UX implementation phases

## Phase 1 — Errors and accessibility

Implemented shared `ApiError`/`formatApiError` handling, safe server-error messages, field-level Pydantic validation, shared `Form`, `Field` and password controls. Drawer/modal forms use the shared primitives; client validation is inline, labels connect to controls, required fields and helper/error descriptions are exposed, contact fields have appropriate semantics. Icon close controls are named; the existing Radix/Vaul focus trap and Escape handling remain, with explicit restoration to the opening control. Login, activation and reset include password visibility and live 12-character guidance. Existing security headers, cookies and checks remain unchanged.

Validation: **435 API tests passed**, **production build passed**, **22 browser checks passed**, including new login error/visibility and guest-drawer validation/focus checks. Existing activation and branding checks passed. Browser API responses are fixtures; these do not replace API integration tests.

Remaining across later phases: dedicated full registration and MFA browser flows, navigation/onboarding, MFA recovery, content/preferences, and final responsive visual checks. Existing English labels are preserved; new validation copy is collected in `lib/strings/forms.ts` for later localization. Full localization is not included.
