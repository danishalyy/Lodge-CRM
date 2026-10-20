# SafariOS Liquid Glass

SafariOS uses a calm glass interface with a midnight background, restrained indigo/violet/teal ambient mesh, champagne identity accents, and Geist typography. Lodge names and private logos remain visible alongside SafariOS. This is a visual system; account and tenant authorization remain enforced by the existing API and guarded shells.

## Foundations

`apps/web/app/design-system.css` is the shared visual source. `tailwind.config.ts` exposes the same semantic CSS variables to Tailwind. Both existing operational classes and new components inherit theme changes. The legacy `globals.css` provides structural compatibility; do not add another palette there.

Dark is the default. An early layout script reads the saved `theme` preference before painting; `ThemeToggle` persists changes. Fonts ship locally through `geist`, without a runtime Google Fonts request. Theme colors use `--bg-base`, `--surface-glass`, `--text-primary`, `--text-secondary`, `--text-muted`, `--accent`, `--accent-hover`, `--premium`, and semantic status tokens.

The requested dark muted swatch `#6B7280` is retained as a palette token. Reading text uses the brighter `--tx3` instead, because the original muted swatch does not meet AA on these surfaces. Light mode uses darker status text and champagne text. Primary buttons layer a subtle dark overlay on the requested indigo/violet gradient for white-label contrast. Reserve raw palette swatches for decorative elements; use reading tokens for text. Check actual composited colors when introducing a new transparent surface.

Glass uses blur 24px, saturation 180%, a translucent border, inner top highlight, and a soft shadow. Browsers without backdrop filtering receive opaque dark/light surfaces. Cards use 24px corners, dialogs 28px, fields 14px, and action buttons/chips pill corners. Space on an 8px grid with 24–32px card padding. Typography uses 12/14/16/20/28/40px, weight 600 headings, and tight heading tracking.

## Components and future screens

Import reusable primitives from `@/components/ui`: Button (Radix Slot and class variants), Card, Input, Badge, Skeleton, DataTable (TanStack sorting), Calendar (react-day-picker), and ConfirmDialog. `components.json` records the shadcn-compatible aliases and theme configuration. These are application-owned primitives rather than a separate UI framework.

Use the existing `Drawer` wrapper for record editors. It uses Radix Dialog on desktop and Vaul on mobile, with focus containment, accessible titles, Escape dismissal, and scroll locking. `WorkspaceCommand` provides cmdk search using only authorized modules. `Providers` supplies Framer Motion spring defaults (300/30), reduced-motion handling, and Sonner notifications. Page templates fade and slide 8px. New charts should reuse `DataViz` (Recharts) and preserve a readable nonvisual summary.

Desktop navigation floats away from the edge and can collapse; the preference persists. Mobile quick tabs show only permitted destinations. More opens a focus-managed drawer listing the authorized screens. Existing top-bar navigation remains available. Avoid adding primary actions to every card: choose one clear action per page and keep secondary work contextual.

For forms, use React Hook Form with Zod, connected labels, inline errors with `aria-describedby` and `aria-invalid`, and server error messages. The lodge branding editor demonstrates this approach. Do not replace API validation with client checks. Confirm destructive changes before submitting; the logo removal flow demonstrates ConfirmDialog. Provide loading, empty, error/retry, and success states; never populate production views with fictitious records.

Every new screen must use the shared shell and semantic tokens. Keep visible focus rings, native keyboard controls, meaningful accessible names, 44px action targets, and reduced-motion behavior. New bespoke components still require review; a shared stylesheet cannot guarantee accessibility for arbitrary future markup.

## Review

Browser tests cover existing account isolation plus theme persistence, collapse state, mobile drawers, keyboard command search, inline branding validation, reduced motion, and horizontal overflow. Screenshot fixtures use mocked frontend records for review only; they do not create production data.

- [Dark lodge portfolio](screenshots/safarios-lodges.png)
- [Light lodge portfolio](screenshots/safarios-lodges-light.png)
- [Mobile portfolio](screenshots/safarios-lodges-mobile.png)
- [Branding dialog](screenshots/safarios-branding.png)
- [Lodge dashboard](screenshots/safarios-workspace.png)
- [Mobile lodge dashboard](screenshots/safarios-workspace-mobile.png)
- [Sign in](screenshots/safarios-login.png)
- [Mobile sign in](screenshots/safarios-login-mobile.png)

Run `npm ci --prefix apps/web`, `npm run build --prefix apps/web`, and `BROWSER_EXECUTABLE_PATH=/usr/bin/chromium npm test --prefix e2e` (after `npm ci --prefix e2e`). See `LOCAL_SETUP.md` for Docker setup; preserve `infra/.env` and database volumes when updating.

`apps/web/AGENTS.md` carries these conventions into future UI work. The current validation includes 265 surface contract checks and browser checks of account isolation and the new interactions. Automated WCAG A/AA checks cover the dark/light portfolio and login fixtures; this is representative coverage, not a complete manual accessibility certification of every workflow.
