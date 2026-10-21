# Lodge CRM 1.8 — security and workflow hardening

This release addresses the source-audit defects identified against 1.7.x. It adds immediate offboarding/session revocation, active-employment enforcement, one-lodge-per-user enforcement, strict request schemas, database/app conflict protection, append-only history, corrected room/housekeeping/maintenance state handling, task proof/recurrence/reassignment safeguards, HR/contact least privilege, custom-role privilege restrictions and role restoration, MFA replay protection and re-authenticated disable, account lockout/password hardening/session management, production docs/header hardening, wildlife protected-location controls, vehicle safety/fuel/odometer checks, missed subscription reminder catch-up, room-readiness alerts, and live runtime acceptance tooling.

## Verification boundary

`pytest` validates the included source/contract/regression suite. Full production sign-off still requires `scripts/runtime_acceptance.sh` against PostgreSQL, Redis, object storage, Celery, and the Next.js UI, plus authenticated two-lodge concurrency/security testing. The script preserves Docker volumes and intentionally fails instead of hiding runtime errors.

## Later account-scope update

On 21 October 2026 the owner restored Group Admin and explicit multi-lodge groups. The one-lodge restriction in this historical release remains in force for ordinary staff and Lodge Admin accounts; assigned Group Admin memberships are now the controlled exception. See [group setup](LODGE_GROUPS_AND_FEEDBACK.md).
