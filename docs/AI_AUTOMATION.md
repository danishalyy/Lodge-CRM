# Role-based AI actions — 19 November 2026

SafariOS can prepare operational changes from a conversation. These are deliberate, single-lodge actions: the model proposes a change, the account owner reviews the exact server-validated details, and **Confirm and apply** saves it. Typing “yes” in chat cannot execute a change. No unattended general-purpose agent or arbitrary database/HTTP/shell tool is enabled.

## Supported requests

| Action | Example | Existing module authority required |
|---|---|---|
| Add a guest | “Add guest Thandi Nkosi, email thandi@example.com, phone +27821112222, nationality South Africa.” | `guests.manage` |
| Create a stay | “Prepare a stay for Thandi Nkosi in River Suite from 10 to 12 December 2026 for two people.” | `stays.manage` |
| Create a guest request | “Record an amenity request for Thandi: extra towels.” | `requests.manage` |
| Schedule an activity | “Prepare a morning walk on 11 December 2026 from 06:00 to 08:00 South African time for Thandi.” | `activities.manage` |
| Schedule a transfer | “Prepare an airport pickup for Thandi on 10 December 2026, 10:00–11:00 South African time, for two passengers.” | `transfers.manage` |
| Create a task | “Assign Sipho a high-priority task to inspect the pump.” | `tasks.manage` |
| Update a task | “Mark my assigned inspection task in progress.” | `tasks.view` plus `tasks.manage` or permitted `tasks.own.manage` |
| Report maintenance | “Report a leaking tap in Room 4.” | `maintenance.view` plus `maintenance.manage` or `maintenance.report` |
| Create housekeeping work | “Prepare a cleaning job for Room 7.” | `housekeeping.manage` |

Names and identifiers must resolve to authorised records. Ambiguous names and missing dates/details need clarification; the model is instructed never to invent them. The guest directory tool returns names and IDs only, with bounded results; it never returns contact, medical or free-form profile information. Room and staff lookups retain their independent read permissions. Date-time actions require an explicit time-zone offset; review the dates and local times carefully. Guest profiles can include the existing form fields provided by the user, subject to the same schema validation.

Each turn creates at most one proposal. For a new guest followed by a stay, confirm the guest first, then ask for the stay. The AI cannot promise a multi-step workflow has completed after preparing just one action.

## Enable and delegate

1. Keep the normal AI provider configured and tool calling working. AI still needs the existing `ai` feature and `ai.use` permission.
2. Set `AI_ACTIONS_ENABLED=true` in the existing ignored `infra/.env`.
3. Super Admin enables **Confirmed AI actions** (`ai_actions`) in the lodge's plan or explicit feature exception. Each affected module must also be enabled; guest requests use the existing `guest_requests` feature.
4. Lodge Admin and Group Admin retain the existing default `ai.actions` grant. Other staff need deliberate delegation through the existing custom-role controls, including `ai.use`, `ai.actions` and the specific module authority above. Enabling AI never grants a missing CRM permission.
5. From the repository root, run:

```sh
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

The existing migration service applies `0029_ai_guest_actions`. No new provider, secret or dependency is introduced. Group Admin must select one assigned lodge to perform work; group-comparison chats remain read-only. Super Admin stays platform-only. The separate guest assistant has no operational action tools.

## Review and execution guarantees

- Preparation and review call the normal CRM mutation implementations inside a rolled-back savepoint. No guest, booking, task, notification or event survives those previews.
- Confirmation uses the existing CSRF-protected, owner/lodge/conversation-bound review token. It expires with the ten-minute proposal, is replaced on re-review, and never enters model context.
- Current account/session, role, package, module, write access, referenced records and snapshots are rechecked before execution. Confirmed replays return the saved result without creating another record. Reference locks and normal scheduling locks remain in place.
- Room overlap, unavailable vehicles, guide/driver schedules, inactive staff and guest activity conflicts use the same checks as the normal screens. The shared guest-request handler also verifies a selected stay belongs to that guest.
- Guest duplicate detection is serialised across normal forms and AI. A matching name/email added after a proposal was reviewed causes confirmation to fail instead of creating a duplicate. Blank guest names are rejected.
- Guest email addresses in the current question become random per-request references before inference/chat persistence. Only an exact reference from that request can populate the guest email field; model-invented addresses and older chat references are rejected. Include an email again in the current message if needed. Other guest details you explicitly type can enter the configured inference service; use an appropriate trusted provider and privacy policy.
- After guest creation, its contact/profile payload is removed from the AI action record; the confirmation result/preview retains only the created guest ID. The CRM remains the guest record. The usual private chat retention policy still applies to user-supplied text.
- Guest-directory source answers stop replaying when a referenced profile is anonymised. New actions cannot reference anonymised guest profiles.
- All nine action kinds remain an explicit database/application allowlist. The new migration changes neither forced RLS nor private ownership policies. Downgrade refuses to discard new action history; retain the current schema or use a deliberate matching pre-upgrade backup/application restore.

To fit smaller local contexts, a model with many available actions first uses `select_action` to load one authorised action schema, then resolves references and prepares a proposal. This selection never changes data or grants permission. Tool-call rounds/context budgets remain bounded; missing evidence cannot become a claimed successful change.

## Verification and acceptance

Real PostgreSQL/RLS tests cover all five new mutation paths, no writes/events before confirmation, idempotency, module/role denial, foreign/anonymised references, changed permissions, booking conflicts, duplicate guests, current-message email binding, names-only lookup and source withdrawal. An isolated old-schema migration rehearsal checks old proposal preservation, forced RLS, round-trip migration and refusal of a lossy downgrade. Existing task, housekeeping, maintenance, group, CSRF and account-isolation regressions are retained.

Browser fixtures cover all five new proposal/review/confirmation flows, readable fields/dates, specific success toasts and mobile/desktop layouts. They supplement the full API suite and production build, rather than proving a particular model will interpret every request correctly. Real local-model accuracy, ambiguous-name handling and tool-selection latency still need acceptance with representative lodge data. No live customer record is created by these tests.
