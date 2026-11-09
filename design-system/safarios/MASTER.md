# SafariOS Premium UI master

Source: owner-supplied SafariOS UI UX Redesign Spec.md and 43-page Premium UI Redesign PDF, reviewed 10 November 2026. These supersede the old #363636/#171717 visual reference. The original text is retained in docs/requirements/ui-reference. This is a visual specification; API contracts, data scopes, entitlements, MFA and tenant isolation remain authoritative.

## Material and type

Dark: canvas #17181C, nav #121317, surface #1E2026, nested #25272E, text #F0ECE2, secondary #A8A59B. Light: #F6F3EC, #EFEBE2, #FFFFFF, #F1EDE3, text #1C1D21 and secondary #5B5A55. Gold #C4A067, reading gold #D8BB86 dark / #7A5C2C light, on-gold #17181C. Status colours come from the supplied semantic tokens.

Outfit 500 headings and figures, Inter 400/500/600 UI, locally bundled. Title 34/28px, card title18px, labels11px with .14em tracking, body14px, tables13px, figures44/36px. Cards20px radius, controls12px, overlays28px, chips99px. Solid surfaces, no card shadows/lift, no gradients. Blur/shadow only on overlays, reduced-motion support and visible contrast-safe focus.

## Composition

Grouped sidebar: Today, Guests, Operations, Safari & Fleet, People, Insight. Keep all authorized existing routes, locked package review screens and Group Admin switching. Pin AI and the user menu. Desktop sidebar260px/rail72px and topbar64px. Mobile uses a role-aware bottom bar and the existing focus-managed drawer.

Command Centre: personal greeting, one authorized primary action, four authoritative KPIs (unknown remains unavailable), a real today timeline and attention list, then task health/memory and collapsed calendar/subscription. Use existing permitted data; never generate example guests, telemetry, alerts, dietary data or staffing totals.

Lists reuse CollectionView and TableScroll for local search/status filters, saved presentation, list/cards/board views and detail drawers. Existing field/action permissions and mutations stay in their owning modules. Native field screens prioritize assigned work and permitted actions.

## Security precedence

The source's reference to a Super Admin acting inside a lodge conflicts with the owner's explicit platform-only requirement. Do not implement it. Platform accounts never enter lodge/group operational routes. Real lodge branding remains alongside SafariOS. Live maps/telemetry and other unimplemented capabilities remain unavailable. Do not add unsupported controls or new API contracts to imitate a reference screenshot.

See docs/UI_UX_DESIGN_SYSTEM.md for implementation and docs/ROLE_CONTROLS_DELIVERY.md for protected access behavior.
