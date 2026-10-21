# SafariOS UI conventions

Apply the shared warm-neutral, translucent design system to every new or edited screen. Read `../../docs/UI_UX_DESIGN_SYSTEM.md` before introducing a new visual pattern.

- The latest owner reference supersedes earlier beige/orange rules. Use exact dark background `#363636` and sidebar `#171717`, olive `#7F8967`, gray reading text, and the semantic dark/light tokens in `app/reference-theme.css`. Keep background layers neutral, with no olive wash or gradient. Olive is reserved for actions and active states. No orange, purple or bright gradients.
- Inter 400/500/600 is bundled locally. Operational headings use 500 weight at 30px desktop/26px mobile; card headings 16px. Avoid oversized bold display typography.
- Default to dark on fresh browsers; preserve explicit saved preferences and retain the light alternative.
- Use the shared 8/10/14/18px radius tokens: cards 14px, inputs/buttons 10px, dialogs 18px. Buttons are no longer pills. Keep the sidebar flush to the left with its divider; cards use 24px padding and 24px gutters, mobile 20px/16px.
- Glass surfaces use blur 32px and saturation 110%, including Safari prefixes and a solid fallback. Blur content behind the surface, never text. Use restrained borders/shadows and no decorative glows or card lift.
- `app/reference-theme.css` is the current semantic specification, loaded after legacy styles; Tailwind exposes the same tokens. Do not introduce another palette in page components. Preserve accessible text contrast and visible focus.
- Reuse `components/ui`, `Drawer`, `WorkspaceCommand`, `DataViz`, and the existing guarded shells. Extend shared components when a new pattern is needed so both themes and other screens inherit it.
- Keep SafariOS identity visible alongside authorized lodge branding. Preserve all existing role, entitlement, MFA, account-switch, and tenant-isolation checks. A navigation link does not grant access.
- Use Radix dialogs on desktop and Vaul drawers on mobile. Both mobile navigation entry points must use the shared focus-managed drawer. Keep labels connected to fields, inline validation readable, focus rings visible, and destructive actions confirmed.
- Every data-driven view needs loading, empty, error/retry, and success feedback. Never add fabricated operational records or inert product controls.
- Honor reduced motion and use the shared spring defaults. Keep the solid-surface fallback functional when blur is unsupported.
- Validate UI changes with a production build and relevant browser interactions. Review desktop/mobile and dark/light screenshots for material layout changes. Automated accessibility checks supplement visual and keyboard review; do not claim comprehensive accessibility certification from them.
