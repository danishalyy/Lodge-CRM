# Lodge CRM 1.8 — Full QA Audit (updated hardening baseline)

This release adds a broad regression/audit suite across authentication, tenancy, roles, subscription states, package entitlements, operational workflows, uploads, migrations, frontend route coverage and UI security wiring.

## Roles covered
Super Admin; Lodge Admin / General Manager; Department Manager / Supervisor; Front Office / Guest Services; Ranger / Guide; Housekeeping; Maintenance / Workshop; Driver / Transport; F&B / Kitchen; Finance / Accounts; General Staff; Read Only / Auditor.

## Operational surfaces covered
Authentication, activation, password reset, MFA, lodge onboarding, subscriptions, entitlements, departments, staff, HR, rooms, guest CRM, stays, tasks, requests, maintenance, fleet, checklists, fuel, activities, transfers, wildlife, ranger workspace, notifications, notification preferences, operational memory, reports, custom roles, housekeeping, feedback, F&B, task attachments and Super Admin platform routes.

## Test approaches
1. Existing functional schema/state contract tests.
2. Dynamic FastAPI route-surface introspection.
3. CSRF coverage for every authenticated mutation.
4. Tenant authorization coverage for every lodge endpoint.
5. Subscription write-gating coverage for every lodge mutation.
6. Super Admin guard coverage for every platform endpoint.
7. Migration chain/revision validation.
8. RLS and restricted application database-role checks.
9. Role/record-scope contract checks.
10. Frontend module/page/API security wiring checks.
11. UI design-system checks (charcoal tokens, reduced-motion support, dashboard charts/calendar).

## Runtime boundary
The source QA suite does not replace a real Docker/PostgreSQL browser E2E run. Full end-to-end acceptance still requires the Compose stack to be running so HTTP requests can exercise PostgreSQL RLS, Redis, MinIO, Celery and the browser together. `scripts/runtime_acceptance.sh` can be added/run on the target machine for that phase.
