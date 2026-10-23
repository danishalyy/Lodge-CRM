# Ask Lodge AI — implementation audit and sequence

Source baseline: commit 7c96bd7. This report precedes AI implementation. Repository inventory covers apps/api, apps/web, all seventeen Alembic migrations, runtime and contract tests, docs, e2e, infra and scripts. Current stack is Next.js **15**, React 18 and FastAPI/SQLAlchemy, PostgreSQL 16, Redis/Celery and MinIO; the prompt's Next.js 14 expectation is older than this repository. Preserve the installed stack.

## Existing, partial, missing

- Existing: 157 API routes; session cookies/hashed tokens, CSRF, MFA/recovery, account-change assertions, DB roles/grants and custom roles, explicit multi-lodge Group Admin assignments, subscription engine, editable DB plans and lodge exceptions, append-only events/audit, private notification recipients and email outboxes, operational reports, S3 upload/checksum workflows, Celery/Beat and scoped service-state helpers.
- Partial AI foundations: code-defined FUTURE capability keys and historical database plan associations; `/lodge-ai` placeholder; frontend `ai.use` navigation guard without an existing DB AI grant. None of these is an inference implementation. AI-related capabilities must remain unavailable until their own implementation and tests pass.
- Missing: inference provider, gateway, AI schema/RLS, usage limits, conversational ACL rules, tool registry, RAG/extraction/embeddings/vector extension, AI confirmations, AI schedules, group AI aggregation, real model evaluation/load evidence.

## Security and tenancy map

`current_user` authenticates the session, checks account assertions, employment and memberships and establishes transaction-local RLS context. Ordinary accounts remain single-lodge; explicit Group Admins may have many assigned lodges. Migration 0011's membership trigger checks active group ownership and prevents mixing ordinary/group memberships. Group routes resolve assigned lodges, then enter each tenant context; they do not grant Group Admin a global database bypass.

`require_permission`, `membership_for`, `access_context`, `has_permission`, subscription guards and `ensure_feature` are reusable. A custom role uses only its custom grants; its base role controls endpoint-specific record scope. Core scope is partly enforced in Python, not all by SQL RLS: task assignees, department records, guest/dietary fields, staff contact/HR and protected wildlife require the endpoint's existing rules as well as tenant RLS. Calling a FastAPI function directly does **not** execute Depends; an adapter must explicitly invoke guards before reusing handlers. Existing report sections have entitlement filtering; additional per-section permission minimisation is required before model inference.

Migrations 0001–0008 introduce tenant policies and operational constraints; 0008 strengthens cross-tenant foreign keys and history immutability; 0009 branding; 0010 email outbox; 0011 groups; 0012 MFA recovery; 0013 preferences; 0014 exact administrator delegation; 0015 editable plans; 0016/0017 currency defaults. Bootstrap grants application tables to a NOSUPERUSER/NOBYPASSRLS role and revokes updates/deletes on audit/events. New AI tables must use FORCE RLS under that same role.

## Reuse and modification boundaries

- Read tools: explicitly guard and adapt existing operational handlers, returning bounded allowlisted DTOs, not ORM objects. No generic SQL, HTTP, filesystem or shell tools. Do not invent a second set of task/state rules.
- Operational Memory: reuse OperationalEvent and existing log filters, but audit department/record visibility before retrieval. It is not conversation history. Existing memory filters alone are not a general department ACL engine; do not indiscriminately expose it to custom department scopes.
- Reports: reuse deterministic calculations; suppress sections and sensitive fields unless the requester owns the corresponding grants. No LLM arithmetic over unbounded raw rows.
- Notifications: reuse create_notification/NotificationRecipient and existing authorised recipient/delivery flows. AI must not broadcast across tenants.
- Workers/storage: existing Celery tasks use explicit privileged operational contexts for scheduled system duties. AI jobs must instead resolve a real authorised actor and tenant, rechecking permissions at execution. S3 keys/checksums and private presigning can be reused for knowledge files; do not reuse public wildlife permissions for documents.
- Frontend: retain AppShell, WorkspaceAccessContext, selected tenant/account assertions, glass tokens, Form/Field and existing API client. Group scope switching must preserve explicit memberships. No fabricated data or enabled future controls.

## Phase 1 schema and gateway design

Add AIConversation, AIMessage, AIToolExecution and AIUsage. Each row records owner and lodge, with composite conversation foreign keys preventing mixed-tenant/owner attachments. FORCE RLS is private owner + selected lodge, without a Super Admin OR bypass. Conversation ACL fingerprints bind history to current effective grants, base scope, department/staff and entitlements; changed access blocks old history instead of replaying previously privileged data. Do not persist hidden reasoning, credentials, raw exceptions or unnecessary tool result bodies.

Provider interface centralises configuration, health, completions and structured tool replies. vLLM is the real provider and external to core Compose. Test provider is deterministic and only allowed with explicit test environment, never presented as real AI. Invalid AI configuration affects AI endpoints only; startup/login/core services must remain independent. Bound provider request/response sizes, context/output, rounds and timeouts. Use shared Redis for per-user/per-lodge limits and expiring concurrency leases, failing closed for AI if unavailable. No credential/model/URL parameters from the model or browser.

AI routes reuse current_user/CSRF/permission/subscription/entitlement guards. Super Admin AI tenant access is denied until an explicit audited support workflow is designed; normal support bypass is not silently inherited. Group Admin can use explicitly assigned individual lodge scopes; all-property aggregation belongs to Phase 5. Prompt history is never an authorization source. Recheck access after inference and before persisting/returning data.

## Subsequent schema, API and frontend plan

2. Controlled read tools for dashboard/tasks/units/stays/requests/housekeeping/maintenance/fleet/activities/transfers/private notifications/reports, each independently gated and tested; provenance from executed tools only. Enable the base AI capability only when its implemented paths pass.
3. Memory adapters with record visibility and historical provenance; no causal claims from incomplete event data.
4. Knowledge documents/chunks with private storage, quarantine/size/type bounds, Celery extraction, embedding version/dimensions, pgvector and prefiltered retrieval. Current postgres:16-alpine does not include pgvector: extension/image compatibility must be addressed in this phase, without replacing customer volumes. No dummy embeddings or metadata-only RAG claimed as implemented.
5. Group comparisons: resolve group owner and explicit memberships, recheck each lodge's subscription and AI capability, enter each RLS tenant separately, aggregate deterministic metrics. No global Group Admin bypass.
6. Write confirmations: actor/conversation/lodge-bound validated proposals, expiry, one-time consumption and idempotency. Invoke existing mutation services so normal audit/events/notifications and FK validation run. No model-generated SQL or browser confirmed=true bypass.
7. Actor-scoped scheduled reports/insights with existing Beat/outbox, deterministic anomaly detectors, provenance and dedupe. Leave each capability FUTURE until independently accepted.
8. Real GPU connection, model tool accuracy, RAG/injection, worker/MinIO integration, load/concurrency and GPU capacity testing. No infrastructure purchase, DNS change or production deployment is authorised.

## Risks and verification

Additive Alembic tables avoid altering customer operational rows. New RLS/composite keys require real least-privilege PostgreSQL tests and downgrade checks. Migration grants must be applied through the existing db-grants service. Never introduce create_all or an AI DB bypass role. Permission changes between turns, revoked group memberships, cross-account conversations, stale confirmations, hostile tool arguments, prompt injection and unavailable Redis/model services require explicit failure tests. Conversation retention and privacy policy must be documented before commercial AI deployment.

Baseline: full API suite **464 passed**; production frontend build passed. Full baseline browser suite is being recorded separately before changing application code. Later phase results must be recorded separately from this baseline. A real vLLM endpoint/GPU was not supplied; deterministic/provider-transport tests cannot count as real-GPU acceptance.

## Phase 0 result

Baseline completed before application implementation: 464 API tests, production frontend build and all 35 existing browser checks passed.

## Phase 1 result

489 API tests, production frontend build, AI outage browser check, Compose configuration validation, Python dependency audit and production npm audit passed. Implemented provider interface/vLLM transport/test-only provider, configuration, cached bounded health, private RLS tables, owner/tenant composite references, conversational ACL fingerprints, CSRF/RBAC/subscription/feature guards, Redis admission, private history/usage, failure isolation and frontend connection/unavailable states. No runtime dependencies were added. Real GPU testing has not occurred. Base AI remains gated while operational adapters are added in Phase 2; RAG, memory, group aggregation, writes and scheduled insights remain unimplemented and their capabilities remain future.

## Phase 2 result and current boundary

Fifteen read-only tools now reuse authoritative handlers with independent session/membership, permission, scope, subscription and entitlement checks. Operational rows are allowlisted, bounded and explicitly marked partial; sensitive contact/medical/HR/financial/coordinate data and raw notes are excluded from initial DTOs. Stay/arrival names are included only through the already-authorised stay surface. Dashboard counters are labelled as stays where that is what the existing calculation counts. Assigned-work scopes are excluded from lodge-wide aggregate tools. Five list endpoints gained optional bounded limits for AI while keeping existing screen defaults.

The base `ai` capability is implemented and uses the existing DB plan/exception grants, with global inference disabled by default. Other AI capabilities remain FUTURE. Successful current tool evidence is required before returning an operational answer. Source labels, scope, record IDs and partial flags come from server execution. Forged model identity/scope/SQL/URL arguments and all write/HR/precise-wildlife tools are rejected. Access is rechecked between rounds and before returning data; the UI clears old answers on access-denial responses. Invalid optional AI configuration cannot break core settings/startup, and Redis failure disables AI admission without disabling core read APIs.

Validation: **543 API tests** pass, including positive/negative tests for every registered tool, private owner/lodge RLS, cross-property/group boundaries, mixed-owner composite foreign keys, department and assigned-work scopes, permission/entitlement revocation during a request, response-without-evidence rejection, provider failure handling, Redis admission failure and concurrency lease release. Production frontend build, full **37-check browser suite**, targeted AI rechecks (including revocation and WCAG A/AA checks in desktop/mobile dark/light fixtures), static guard audit, Compose config validation and Python/npm dependency audits pass. No additional runtime packages were needed.

No production deployment or infrastructure purchase occurred. Migrations were exercised on temporary test databases, not customer databases. Provider transport and browser fixtures are deterministic test evidence; no real vLLM/GPU connection, model grounding evaluation, full running Docker/worker/MinIO AI pipeline, concurrency/load benchmark or production acceptance has been claimed.

Remaining phases: **3** Operational Memory retrieval; **4** private document/RAG ingestion, extraction, embeddings and pgvector; **5** cross-property AI aggregation; **6** controlled actions and single-use confirmations; **7** scheduled summaries/reports/insights and notification integration; **8** real-model, infrastructure, adversarial and load acceptance. Existing non-AI memory, multi-lodge groups, operational reports, notifications and CRM actions are preserved. Retention jobs, streaming and commercial token allowances also remain future work. The next implementation phase is Operational Memory; the migration/security plan above applies before enabling it.

UI review artifacts use explicit browser test fixtures: [desktop dark](screenshots/safarios-ai-desktop-dark.png), [mobile light](screenshots/safarios-ai-mobile-light.png). Actual inference remains dependent on the private configured provider; these screenshots are UI checks.
