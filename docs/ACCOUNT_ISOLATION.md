# Account isolation and verification

Users authenticate as themselves. Opening a lodge workspace does not change a Super Admin's identity. Lodge staff must use separate accounts; role-authorized shared operational records remain accessible to the appropriate managers. Private account security information and sessions are not shared.

## Enforced boundaries

- Platform APIs require Super Admin and completed MFA. Super Admin requests to lodge APIs now also require completed MFA; account-security endpoints remain available for enrollment.
- Lodge APIs authenticate the session, verify the membership, apply role permissions and use transaction-local PostgreSQL row-level security. The database enforces one lodge membership per user.
- Invitations explicitly reject an existing login from another lodge, including inactive users, and reject linking a login to a second staff profile. They cannot change a platform account into a staff account.
- Session lists and revocation target only the authenticated user. CSRF checks include session expiration. Logout revokes the server session; password changes revoke other sessions for that user, preserving unrelated users' sessions.
- Activation and recovery tokens are consumed under row locks. Activation cannot reset an already active account.
- Private notifications filter by recipient. Own-assignment and department scopes remain enforced on the tested task and HR paths.
- Platform and lodge layouts check identity and permissions before rendering children. Hiding navigation is not used as the backend security boundary.
- The frontend binds its active lodge to the authenticated user, clears the previous user's lodge context on account changes, and offers Sign out. Other open tabs reload when the active user changes.
- `X-Expected-User-Id` optionally binds a request to the account the browser expects. A mismatch is rejected with 409, so a stale tab cannot silently write under a new login. The header can only restrict a valid session; it cannot authenticate or grant access.
- Offline wildlife records use a composite user/lodge/record key. Sync requests pin both the original lodge and expected user rather than relying on a mutable current selection.

## Offline migration and device boundary

The browser database upgrades to version 2 with a separate scoped queue. Legacy entries without reliable owner/lodge metadata remain in the old store, unmodified and excluded from automatic display/sync. Do not automatically assign them to whoever signs in next. Recovery requires confirming their original ownership; this change deliberately favors isolation over guessing.

These scopes separate normal application access. Browser storage is not encrypted per account and is not protection against someone controlling the device, browser profile, developer tools, or a compromised browser script. Use separate OS/browser profiles on shared devices when local confidentiality is required. Server authorization remains mandatory for every synchronized record.

## Verification

Real PostgreSQL HTTP tests exercise all tenant routes (104 with branding) with a foreign lodge ID, alongside session/CSRF ownership, account/membership revocation, platform-role denial, MFA gates, invitation rejection, private notifications, assigned tasks, department HR, password changes, logout replay and one-time activation/recovery concurrency. Tests use a temporary database and a non-superuser application role; customer data is not used.

Browser tests run the built standalone frontend. API responses are controlled fixtures for frontend route/layout/context checks; those checks do not replace the real backend tests. IndexedDB isolation is exercised in actual Chromium with distinct users, lodges, matching record IDs, real Blobs and a legacy store.

To run browser checks from the repository root:

```sh
npm ci --prefix apps/web
npm run build --prefix apps/web
npm ci --prefix e2e
(cd e2e && npx --no-install playwright-core install chromium)
npm test --prefix e2e
```

For an existing browser executable, set `BROWSER_EXECUTABLE_PATH` instead of downloading one. Python integration setup is described in `apps/api/tests/integration/README.md`. GitHub CI includes these checks; a local pass does not establish a hosted CI pass.

This is scoped regression evidence, not a claim that every possible security defect has been eliminated. Full release gates, including real storage/email/provider paths and deployment security, remain in `COMMERCIAL_RELEASE_PLAN.md`.

Latest local verification: 358 backend tests passed, including the cross-lodge route matrix; five browser checks passed; the frontend production build and static guard audit passed. The browser checks also verify sign-out context cleanup and removal of a previously authorized platform console when the account changes in another tab. Hosted CI results are separate from these local results.
