# Roles and packages usability

## Part A — Roles

The API supplies eleven locked staff presets, their actual DB grants, copyable permissions, allowed assignments, scope descriptions, and grouped action metadata. Custom copies exclude sensitive grants and actions the creator does not own. The editor provides simple group choices, Advanced controls, a live summary, editable custom roles, assignment counts and impact confirmation. Staff Add/Edit access forms show preset and custom-role choices. Assignment validates actor permissions, active roles, department requirements and lodge ownership. Invitations apply custom roles before their transaction commits. Deactivation restores the previous preset and retains history rather than hard-deleting roles.

Scope descriptions reflect endpoint behavior; maintenance is a workshop pool and finance is not a universal money-only filter. Migration 0014 makes three narrow existing administrator capabilities explicit for strict preset-copy/delegation checks. RLS and sensitive custom-role blocks are unchanged.

Validation: 453 API tests, production build and targeted browser flows passed. Preset → custom copy → edit → staff assignment → deactivate is covered. Optional per-lodge preset editing is intentionally not implemented; presets stay locked.

## Part B — Packages

Super Admin can edit each active database plan's working feature grants. The review step shows the affected lodge count; the API checks both the plan revision and count before committing an audited change. Changes apply dynamically through existing entitlement checks, while lodge exceptions remain in force. Plans and their descriptions now populate registration and subscription choices, with a shared comparison table.

One server catalogue describes and groups implemented capabilities separately from coming-soon capabilities. AI, external integrations, live tracking and telemetry cannot be enabled as usable access. Existing future plan associations are retained as roadmap information only. Lodge exceptions require a reason, display plan/default/exception/final access separately, and record the reason in the audit log. Locked screens query actual database plans and can create a private access-review notification for active Super Admin recipients, with daily request deduplication. They do not grant access. Existing subscription write restrictions apply. Optional email delivery follows recipient preferences and configured delivery settings; the in-app notification does not require an email provider.

Migration 0015 adds plan descriptions, revisions, ordering and exception reasons. No RLS policy is removed. Validation: 462 API tests, production frontend build, static guard audit and browser checks for registration, affected-lodge confirmation and locked navigation. No requested Part B work remains; unfinished product capabilities remain explicitly marked coming soon, rather than being implemented by this access-management change.
