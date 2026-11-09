# SafariOS UI conventions

Apply the shared warm-neutral, translucent design system to every new or edited screen. Read `../../docs/UI_UX_DESIGN_SYSTEM.md` before introducing a new visual pattern.

- The owner-supplied November 2026 Premium UI spec supersedes earlier charcoal/glass guidance: canvas #17181C, navigation #121317, surface #1E2026, surface-2 #25272E, ivory #F0ECE2, secondary #A8A59B, matte gold #C4A067. Light uses #F6F3EC, #EFEBE2, white, #F1EDE3 and #1C1D21. Use the semantic variables in reference-theme.css and Tailwind, never a page-specific palette.
- Bundle Outfit 500 for headings/key figures and Inter 400/500/600 for body/UI. Titles 34px desktop / 28px mobile; card headings 18px; figures 44px / 36px. Use gold text #D8BB86 dark / #7A5C2C light. No gradients, glows, meshes or decorative gold underlines.
- Cards have 20px corners, inputs/buttons 12px, dialogs 28px. Inputs 48px high, controls at least 44px. Static surfaces are solid and shadow-free; blur and shadow belong only to overlays, with a solid fallback. Default dark and preserve saved theme.
- Use six permission-filtered, collapsible navigation groups, a pinned authorized AI link and a user menu. Desktop rail is 260px, collapsed 72px; top bar is 64px. Mobile navigation is role-aware and safe-area aware. Do not infer permissions from a chosen view.
- New views reuse PageHeader/KpiCard, CollectionView, TableScroll, DietaryChips, CodeInput, UserMenu, GroupedNavigation and SyncChip. Collection views present already-authorized rows; search/saved filters are local and scoped to user/lodge. Do not invent bulk mutation APIs or operational data.
- Reuse `components/ui`, `Drawer`, `WorkspaceCommand`, `DataViz`, and the existing guarded shells. Extend shared components when a new pattern is needed so both themes and other screens inherit it.
- Keep SafariOS identity visible alongside authorized lodge branding. Preserve all existing role, entitlement, MFA, account-switch, and tenant-isolation checks. A navigation link does not grant access.
- Use Radix dialogs on desktop and Vaul drawers on mobile. Both mobile navigation entry points must use the shared focus-managed drawer. Keep labels connected to fields, inline validation readable, focus rings visible, and destructive actions confirmed.
- Every data-driven view needs loading, empty, error/retry, and success feedback. Never add fabricated operational records or inert product controls.
- Honor reduced motion and use the shared spring defaults. Keep the solid-surface fallback functional when blur is unsupported.
- Validate UI changes with a production build and relevant browser interactions. Review desktop/mobile and dark/light screenshots for material layout changes. Automated accessibility checks supplement visual and keyboard review; do not claim comprehensive accessibility certification from them.

- Group Admin is an explicitly assigned multi-lodge role, never a platform role. Preserve lodge isolation, per-lodge subscriptions and account-change guards when switching. Ordinary accounts remain single-lodge.
- Use `WorkspaceAccessContext`/`useWorkspaceAccess` for per-feature tabs and controls. Show role-authorized package-gated modules as locked navigation items with an access-review screen. Keep unavailable subfeature controls hidden and avoid disabled-feature API requests. Keep backend feature and role checks intact.
- Mutations through `lib/api.ts` receive shared success/error feedback. Avoid duplicate manual success toasts; keep inline validation and destructive-action confirmation.

- The owner’s latest acacia/savannah SafariOS logo and matte gold/ivory palette supersede the earlier olive accent. Reuse `SafariBrand` and the bundled mark; never replace a lodge’s own logo. `design-system/safarios/MASTER.md` records the accepted UI/UX Pro Max synthesis. Consult the installed project skill at `.agents/skills/ui-ux-pro-max/SKILL.md` for future design work.

- Wrap operational tables with `components/ui/table-scroll.tsx` so horizontal overflow remains keyboard accessible without adding unnecessary tab stops.

- Super Admin is strictly platform-only. Never offer an Open lodge action, synthesize a lodge membership, grant operational permissions from is_super_admin/platform, or fetch tenant data from blocked operational screens. Platform branding previews use the explicitly guarded platform logo endpoint. Separate lodge and Group Admin identities retain their existing membership scopes.

- Use workspace permissions for every operational action and both feature/read permission for reference lookups. Use server-provided per-record workflow capabilities for owned work; these never replace API guards. When authority changes, close editors, clear reference choices and reject late results with the current workspace scope.
