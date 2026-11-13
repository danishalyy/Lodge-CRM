# Interactivity QA — Phases 1–4

Phase 1 provides instant actions; Phase 2 adds shared status boards; Phase 3 adds private, resumable live invalidations; Phase 4 adds installability, private device queues and opt-in browser push. Global shortcuts and walkthroughs remain later phases and require owner approval.

## Phase 1 implementation

`lib/data-cache.ts` provides a two-second, in-memory cache and coalesces simultaneous reads for the selected operational collections and private notification summary/list. Keys include the expected user, selected lodge and exact request path. Results are cloned. Failed responses are evicted; writes invalidate before and after sending. Reads overtaken by invalidation fetch fresh state. Authentication, permissions, AI review tokens and API writes are never cached. Nothing is persisted to disk or a service worker.

`Providers` installs focus, visible-tab and reconnect listeners. Mounted Phase 1 modules revalidate existing authorized endpoints, keep prior rows visible, and pause automatic refresh during pending work or creation forms. Sign-out, identity/permission snapshot changes, lodge selection, relevant storage events and authorization conflicts clear the cache. Existing request cookies, CSRF, expected-user headers and scope checks remain intact; late responses from a former account/lodge are rejected.

`useInstantRows` applies per-record optimistic patches, synchronously locks duplicate submissions and overlays pending patches on background reads. It restores the affected record after failure, clears pending state, and offers Retry for retryable failures. Authorization/account/concurrency failures do not expose a stale-authority Retry. The owning module retains its existing access-denial behavior. Undo and Retry callbacks stop working after unmount or a scope change.

Tasks, request status/assignment, maintenance, housekeeping and room status use the existing write endpoints. Undo is offered for the supported request/maintenance waiting ↔ in-progress transitions and reassignment to an existing previous assignee. It submits another authorized server request and can itself fail and roll back. Terminal task/completion transitions, room/housekeeping side effects, notification mark-read, and AI confirmation/dismissal have no fabricated inverse endpoint. An unassigned request cannot be restored by the existing API; the assignment control therefore does not offer unassignment.

Notifications mark-read/all-read optimistically and update the private unread badge, then reconcile with the server. AI dismissal shows an immediate pending state and restores the proposal on rejection. AI approval keeps explicit review/token confirmation and shows pending feedback; it never claims the underlying operational write succeeded before server acknowledgement. A failed confirmation Retry returns to review instead of silently replaying an irreversible action. These are intentional security and contract limits, not new permission rules.

The existing visual tokens, routes and database/API contracts are unchanged. No dependency or backend runtime change is required. The existing scoped wildlife queue is untouched in this phase.

## Automated checks

Run the existing API suite using `apps/api/tests/integration/README.md`, then:

```sh
npm run build --prefix apps/web
BROWSER_EXECUTABLE_PATH=/usr/bin/chromium npm test --prefix e2e
```

Run frontend builds and browser checks sequentially. New `instant` scenarios cover cache coalescing/cloning/failure recovery, invalidation of late reads, logout/lodge cleanup, uncached auth checks, status rollback and Retry, duplicate submission, real Undo, request reassignment, room/housekeeping rollback, notification badge rollback, AI dismissal without confirmation, late/stale controls during a lodge switch, deferred refresh without losing typed form values, and notification polling/navigation while a read is pending. Existing browser checks retain activation, MFA, authorization, private AI, forms and responsive coverage.

## Manual script

Use separate test accounts, authorized records and a test installation. Run at desktop and phone widths with keyboard and touch. Do not use production customer data for failure injection.

1. **Lodge Admin / authorized manager:** progress a task; resolve a request with notes; assign a request to another permitted staff member; move a maintenance ticket between in-progress and waiting. Confirm instant state, the affected pending control, one submission, success feedback, and working Undo only for reversible changes.
2. **Housekeeping / maintenance staff:** use only the workflow controls the current account is authorized to see. Check the room/job status and server result. Restricted users must not gain management controls or staff-directory calls.
3. **Guide / driver / general staff:** progress an assigned task using its existing server-provided capability. Another person's restricted task must not become actionable.
4. **Read-only / expired subscription:** confirm existing write restrictions. If permissions/subscription change after the screen loads, reject a test write server-side; confirm rollback or the existing access-denial state, with no success or Undo.
5. **Group Admin:** start a delayed update, switch to another assigned lodge and then finish/reject the old response. No previous-lodge row, error or action toast should enter the new view. Repeat with an account change in another tab.
6. **Super Admin:** remain within platform pages. Mark a private notification read; confirm the badge changes immediately. Attempting an operational lodge URL must remain blocked.
7. **AI-authorized user:** review without applying; dismiss and simulate rejection; retry dismissal. Confirm that neither dismissal nor Retry applies the underlying action. Review and confirm separately; double presses submit once and there is no Undo for a confirmed operation.
8. **Failure/reconnect:** delay/reject a test endpoint using a test proxy or browser routing. Confirm previous data remains visible on refresh, optimistic writes roll back, Retry uses the original scope, and returning focus/reconnecting refreshes mounted collections without clearing typed form values.
9. **Keyboard/accessibility:** Tab to controls, activate using Enter/Space, verify disabled/pending states and status announcements, Undo/Retry toast actions, Escape/focus return for existing drawers, both themes and reduced-motion preference. No action requires dragging.

Automated browser fixtures verify frontend behavior; real API tests verify backend authorization. They do not constitute hosted deployment or a comprehensive accessibility certification.

## Local verification — 10 November 2026

- API suite: **756 passed**, using disposable test services; no backend runtime or contract changes.
- Production frontend build: **passed**.
- Full browser run: **68 passed**, including the existing 272 width/theme combinations. After the final notification polling/navigation guard, **13 relevant checks passed** on the rebuilt app, including the additional navigation case (**69 distinct browser scenarios covered overall**).
- Static audit: **169 API routes**, **zero guard issues**, **25 visible modules**, **zero missing pages**.
- New dependencies: **none**. Visual tokens, routes, permission/entitlement keys, RLS, CSRF and MFA contracts are unchanged.

Phase 1 is complete within the existing API capabilities described above. Its checkpoint was approved before starting Phase 2 below. Real-device/manual checks and hosted deployment verification are separate from these local automated results.

## Phase 2 — Shared status boards

`components/ui/status-board.tsx` uses the explicitly requested `@dnd-kit/core` dependency (with its accessibility/utilities dependencies). Tasks and Requests adapt their existing `CollectionView` cards; Maintenance, Housekeeping and Rooms reuse their existing cards inside the same board. Ordinary list actions remain available. This is status movement, not arbitrary sorting or bulk assignment.

Each card has a native **Move to…** selector for keyboard and phone use. Board cards also have a drag handle: **Space**, arrow keys, **Space** to drop, **Escape** to cancel. Mouse and touch sensors activate only from the handle, leaving card links, selection, forms and scrolling available. A synchronous keyboard adapter tracks the selected column without waiting for pointer geometry or deferred sensor listeners; the same guarded commit function handles its drop. This also supports rapid key sequences and shows a destination preview. Read-only and expired contexts disable movement. Task-owned workflows retain their existing server-provided `can_transition` capability and cannot gain management cancellation through the board.

`lib/status-transitions.ts` contains presentation hints for existing transitions, not authorization. Disallowed columns refuse a drop, and the move menu disables unavailable targets. Every accepted gesture calls the owning module’s original mutation and the original API endpoint. The server still checks membership, permissions, subscriptions, entitlements, record scope, occupancy, checklist/proof and inspection rules. Resolution/completion notes use the existing notes flow; assigning a task requires its actual assignee. Cancellation uses the existing focus-managed confirmation dialog. Failed server transitions restore the card and announce failure; account/access failures retain the existing denial behavior.

Movement announcements use live regions. A moved card is revealed and focused, while a delayed acknowledgement cannot steal focus from a newly opened form. Keyboard scrolling is immediate rather than decorative animation. Styles reuse existing colour, spacing, focus and surface tokens. Column collapse and board/card choices are stored under user/lodge/module-specific keys; `CollectionView` also remembers its list/card/board choice. Only presentation settings are stored, never records, permissions or authorization decisions. Changing authority cancels the active board gesture.

No backend route, API contract, permission key, RLS, CSRF or MFA check changes in this phase. A new client `readOnly` context reflects existing subscription metadata and can only restrict board actions. Explicit `units.status.manage` allows room status movement without granting room configuration or creation.

### Phase 2 manual checks

1. On desktop, move a permitted card with its handle; try a forbidden column and release outside the board. Confirm refused targets, no unintended write and a clear status announcement.
2. Focus a handle, press Space, use Left/Right arrows and Space. Repeat with Escape. Tab to **Move to…** and choose a permitted status without dragging. Check focus after completion/rejection.
3. On a phone, scroll through columns using the card body, drag using the handle, and use the native move menu. Confirm that touching links, inputs or action buttons does not start a drag.
4. Try to complete required-checklist/proof tasks, an occupied room, or a housekeeping job needing inspection. The server must reject invalid transitions; the card must return to its prior state with error feedback.
5. Cancel the cancellation dialog using Escape; confirm no write. Confirm cancellation separately and verify a single request. Supply resolution notes when resolving requests or completing maintenance.
6. Collapse a column and change the view, reload, then use a different account/lodge. Preferences must be scoped, and another account must never adopt records or permissions from saved settings.
7. Start dragging, then switch to another assigned lodge or revoke the relevant permission/subscription. The old gesture must not submit into the new context. Check read-only, field-role and platform-only accounts.
8. Check 375, 768, 1366 and 1440px widths, both themes and reduced motion. On real touch hardware, verify drag activation and use the move menu as the reliable alternative.

The next section records the separately approved Phase 3 live updates.

### Phase 2 local verification — 10 November 2026

- API suite: **756 passed**. Backend runtime, contracts and security policies are unchanged.
- Production build: **passed**.
- Full browser suite: **82 passed**, including the 272 route/width/theme combinations and the new real mouse, touch-event and keyboard cases. After the final refusal-focus and copy cleanup, **six focused checks passed**, including the additional status-only room-permission case (**83 distinct suite checks verified overall**).
- Populated boards additionally passed 375/768/1366/1440px overflow checks in both themes and automated contrast/accessibility checks after theme transitions settled.
- Static audit: **169 API routes, zero guard issues; 25 modules, zero missing pages**.
- Dependency: **@dnd-kit/core 6.3.1**, plus its accessibility/utilities dependencies; no alternative drag library.

Preview screenshots use test fixtures: [desktop dark](screenshots/safarios-status-board-desktop-dark.png), [phone light](screenshots/safarios-status-board-mobile-light.png). Real touch hardware and hosted deployment checks remain separate from local Chromium verification.

Phase 2 implementation is complete.


## Phase 3 — private live updates

The additive `GET /api/v1/lodges/{lodge_id}/events` route uses the normal HttpOnly session, expected-user header, selected lodge, membership and subscription-read guards. Platform accounts remain prohibited, including legacy platform memberships. A fresh short transaction rechecks the session, permissions, feature overrides, department and staff assignment on every poll; it never holds a database connection for the lifetime of the response.

Migration `0025_live_events` adds an RLS-protected transactional outbox. Deferred database triggers record inserts/updates for tasks (including checklist/comments/attachments), requests, stays, rooms, maintenance, housekeeping, private notifications/recipients and subscriptions. Rolled-back writes produce no committed events. A per-lodge commit lock keeps sequence allocation in commit order, so a later checkpoint cannot skip an earlier uncommitted change. The application role may append/read but cannot update/delete outbox rows. Existing RLS, CSRF, permissions and audit policies remain intact.

Business event payloads contain only `type`, entity `id`, and a random opaque `version`. They contain no names, guest details, descriptions, assignees or counts. Delivery rechecks module permission, entitlement and the same current-record scope as the module API. Notification events require an actual recipient row for that user. The opaque encrypted resume token is bound to the session, user, lodge and access fingerprint; it exposes no global sequence or other lodge activity. A checkpoint follows each complete batch. Heartbeats run every 15 seconds; streams rotate after five minutes. Access changes close the stream with a control event and force a guarded metadata refresh.

`LiveUpdates` owns one connection in the authorized lodge AppShell, using same-origin fetch so the existing context headers are preserved. It pauses while hidden/offline, aborts on identity changes, reconnects with bounded exponential backoff, remembers its cursor only in memory, deduplicates versions and uses the existing cache invalidation/read hooks. A 30-second authoritative reconciliation also runs while visible. This is the fallback for unavailable SSE and removes records which have left the user's scope without sending newly unauthorized record IDs. Assignment removals may therefore take up to 30 seconds to disappear. No private response is persisted.

While editing, dragging or scrolling, changes accumulate behind an update pill; applying updates is disabled while an editor is active. Finishing an editor does not silently apply the live queue. Idle updates refresh existing rows, briefly highlight affected records using the existing gold token and fade dashboard figures in place. Reduced motion removes the animation. Access or subscription revocation takes priority over editing: operational children unmount during access revalidation; a failed access check stays blocked with Retry. Expired subscriptions retain existing read-only behavior and hide affected workflow write controls.

### Phase 3 deployment and retention

Use the existing Compose migration/grants ordering when updating:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

The migration must complete and `db-grants` must run before the new API is served. No new environment variables or dependencies are required. At an external reverse proxy, preserve streaming, disable buffering/caching for `/api/v1/lodges/*/events`, and allow an upstream read timeout longer than the 15-second heartbeat (e.g. 60 seconds). The API sends `X-Accel-Buffering: no` and `Cache-Control: no-store, no-transform`. Verify these settings on the eventual Hostinger VPS; local browser mocks do not verify hosted proxy behavior.

The outbox is ephemeral invalidation metadata, separate from immutable operational/audit history. Schedule an owner-controlled daily retention job before production launch, retaining at least eight days (resume tokens expire after seven). For example, run this bounded statement repeatedly through the existing database maintenance connection until it deletes zero rows:

```sql
DELETE FROM live_events WHERE id IN (
  SELECT id FROM live_events
  WHERE created_at < clock_timestamp() - interval '8 days'
  ORDER BY created_at LIMIT 10000
);
```

The CRM application role intentionally cannot perform this maintenance. Do not grant it DELETE or use it to prune audit/history tables. A reconnect always reconciles current authoritative reads, including after old invalidations have been pruned. A site scheduler and production concurrency/load measurements remain deployment tasks; the implementation polls the database once per second per visible connected tab, so size connection/query capacity using the real lodge workload.

### Phase 3 manual checks

1. Open two authorized accounts in the same lodge. Create/assign/update a task or request, change a room, stay, maintenance ticket or housekeeping job. The second idle page should refresh and briefly highlight the affected record. Check dashboard figures and private notification badges.
2. Repeat with another lodge, a field-role user and a department manager. Events must never reveal another lodge, an unauthorized module, work outside the role's record scope or another recipient's notification. Use a platform account to confirm the stream is forbidden.
3. Open an editor and type an unsaved value, then change its record from the other account. The queued pill must appear without replacing the draft. Close the editor and apply the queued updates. Repeat while scrolling and dragging.
4. Disconnect/reconnect, hide/show the tab and restart the API. Check paused/reconnecting/live states, cursor resume and eventual authoritative data without duplicate mutations. With SSE blocked, visible-page reconciliation should continue every 30 seconds.
5. Remove membership, revoke the session, change permissions/package, suspend the lodge or expire the subscription while connected. Access changes should hide operational children for revalidation; revoked access must remain denied, and expiry must remove workflow writes while retaining authorized reads.
6. Change an assignment so a field user loses record access. Their next reconciliation must remove the record; the stream must not disclose its ID after access is lost. Verify behavior in both themes, reduced motion and 375/768/1366/1440px layouts.

The following section records the separately approved Phase 4. Production proxy verification, scheduled live-outbox retention, real-device checks and workload sizing remain deployment checks.

### Phase 3 local verification — 12 November 2026

- Full API suite: **771 passed**, including 14 real PostgreSQL live-event tests for atomic rollback, late commit/resume, RLS, append-only grants, recipient privacy, department/own-work scope, entitlement overrides, session/membership revocation, suspension, heartbeat and cursor binding.
- Production frontend build: **passed** after the final changes.
- Full browser suite: **86 passed**, including the 272 screen/width/theme combinations. After refresh-completion and error-state review, **31 targeted checks passed**, including one additional dashboard-denial flow. The final mobile header adjustment also passed **four live-flow checks**. This verifies **87 distinct suite checks overall**; the final targeted runs supplement the earlier full run.
- Queued updates passed 375/768/1366/1440px overflow checks. The 375px queued state also passed automated WCAG 2 A/AA checks and visual review; this does not certify comprehensive accessibility or real-device behavior.
- Static audit: **170 API routes, zero guard issues; 25 modules, zero missing pages**.
- No new runtime dependencies or production demo records.

The [queued-update phone preview](screenshots/safarios-live-queued-mobile.png) uses browser test fixtures. On a narrow phone, the status icon retains an accessible state label while the update button preserves space for the SafariOS mark.

Phase 3 implementation is complete. Hosted streaming/proxy checks, scheduled live-event retention, capacity sizing and real-device verification remain deployment work. The following section records Phase 4.

## Phase 4 — installable app, device queue and browser push

The manifest at `/manifest.webmanifest` provides a standalone SafariOS app with maskable 192px/512px icons derived from the approved acacia mark. `PwaRegistration` installs the same-origin service worker in secure contexts. Its cache contains only the public offline page, manifest, SafariOS assets and hashed Next static files; static entries are bounded. Authenticated documents, RSC responses, APIs and lodge media are never added to Cache Storage. Navigation always goes to the network, falling back to a public offline page on connection failure. Public assets can remain cached after sign-out because they contain no account information. Private in-memory reads are invalidated on identity changes and sign-out; restored browser pages reload for authentication.

Offline changes are available on an already authenticated, loaded workspace when connectivity is lost. A cold offline launch shows the public fallback and requires reconnection to authenticate; it does not restore a private dashboard from disk. This is intentional. The queue stores only a user's pending input and minimal command metadata, never copies of guest/HR records or authenticated API responses.

### Shared queue and replay

`lib/offlineWildlife.ts` now exposes shared typed queue operations while retaining the existing wildlife function exports. IndexedDB version 3 migrates scoped wildlife photos into a shared store keyed by user, lodge and command ID. Legacy unscoped records are never adopted. New commands cover task status, task checklist ticks, housekeeping status, transfer status and wildlife sightings/photos. Unsupported edits still require a connection. The existing `offline_mobile` entitlement gates capture/replay; no plan grants or role checks are expanded. Existing housekeeping read/create/update routes also enforce the declared housekeeping feature flag; replay review found that this check was missing there.

The shared sync manager replays only in a visible, authenticated tab. It pins the original user/lodge, revalidates metadata, uses Web Locks where available and atomic, renewable per-item IDB leases with owner tokens as a fallback. A late result from an older lease cannot overwrite a newer claim. Network failures retain queued work with backoff. Permanent validation, authorization and conflict responses become Rejected; Retry is deliberate, keeps the original command ID and expected state, and cannot force an overwrite. Discard requires confirmation. Synced entries retain only completion metadata; input payloads and photo blobs are removed. Removing a completed entry affects only this device, not the lodge record.

The SyncChip and device drawer report Online, Offline with queued count, Syncing and Needs attention. Each row shows Queued/Syncing/Synced/Rejected, its action, starting/target state and a readable error. Offline checklist ticks update immediately, disable duplicate interaction while storage commits and roll back on storage failure. Other queued status changes update the local view after successful storage; queued feedback explicitly says the change has not reached the server yet.

`POST /api/v1/lodges/{lodge_id}/offline-actions` is a narrow adapter over the existing workflow handlers. It accepts only the four supported status/checklist command types. Normal membership, module permission, feature, subscription-write, record-scope, transition, proof and inspection rules still apply. It locks the record and checks the supplied starting state. A receipt is committed atomically with the existing handler's mutation/audit entry. Reusing an ID with a different body is rejected; an authorized retry after a lost acknowledgement returns the prior receipt without repeating the change. Receipts are RLS-protected, user/lodge scoped and append-only for the application role. They retain only IDs, a request hash and creation time.

`POST /api/v1/lodges/{lodge_id}/offline-sightings` reuses existing per-lodge `client_ref` idempotency and enforces offline access. Photo upload/registration checkpoints are retained until acknowledged. Retrying an identical, already registered object returns its existing ID only for the same uploader, sighting, checksum, type and size. Conflicting details still return 409; storage verification and upload permissions remain intact.

### Account and device boundaries

Sign-out clears the user's queued work across lodges, removes the browser push binding, unsubscribes the device and invalidates private memory caches. A persisted local sign-out marker locks private requests immediately if the network is unavailable; reconnection finishes server-session revocation before private pages, login or activation can resume. Cleanup is retried if storage was temporarily blocked. A successful new login revokes the browser's replaced session after password/MFA checks succeed; sessions on other devices are unchanged. Session cookies remain HttpOnly. An offline device cannot revoke a remote server session until it reconnects.

Changing accounts purges the previous user's device work. Group Admin lodge switches keep separately scoped queues, stop the previous scope's replay and remove its push binding; returning to that lodge still requires current membership and entitlements. Changing roles, employment, package or subscription never grants replay authority from saved client state. The API remains authoritative for every item.

### Browser push

Browser push is optional and disabled until installation keys are configured. Opening notification settings does not prompt for browser permission; **Enable on this device** is the only permission-prompt action. Preferences cover task assignment, guest-request assignment, overdue tasks and arrival-readiness alerts generated by the existing notification system. These preferences apply to the user's devices for the selected lodge. Turning off a device clears its binding and subscription; personal opt-out remains available after subscription expiry without granting operational write access. Super Admin remains platform-only; lodge push is never a way to enter a lodge workspace.

Subscription endpoints and browser keys are encrypted at rest with a dedicated Fernet key, and RLS restricts device/preferences reads to their user and lodge. Notification creation records a durable, payload-free intent in the same transaction. The trusted worker resolves private device bindings and rechecks session expiry/revocation, active user/membership/employment, current permissions/entitlements, subscription state, recipient ownership, unread/archive state, record scope and category preferences before delivery. Operational callers cannot read another user's devices. Expired-session capabilities are purged; terminal delivery metadata is retained for eight days. HTTP 404/410 removes the stale endpoint; transient failures use bounded retries and sanitized error codes.

Push payloads contain only a generic type and opaque device binding. The worker never sends notification titles, guest names, room details, message contents or record IDs. The service worker verifies the binding and current authenticated account before presenting a generic SafariOS alert. Clicking it opens the guarded notification inbox. Clearing a binding suppresses late delivery/clicks. Delivery is best-effort; the browser groups duplicate alerts under one tag. Push destinations are restricted to supported browser vendor HTTPS services, browser keys are validated and redirects are disabled.

### Configure/install locally or on the VPS

Update using the existing Compose migration/grants ordering:

```bash
git pull
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

Migration `0026_offline_push`, current grants and the updated API image must be applied before running the new workers. The new runtime dependencies are `pywebpush==2.5.0` and `requests==2.34.2`. Docker installs `apps/api/requirements.lock.txt`; both direct requirements and their full dependency closure must be included there. A regression test checks that every direct requirement has a compatible lock entry. The optional Docker `build_ca` secret supports dependency installation behind a trusted proxy without persisting its certificate in the image.

Dependency-lock correction verification: **826 API tests passed**, frontend production build passed, and a fresh Python 3.12 API Docker build passed its application import smoke test. Inside that image, `pip check` found no broken requirements and the dependency-lock regression test passed with networking disabled.

For optional push, generate keys privately in your own terminal:

```bash
docker compose --env-file infra/.env -f infra/docker-compose.yml run --rm --no-deps api python -m app.generate_push_keys
```

Copy the generated public/private/encryption values into `infra/.env` and set `PUSH_VAPID_SUBJECT` to a monitored contact such as `mailto:operations@your-domain.example`. Keep private/encryption keys out of Git and chat. Recreate API/worker/beat with the same four values; Compose passes them to each service. Do not rotate the encryption key without a binding migration or re-enrolment plan. Incomplete/invalid optional configuration leaves core CRM usable and push unavailable. `.env.example` contains blank placeholders.

Service workers/push require HTTPS, with localhost allowed for development. The API's same-origin proxy and existing security headers remain in place. Browser delivery needs worker egress to supported push vendors on HTTPS. No booking, accounting, SMS or messaging provider is selected by this phase.

On desktop Chrome/Edge, use the browser's **Install app** action. On iPhone/iPad with supported iOS (16.4+), use **Share → Add to Home Screen**, open SafariOS from that icon, then explicitly enable notifications. Mobile installation, operating-system delivery and the eventual Hostinger HTTPS/proxy/firewall configuration require real-device/deployment checks.

### Phase 4 manual checks

1. Open an authorized task, checklist, housekeeping job or transfer while online. Disconnect, apply a permitted change and check the explicit device-only message and Queued row. Reconnect: check Syncing then Synced and the authoritative record. Repeat with a wildlife photo.
2. Change the record from another account before replay. The old expected state must be rejected, without overwriting newer work. Review Retry and Discard; Escape must cancel confirmation without deleting anything. Try required proof, inspection and assignee rules.
3. Open two tabs, queue work and reconnect simultaneously. Confirm one active lease and stable command IDs. Interrupt/restart during upload, registration or an acknowledgement; retries must not duplicate the sighting or workflow mutation.
4. Revoke membership, employment, permission, offline entitlement or subscription before reconnecting. The server must reject or stop replay. Repeat as a field-role user, Group Admin switching lodges, and platform-only account.
5. Sign out offline and reconnect. No private page or previous queue should be restored. Switch accounts and use browser Back; confirm authentication and scope guards. A cold offline launch must show only the public fallback.
6. Inspect Cache Storage: only public/static assets should exist. Check that guest, HR, notification, authentication and RSC responses are absent. Verify scoped v2 photo migration and that unscoped legacy rows never appear under a new owner.
7. Configure push on a test installation. Check that no permission prompt appears before Enable. Change each category, turn off the device, revoke its session/membership and simulate an expired vendor endpoint. No personal/guest data may appear in push payloads or OS alerts, and stale bindings must not display/open notifications.
8. Review both themes at 375/768/1366/1440px, reduced motion, keyboard focus, drawer dismissal, readable statuses and retry/empty/error feedback. Confirm SafariOS and lodge branding remain intact.

Phase 5 and later phases require the owner's approval. Production key/HTTPS setup, real-device delivery, hosted proxy/firewall checks and load measurements remain deployment work.


### Phase 4 local verification — 12 November 2026

- Full API suite: **825 passed**, including real PostgreSQL tests for offline state conflicts, immutable atomic receipts, duplicate acknowledgements, own-work/tenant scope, checklist/inspection rules, offline entitlements, housekeeping feature gating, expiry, CSRF and photo-registration retry. Browser-push tests cover opt-out/categories, encrypted keys, approved destinations, redirect refusal, current recipient/resource access, session replacement/revocation, stale endpoints and durable failures.
- Production frontend build: **passed** after the final changes. Compose configuration and static guard audit also passed: **176 routes, zero guard issues; 25 modules, zero missing pages**.
- Full browser suite: **97 passed**, including the original login, activation, MFA, registration and create-guest flows, existing workflows, 272 screen/width/theme combinations and the new PWA paths. Final review added two more cases and rechecked the affected components: **three final targeted checks passed**, verifying **99 distinct suite checks overall**. The targeted runs supplement the earlier full run.
- The device drawer passed 375/768/1366/1440px overflow and automated WCAG 2 A/AA checks in both themes, with collapsed-navigation and visual review. Escape preserves the parent device drawer when cancelling confirmation; Discard cannot race an active replay claim. Late push setup cannot clear a new account's binding. These checks do not certify full accessibility or OS/browser delivery on physical devices.
- Native notification/push delivery is simulated in browser tests; API transport tests are mocked. No customer notification or external message was sent. Real HTTPS/VAPID/vendor delivery and iOS Home Screen behavior remain deployment/device checks.

Previews use test fixtures: [device sync — desktop dark](screenshots/safarios-device-sync-desktop-dark.png), [device sync — phone light](screenshots/safarios-device-sync-mobile-light.png).

Phase 4 implementation is complete. Remaining setup is installation-specific push keys/contact, HTTPS/worker egress and real-device verification; the existing Phase 3 hosted proxy/live-outbox-retention checks also remain. Phase 5 (speed, shortcuts and quick actions) and later phases await owner approval.

## Phase 5–6 (client-only): shortcuts, quick create, welcome tour

No API, permission, entitlement or data-contract change. Everything is derived from the already permission-filtered module list in `AppShell`; a locked or hidden module never gets a shortcut or action.

- **Keyboard shortcuts** (`components/KeyboardShortcuts.tsx`): `/` opens search, `?` opens the cheat sheet, `N` opens New task (the Tasks page still checks manage permission), `G` then `D/T/G/S/R/Q/H/M/N/W/F/A` jumps to a module. Ignored while typing in a field or while any dialog is open. The `G` prefix expires after 1.2 s. Also reachable from the user menu and the search palette.
- **Search palette quick actions**: New task, Record a sighting, Keyboard shortcuts, Welcome tour appear above the module list when the user may use them.
- **Quick create** (`components/QuickCreate.tsx`): mobile-only floating button above the bottom tabs offering New task and Record a sighting.
- **Welcome tour** (`components/WelcomeTour.tsx`): skippable first-run walkthrough, 3–5 steps filtered to the modules the user can use. Completion is remembered per user and lodge in `localStorage`; replay from the user menu.
- **Fixes**: mobile bottom-tab icons now match their destination (Tasks, Requests, Sightings, Alerts and field-role home) instead of reusing Dashboard, Users and Settings icons; the pinned "Ask Lodge AI" entry uses the sparkle icon; the authenticator QR dark colour uses the logo ink.

### Manual checks
1. Press `?` on any lodge page: the list shows only modules you can open. Press `G` then `T`: Tasks opens. Typing `g` or `n` inside any text field does nothing.
2. Press `N` as a Lodge Admin: Tasks opens with the form. As a role without task management: Tasks opens without the form.
3. Open search (Ctrl/Cmd+K): quick actions appear and run.
4. On a 375 px screen: the "+" button sits above the tab bar and opens New task / Record a sighting; Escape or tapping elsewhere closes it.
5. First login as a new user shows the tour; Skip stops it from returning; user menu → Welcome tour replays it.
6. Super Admin and suspended lodges: no shortcuts, tour or quick create are rendered.

Not included (needs device testing): swipe gestures, pull-to-refresh, bulk actions.

## Verified in a running stack (headless Chromium, PostgreSQL 16 + pgvector, Redis, FastAPI, `next start`)

Checked with a seeded lodge as Lodge Admin (desktop 1440 px and phone 390 px) and as a Ranger (phone). Screenshots: `docs/screenshots/verified/`.

Confirmed: first-login tour shows once and does not return; `?` cheat sheet; `G` then `T`; palette "Quick actions"; `N`; mobile "+" menu; Ranger lands on "My safari day" with correct bottom-tab icons; Live indicator turns "Live".

Fixed while testing:
- **Live updates never connected through the web server.** Next.js response compression buffered the server-sent event stream, so the indicator stayed on "Reconnecting" and the app silently fell back to polling. `next.config.mjs` now sets `compress: false` (compress at your reverse proxy instead; enable gzip/brotli there but exclude `text/event-stream`) and marks the events route `no-transform`.
- **`N` / the "+" menu did nothing when already on `/tasks`** (the page only read `?create=1` once). A small event (`lib/quick-actions.ts`) now opens the form.
- **Search icon overlapped the placeholder** in list toolbars.
- **Phones**: list pages now start on Cards instead of a sideways-scrolling table (unless the person chose a view); page header and toolbars are more compact.
- **Status boards**: columns are equal width; the "Move to…" control and drag handle are compact on desktop and stay large on touch screens.

Known, not changed: sidebar groups scroll when the window is shorter than about 900 px; on a brand-new lodge the setup checklist pushes the KPI cards below the fold; Rooms status is a manual field and does not follow in-house stays.
