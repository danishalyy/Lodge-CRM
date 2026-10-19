# Lodge CRM UI / UX Design System — v1.7

## Direction
Premium, restrained and operational. The product should feel like high-end hospitality software rather than a generic AI dashboard.

## Colour system
Dark default:
- Background: `#181918`
- Sidebar: `#141514`
- Card: `#222421`
- Secondary surface: `#292B28`
- Border: `#373A35`
- Primary text: `#F3F3EF`
- Secondary text: `#B2B4AC`
- Muted text: `#777B73`
- Primary accent: `#8D9874` (sage/olive)
- Secondary accent: `#AAB58F`
- Warning: `#C29B5F`
- Critical: `#C36F63`
- Supporting teal: `#6E9790`

No glossy gradients are used.

## Interaction language
- Short transform/opacity transitions for hover, drawers and command surfaces.
- No excessive bouncing or decorative motion.
- Important operational states are always communicated through text as well as colour.
- `prefers-reduced-motion` disables nonessential animation.
- Cards lift by 1–2px at most.
- Buttons use subtle press feedback.

## Information hierarchy
- Command Centre prioritises current lodge condition, attention, calendar and operational memory.
- Tables remain the detailed source of truth for operational records.
- Charts are summaries only and derive exclusively from real persisted records.
- Calendar combines authorised arrivals, departures and activities; inaccessible sources are omitted rather than simulated.

## Responsive behaviour
- Desktop: fixed 248px navigation and multi-column operational workspace.
- Tablet/mobile: off-canvas navigation, simplified chart/calendar density and full-width content.
- Command palette remains keyboard accessible through Cmd/Ctrl + K.

## Components
- Premium metric cards
- Status pills
- Operational bar chart
- Completion ring chart
- Monthly operations calendar
- Command palette
- Sticky top bar
- Animated drawer
- Filter panel
- Responsive data tables
- Empty/error/loading states

## Product rule
UI may visualise only real application data. Missing data must render as empty state, zero, unavailable, or permission-limited — never as sample or simulated lodge operations.
