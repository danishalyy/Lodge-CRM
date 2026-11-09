# SafariOS accepted design master

Owner-approved direction: premium minimalist operational software. This master synthesizes the installed UI/UX Pro Max Minimalism & Swiss guidance with the actual SafariOS reference. User decisions take precedence over generated search recommendations.

## Palette and identity

Dark canvas #363636; navigation #171717; warm ivory #F2EEE7; matte gold #C6A568. Light canvas #F5F3EF, navigation #EEEBE5, text #29251E. Gold-filled buttons use #201C15 text. Small reading accents use #DFC899 dark / #70532D light; the light wordmark uses #846437. Use semantic status colours from reference-theme.css. No purple, colourful mesh, metallic gradient or decorative glow.

Use SafariBrand’s acacia/savannah SVG adaptation of the owner-provided logo. Preserve authorized lodge logos alongside SafariOS. Never imply the hand-coded adaptation is the supplied original vector artwork.

## Hierarchy and material

Locally bundled Inter 400/500/600. Titles 30px desktop / 26px mobile, card headings 16px, body 14px, key numbers 36px with tabular figures. Quiet spacing and readable density, rather than marketing-page hero sections. Cards 24px radius/padding, dialogs 28px radius, buttons/inputs 12px radius. Section spacing 32px and card gaps 24px; mobile gaps 16px. Shared controls provide 44px targets where applicable.

Glass uses neutral translucent fills, blur(32px) saturate(115%), restrained borders/shadows, a Safari prefix and solid fallback. Text remains sharp. Respect reduced motion. Do not animate tables or create decorative card lift.

## Interaction and future components

Reuse components/ui and existing guarded shells. Use TableScroll for wide tables, connected field labels, visible focus, inline error messages and real success feedback. Dialogs/drawers retain focus management and mobile behavior. Every data view needs loading, empty and recoverable error states. Preserve RLS, permissions, MFA, audit and subscription checks. Never fabricate operational figures or show unavailable values as zero. Keep new strings in lib/strings.

Validate responsive layouts at 375, 768, 1366 and 1440px, both themes; check keyboard scrolling, dialog flow and accessible contrast. Automated fixture checks supplement manual review and do not certify all accessibility or live integrations.

## Source and scope

Skill: nextlevelbuilder/ui-ux-pro-max-skill, commit 4f2dbb67e64969a9a30ab00742f2d55d66ddec2b, MIT; installed in .agents/skills/ui-ux-pro-max. Reviewed Minimalism & Swiss, enterprise dashboard, focus visibility, chip labels and responsive grid guidance. Generic blue/orange palettes, restaurant typography, marketing testimonials and framework upgrade suggestions were rejected as inappropriate for this existing application.

Implementation: apps/web/app/reference-theme.css, app/design-system.css, tailwind.config.ts and shared components. Detailed specification: docs/UI_UX_DESIGN_SYSTEM.md.
