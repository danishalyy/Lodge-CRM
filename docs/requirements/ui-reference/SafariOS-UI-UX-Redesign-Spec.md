# SafariOS UI/UX Redesign Spec

*For Codex. Visual UI/UX only: no changes to API, permissions, entitlements, MFA, tenant isolation or data logic. Visual reference: the "SafariOS — Premium UI Redesign" canvas (Command Centre, Sign in, Ranger mobile).*

## 0. What changes and why

The current app is competent but flat: every screen is a grid of identical dark cards on `#363636`, navigation is a long 25-item list, and gold is used as decoration. The redesign keeps all features and routes and does four things:

1. **Re-bases the palette on the new logo** (cooler near-black ink, warm ivory, matte gold), replacing the `#363636` charcoal.
2. **Gives every screen one clear job-first hierarchy**: a greeting and primary action, then what needs attention, then detail.
3. **Collapses navigation to what each role actually uses** (Section 3).
4. **Makes the safari-specific parts feel native**: a ranger/offline mobile experience, a vehicle map, and wildlife views.

**Update `apps/web/AGENTS.md`, `design-system/safarios/MASTER.md` and `docs/UI_UX_DESIGN_SYSTEM.md` to match this spec**, since they currently mandate `#363636`/`#171717`. This spec supersedes them.

## 1. Design tokens (from the logo)

Sampled from the supplied logo file.

| Token | Dark (default) | Light | Use |
| --- | --- | --- | --- |
| `--bg` canvas | `#17181C` | `#F6F3EC` | Page background, flat, no gradient |
| `--bg-nav` | `#121317` | `#EFEBE2` | Sidebar, login brand panel, mobile tab bar |
| `--surface` | `#1E2026` | `#FFFFFF` | Cards, tables, drawers |
| `--surface-2` | `#25272E` | `#F1EDE3` | Inputs on cards, hover rows, nested blocks |
| `--line` | `rgba(240,236,226,.09)` | `rgba(23,24,28,.10)` | All borders and dividers |
| `--text` | `#F0ECE2` | `#1C1D21` | Primary text (logo ivory) |
| `--text-2` | `#A8A59B` | `#5B5A55` | Secondary, labels |
| `--gold` | `#C4A067` | `#C4A067` | Primary actions, active state, key figures |
| `--gold-hover` | `#D2B27A` | `#B38E54` | Hover |
| `--gold-text` | `#D8BB86` | `#7A5C2C` | Gold text on small sizes (contrast-safe) |
| `--gold-wash` | `rgba(196,160,103,.12)` | `rgba(196,160,103,.16)` | Active nav, selected rows, chips |
| `--on-gold` | `#17181C` | `#17181C` | Text on gold buttons |
| `--ok` | `#A3B899` | `#43603A` | Success |
| `--warn` | `#D9B26F` | `#7A5A1E` | Warning |
| `--danger` | `#E0968A` | `#9B463D` | Danger/overdue |
| `--info` | `#9DB4B0` | `#3E625B` | Info |

Rules:

- **Gold means "act here" or "this is the headline".** One gold primary button per view. Gold figures only for the single most important number (e.g. Overdue). Never gold body text, never gold gradients, glows or metallic effects.
- Status always pairs colour with an icon or word (never colour alone).
- All text must meet 4.5:1 (check `--text-2` and `--gold-text` in both themes).
- Remove the old compatibility aliases (`--color-beige`, `--color-orange`, `--color-olive`, etc.) once pages no longer use them.

## 2. Typography, shape, motion

- **Headings and key numbers: Outfit 500** (geometric, close to the wordmark). **Body/UI: Inter 400/500/600.** Bundle both locally (self-host, as Inter already is).
- Scale: page title 34px/-0.02em (mobile 28px); card title 18px; section label 11px, uppercase, 0.14em tracking, `--text-2`; body 14px; table 13px; **key figures 44px Outfit** with tabular numbers (mobile 36px).
- Radii: cards 20px, inputs and buttons 12px, dialogs and drawers 28px, chips 99px, avatars round. Inputs 48px high, buttons 44px (56px for primary field actions on mobile).
- Depth: 1px `--line` borders plus one soft shadow on overlays only. No card lift on hover; hover is a `--surface-2` background change.
- Glass blur only on overlays (command palette, drawers, dialogs) with a solid fallback.
- Motion: 150-200ms ease-out for state changes, 250ms spring for drawers/dialogs. Honour `prefers-reduced-motion`. Never animate tables.
- Focus ring: 2px `--gold` with 2px offset, on every interactive element.

## 3. Shell and navigation

### 3.1 Desktop shell

- Sidebar 260px, `--bg-nav`, 1px right border. Collapsible to a 72px icon rail (persist choice).
- Top: logo (mark + "Safari**OS**" with OS in gold), then a **lodge switcher card** (lodge logo, name, role, package badge). For group admins this becomes a dropdown listing lodges with a "Group overview" entry first.
- Bottom: **Ask Lodge AI** pinned as a distinct gold-outlined item, then the user chip (avatar, name, role) with a menu: Account security, Theme, Sign out. Remove the separate Sign out and theme buttons from the top bar.
- Top bar (64px, no border, transparent): global search field (opens the existing command palette, `Cmd/Ctrl+K`), notification bell with count, subscription status chip only when Expiring Soon/Expired.
- Active nav item: `--gold-wash` background, 3px gold inset bar on the left, ivory text. Counts are small right-aligned figures in `--text-2`.
- **Locked (package-gated) items** stay visible with a lock icon, dimmed, and open the existing access-review screen. Items the role cannot see stay hidden. A nav link never grants access.

### 3.2 Navigation grouping (reduces 25 flat items to 6 groups)

Keep every route. Only group labels and order change; show a group only if at least one item is permitted.

| Group | Items |
| --- | --- |
| **Today** | Command Centre, Arrivals & Departures (filtered view of Stays), Tasks, Notifications |
| **Guests** | Guest CRM, Stays, Rooms & Units, Guest Requests, Guest Feedback |
| **Operations** | Housekeeping, Maintenance, Food & Beverage, Transfers, Activities |
| **Safari & Fleet** | Ranger View, Wildlife, Fleet, Fuel (and Live Map when Premium telemetry exists) |
| **People** | Staff, Staff HR, Departments, Roles & Permissions |
| **Insight** | Reports, Operational Memory, Knowledge Library |

Groups are collapsible; collapsed state persists. The group containing the active route is always open. Super Admin sees a separate **Platform** group at the very top, visually divided, so platform and lodge contexts are never confused.

### 3.3 Role-adaptive home

The Command Centre (`/dashboard`) must change with the role, using the existing permission set:

- **Lodge Admin / GM / Group Admin:** full Command Centre (Section 4.1).
- **Department Manager:** same layout scoped to their department; KPIs become team tasks, team on shift, pending approvals.
- **Front Office:** arrivals/departures timeline first, then requests.
- **Ranger, Driver, Housekeeping, Maintenance, F&B, Basic Staff:** a **"My day"** screen (Section 6): their own assignments only, big touch targets, no analytics. Redirect these roles to it after login.
- **Read-only/Auditor:** Command Centre with all create actions removed.

### 3.4 Mobile shell

- Bottom tab bar (84px with safe area) with at most 4 tabs plus "More". Tabs per role: Day, Tasks, Sightings/Requests, Alerts. "More" opens the shared Vaul drawer with the full grouped navigation.
- Header: page title and a single status chip (Online / Offline · N queued).
- Single column, 20px page padding, 16px gaps, 44px minimum targets.

## 4. Screen designs

### 4.1 Command Centre (see canvas)

1. **Greeting band:** date label, "Good morning, {first name}" (name in gold), primary gold button "+ New task".
2. **Four KPI cards:** In-house, Arrivals, Open tasks, Overdue. The Overdue card gets a gold border and gold figure when above zero; otherwise neutral. Each card links to its filtered list. Unavailable values show "-" with a small "Unavailable" caption, never 0.
3. **Two columns:** left **"Today's run of the lodge"**, a chronological timeline (time in gold, then event; arrivals, departures, game drives, transfers) replacing the bar chart and the month calendar. Right **"Needs your attention"**, a prioritised list (room awaiting inspection before an arrival, overdue maintenance, unconfirmed allergy notes, expiring licences), each row clickable to its record.
4. **Below the fold:** task health ring, operational memory feed, month calendar (collapsed by default), subscription details (only shown to Admin, small).
5. Replace the "Operational pulse" bar chart. It tells staff nothing actionable. Use real data only.

### 4.2 Sign in and account pages

- Desktop split: left brand panel (`--bg-nav`) with logo, headline "Every guest, vehicle and task. One calm view.", one supporting line, and a faint gold line illustration of the savannah horizon with acacia at the bottom. Right: a 420px form card, radius 28px. Keep labels connected to fields, show/hide password, inline errors.
- Mobile: brand panel collapses to a 120px header; form fills the screen.
- The same card pattern applies to activate, forgot password, reset password and the MFA prompt. MFA code entry uses six separated digit boxes with auto-advance and paste support.
- Subscription-suspended and pending states use a centred state card with a quiet lock icon and one clear next step (not red alarm styling).

### 4.3 List pages (Guests, Stays, Staff, Requests, Feedback, Tasks, Maintenance, Transfers, Fuel, Fleet, Rooms, Departments, Roles, HR)

One shared pattern, built once in `components/ui` and reused:

- **Header row:** page title, one-line description, primary gold action on the right.
- **Toolbar row:** search, filter chips (status, department, date), view switcher (List / Board where meaningful), saved view dropdown. Active filters show as removable gold-wash chips.
- **Table:** `TableScroll`, 56px rows, sticky header, status as a chip with icon, avatar + name in the first column, row hover `--surface-2`, a trailing "…" menu. Clicking a row opens the **detail drawer** (right-side, 520px; bottom sheet on mobile) rather than navigating away.
- **Bulk bar:** appears on selection.
- **Empty state:** icon, one sentence on what belongs here, and the primary action. **Loading:** row skeletons. **Error:** inline retry card.

### 4.4 Module-specific layouts

- **Guests:** two-pane. List on the left, **guest profile** on the right: header with name, nationality flag, VIP/repeat chips; tabs Overview, Stays, Preferences & Dietary, Requests, Feedback, Notes. Dietary/allergy items render as high-visibility chips with an icon on every screen where the guest appears.
- **Stays / Arrivals & Departures:** day timeline grouped Arrivals / In-house / Departures, with unit, party size, transfer status and readiness chips on each card; date strip at the top.
- **Rooms & Units:** a **status board**: unit cards grouped by Available, Occupied, Cleaning, Awaiting inspection, Maintenance, Out of service. Tapping a unit opens a drawer with the current stay, housekeeping job and open tickets.
- **Guest Requests:** three-column board (New, In progress, Done) with department tag and a "Assign to" quick action; list view available.
- **Tasks:** My tasks / All tasks / Overdue tabs, Board view by status, Calendar view. Detail drawer: title, status stepper, assignee, due, priority, checklist with progress bar (completion blocked until required items are done), attachments grid, comment thread, and the existing history panel as a timeline. Basic Staff see only their own tasks, as today.
- **Housekeeping:** room-by-room cards in a Cleaning, Inspection, Ready flow; each card shows linen/turndown needs and a single large action (Start, Mark clean, Inspect, Ready). Inspector flow has a checklist and pass/fail with photo.
- **Maintenance:** board by status with priority colouring, asset and vehicle link, cost and downtime fields in the drawer, service history tab on the asset.
- **Food & Beverage:** today's meal service as a timeline (Breakfast, Lunch, Dinner, Special), with **allergy/dietary summary chips at the top** and guest counts per meal.
- **Transfers:** time-ordered cards with flight number, pickup, driver, vehicle, status stepper (Scheduled, En route, Collected, Dropped).
- **Activities:** day schedule grid with guide and vehicle lanes; conflict highlighting.
- **Fleet & Fuel:** vehicle cards (status chip, odometer, next service, licence/insurance expiry bars) with a detail drawer; Fuel as a table plus a small consumption trend per vehicle; anomalies flagged with a warn chip. **Premium:** a Live Map page with vehicle markers, last-seen time, geofence outlines, device-health list and trip playback scrubber.
- **Wildlife:** a gallery-first view (photo cards with species, time, location, recorder) with a map toggle; "Record sighting" is the primary action (camera + GPS + species picker). Premium analytics adds species frequency and heat map tabs.
- **Ranger View:** the "My safari day" screen, see Section 6.
- **Staff / HR / Departments / Roles:** Staff as a directory (cards or table toggle). HR as tabs (Leave, Certificates and training with expiry chips, Roster, Incidents, Performance). Roles page uses a **permission matrix** with modules as rows and View/Create/Edit/Approve/Manage as columns of toggles; plus a role-preview showing what the role's sidebar will look like.
- **Reports:** KPI strip, then sections as cards, each with a chart and "Export". Use only gold plus ivory tints and the four status colours in charts.
- **Notifications:** grouped Today / Earlier, unread dot, one-tap mark read, filter by type.
- **Operational Memory:** vertical timeline feed with actor, module and time.
- **Account Security:** sections for Password, Authenticator (QR), Recovery codes, Email delivery, Lodge display preferences; each as a separate card with its own save.

### 4.5 Lodge AI

- Welcome state: assistant greeting, four suggestion chips drawn from authorised capabilities. Chat: narrow 720px column, questions right-aligned on `--surface-2`, answers left on transparent background with a gold sparkle avatar, sources as collapsed "N sources" chips.
- Composer pinned at the bottom with a subtle `--surface` card. History in a collapsible left rail (drawer on mobile).
- **Action proposals** (AI-suggested actions) render as a distinct card with gold border, a plain-language summary, and Approve / Dismiss buttons; the approved state shows a success chip. Reports library: cards per daily/weekly report with generated date and a Read action.
- Do not add voice, attachments, stop buttons or token streaming. Preserve the existing rules in `docs/UI_UX_DESIGN_SYSTEM.md`.
- Knowledge Library: document table with processing status chips (Processing, Ready, Failed + retry) and an upload dropzone.

### 4.6 Super Admin (Platform)

- Uses the same shell with a **"Platform" badge in gold** next to the logo so it can never be mistaken for a lodge view.
- **Overview:** counts for lodges by subscription state (Active, Expiring Soon, Expired, Suspended) and an **Expiring soon list** (lodge, package, days left, Extend button).
- **Lodges:** card or table toggle. The "Register lodge" drawer is a 3-step stepper: Property identity, Subscription (package, start, expiry), Lodge Administrator invite; the activation link is shown with Copy.
- **Subscriptions:** table with status chips and an inline "Extend" date picker dialog.
- **Packages:** side-by-side Basic / Standard / Premium columns, features as rows, with checkmarks and "Advanced" labels exactly as the package guide; editable toggles for Super Admin.
- **Groups, Users, Audit, Notifications, Settings:** standard list pattern; Audit has actor/action/target/time filters.
- Every cross-lodge action shows a confirmation naming the lodge, and a persistent "Acting in {lodge}" banner appears while Super Admin is inside a lodge.

### 4.7 Group Admin (`/group`)

Hero: group name and lodge count. Grid of lodge cards (logo, name, subscription chip, 3 mini KPIs, "Open" button). Cross-property comparison table below. Invite Lodge Admin opens a drawer.

## 5. Shared component checklist (build once in `components/ui`)

`AppShell`/`SuperAdminShell` (new grouping), `PageHeader`, `KpiCard`, `StatusChip`, `FilterBar`, `DataTable` (TableScroll), `DetailDrawer`, `StatusBoard` (columns), `Timeline`, `EmptyState`, `ErrorRetry`, `Skeletons`, `PermissionMatrix`, `Stepper`, `CodeInput` (OTP), `LockedFeatureCard`, `OfflineBanner`/`SyncChip`, `DietaryChips`. Keep Radix dialogs (desktop), Vaul (mobile), cmdk, Sonner, Recharts, TanStack Table. Charts: gold primary series, ivory-tint secondary, no rainbow.

## 6. Field experience (mobile, offline-first)

Build these as a **role-driven "My day"** using the existing Ranger/tasks/transfers data:

- Header with role, lodge, and a **sync chip**: Online, Offline with N queued, Syncing, Sync failed with Retry.
- A single **Next up** card in gold outline with a full-width action (e.g. "Start pre-drive checklist"). Below it: guest notes (dietary first), then the rest of the day as a list.
- **Record sighting** as a persistent 56px button: opens camera, auto-captures GPS and time, species search, notes; saves locally and shows "Waiting to sync" on the card until upload completes.
- Driver: transfers as cards with Call guest, Open maps, and status stepper buttons. Housekeeping: room cards with Start/Done. Maintenance: ticket cards with photo and cost entry. F&B: today's meals and dietary alerts.
- Controls are at least 44px, bottom-reachable; avoid hover-only affordances. Respect safe areas.
- Offline records are visually distinct (dashed gold border plus "Queued" chip) and are re-authorised by the server on sync; show a clear message if rejected.

## 7. States and feedback (every data view)

Loading skeleton, empty (with action), error with Retry, success toast via the existing shared feedback (do not add duplicate toasts), destructive confirmation dialogs naming the record, inline validation under fields. Never show fabricated records or turn unavailable values into zero.

## 8. Accessibility

Visible focus on everything; labels connected to inputs; 4.5:1 text contrast in both themes; status never by colour alone; drawers trap focus and return it; keyboard operable boards (move card via menu, not only drag); reduced motion respected; table scroll regions are focusable only when they overflow. Support 375, 768, 1366 and 1440 widths in dark and light.

## 9. Implementation order for Codex

1. **Tokens:** rewrite `reference-theme.css` and `design-system.css` with Section 1-2 values, expose in `tailwind.config.ts`, bundle Outfit, update `SafariBrand` and `public/branding/safarios-mark.svg` to the new logo (circle horizon, acacia, wordmark "Safari" ivory + "OS" gold; light theme uses `--gold-text`). Update `AGENTS.md`, `MASTER.md` and design doc.
2. **Shell:** new sidebar grouping, lodge switcher, user menu, top bar, mobile tab bar, role-based redirect to "My day".
3. **Shared components** from Section 5, then the **List page pattern**, migrating pages in this order: Tasks, Guests, Stays, Requests, Rooms, Housekeeping, Maintenance, then the rest.
4. **Command Centre** and **Sign in** pages.
5. **Field screens** (Ranger, Wildlife, Transfers, mobile tabs, sync chip).
6. **Lodge AI, Reports, Roles matrix, Super Admin, Group.**
7. Screenshot review at the four widths in both themes; run existing contract/e2e tests; confirm no permission, entitlement or API behaviour changed.

## 10. Do not

Change routes, permission keys, entitlement keys or API calls. Add orange, purple, gradients, glows or emoji. Replace a lodge's own logo. Show controls for unavailable subfeatures. Seed demo data into the real app (the canvas data is illustrative only).
