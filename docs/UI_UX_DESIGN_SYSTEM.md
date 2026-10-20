# SafariOS — warm neutrals and translucent surfaces

SafariOS uses warm charcoal, ivory, and stone with translucent blurred surfaces. Page titles use Cormorant Garamond; navigation, forms, tables, and operational labels use Manrope. Primary actions are solid colors. There are no purple accents, colored background meshes, or decorative gradients. Lodge names and private logos remain visible alongside SafariOS.

The user supplied Fitosauna as a visual reference. That domain was blocked by the execution environment, so this palette and font pairing are an implementation of the requested neutral direction, rather than a verified match to the reference. A reference screenshot is needed to match its exact colors and typography.

## Foundations

`apps/web/app/design-system.css` is the shared visual source. `tailwind.config.ts` exposes the same semantic CSS variables to Tailwind. Both existing operational classes and new components inherit theme changes. The legacy `globals.css` provides structural compatibility; do not add another palette there.

Dark is the default; the saved light preference is restored before paint. Fonts are bundled locally through `@fontsource`, with no runtime third-party font request. The semantic CSS variables are exposed to Tailwind, including font families `sans` and `serif`.

Dark: base `#191C18`, text `#F0EDE5`, stone accent `#C8BDAA`, and glass `rgba(237,231,219,.055)`. Light: base `#EEEAE1`, text `#292E26`, charcoal accent `#424C3B`, and glass `rgba(255,253,247,.62)`. Reading text uses the theme's secondary and muted tokens. Status colors use restrained sage, ochre, clay, and gray-green, with darker versions in light mode. Primary buttons use the contrasting `--acText` color.

Translucent surfaces use blur 24px, saturation 110%, fine neutral borders, a restrained inner highlight, and soft shadows. Static neutral background planes give the glass depth without colored gradients or moving blobs. Browsers without blur use solid theme surfaces. Cards retain 24px corners, dialogs 28px, fields 14px, and pill actions. Page headings are editorial serif; dense data and component titles remain sans serif. Motion stays subtle and respects reduced-motion preferences.

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
