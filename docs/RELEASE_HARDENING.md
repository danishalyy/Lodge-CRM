# Security and reliability checkpoint — 16 November 2026

**Release status: not yet commercially production accepted.** This checkpoint fixes reproduced defects and adds operational controls. It does not replace the original 63-item requirements register, make unfinished features complete, prove Hostinger capacity, or guarantee an absence of bugs.

## Confidentiality

- Shared server-side feature policy now checks entitlements alongside existing role permission, subscription and RLS enforcement, including direct core API calls. Unknown permission namespaces fail closed.
- Dashboard aggregates, attention items and historical summaries respect the underlying module permissions and entitlements; dashboard-only custom roles do not gain operational data.
- Operational history filters by underlying resource permission and department/assignment visibility before returning events. Anonymised guest projections mask old identifying summaries/details while preserving immutable stored evidence. Guest creation no longer writes names into new event summaries.
- Existing platform-only Super Admin, explicit Group Admin memberships, CSRF, session isolation and MFA checks remain intact. No impersonation path was added.
- Production uses HTTPS-only app/media origins, secure cookies, private internal service ports and validated runtime DB privileges. API/web run without root; the production overlay drops capabilities and uses read-only application filesystems.
- Encrypted backups include stable encryption keys/configuration and private media. Separate private HMAC keys authenticate recovery manifests; restore rejects tampering, unsafe archive paths and nonempty targets.

## Integrity

- Shared domain-state service uses transaction-scoped asset locks, preserving departing-stay occupancy and preventing concurrent room/vehicle transitions from overwriting authoritative state.
- Vehicle departures recheck live scheduled faults rather than trusting cached readiness. Returns retain newly due faults, and completing repairs preserves an active drive/transfer until it actually finishes. Manual ready cannot override an active journey.
- Dirty or maintenance-blocked rooms cannot be checked in. Closing one ticket cannot release an asset with another active blocking fault; future scheduled faults do not prematurely block available assets. Manual ready overrides cannot bypass active faults.
- Local lodge business dates govern subscription/date-dependent operations instead of server UTC calendar boundaries.
- Restored sessions/tokens/actions are invalidated and old delivery jobs held to prevent stale credentials or duplicate outbound effects. Audit/history remain append-only.
- Vulnerable pinned Python dependencies were updated. Regression tests exercise reproduced security/workflow failures, archive tampering, recovery and configuration rejection.

## Availability and encapsulation

- Shared deployment, clock, history, state, feature-policy, login-limit and recovery services encapsulate security/domain rules rather than duplicating them across screens.
- A bounded local authentication limiter prevents unbounded login retries during Redis failure. It is per process, not a replacement for distributed Redis limiting.
- Readiness measures DB, Redis, actual scheduled worker heartbeat and object storage with bounded downstream calls and sanitised errors. Worker/beat healthchecks no longer depend on a nonexistent HTTP server.
- Production overlay includes restart policies, rotating logs, private services and a TLS reverse proxy. API startup smoke runs as the actual nonroot image user.
- Live queued-update controls are visible outside the hidden desktop header. Notification controls remain reachable across desktop/mobile shells. Browser fixtures distinguish first-run onboarding from established-account workflows.
- Runtime/build uses supported Node 24 and Debian-based images. The existing pinned MinIO server release is built from source using updated build/runtime bases; existing data volumes are preserved.

## Validation evidence

The release work includes the full API suite, production frontend build, automated browser flows, dependency audits and an isolated real Docker backup/restore drill. Final local outcomes are recorded below; no simulated UI response is treated as proof of backend or real-provider correctness.

Local checks completed: all 100 browser tests passed with no skips; the production frontend build passed; static guard QA passed for 177 API routes and 25 module pages; Python and npm audits reported zero known vulnerabilities; the final API image imported its security/state services successfully as UID 10001. The final frozen-code API suite passed **893 tests**, with no skips or failures; five framework deprecation warnings remain. A separate fresh 98-case history/workflow run also passed. Automated browser checks use mocked HTTP fixtures; API integration cases use real PostgreSQL/RLS and Redis. These checks complement the isolated Docker recovery drill and do not replace live-provider acceptance.

The isolated recovery drill passed all nine checks: encrypted/authenticated archive validation, empty-target restore, recovered guest record, exact private-media bytes, rejected pre-backup session, new login, source services resumed, real worker/scheduler/storage readiness and refusal to overwrite the restored nonempty target. This used synthetic records and separate disposable volumes, not customer data. It does not certify real email or live AI quality.

## Phase changelog

- Phase 1: fixed reproduced entitlement, departmental history, privacy, occupancy and multi-fault release defects; repaired live-update visibility and browser fixtures; updated vulnerable dependencies. The first complete API checkpoint passed 876 tests.
- Phase 2: added production isolation, configuration checks, bounded dependency calls, outage login limiting, encrypted/authenticated recovery, scheduler readiness and connected vehicle/dashboard regressions. Live-provider deployment and unfinished product capabilities remain open below.

## Outstanding product and launch work

[REQUIREMENTS_DELIVERY.md](REQUIREMENTS_DELIVERY.md) and `requirements/delivery-map.json` remain authoritative for all 63 package items. The current register contains 24 implemented cores, 25 partial capabilities, 4 missing capabilities, 9 provider-dependent capabilities and 1 operational service requirement. “Implemented core” still requires connected-role and commercial acceptance. In particular, the restricted guest web/QR journey, expanded reporting/exports, maintenance media/history/recurrence, task templates/escalations and additional advanced fleet/AI workflows must be completed and accepted before selling those capabilities. Existing feature flags are not proof of implementation. Native apps and payment processing remain deferred; South Africa/ZAR and external payments remain the owner's choices.

Provider adapters cannot be accepted until booking/accounting/GPS/WhatsApp/SMS services are selected and their sandbox/contract tests run. Production DNS/TLS, SMTP sender delivery, optional push and live-model tool/permission evaluations need configured services. Hosting was deferred by the owner; no production deployment or infrastructure purchase occurred here. Establish real VPS load/concurrency limits, off-server backup scheduling, measured RPO/RTO, monitoring/on-call response, legal/privacy retention and launch-lodge role acceptance. A single VPS is not redundant infrastructure.

Use [PRODUCTION_OPERATIONS.md](PRODUCTION_OPERATIONS.md) for concrete setup/recovery commands. Keep credentials out of Git and preserve encryption keys on upgrades. This checkpoint should be reviewed alongside the full requirement gap register, not advertised as completion of the entire application.
