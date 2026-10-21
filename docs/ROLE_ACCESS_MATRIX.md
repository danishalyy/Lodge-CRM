# Lodge CRM role-access policy — 1.5

This file describes the enforced server-side access model. UI hiding is not treated as authorization.

| Role | Production access rule |
|---|---|
| Super Admin | Platform-wide administration. Can register lodges, control subscriptions and package overrides, inspect tenants for support, and review platform audit/users. Operational writes still respect subscription write state. |
| Group Admin / Owner | Full authorized operations in explicitly assigned group lodges, subject to each lodge’s package and subscription. Group overview and lodge switching; no platform administration. |
| Lodge Admin / General Manager | Full authorized access inside one lodge, subject to package entitlements and subscription state. Can manage HR records and Standard/Premium custom roles where entitled. |
| Department Manager / Supervisor | Department-scoped staff, HR records, tasks, requests, housekeeping/maintenance, activities, transfers, reports and command-centre metrics. No lodge-wide operational memory or guest CRM by default. |
| Front Office / Guest Services | Guest CRM, stays/arrivals/departures, rooms, guest requests, activities/transfers and relevant operational tasks according to permissions. |
| Ranger / Guide | Own assigned activities/game drives and tasks, ranger workspace, vehicle checklist/fuel/wildlife functions allowed by package. Does not receive lodge-wide guest CRM or operational memory. |
| Housekeeping | Own assigned tasks and housekeeping jobs, department-relevant guest requests, room operational status updates through the housekeeping workflow and issue reporting. Cannot edit room configuration or full guest CRM. |
| Maintenance / Workshop | Maintenance workflow, relevant vehicles/inspection/fuel visibility, own tasks. Does not receive lodge-wide operational memory. |
| Driver / Transport | Own assigned transfers and tasks, vehicle/checklist/fuel functions required for transport. Cannot administer all transfers. |
| F&B / Kitchen | Own tasks, department-relevant guest requests and a restricted dietary/allergy view. Does not receive the full guest CRM. |
| Finance / Accounts | Reports and approved cost/fleet/fuel visibility. No broad operational-memory access. |
| General Staff | Own assigned tasks and own assigned guest requests, plus issue reporting. |
| Read Only / Auditor | Read-only information/reports according to granted permissions; no operational writes. |

## Subscription access states

- **Active / Expiring Soon**: normal role + entitlement access.
- **Expired**: existing authorized records remain readable; all operational writes are rejected by the API.
- **Pending**: operational CRM is blocked until the subscription start date.
- **Suspended**: operational CRM is hard-blocked regardless of dates. Account-security functions remain available.

## Authorization layers

1. Authenticated server-side session.
2. Active user-to-lodge membership.
3. PostgreSQL tenant context / RLS.
4. Role permission.
5. Record scope (department or own assignment where applicable).
6. Subscription state.
7. Package entitlement / Super Admin override.

## Custom roles

Standard/Premium lodges can define a custom role by choosing a built-in base operational scope and an explicit permission set. The base role continues to control record scope (for example department-only or own-assignment-only), while the custom permission set controls which modules/actions are authorized. A custom role cannot be used to bypass tenant, subscription, package, department or own-record restrictions.

Group Admin was restored by the owner on 21 October 2026. See [group setup and boundaries](LODGE_GROUPS_AND_FEEDBACK.md). Ordinary staff/Lodge Admin accounts remain single-lodge.
