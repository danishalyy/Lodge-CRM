# Interactivity QA — Phase 1

Only instant actions are implemented here. Boards with drag-and-drop, SSE, push, generalized offline work, global shortcuts and walkthroughs remain later phases and require owner approval.

## Implementation

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

Phase 1 is complete within the existing API capabilities described above. Phases 2–7 remain unstarted pending the owner's approval. Real-device/manual checks and hosted deployment verification are separate from these local automated results.
