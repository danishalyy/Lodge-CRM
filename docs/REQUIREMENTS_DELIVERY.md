# Document-led delivery and acceptance map

Reviewed 9 November 2026 against the three original attachments and the current source, including verified scheduled-report implementation. This replaces stale completion assumptions in earlier milestone inventories. `requirements/delivery-map.json` contains all 63 named package items, their document references and outstanding acceptance; this file summarises the same register. No feature is considered commercially accepted merely because a model, endpoint, screen or feature flag exists.

## Source precedence and confirmed owner decisions

1. The package guide defines Basic → Standard → Premium inheritance and named capabilities. The operating-system scope defines the connected product. The workflow PDF defines the detailed role/record boundaries and end-to-end flows.
2. The workflow PDF's exclusion of Group Admin is superseded by the owner's later explicit restoration. Group Admin is retained, with explicit property membership and each lodge's own subscription/features.
3. The initial release is web first. Native apps are deferred; the documented restricted guest web/QR experience and selected offline staff/field workflows remain requirements.
4. Payments stay external. Currency/cost records remain, with South Africa/ZAR defaults. No payment gateway or payroll engine is added by implication.
5. Super Admin sets lodge identity; SafariOS remains visible. The latest charcoal design governs the application. Hostinger is the future hosting target; no infrastructure purchase or deployment has occurred.
6. Account invitations cover Gmail and business addresses; owners set their own passwords through expiring links. Each person retains their own identity/session. Shared operational access is permission based, not access to another person's private account.

7. Super Admin is platform-only: no lodge workspace, operational API or group-owner access, including legacy assignments. Platform branding previews use a separate platform endpoint. Lodge access requires a separate lodge or Group Admin identity.
8. No external booking, accounting, GPS or messaging systems have been selected by the owner. Provider-dependent connections stay pending; core work continues independently.

The original-file SHA-256 identifiers are recorded in the JSON register. Attached documents are requirements sources; owner instructions govern execution and later overrides.

## Status definitions

- **Implemented core:** the named capability has a persistent implementation; connected-role, real-provider and commercial acceptance may still remain.
- **Partial:** a documented subfeature or connected workflow is incomplete or lacks the required acceptance evidence.
- **In verification:** implementation is being checked; do not advertise it as commercially accepted.
- **Missing:** no complete implementation for the stated workflow was found.
- **Provider dependent:** the feature remains in scope, with real adapters/hardware/configuration still required.
- **Operational requirement:** a service/process must actually be provided; a software flag cannot satisfy it.

## Basic

| ID / source | Requirement | Current state | Work needed for acceptance |
| --- | --- | --- | --- |
| B01 / §3.1 | Lodge dashboard | partial | Finish the complete command-centre journey, scoped AI brief/recommendations where enabled, and connected readiness/alert acceptance. |
| B02 / §3.2 | Guest CRM | partial | Birthday/anniversary, repeat-guest/safari preferences and a scoped interaction log are implemented. Finish the unified stay/activity/request/feedback history and connected-role acceptance. |
| B03 / §3.3 | Arrivals and departures | implemented core | Run the connected front-office, kitchen, transfer and room-preparation acceptance journey. |
| B04 / §3.4 | Operational stay records | implemented core | Verify the complete guest/stay history and concurrent room-assignment journey; a booking engine is not required. |
| B05 / §3.5 | Staff profiles | implemented core | Verify all role-confidentiality, supervisor, employment and operational-availability journeys. |
| B06 / §3.6 | Basic roles and permissions | implemented core | Complete the default/custom-role matrix for every contextual field, export, worker and offline action. |
| B07 / §3.7 | Task management | implemented core | Assignment timing/history, direct vehicle/maintenance links and all three creation paths are implemented in 0024. Complete connected-role and operational acceptance. |
| B08 / §3.8 | Guest requests | implemented core | Accept request → assigned task → proof/checklist → resolution → guest/history/notification journey. |
| B09 / §3.9 | Basic housekeeping | implemented core | Accept room preparation, defect hand-off and readiness under assigned-role constraints. |
| B10 / §3.10 | Basic maintenance tickets | partial | Complete maintenance media and the linked repair/inspection/history experience. |
| B11 / §3.11 | Activities and safari schedule | implemented core | Accept guide/guest/vehicle scheduling, checklist, departure, return and issue reporting together. |
| B12 / §3.12 | Basic fleet records | implemented core | Accept availability, linked activity/transfer and maintenance state consistently. |
| B13 / §3.13 | Basic notifications | implemented core | Verify live delivery/retry and every specified recipient, priority and status path. |
| B14 / §3.14 | Guest mobile experience | missing | Deliver the restricted guest web/QR equivalent now; native applications remain deferred by the owner. |
| B15 / §3.15 | Staff mobile companion | partial | Responsive staff screens exist; complete the focused companion and documented offline subset. |
| B16 / §3.16 | Basic reports | partial | Expand the dedicated report/export journeys beyond the existing summary surface. |
| B17 / §3.17 | Audit logs | implemented core | Retain append-only administrative audit and verify support/export paths; audit is distinct from operational memory. |
| B18 / §3.18 | Subscription access control | implemented core | Verify live expiry/reminder delivery and launch date boundaries; retain external payment collection. |

## Standard

| ID / source | Requirement | Current state | Work needed for acceptance |
| --- | --- | --- | --- |
| S01 / §4.1 | Department management | implemented core | Accept own-department staffing, work, approvals and contextual access together. |
| S02 / §4.2 | Custom roles and permissions | implemented core | Retain exact administrator delegation and accept every custom base-scope combination. |
| S03 / §4.3 | Advanced task management | partial | Assignment timing/history and vehicle/maintenance relationships are implemented. Finish configurable escalation/templates, wider lifecycle reporting/export and connected-role acceptance. |
| S04 / §4.4 | Full housekeeping workflow | implemented core | Accept cleaning, inspections, turndown, linen, overdue preparation and defect hand-off end to end. |
| S05 / §4.5 | Room/unit management | implemented core | Verify all documented states with occupancy and maintenance precedence and custom unit names. |
| S06 / §4.6 | Full maintenance/workshop | partial | Complete attachments/photos, inspection/service history, recurrence and repeated-issue evidence. |
| S07 / §4.7 | Transport/driver management | implemented core | Accept stay need → confirmed transfer → assigned driver/vehicle → delay/completion and history. |
| S08 / §4.8 | F&B/dietary management | partial | Accept single-entry dietary data, meal counts and only the relevant kitchen/guest-service alerts. |
| S09 / §4.9 | Ranger/guide module | implemented core | Accept the assigned-drive journey with permitted requirements, checks, fuel/issues and return. |
| S10 / §4.10 | Advanced fleet management | partial | Reconcile tyre, licence/insurance, inspection and detailed service history requirements with the current fields and UI. |
| S11 / §4.11 | Fuel management | implemented core | Accept accurate per-vehicle consumption/cost review and field confidentiality across roles. |
| S12 / §4.12 | Vehicle maintenance reminders | partial | Reconcile and accept all date/mileage, tyre/brake/battery service rules; existing fixed reminders are a subset. |
| S13 / §4.13 | Wildlife sightings | implemented core | Accept authorised species/photo/GPS capture, protected-species visibility, storage and history. |
| S14 / §4.14 | Offline photo/GPS capture | partial | Wildlife queue exists; verify real-device persistence, photos, reconnect, duplicate replay and account isolation. |
| S15 / §4.15 | Offline mobile mode | partial | Assigned tasks, essential lodge/emergency information, notes and inspections are not delivered by the wildlife queue alone. |
| S16 / §4.16 | Push notifications | missing | Deliver browser push for the web release where supported; native delivery stays deferred. |
| S17 / §4.17 | Lodge AI chatbot | partial | Management chat/tools exist; complete default staff access, guest access and the documented operational question set. |
| S18 / §4.18 | AI knowledge base | implemented core | Private scoped retrieval exists; real-model grounding and complete live ingestion acceptance remain. |
| S19 / §4.19 | Document knowledge uploads | implemented core | Extraction/vector/ACL boundaries are tested; verify the full real storage/worker/embedding pipeline. |
| S20 / §4.20 | AI for guest questions | missing | Add a separate guest principal and explicitly guest-approved knowledge; internal lodge SOP access is not guest access. |
| S21 / §4.21 | AI for staff questions | partial | Complete the default staff role grants and contextual questions without broadening assigned/department scopes. |
| S22 / §4.22 | Advanced operational reports | partial | Dedicated department, housekeeping, maintenance, activities, fleet/fuel, staff and wildlife report/export coverage remains. |
| S23 / §4.23 | Enhanced branding | partial | Co-branding exists; guest welcome content/selected colours remain. Preserve Super Admin logo control and SafariOS identity. |

## Premium

| ID / source | Requirement | Current state | Work needed for acceptance |
| --- | --- | --- | --- |
| P01 / §5.1 | Multi-lodge/group management | partial | Explicit assignments/switching exist; reconcile Premium availability and per-property overrides with the package guide. |
| P02 / §5.2 | Group dashboard | partial | Current scoped totals exist; finish package and documented guest/staff/fleet/alert coverage acceptance. |
| P03 / §5.3 | Cross-property reporting | partial | Read-only comparisons exist; finish the complete selected report set and acceptance. |
| P04 / §5.4 | Live vehicle GPS tracking | provider dependent | Select compatible devices/provider API and implement/accept actual ingestion and live status. |
| P05 / §5.5 | Trip history/route playback | provider dependent | Needs real tracking ingestion, scoped route storage and playback; entitlement flags are not an implementation. |
| P06 / §5.6 | Geofencing | provider dependent | Needs actual location events, zone rules, scoped alerts and tests. |
| P07 / §5.7 | Advanced telemetry | provider dependent | Needs supported device/provider events and the dedicated ingestion/processing path. |
| P08 / §5.8 | GPS device health | provider dependent | Needs actual last-contact/stale-device signals and operational acceptance. |
| P09 / §5.9 | Advanced fuel alerts | partial | Existing low-fuel rules do not establish abnormal-consumption/drop detection; add evidence-based rules and any required sensor adapter. |
| P10 / §5.10 | Satellite tracking | provider dependent | Requires compatible hardware, subscriptions and a selected supported provider. |
| P11 / §5.11 | Advanced lodge AI | partial | Scoped reads, memory, documents, comparisons and confirmed proposals exist; complete all source question/scenario coverage. |
| P12 / §5.12 | AI daily lodge summary | implemented core | Private opt-in daily reports pass 706 API tests, the build and 43 browser checks. Real-model and live worker/delivery acceptance remain. |
| P13 / §5.13 | AI weekly management report | implemented core | Private weekly reports pass 706 API tests, the build and 43 browser checks. Complete the wider documented KPI/pattern set and real-model acceptance. |
| P14 / §5.14 | AI operational insights | partial | Current advisory count rules are a subset; repeated maintenance, downtime and recurring service issues need complete authoritative data. |
| P15 / §5.15 | Advanced wildlife analytics | missing | Add authorised species frequency, periods, location trends/maps and comparative views. |
| P16 / §5.16 | Workflow automation | partial | Fixed background alerts exist; configurable rules, acknowledgement and source-event history remain. |
| P17 / §5.17 | PMS/booking integrations | provider dependent | Select the system and supported API; implement per-lodge mapping, idempotency, conflicts and retry acceptance. |
| P18 / §5.18 | Accounting/business integrations | provider dependent | Select the system and supported API; implement only authorised business exchange. |
| P19 / §5.19 | WhatsApp/SMS integrations | provider dependent | Select the supported messaging channel/provider and configure consent, delivery and retries. |
| P20 / §5.20 | Controlled external API access | missing | Implement separately scoped/revocable integration credentials, limits, audit and cross-lodge denial tests. |
| P21 / §5.21 | Advanced custom branding | partial | Core co-branding exists; assistant naming, stronger guest branding and domain options remain separate work. |
| P22 / §5.22 | Priority support/assisted integrations | operational requirement | Define and configure the actual support service, destination and assistance process; no service level is invented. |

## Connected workflows that decide completion

| Acceptance ID | Document basis | Required result |
| --- | --- | --- |
| FLOW-01 | Workflow §§6–7, 27 | Super Admin registers a branded lodge/access period → separate Lodge Admin activates → staff/roles/units are configured → unrelated accounts/lodges remain inaccessible. |
| FLOW-02 | §§9, 13, 17–18 | Stay with transfer/dietary needs → only relevant front office, kitchen, driver and housekeeper receive context → inspection/readiness → check-in → coherent history. |
| FLOW-03 | §§10, 12, 21–22 | Request/complaint → responsible department/person → accepted/started work → required proof/checklist → resolution → guest history, alerts and memory agree. |
| FLOW-04 | §§14–16, 19–20, 22 | Assigned safari → vehicle checks/fuel → departure → offline photo/GPS/notes → return/defect → maintenance/downtime/repair → ready → later traceable history. |
| FLOW-05 | §11 | Shift/leave/credential affects availability and allocation; workload is scoped; confidential incidents/notes stay protected. |
| FLOW-06 | §§4–5, 20, 23–24, 27 | Manager, department manager, assigned staff and guest ask the same operational question and receive only their authorised facts/documents. |
| FLOW-07 | §§6–7, 19–21, 27 | Active/expired/suspended/renewed access, retries, offline replay and account switching never misattribute or duplicate records. |

The thirteen manager questions in workflow §23.1 are acceptance cases, including department comparison, repeated room maintenance, per-vehicle monthly fuel, permitted arrival dietary needs, outstanding staff work, period comparisons and yesterday's drive issues. Current generic list tools do not establish complete coverage of these questions. Add authoritative scoped aggregates/context readers and real-model evaluation where the present data is insufficient; do not infer totals or causes from truncated pages.

## Next implementation order

1. Finish and validate the current daily/weekly report milestone against §§8, 23–24, including per-property package checks and private delivery.
2. Complete guest-profile and task-relationship/timing/event gaps (§§9, 12, 22, 26), then accept FLOW-02/03/04.
3. Complete default staff AI access and the explicit §23.1 question set, maintaining field/department/assignment scope and source provenance.
4. Deliver restricted guest web/QR and guest-approved AI knowledge (§20.2), followed by the remaining selected offline workflows (§20.3).
5. Complete the named Standard reports, HR/workload, maintenance media and notification/automation/acknowledgement gaps.
6. Complete independent Premium analytics and controlled API access. Named provider/hardware integrations stay tracked until selected and actually tested.
7. Complete the production operations, migration/restore, live email/storage/worker/model, security and load acceptance gates before customer launch.

Optional presentation or infrastructure refinements must not displace these documented workflows. Permanent operational memory remains append-only and distinct from private chat retention and administrative audit. Existing security checks must remain in force throughout.

## Explicit AI question acceptance

| ID | Source question | Current state / acceptance gap |
| --- | --- | --- |
| AI01 | What is happening in the lodge today? | Current dashboard facts/tools exist; validate real-model grounding and permitted-source completeness. |
| AI02 | What needs my attention? | Current overdue/count sources exist; accept the complete prioritisation/alert context without invented causes. |
| AI03 | Give me today's full operational report. | Scoped daily sources/scheduling are under verification; distinguish bounded details from complete totals. |
| AI04 | What happened yesterday? | Scoped historical retrieval exists; complete event coverage, immutable snapshots and connected reconstruction. |
| AI05 | Which tasks are overdue? | The reader exists; accept old/large datasets and apply overdue filtering before pagination. |
| AI06 | Which department is having the most problems? | Add complete scoped, deterministic department comparisons and define the counted issue types. |
| AI07 | Which rooms have recurring maintenance problems? | Add authoritative repeated-issue/room history analysis with ticket evidence, period and coverage. |
| AI08 | Which vehicle has used the most fuel this month? | Add complete per-vehicle period aggregates/ranking; a truncated fuel-record page is insufficient. |
| AI09 | Which guests arriving tomorrow have dietary requirements? | Add the permitted arrival/need context with explicit sensitive-field checks; generic stay DTOs intentionally omit medical/dietary data. |
| AI10 | Which staff members still have outstanding tasks? | Complete assignment context and authoritative scoped staff/workload aggregation. |
| AI11 | Give me a maintenance report for this month. | Date-bounded summary metrics exist; complete the requested maintenance detail, scope and real-model acceptance. |
| AI12 | Compare this month with last month. | Date-bounded metrics exist; add complete deterministic comparisons and clearly disclose period length/time basis. |
| AI13 | What problems occurred during yesterday's game drives? | Complete activity/vehicle issue links and immutable event detail before claiming historical issue coverage. |

## Cross-cutting requirements beyond package names

| ID / source | Requirement | State / acceptance |
| --- | --- | --- |
| C01 / Operating-system p3; workflow §22 | Permanent operational memory, separate from administrative audit | partial: Task assignment/lifecycle snapshots are implemented. Complete historical reconstruction for the other modules and an approved scoped AI reader for the new task snapshots. |
| C02 / Workflow §§4–5, 7, 27 | Complete default/custom role and contextual-field matrix | partial: Test each named role, department/own-record scope, contextual field, export, worker, notification and offline replay boundary. |
| C03 / Workflow §§12, 26 | Cross-module relationships and responsibility/timing | partial: Guest/stay/unit/staff/department/task/vehicle/activity/maintenance/notification links support the complete event chain. |
| C04 / Workflow §§20.2, 23, 27 | Distinct guest identity and guest-approved knowledge | missing: A guest receives only their own stay/itinerary/requests and approved guest information, with no staff/internal knowledge or other guest data. |
| C05 / Owner invitation/security decisions; workflow §§6–7 | Account activation and private identity/session protection | implemented core: Each person uses their own activated email/password; invitations expire; no account impersonation or cross-account private history. |
| C06 / Owner branding decisions; package §§4.23, 5.21 | SafariOS identity alongside Super Admin-managed lodge identity | implemented core: The authorised lodge logo/name never removes SafariOS identity or grants platform access. |
| C07 / Workflow §§19–20.3, 27 | Selected offline work with authorised idempotent reconnect | partial: Persist the documented subset, protect account/lodge boundaries, validate current access on sync, and do not replay duplicates. |
| C08 / Owner launch-market decision; production requirements | South African commercial web launch acceptance | partial: Keep ZAR defaults and external payments; verify actual SMTP/storage/workers/model, backups/restore, migrations, monitoring and measured capacity before launch. |

Task responsibility/history checkpoint: [scope, migration and validation](TASK_WORKFLOW_DELIVERY.md). This implements the core B07 gaps while S03 and the cross-module memory/relationship requirements remain partial.

Platform/lodge isolation checkpoint: [scope and verification](PLATFORM_ISOLATION_DELIVERY.md). This removes the former platform support bypass; it does not declare the wider role/field acceptance matrix or remaining functional requirements complete.

Role-control checkpoint: [scope and verification](ROLE_CONTROLS_DELIVERY.md). Remaining operational action controls now follow permissions, with server-provided assignment capabilities and guarded reference data. The wider connected-role, worker and offline acceptance register remains open.
