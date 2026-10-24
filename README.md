# SafariOS — Lodge operations

A co-branded lodge operations platform with a beige, brown, and orange translucent interface with dark and light themes. Super Admin configures each lodge’s logo and display name while SafariOS identity remains visible.

Start with [LOCAL_SETUP.md](LOCAL_SETUP.md). Read the [application requirements review](docs/REQUIREMENTS_REVIEW.md) for the documented product scope and remaining functional gaps. See [the new design and screenshots](docs/UI_UX_DESIGN_SYSTEM.md) and [commercial release scope](docs/COMMERCIAL_RELEASE_PLAN.md).

---

# Lodge CRM — Production Core Operations 1.6

Version 1.6 continues the real application build from 1.5.5. It adds persistent guest feedback/complaints, staff roster/shifts, incidents and performance records, F&B meal-service operations, and verified task image/PDF attachments. No demo operational records are seeded.

New migration: `0007_core_ops_completion`.

Release verification in this package: 44 Python contract/schema tests, Python compilation, migration-chain/revision checks, and TypeScript syntax transpilation for every changed frontend file. Full Docker/runtime acceptance still needs to run on the target Docker host.

# Lodge CRM — Production Operational Workflows 1.5.1

**Maintenance release:** fixes Tasks page permission-state build failure and tightens task-comment authorization.

# Lodge CRM — Production Operational Workflows 1.5

This release continues the production build on top of the hardened 1.4 foundation. It adds persistent operational workflows required by the final Lodge CRM scope. It does **not** seed guest, staff, task, room, maintenance, wildlife, report or AI data and it does not simulate successful actions.

## What 1.5 adds

- Staff HR records: supervisor, hire date, leave requests/approval, credentials/certificates and training/renewal records.
- Lodge-specific custom roles with a base operational scope and explicit permission list.
- Custom roles can be assigned to real staff memberships; server-side authorization uses the custom permission set.
- Advanced tasks: recurrence, required checklist items, comments, completion blocking until required checklist items are finished, and automatic creation of the next recurring task.
- Full housekeeping jobs: cleaning, turndown, inspection, linen and guest-request work with assignments, inspector, due time, lifecycle timestamps and authoritative room readiness updates.
- Basic package housekeeping remains limited; Standard/Premium unlock turndown, inspection and linen workflows.
- Maintenance workshop additions: asset register, service schedule fields, scheduled/recurring maintenance, downtime timing, parts usage and ticket-cost accumulation.
- PostgreSQL RLS policies on every new tenant table.
- New contract tests for HR, custom roles, advanced tasks, housekeeping, workshop features and RLS coverage.

## Migration

1.5 adds:

`0006_operational_workflows`

Run migrations only through the migration service. Existing data is preserved.

## Run locally

Copy the environment template and set the required secrets:

```bash
cp .env.example infra/.env
cd infra
docker compose up --build
```

Open:

- Web: `http://localhost:3000`
- API docs in development: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

Do **not** run `docker compose down -v` during an upgrade unless you intentionally want to delete the local database/object-storage volumes.

## Verification performed on this source snapshot

- Python compile: PASS
- API contract tests: 13 PASS
- Docker Compose YAML parse: PASS
- TypeScript/TSX syntax transpile checks for the changed UI files: PASS

A complete Next.js production build still needs the normal npm dependencies installed; Docker performs that during your local build.

## Requirement audit

See:

- `docs/REQUIREMENTS_COMPLIANCE.md`
- `docs/ROLE_ACCESS_MATRIX.md`
- `docs/PRODUCTION_READINESS.md`

The audit intentionally marks unfinished requirements as partial/not built rather than representing them with fake functions. Lodge AI, full native mobile applications, Premium telemetry/GPS, external integrations and several analytics/automation requirements are still later production stages.


## 1.5.3 migration compatibility fix
Alembic revision ID `0005_access_hardening` replaces the longer internal revision identifier so it fits Alembic's default `alembic_version.version_num VARCHAR(32)` column. No application tables or user data are removed by this fix. Migration `0006_operational_workflows` now depends on the shortened revision ID.

## 1.5.4 consolidated startup fix

This release fixes the PostgreSQL application-role bootstrap failure seen after successful migrations. PostgreSQL role DDL does not accept a bind placeholder for `PASSWORD`, so the bootstrap now composes the password as a safely quoted SQL literal while continuing to quote the role identifier separately. Regression tests also verify all Alembic revision IDs fit the default 32-character version column and prevent parameterized role-password DDL from returning.

## 1.5.5 consolidated API startup fix

This build fixes the API startup NameError caused by workflow request schemas being defined in `schemas.py` but not imported into `app.main`. It imports all Staff HR, custom role, advanced task, housekeeping and maintenance workflow schemas used by FastAPI route annotations. The API Docker image now performs `import app.main` during image build, so unresolved startup-time route annotations fail the build instead of appearing only after `docker compose up`. A regression test also verifies that every route annotation name resolves at module scope.

## v1.7 Premium UI / UX refresh

The current web application uses the SafariOS brand system: exact beige/brown/orange palette, translucent blur, solid orange actions with brown text, Archivo controls and bold sans-serif headings/figures, Archivo Narrow labels, and a cream light theme by default with saved dark-mode support. Dashboards use real operational data. See [the shared design system](docs/UI_UX_DESIGN_SYSTEM.md) for component APIs and current screenshots.

Key UX additions:
- responsive premium navigation with mobile drawer
- command palette (`Cmd/Ctrl + K`) for authorised modules
- real-data dashboard charts and operational calendar
- report visualisations derived from persisted report data
- redesigned login experience and polished cards/tables/forms/drawers
- micro-interactions using transform/opacity patterns and reduced-motion accessibility support
- responsive layouts for desktop, tablet and mobile

Shared components integrate Radix, Vaul, Framer Motion, cmdk, Sonner, Recharts, TanStack Table, React Hook Form, Zod, and react-day-picker. Tailwind exposes the same semantic tokens as the legacy screen classes.


## 1.7.2 UI runtime hotfix
- Fixed AppShell React hook-order violation caused by conditional returns before useMemo.
- Hardened dashboard rendering against partial/missing optional API arrays and subscription metadata.
- Added application error boundary for graceful recovery and console diagnostics.


## 1.8 security & integrity hardening
See `docs/HARDENING_1.8.md`. Run `./scripts/runtime_acceptance.sh` for live stack acceptance; it does not delete Docker volumes.

## Commercial web foundation milestone

The current delivery scope is web-first, with externally collected payments and manual Super Admin subscription controls. Hosting provisioning is deferred; Hostinger VPS is the intended deployment target. See [the commercial release plan](docs/COMMERCIAL_RELEASE_PLAN.md) for document precedence, missing features and release gates.

This milestone closes password-reset/MFA bypasses, protects one-time reset consumption against concurrent use, repairs the MFA disable form and worker registration, and upgrades audited dependencies. Python dependencies are installed from `apps/api/requirements.lock.txt`; the frontend uses `npm ci` and its committed `package-lock.json`.

The browser now uses same-origin `/api` requests by default. Next.js proxies those to `API_INTERNAL_URL` at **build time**: local default `http://127.0.0.1:8000`, Docker build default `http://api:8000`. Rebuild when changing the internal destination. Avoid setting `NEXT_PUBLIC_API_URL` unless a deliberately configured cross-origin deployment is required. Production domains, HTTPS, email and object storage still need real deployment configuration.

The PostgreSQL runtime test fixture and its required environment are documented in [integration tests](apps/api/tests/integration/README.md). The original source/schema tests alone are not commercial acceptance evidence. CI now runs both suites, dependency audits and the frontend production build. CI execution on GitHub remains unverified until the project is pushed.

### Ask Lodge AI

See [AI audit and phased implementation status](docs/AI_IMPLEMENTATION_AUDIT.md) and [local/test/vLLM setup](docs/AI_SETUP.md). The optional external vLLM gateway and read-only operational tools do not require a GPU to start the core CRM. Real inference requires an operator-configured private vLLM endpoint. Later AI capabilities remain explicitly gated until implemented and verified.

### Private document knowledge update

Optional lodge knowledge now supports private PDF/DOCX/TXT uploads, actor-scoped Celery processing, a separate real embedding endpoint and permission-filtered pgvector retrieval. It defaults off. This update requires the PostgreSQL 16 image built from `infra/postgres` **before migration 0019**; keep the existing volume and take/restore-test a database backup before updating an installation. [AI setup and acceptance](docs/AI_SETUP.md) explains configuration, sharing rules, limits and the verified test boundary. Chat and embedding GPU services remain external; live provider/full pipeline acceptance is still required before commercial launch.

Group Owners can now open **Compare lodges with AI** for authorised cross-property metrics. Migration 0020 preserves individual lodge history and adds explicit private group scope; each property's membership, permissions, subscription and AI capabilities remain authoritative. See [Group Owner AI setup](docs/AI_SETUP.md#group-owner-ai-phase-5) for coverage, limits and remaining live-provider acceptance.
