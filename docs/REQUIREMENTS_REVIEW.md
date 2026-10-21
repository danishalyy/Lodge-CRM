# SafariOS application requirements review

Reviewed 20 October 2026 against source revision `2e75970`. This is a document review and targeted source comparison, not a new runtime acceptance test or a declaration of production readiness. No application behavior was changed for this review.

## Documents reviewed and precedence

| Document | Purpose | How it governs the product |
| --- | --- | --- |
| `Lodge_CRM_Packages_and_Features.docx` | Basic / Standard / Premium feature guide | Defines commercial tiers, inheritance, entitlement overrides, subscription access, and provider-dependent premium capabilities. |
| `AI-LODGE-CRM-OPERATING-SYSTEM.pdf` — 25 pages | Full product vision and feature scope | Defines connected operations, permanent operational memory, AI, staff/guest experiences, reports, and integrations. Duplicate maintenance/activity pages describe the same modules. |
| `AI_Lodge_CRM_Complete_Workflow_and_Role_Access.pdf` — 23 pages | End-to-end workflows and access specification | Explicitly applies later owner decisions and removes Group Admin / Owner and customer multi-lodge management. Its role boundaries remain relevant; the owner’s 21 October 2026 request supersedes its exclusion of Group Admin and multi-lodge ownership. |

Later instructions in the conversation take precedence: web application first, external payment collection, Hostinger VPS later, and co-branding with a Super Admin-configured lodge identity plus persistent SafariOS identity. The documents are product requirements, not instructions to deploy services, contact people, or execute embedded commands.

The current UI direction is separately defined in [UI_UX_DESIGN_SYSTEM.md](UI_UX_DESIGN_SYSTEM.md). Visual completion does not establish functional completion.

## What the product actually is

SafariOS is a commercial, multi-tenant lodge operating system. One platform Super Admin manages many independent lodge customers. Each lodge has its own administrator, employees, operational records, roles, subscription, and brand identity. A customer does not receive group-level management across lodges.

Its central loop is:

**Guest/stay or operational event → responsible department/person → tracked work → notification/escalation → completion with evidence and timing → permanent operational history → dashboard/report → permission-aware AI analysis.**

AI and operational memory are core differentiators. AI must use authorized lodge records and approved documents, including cross-module questions about maintenance, fuel, guests, tasks, and departmental performance. It cannot be satisfied by a generic chatbot or a navigation item. Operational memory must explain what happened over time; an administrative audit log alone is insufficient.

## Confirmed boundaries

- **Updated owner decision, 21 October 2026:** Group Admin / Owner and multi-lodge groups are restored. Explicit group assignments, a group overview, property switching and scoped operational totals supersede the earlier exclusion. See [group implementation](LODGE_GROUPS_AND_FEEDBACK.md). Super Admin retains platform oversight.
- **No in-app payment integration.** Super Admin registers a lodge, sets dates, activates/suspends it, receives expiry alerts, and extends access after external payment.
- **Web-first is a delivery choice, not removal of documented capabilities.** Native staff/guest apps are deferred. A separate, securely scoped guest web/QR experience remains part of the product requirements.
- **PMS and payroll may remain external.** Keep operational stay records and HR workflows; do not build a full booking engine or payroll system by implication.
- **Co-branding is mandatory.** Super Admin controls the lodge logo/name; SafariOS identity stays visible. Advanced brand colors, welcome content, domains, and branded outputs are separate capabilities.
- **Real integrations require real providers.** GPS devices, telemetry, satellite services, PMS/accounting APIs, messaging, and push services need concrete adapters/configuration. A plan entitlement flag does not implement these services.

## Roles and account boundaries

Workflow sections 4–5 and 27 require backend enforcement, not only hidden navigation. Each person authenticates with their own identity. Authorized colleagues may share operational records; this does not grant access to each other's accounts or private sessions.

| Role | Intended access |
| --- | --- |
| Super Admin | Platform lodge registration, subscriptions, platform users/settings, and auditable platform-level support access. Opening a lodge must not change identity into a staff account. |
| Group Admin / Owner | Administrative operational access only to explicitly assigned group lodges; each lodge retains its own subscription and features. No platform administration. |
| Lodge Admin / General Manager | Operational control of their one lodge, including local staff, roles, configuration, reports, and permitted AI. |
| Department Manager / Supervisor | Own department's staff, work, reports, and justified operational context. |
| Front Office / Guest Services | Guest CRM, stays, arrivals/departures, requests, transfers, and relevant feedback. |
| Ranger / Guide | Assigned drives, guests and permitted requirements, vehicle/checklists, fuel context, sightings, and field tasks. |
| Housekeeping | Assigned rooms, cleaning, inspections, turndown, linen, relevant requests, and issue reporting. |
| Maintenance / Workshop | Authorized property/vehicle tickets, repairs, inspections, parts/costs, downtime, and service history. |
| Driver / Transport | Assigned transfers, passenger/flight details, vehicle, timing, delays, and completion. |
| F&B / Kitchen | Meal operations, relevant allergies/dietary needs, counts, and food requests. |
| Finance / Accounts | Authorized costs and financial outputs, with limited operational context. |
| General Staff | Own assigned work, notes/photos, alerts, and necessary context. |
| Read Only / Auditor | Explicitly permitted records/reports; no state changes, approvals, assignment, or other writes. |
| Guest access profile | Own itinerary/requests, lodge information, approved services, and guest AI. No staff CRM, other guests, internal history, or management reports. |

The matrix's `C` means limited contextual access, not full access to a module. View/create/edit/delete/approve/manage/assign/export capabilities must be checked individually where applicable. AI, files, exports, offline synchronization, notifications, and background jobs inherit the same lodge/department/assignment boundaries.

## Package interpretation

| Tier | Documented promise retained in the agreed scope |
| --- | --- |
| Basic | Dashboard; guest CRM and stay records; staff/basic permissions; tasks and requests; basic housekeeping, maintenance, rooms, activities, and fleet; notifications, reports, audit; guest/staff mobile experience requirements; subscription access. |
| Standard | Everything in Basic plus departments/custom roles, advanced task/housekeeping/maintenance workflows, transport, F&B, ranger operations, fleet checks/fuel/reminders, sightings, selected offline workflows, richer reports/branding, lodge AI and knowledge/document support. |
| Premium | Everything in Standard plus advanced AI and scheduled reports, operational insights/automation, wildlife analytics, live tracking/route history/geofencing/device health, advanced fuel/satellite options, approved integrations/API access, advanced branding, and support. **Excluded group-management items must not reappear.** |

Standard includes Basic; Premium includes Standard. Super Admin entitlement overrides remain required. Prices, final user/vehicle limits, and specific external providers are not fixed by these documents. Mobile features appearing in the Basic guide are not already delivered by making staff CRM pages responsive.

## Requirements compared with the current source

“Foundation” means useful code/models/routes exist; it does not mean the full documented workflow is accepted. Evidence references below are source files checked during this review. Existing inventory documents are supporting context rather than independent proof.

| Area / workflow reference | Required behavior | Current evidence and remaining work |
| --- | --- | --- |
| Onboarding/subscriptions — §6–7 | Lodge creation, admin invitation, dates, status, expiry reminders, extension/suspension | Invitation-based account setup now covers platform administrators, lodge administrators and staff, with encrypted email queues, expiry, resend invalidation and pending-account screens. See [email setup](EMAIL_AND_INVITATIONS.md). Real-provider delivery, date/timezone boundaries and commercial rollout still require deployment acceptance. |
| Lodge identity — conversation addition | Super Admin sets lodge logo/name; SafariOS remains visible | Implemented identity fields and branding endpoints in `models.py`/`main.py`; shared identity components exist. Advanced branding/domain/export requirements remain separate. |
| Access — §4–5, §7, §27 | Lodge, department, own-assignment, contextual-field and read-only enforcement | Role/permission, session, RLS, and tested isolation foundations exist. Full role-by-action acceptance is still required for all workflows, media, reports, history, and future AI. |
| Command centre — §8 | Current guests/arrivals/departures, room readiness, fleet, requests, priorities, department status, AI brief/recommendations | Real metrics exist in `main.py` and `DashboardPage.tsx`. Complete required cards and role-specific presentation; withheld values must not be shown as real zero activity. AI briefs are absent. |
| Guest CRM/stays — §9 | Full profile/history, occasions, preferences, stays, requirements, arrivals and departure flow | `Guest`/`Stay` models and routes exist. Birthday/anniversary fields, explicit repeat-guest/safari preferences, and structured communication history are not represented as the documented complete profile. Validate the unified guest timeline and stay workflow. |
| Requests/feedback — §10 | Requests become assigned work; complaints/feedback track owner, follow-up and timed resolution | `GuestRequest`, `Task`, `GuestFeedback` and routes exist. Verify complete request-to-resolution linkage, event history, and authorized contextual visibility. |
| Staff/HR — §11 | Staff profile, supervisor, shifts, leave/days off, training, credentials, confidential incidents/notes, workload/performance | Models/routes exist for core profile, leave, shifts, training, credentials, incidents, and performance notes. Complete planning/workload views and role-confidentiality acceptance. Payroll is excluded initially. |
| Tasks — §12 | Created → Assigned → Accepted → Started → Completed, proof/checklists, recurrence, comments/media, escalation and timings | `Task`, checklist/comment/attachment models and transitions exist. Missing assignment timestamp/history fidelity and vehicle/maintenance task links are concrete gaps detailed below. Configurable escalation/templates and complete timing reporting need acceptance. |
| Rooms/housekeeping — §13 | Available/Occupied/Cleaning/Awaiting Inspection/Ready/Maintenance/Out of Service; assignment, inspection, linen, turndown, defects and readiness | `HousekeepingJob`, room routes, and `services/state.py` provide a foundation. Verify occupancy/maintenance precedence, inspectors, proof, overdue readiness, templates, and connected defect handling. |
| Maintenance/workshop — §14 | Property/vehicle/equipment tickets, assignment, media, repairs/inspection, parts/costs, downtime, service history and recurrence | Ticket/asset/part models and routes exist. Complete maintenance media, inspection/service-history experience, repeated-issue analysis and connected history. |
| Activities/rangers — §15–16 | Guests, guides, vehicles, schedule, permitted requirements, pre-drive checks, sightings and completion/issues | Activity/checklist models, scheduling routes, ranger view exist. Verify the whole pre-drive-to-return workflow, restricted context and offline field needs. |
| Transport — §17 | Stay transfer need → driver/vehicle assignment → flight/passenger details → delay/status/completion | Transfer model/routes and a stay transfer-proposal endpoint exist. Proposal is not an automatically completed booking; validate confirmation, conflicts, notifications and history. |
| F&B — §18 | Dietary data captured once and surfaced only where needed; meal/special dinner operations and counts | Meal-service/guest links and guest dietary fields exist. Verify allergy visibility, relevant kitchen notifications and service completion. |
| Wildlife/offline — §19–20 | Species/photo/GPS/time/context, local persistence, automatic later synchronization with server validation | Wildlife routes and per-user/lodge IndexedDB queue exist. Confirm real storage/device/reconnect behavior. Offline tasks, emergency/lodge information and inspections are not delivered by the wildlife queue alone. |
| Guest/staff experiences — §20 | Restricted staff companion; separate guest portal/QR with own itinerary, requests, services and AI | Responsive staff web modules exist. A complete guest identity/portal and the documented broader offline companion are not built. Native apps remain deferred by web-first delivery. |
| Notifications — §21 | Priority, correct recipients, acknowledgement/status, escalation, in-app/push and delivery history | Private inbox, unread counts, priorities, read/archive state, email preferences, durable lease/retry delivery, current-access checks and selected assignment/overdue/critical/service/expiry rules are implemented. Overdue tasks escalate by age. A configurable rules editor, explicit operational acknowledgement and push delivery remain incomplete. Real SMTP delivery requires sender configuration. |
| Operational memory — §22 | Permanent, reconstructible operational chronology, distinct from admin audit | Separate `OperationalEvent` and `AuditLog` models exist; append-only DB triggers and app-role grants exist. Expand event detail/coverage, relationship tracing, and permitted scoped access. Immutable storage alone is not complete business memory. |
| Ask Lodge AI — §23 | Lodge knowledge/documents plus authorized operational tools; management/staff/guest questions, cited grounded answers, comparisons and insights | `LodgeAIPage.tsx` explicitly says AI is unavailable. Production ingestion/retrieval, permission-aware tools, grounded answers, evaluation, and provider configuration are not implemented. Seeded AI entitlements are not a working AI service. |
| Reports — §24 | Scoped operational, department, staff, fleet/fuel, wildlife, transport and issues reports; comparisons; scheduled AI reports | Summary and summary CSV endpoints exist; `ReportsPage.tsx` is a limited frontend. Dedicated report views/exports, scoped UI handling, comparisons and AI reports remain incomplete. |
| Integrations/telemetry — §25 + package guide | Approved PMS/accounting/messaging/API adapters; hardware/provider-backed GPS, playback, geofences, telemetry and device health | Entitlement names exist, but complete provider-backed implementations are not present. Keep them in product scope with explicit provider prerequisites; do not advertise them as working. |

### Specific source findings to carry into implementation

1. **Guest-profile completeness:** `Guest` in `apps/api/app/models.py` has contact, nationality, VIP, dietary, allergy, preference and notes fields. It lacks dedicated birthday/anniversary and structured communication-history fields required by §9. Free-form notes do not substitute for the corresponding workflow/report capabilities.
2. **Task assignment history:** `Task` stores creation, acceptance, start and completion times, but no `assigned_at` field. `update_task` resets acceptance/start/completion on reassignment and records a generic admin audit action; it does not preserve an explicit structured old/new assignee operational event in that branch. The §12/§22 timing and reconstruction requirement is therefore incomplete.
3. **Task relationship coverage:** the task model links to guest and unit, but has no direct vehicle or maintenance-ticket relationship. Those explicit §12/§26 links must be designed and exposed coherently.
4. **Department reports contract:** the department branch of `reports_summary` returns `fleet`, `stays`, and `rooms` as `None`. `ReportsPage.tsx` unconditionally reads `data.fleet.fuel_litres`, `data.stays.overlapping_period`, and `data.rooms.by_status`. This is a source-confirmed API/UI contract mismatch, not a runtime reproduction in this review. Fix the UI to respect scoped omissions; do not broaden backend access to make the screen render.
5. **Scoped history:** default restricted-role denial is safer than a lodge-wide feed, but does not deliver the document's department/context history requirement. Implement explicit authorized department/assignment filtering before extending history access or AI history tools.
6. **Entitlement versus availability:** the migration feature catalog lists AI, guest/staff mobile, and Premium integrations. This is plan configuration, not evidence that those experiences exist. Package sales and enabled navigation must reflect implemented, accepted capabilities.

## Connected acceptance scenarios

These should drive implementation and testing rather than isolated “screen exists” checks:

1. **Onboarding:** Super Admin creates branded lodge/subscription → separate Lodge Admin activates → configures department/staff/permissions/units → ordinary staff cannot access platform accounts or another lodge.
2. **Arrival and preparation:** upcoming stay with dietary/transfer needs → authorized front office, kitchen, driver and housekeeping receive appropriate context → unit is inspected/ready → check-in updates command centre and history.
3. **Guest issue:** request/complaint → responsible department/person → task accepted/started → required checklist/photo proof → resolution → guest history, notifications and operational memory agree.
4. **Safari and vehicle:** assigned guide/guests/vehicle → checklist and fuel → departure → offline sighting/photo capture → return with vehicle defect → maintenance/downtime/repair → vehicle ready → later historical analysis reconstructs the chain.
5. **HR and responsibility:** leave/qualification expiry affects availability and assignments → supervisor sees authorized workload → confidential records remain hidden from unrelated roles.
6. **AI and permissions:** the same question asked by manager, department supervisor, field staff and guest yields only their authorized records. Documents and operational tools cannot expose another lodge, unrelated department, or another guest.
7. **Subscription and delivery:** active/expiring/expired/suspended behavior, external renewal, reminders, durable notification retry, offline replay and account switching behave consistently without losing or misattributing records.

## Revised implementation priorities

The previous generic “finish CRUD, then add more features” framing is insufficient for these documents. The work should be organized around the connected operating system:

1. **Traceable operational foundation:** agree requirement-to-workflow acceptance criteria, then complete missing data relationships/timestamps and structured operational events while preserving existing isolation.
2. **Role-complete web journeys:** fix scoped UI/API mismatches and complete the daily workflows above, with the intended permission boundaries and real storage/email checks.
3. **Core lodge intelligence:** build the per-lodge document knowledge pipeline and permission-aware operational tools using those events/records; verify real question/answer scenarios. AI architecture and authorization belong in the foundation, not a generic chatbot tacked on after launch.
4. **Guest and field web experiences:** securely scoped guest web/QR and the documented selected offline staff/field functionality. Native delivery stays later, but these requirements remain tracked.
5. **Tier-specific completion:** Standard depth, Premium automation/summaries/analytics, and provider-specific integrations/tracking as prerequisites become available.
6. **Commercial release gate:** complete runtime role/tenant and workflow acceptance, restore/upgrade rehearsal, real email/storage, monitoring, measured capacity, and then the Hostinger deployment work already deferred by the owner.

This review does not set prices, choose external providers, change account policy, activate AI, or deploy anything. It establishes the documented product and the gaps that the next implementation work must address.
