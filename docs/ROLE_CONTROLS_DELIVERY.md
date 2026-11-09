# Role-aware controls and operational reference data

Following platform/lodge separation, this checkpoint aligns remaining operational controls with actual permissions.

- Activities, transfers, fleet, fuel, departments, wildlife and ranger screens hide creation or administrative controls without the corresponding write permission. Fleet readers see a status label. Department readers cannot activate or deactivate teams. Wildlife readers cannot sync queued writes. Checklist creation also requires its feature entitlement.
- Assigned guide and driver workflow buttons use the API's per-record `can_transition` capability together with the relevant permission. These hints reflect current record assignment and never replace server write authorization. Scheduling remains a separate permission.
- Activity, transfer, fuel, ranger, feedback and meal-service reference requests require the relevant feature and read permission. Read-only screens do not fetch whole guest/staff/vehicle/department directories for hidden forms. Removed duplicate department fetching in feedback.
- Removed remaining frontend `is_super_admin` operational permission shortcuts. The shared workspace hook never grants operational access to platform identities.
- Workspace scope includes the user, lodge, features and permissions. A scope change closes affected editors and clears reference choices. Guarded asynchronous results cannot refill those choices after their scope changes or the component unmounts.

Verification includes real API tests for Lodge Admin, read-only, assigned guide and assigned driver capabilities; direct unauthorized updates and creation remain denied. Browser checks cover nine read-only screens, forbidden lookup requests, owned-record actions and a deliberately late staff response after access revocation. The earlier platform-isolation suite remains in the regression set.

Phase 2 verification passed: 756 API tests, 52 browser checks including the 272-layout audit, the production frontend build, static QA (169 API routes, zero guard issues, 25 modules) and git diff whitespace checks. The browser catalogue fixture was corrected to include the preset permission arrays returned by the real API. Capability permissions are evaluated once per list request rather than once per returned record. Existing database policies, CSRF, MFA, package gating and record-scope write checks remain intact. No migration is required.

Remaining completion work is tracked in REQUIREMENTS_DELIVERY.md. The owner confirmed that no booking, accounting, GPS or messaging systems have been selected yet; external connections remain pending rather than being represented as working integrations. Guest web/QR access, push delivery, expanded offline work and the other open document requirements are separate implementation phases.
