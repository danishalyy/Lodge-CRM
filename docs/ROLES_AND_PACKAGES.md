# Roles and packages usability

## Part A — Roles

The API supplies eleven locked staff presets, their actual DB grants, copyable permissions, allowed assignments, scope descriptions, and grouped action metadata. Custom copies exclude sensitive grants and actions the creator does not own. The editor provides simple group choices, Advanced controls, a live summary, editable custom roles, assignment counts and impact confirmation. Staff Add/Edit access forms show preset and custom-role choices. Assignment validates actor permissions, active roles, department requirements and lodge ownership. Invitations apply custom roles before their transaction commits. Deactivation restores the previous preset and retains history rather than hard-deleting roles.

Scope descriptions reflect endpoint behavior; maintenance is a workshop pool and finance is not a universal money-only filter. Migration 0014 makes three narrow existing administrator capabilities explicit for strict preset-copy/delegation checks. RLS and sensitive custom-role blocks are unchanged.

Validation: 453 API tests, production build and targeted browser flows passed. Preset → custom copy → edit → staff assignment → deactivate is covered. Optional per-lodge preset editing is intentionally not implemented; presets stay locked.
