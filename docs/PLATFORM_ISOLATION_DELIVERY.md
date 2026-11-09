# Platform and lodge account separation

The owner requires Super Admin to administer the platform without entering lodge operations. The former Open lodge support route and blanket support read/write permission bypass are removed.

## Enforcement

- Authenticated platform accounts are rejected on every /api/v1/lodges/ and /api/v1/groups/ route. This covers AI, documents, downloads, record reads and writes, including existing sessions and legacy membership rows.
- require_permission, require_lodge_access, access_context and membership_for independently reject platform operational access. Authentication starts with a non-elevated, unselected RLS context; only the explicit MFA-protected platform dependency establishes administrative context. Background services retain their established internal scopes. No RLS policy or CSRF/MFA check was removed.
- /auth/me returns no operational memberships or group-owner assignments for platform users. Frontend account binding clears stale lodge selections. Operational routes render a platform-only explanation before mounting children, rather than fetching lodge data. Own account security remains available.
- Super Admin retains lodge registration, subscriptions, branding, account invitations and other explicit platform management endpoints. Branding logo previews have a separate MFA-protected platform endpoint; lodge users retain their membership-protected logo endpoint.
- Group Admin retains explicitly assigned lodges; Lodge Admin and staff retain their own lodge and role scopes. A platform identity never becomes a lodge identity through a selector, URL or local storage.

## Verification

The real PostgreSQL/API regression exercises the running route registry for every lodge/group endpoint with MFA-enabled platform accounts, with and without a legacy membership. It checks denial, no support audit writes, empty operational memberships, normal platform management and independent dependency/RLS boundaries. A separate test covers platform branding preview and lodge denial of that endpoint. Browser regression covers forged/stale selections, direct operational URLs, no tenant fetches, removal of Open lodge and own account security.

Phase 1 verification passed: 750 API tests, 49 browser checks (including the 272-layout audit), production frontend build and static guard audit. No migration is required; rebuilding API and web containers applies the restriction to existing sessions.

## Remaining project work

This security checkpoint does not complete the guest portal, remaining offline workflows, broader reports/analytics, provider integrations or production acceptance gates. Those remain explicitly tracked in REQUIREMENTS_DELIVERY.md and requirements/delivery-map.json.
