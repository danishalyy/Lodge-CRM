# SafariOS Premium UI design system

The owner supplied a new Markdown specification and 43-page visual PDF on 10 November 2026. Their ink/ivory/gold design supersedes the earlier charcoal/glass treatment. Original specification: [source](requirements/ui-reference/SafariOS-UI-UX-Redesign-Spec.md). Accepted master: [MASTER](../design-system/safarios/MASTER.md).

## Tokens

| Purpose | Dark | Light |
|---|---|---|
| Canvas | #17181C | #F6F3EC |
| Navigation | #121317 | #EFEBE2 |
| Surface | #1E2026 | #FFFFFF |
| Nested surface | #25272E | #F1EDE3 |
| Text | #F0ECE2 | #1C1D21 |
| Secondary | #A8A59B | #5B5A55 |
| Gold | #C4A067 | #C4A067 |
| Gold hover | #D2B27A | #B38E54 |
| Reading gold | #D8BB86 | #7A5C2C |
| On gold | #17181C | #17181C |
| Success | #A3B899 | #43603A |
| Warning | #D9B26F | #7A5A1E |
| Danger | #E0968A | #9B463D |
| Info | #9DB4B0 | #3E625B |

`app/reference-theme.css` maps the supplied semantic variables to the existing application; `app/design-system.css` owns shared structure/material tokens, and Tailwind exposes them. Legacy variable names remain internal compatibility bridges where old selectors still reference them; they resolve to this palette. Outfit 500 is locally bundled for headings/figures, alongside Inter UI. No remote font dependency.

Cards have 20px corners and no shadow/blur; controls12px, overlays28px. Inputs48px, buttons44px, mobile field actions56px. Blur/shadow are reserved for drawers/dialogs/command palette/user popovers. Solid fallback, reduced motion, visible focus and readable status text remain mandatory. Light focus uses the darker reading gold for contrast.

## Shared presentation

`GroupedNavigation` groups authorized routes and persists collapsed sections. The active group stays open. `UserMenu` provides account security/theme/sign-out; `NavigationEnhancements` keeps the existing focus-managed mobile drawer and role-aware bottom tabs. Desktop sidebar260px/rail72px; topbar64px. `CollectionView` uses existing authorized table rows for local search, status filters, saved presentations, cards, boards and detail drawers. It creates no new data endpoint or bulk mutation. Selection supports reviewing visible records. Existing owning-module actions remain authoritative. Workspace changes clear detail/selection state.

`PageHeader`, `KpiCard`, `CodeInput`, `DietaryChips` and `SyncChip` support consistent future screens. OTP stays one accessible input with six visual cells, natural typing/paste and the existing validation contract. Sync reports the actual scoped wildlife queue only; it does not claim complete staff offline support.

## Scope and precedence

Keep existing API contracts, routes, roles, scopes, CSRF, MFA and entitlements unchanged. A visual prototype cannot authorize new data. The source's Super Admin acting-in-lodge banner is intentionally excluded: Super Admin remains platform-only. Live maps, device telemetry, unsupported analytics, unavailable guest-history fields and missing bulk APIs are not fabricated. Existing Group Admin and co-branding remain intact.

## Conversational AI

Retain the 720px reading column, private history and scope-safe pending turns. Render Markdown without raw HTML or model-authored remote tracking images. Sources remain server-provided and collapsed. Keep action review/confirmation and explicit provenance. No fake streaming, stop, voice or attachment controls. Preserve drafts, IME handling and rejection of stale responses after account/lodge changes.

## Verification

Phase 1 interactivity extends existing controls without changing these visual tokens. Use the shared scoped memory cache and instant-action hook for optimistic workflows; retain server-authorized transitions and avoid unsupported Undo actions. See [interactivity implementation and QA](INTERACTIVITY_QA.md). Drag-and-drop, live events, push and broader offline behavior are separate later phases.

Run the production build, existing API suite and browser checks for forms, activation, MFA, registration, role separation and data flows. Review 375/768/1366/1440px in both themes. Automated checks supplement visual/keyboard review; they do not establish full accessibility certification or commercial completion of unavailable integrations.
