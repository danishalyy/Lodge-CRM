# SafariOS UI conventions

Apply the shared Liquid Glass design system to every new or edited screen. Read `../../docs/UI_UX_DESIGN_SYSTEM.md` before introducing a new visual pattern.

- Use the semantic tokens in `app/design-system.css` and `tailwind.config.ts`. Do not introduce another palette or hardcode opaque backgrounds in page components. Reading text must use accessible reading tokens rather than decorative muted/accent swatches.
- Reuse `components/ui`, `Drawer`, `WorkspaceCommand`, `DataViz`, and the existing guarded shells. Extend shared components when a new pattern is needed so both themes and other screens inherit it.
- Keep SafariOS identity visible alongside authorized lodge branding. Preserve all existing role, entitlement, MFA, account-switch, and tenant-isolation checks. A navigation link does not grant access.
- Use Radix dialogs on desktop and Vaul drawers on mobile. Both mobile navigation entry points must use the shared focus-managed drawer. Keep labels connected to fields, inline validation readable, focus rings visible, and destructive actions confirmed.
- Every data-driven view needs loading, empty, error/retry, and success feedback. Never add fabricated operational records or inert product controls.
- Honor reduced motion and use the shared spring defaults. Keep the solid-surface fallback functional when blur is unsupported.
- Validate UI changes with a production build and relevant browser interactions. Review desktop/mobile and dark/light screenshots for material layout changes. Automated accessibility checks supplement visual and keyboard review; do not claim comprehensive accessibility certification from them.
