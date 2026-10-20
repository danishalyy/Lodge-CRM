# Lodge CRM requirements compliance review — Security & Integrity Hardening 1.8

Source of truth reviewed: the final operating-system scope, package/feature guide, and role-access document. A later product decision removes **Group Admin / Owner**; therefore multi-property Group Admin functionality is intentionally excluded until the product owner explicitly reintroduces it.

Status legend: **Implemented** = backed by persistent production data/authorization; **Partial** = meaningful foundation exists but the documented workflow is not complete; **Not built** = intentionally unavailable rather than simulated.

## Platform, identity and subscriptions

| Requirement | Status | Notes |
|---|---|---|
| Multi-tenant lodge isolation | Implemented | Lodge-scoped records, membership verification, PostgreSQL RLS foundation. |
| Super Admin | Implemented | Lodge registration, subscriptions, entitlement overrides, audit/user inspection. |
| External subscription payment only | Implemented | No in-app lodge subscription payment processing. |
| Start / expiry dates | Implemented | Super Admin controlled. |
| Active / Expiring Soon / Expired / Suspended | Implemented | Expired is read-only; Suspended and Pending are hard-blocked. |
| Expiry reminders 30/14/7/3/0 | Implemented | Background scheduler / persisted alerts. |
| Basic / Standard / Premium entitlement hierarchy | Implemented | Server-side plan entitlement tables plus per-lodge overrides. |
| Password recovery | Implemented | One-time expiring reset token; requires real SMTP. |
| MFA | Implemented | TOTP with encrypted secret, replay protection and forced Super Admin setup; production requires encryption key. |
| Custom roles created by each lodge | Implemented foundation | Lodge Admin can create lodge-specific roles with a base operational scope and explicit permission set, then assign them to real staff memberships. Additional UX for role cloning/templates can be added later. |

## Core CRM

| Requirement | Status | Notes |
|---|---|---|
| Lodge command centre | Implemented | Real database metrics. Department Manager view is department-scoped. |
| Guest CRM | Partial | Core guest details, preferences, dietary/allergy fields, notes and stay linkage exist. Dedicated occasions, communication history, feedback/complaint history and richer safari preferences remain. |
| Arrivals / departures / stay records | Implemented | Persistent stay lifecycle, room linkage and conflict prevention. |
| Guest requests -> trackable work | Implemented | Requests can be assigned/resolved and linked to real tasks. |
| Guest feedback / complaints workflow | Implemented | Ratings, categories, compliments/complaints, department/staff assignment, follow-up flag, resolution and resolution timestamp are persistent and scoped. |
| Staff profiles | Implemented | Core profile, department, role/account linkage and operational state. |
| Full HR operations | Partial | Supervisor, hire date, leave, shifts/roster, training, credentials/certificate expiry, confidential incidents and performance notes are implemented. Dedicated days-off planning and workload analytics remain. Payroll remains intentionally external. |
| Departments | Implemented | Standard entitlement with department-scoped manager visibility. |
| Tasks lifecycle | Implemented | Created -> Assigned -> Accepted -> Started -> Completed, timestamps and responsibility. |
| Advanced task features | Partial | Recurring tasks, required task checklists, comments and verified image/PDF attachments are implemented. Reusable checklist templates and formal configurable escalation rules remain. |
| Basic housekeeping | Implemented | Room status and housekeeping-related task/request workflow. |
| Full housekeeping | Implemented foundation | Dedicated cleaning/turndown/inspection/linen jobs, assignees, inspectors, due times and room-ready transitions are persistent. Overdue-room-prep alerts/analytics and richer inspection templates remain. |
| Maintenance tickets | Implemented | Room/vehicle linkage, assignment, priority/status, costs, resolution. |
| Full maintenance/workshop | Partial | Asset register, parts usage/cost, downtime timestamps and scheduled/recurring maintenance are implemented. General attachments/photos, richer inspections/service-history views and repeated-issue analytics remain. |

## Safari, transport and lodge operations

| Requirement | Status | Notes |
|---|---|---|
| Shared activities schedule | Implemented | Persistent activities with guests, guide, vehicle, conflicts and status lifecycle. |
| Ranger / guide operational view | Implemented | Own assigned drives/tasks, vehicle details and assigned guest dietary/allergy context. |
| Transport / driver workflow | Implemented | Driver/vehicle/guest/flight/timing/status plus assignment conflict checks. |
| F&B / dietary workflow | Implemented foundation | Meal schedules, special dinners/events, guest counts, assigned guest lists, live dietary/allergy visibility and service lifecycle are persistent. Dedicated kitchen push notifications and menu/inventory features remain outside this foundation. |
| Basic fleet register | Implemented | Real vehicle records/status/odometer/service data. |
| Advanced fleet | Partial | Pre-drive checks and service fields exist; tyre detail, licence/insurance expiry and richer repair/inspection history remain. |
| Fuel records | Implemented | Real litres, cost, odometer, recorder/date records. |
| Vehicle maintenance reminders | Partial | Alert foundations exist; complete date/mileage rule configuration for tyres/brakes/batteries etc. remains. |
| Wildlife sightings | Implemented | Species, notes, GPS, time, reporter/activity and real photo object storage. |
| Offline wildlife capture/sync | Implemented foundation | Browser IndexedDB queue and duplicate-safe synchronization exist. Full native mobile offline experience remains. |
| Advanced wildlife analytics | Not built | Premium maps/frequency/location-trend analytics remain. |

## Mobile and notifications

| Requirement | Status | Notes |
|---|---|---|
| Staff mobile companion | Not complete | Responsive web modules exist, but a dedicated production mobile application with full offline selected data is still required. |
| Guest mobile experience | Not built | Lodge info, itinerary, contacts, guest requests and Guest AI mobile experience remain. |
| Offline tasks/info/emergency/inspections | Not built | Only wildlife offline foundation exists today. |
| In-app notifications | Implemented | Persisted user notifications/preferences. |
| Email delivery/retries | Implemented | Durable outbox and worker retry handling; real SMTP required. |
| Push notifications | Not built | APNs/FCM provider integration remains. |
| Intelligent priorities/escalations | Partial | Severity and selected operational alerts exist; complete configurable escalation rule engine remains. |

## Reports, operational memory and AI

| Requirement | Status | Notes |
|---|---|---|
| Audit log | Implemented | Sensitive/admin actions stored and exposed to Super Admin. |
| Operational memory | Implemented foundation | Persistent event timeline separate from audit logs. Event coverage must continue expanding as remaining modules are built. |
| Standard operational reports | Partial | Live summary for tasks, maintenance, requests, stays, fuel, activities, transfers, wildlife and room status. Dedicated/exportable report suite remains. |
| Department-scoped reports | Implemented | Department Manager summary cannot expose lodge-wide unrelated metrics. |
| Lodge AI chatbot | Not built | Intentionally disabled rather than returning simulated answers. |
| AI knowledge base / document uploads | Not built | Production ingestion, chunking, embeddings, source grounding and isolation remain. |
| AI staff / guest questions | Not built | Requires production AI layer. |
| AI daily/weekly reports and insights | Not built | Premium requirement remains. |

## Premium / integrations

| Requirement | Status | Notes |
|---|---|---|
| Multi-property / Group Admin | Intentionally excluded | Later product-owner decision removed Group Admin / Owner despite older documents. |
| Live GPS | Not built | Requires real supported hardware/provider. |
| Trip playback | Not built | Requires telemetry history. |
| Geofencing | Not built | Requires telemetry layer. |
| Advanced telemetry/device health | Not built | Provider/device integration required. |
| Satellite integration | Not built | Requires compatible hardware/service subscription. |
| Advanced fuel alerts | Not built | Sensor/provider or enough validated fuel data required. |
| PMS integration | Not built | Integration framework/provider-specific work remains. |
| Accounting integration | Not built | Provider-specific work remains. |
| WhatsApp/SMS integration | Not built | Provider/consent configuration remains. |
| Enterprise API access | Not built | Controlled external API credentials/scopes remain. |
| Lodge identity / co-branding | Implemented | Super Admin manages display name and validated raster logo across packages; SafariOS remains visible. Custom domains, branded exports and deeper white-label controls remain. |
| Workflow automation | Partial | Scheduled system jobs exist; customer-configurable automation rules remain. |

## Production readiness conclusion

Version 1.6 adds guest feedback/complaints, staff rosters/incidents/performance, F&B meal operations and verified task attachments on top of the 1.5 workflows, but the **full application described in the documents is not yet feature-complete**. The system must not be sold as the complete Standard/Premium product until the remaining rows above are implemented and verified. No unbuilt requirement should be represented by fake data or a simulated success path.
