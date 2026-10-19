# Lodge CRM 1.6 — Use-case and regression test matrix

This release treats the requirements documents as the source of truth. Automated contract/schema tests cover the critical authorization, tenancy, subscription, workflow, validation and persistence rules that can be verified without an external browser/device/provider. Docker-based end-to-end tests must still be run on the target machine because this build environment does not provide Docker.

## Automated coverage

- Identity: login/session contract, CSRF contract, password recovery, MFA annotations/imports.
- Tenant security: lodge scope, RLS policy generation, restricted app DB role contract, no trusted tenant header.
- Subscriptions: Pending/Suspended hard block, Expired read-only, Active/Expiring Soon, package entitlements and overrides.
- Role scope: Department Manager department-only; General Staff own-task; Ranger/Driver/Housekeeping own-assignment rules; read-only write denial contract.
- Core CRM: guests, stays, room conflicts/status transitions, guest requests and linked tasks.
- Guest experience: feedback/compliment/complaint validation, department scope, ratings and mandatory resolution.
- Staff/HR: leave overlap, credentials, training, shift overlap/state machine, incidents, performance ratings.
- Tasks: lifecycle, recurrence, required checklist completion, comments, verified attachments, own-task visibility.
- Housekeeping: workflow/state transitions and authoritative room status updates.
- Maintenance: assets, parts, recurrence and workshop linkage.
- Safari: vehicle/activity/transfer/wildlife contract tests retained from previous releases.
- F&B: meal scheduling, guest assignment, dietary/allergy context, service state machine.
- Object storage: allowed content types, size caps, tenant-key prefix and SHA-256 verification.
- Migrations: chain continuity, revision length safety, RLS on new tenant tables, permissions and entitlements.
- Anti-prototype checks: no demo lodge/guest seeds or fake provider success paths in new migration.

## Target-machine acceptance tests

After Docker starts, verify: `docker compose ps`, `/health`, Super Admin bootstrap/login, lodge creation, activation link, subscription state changes, one user from each role, cross-lodge denial, package denial, each workflow create/update/complete path, MinIO upload/download, Celery overdue/expiry jobs, restart persistence, and database backup/restore before a live pilot.
