# Commercial web release

See [the latest requirements review](REQUIREMENTS_REVIEW.md) for the three-document scope reconciliation, role/workflow matrix, and source findings against revision `2e75970`. Historical milestone evidence below is not a current feature-completion certificate.

## Agreed product boundaries

The owner confirmed a web application first, external payment collection, and Hostinger VPS as the future deployment target. Hosting provisioning is deferred. Super Admin manually controls package, activation, suspension and subscription dates; no payment integration is required.

Requirements were supplied as `Lodge_CRM_Packages_and_Features.docx`, `AI_Lodge_CRM_Complete_Workflow_and_Role_Access.pdf`, and `AI-LODGE-CRM-OPERATING-SYSTEM.pdf`. The workflow specification explicitly applies newer owner decisions: **Group Admin / Owner and multi-lodge management were initially excluded**. The owner explicitly restored them on 21 October 2026; [group setup and boundaries](LODGE_GROUPS_AND_FEEDBACK.md) now govern this scope. Payroll and the booking system can remain external.

Web-first delivery defers native mobile applications. It does not silently remove the remaining documented web, role, package, AI, offline and integration requirements. Standard/Premium features must not be advertised as available until implemented and verified. External integrations require a named provider, supported API and customer configuration; telemetry additionally requires real devices/providers.

## Implementation and evidence register

The existing `REQUIREMENTS_COMPLIANCE.md` is a source-code inventory, not a production acceptance certificate. Most of the original 323 tests check source structure or schemas. They do not demonstrate all role or tenant boundaries at runtime.

| Area | Current evidence / gap | Release acceptance |
| --- | --- | --- |
| Identity and MFA | Password reset previously created a session without MFA; enrollment could overwrite enabled MFA. Both paths corrected in this milestone. | Real PostgreSQL HTTP regression tests; recovery invalidates sessions; enrollment cannot replace active MFA; password and OTP required for disable. Login and enrollment now serialize MFA state updates, and password reset consumes tokens under a row lock. Concurrent reset and OTP reuse regressions are covered. Broader recovery-abuse and session-policy review remains. |
| Tenant isolation | RLS and application scope checks exist. Representative real PostgreSQL tests added using a dedicated non-superuser role. | Expand to every resource, department, own-record role, export, attachment and worker path; test both reads and writes. |
| Package/subscription gates | Basic/Standard/Premium and external subscription controls exist. Runtime expired/pending/suspended cases added. | Full entitlement and override matrix, date boundaries and user-visible denied/read-only states. |
| Guests/stays/requests/feedback | Persistent foundation exists. | Browser workflows and concurrent arrival/room conflicts; guest history, occasions and communication gaps resolved. |
| Staff/HR/departments | Persistent foundation exists; confidential scope is sensitive. | Department/own-record access matrix, employment revocation, assignment and approval tests. Complete planning/workload gaps. |
| Tasks/housekeeping/maintenance | Persistent workflows and attachments exist. | Full browser lifecycle, required proof/checklists, recurrence and inspection tests. Complete escalation/template/maintenance media gaps. |
| Fleet/safari/transfers/F&B | Persistent foundation exists. | Concurrency, scheduling, safety/expiry/reminder rules, diet/allergy visibility and completion tests. |
| Files/object storage | MinIO build was blocked by Alpine package network access during onboarding. | Real upload/download, content validation, tenant-scoped URLs, expiry, retention and backup/restore. |
| Notifications/workers | Default worker did not import operational tasks; Compose startup corrected. | Durable delivery/retry tests, failure recovery, deduplication, real SMTP staging; push deferred with native apps unless web push is explicitly selected. |
| Offline wildlife | IndexedDB queue foundation exists. | Per-user/lodge isolation, account switching/logout, crash recovery, photo persistence, conflict/idempotency and reconnect tests. |
| Reports/history | Live summaries and event/audit foundation exist. | Complete scoped reporting/export suite, operational event coverage and append-only guarantees. |
| AI/knowledge | UI explicitly reports unavailability; ingestion/RAG/tool authorization not implemented. | Real document pipeline with provenance, per-lodge authorization, cited answers, evaluation, provider configuration, retention and cost controls. No simulated chatbot. |
| Guest experience | Dedicated guest access/portal not implemented. | Scoped guest identity or revocable stay invitation; only own itinerary/services; no staff data exposed. |
| Integrations/telemetry | Not implemented. | Provider-specific adapters and contract/retry/security tests after selecting providers; do not sell unavailable integrations. |
| Branding | Core lodge logo/display-name co-branding is implemented across packages; custom domains and branded exports remain. | Validated assets/colors, accessible UI and isolation. Custom domains require separate infrastructure work. |
| Operations | No verified production backup, recovery, observability or load capacity. | Hostinger VPS deployment review, TLS, secrets, persistent storage, monitoring, restore drill, upgrade rollback and measured capacity before customer launch. |

## Delivery order

1. **Release foundation (started):** close auth bypasses, reproducible frontend dependencies and security audit, background task registration, same-origin browser/API routing, real PostgreSQL security tests and CI.
2. **Complete core web operations:** implement remaining Basic workflows and run full browser/role/tenant acceptance. Validate real storage and email. Establish a usable Super Admin onboarding journey and lodge lifecycle.
3. **Standard web completion:** operations gaps, reports/exports, branding, reliable offline safari capture and AI knowledge/chat with permission-aware retrieval. Guest web access is a separately secured surface.
4. **Premium web completion:** automation, AI summaries/insights and approved external integrations; telemetry requires provider/hardware decisions.
5. **Commercial launch gate:** independent security review, regression/load/accessibility checks, migration/restore rehearsal, monitoring and incident runbooks, customer onboarding/support and privacy/retention policies appropriate to launch markets.

A milestone passing its tests does not establish overall production readiness. No customer deployment or commercial readiness is claimed by this document.

## Foundation milestone validation

- 334 tests passed locally: 323 existing source/schema tests plus 11 real PostgreSQL integration cases. Fresh temporary database migrations and least-privilege role grants were exercised for each integration session; concurrent recovery requests and MFA replay are included.
- Frontend production build passed with Next.js 15.5.28, React 18.3.1 and a pinned PostCSS 8.5.31 override. `npm ci` was exercised. One existing CSS compatibility warning remains.
- `npm audit` and `pip-audit` reported zero known vulnerabilities in the installed dependency sets. FastAPI, Starlette (resolved through FastAPI), cryptography, python-multipart and pytest were updated; Python transitive pins are saved in `requirements.lock.txt`. Audits are point-in-time checks, not security certification.
- Standalone frontend served its login form and static JS. Same-origin `/api/v1/auth/me` returned JSON 401 and invalid login payload returned JSON 422 through the proxy. API health verified live PostgreSQL and Redis connectivity.
- Static guard audit passed for 124 API routes and 25 module pages. This complements runtime checks; it is not comprehensive role coverage.
- GitHub Actions configuration was added, but no hosted CI run or Docker rebuild with the new dependencies has been established. Object storage remains blocked by the previously observed environment network restriction. No deployment, live email test, full browser acceptance, backup/restore drill or commercial sign-off is claimed.
