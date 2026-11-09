# Guest CRM document checkpoint

The source is workflow §9.1 (guest profile data), operating-system guest CRM scope and package §3.2. This checkpoint extends the existing forms and endpoints; it does not replace the guest/stay module or certify the complete commercial journey.

## Delivered

- Optional birthday and anniversary, an explicit repeat-guest flag for visits predating SafariOS, and dedicated safari preferences. Recorded completed stays remain a separate derived count. Dates can be cleared; an omitted patch preserves the existing date. Future/invalid dates and oversized preferences are rejected inline.
- Tenant-scoped communication history with channel, direction, subject, notes, occurrence/recording times, pagination and a client reference. Repeating the same submission returns the same record; reusing its reference with different contents is refused. This records prior interactions and does not send an email or WhatsApp message.
- New reads require `guests.view` and the guest feature; new writes require `guests.manage`, CSRF, the guest feature and writable subscription. Composite guest/lodge foreign keys and FORCE RLS protect the new table. Existing support access remains audited. There are no interaction edit/delete endpoints or model tools for reading its contents.
- Guest privacy exports include the new fields and communication log. Anonymisation clears those fields and the log's subject/notes, retaining only redacted history metadata. Row locks serialize logging against anonymisation. Newly anonymised profiles cannot receive fresh personal details. This does not claim a complete application-wide POPIA retention process or erase personal information embedded in legacy linked records.
- Shared form fields, drawers, inline validation, precise success feedback and both themes. Save/log submissions capture their original account/lodge; access changes clear stale content and late results are discarded. A long mobile sheet no longer allows Vaul's overscroll extension to paint over later fields/history.

## Migration and validation

Back up first, upgrade through `0023_guest_profiles`, and run the existing app-role grants step before recreating the API/web services. Use the privileged migration administrator for schema changes and retain the least-privilege application role. No customer volumes need to be deleted. Downgrade deletes communication rows/new fields; export/back up those data first. The upgrade/downgrade/re-upgrade rehearsal used a disposable database and preserved an existing guest's original fields.

725 API tests pass, including 19 new guest-profile/log cases. The production frontend build passes. All 44 browser checks pass, including guest creation/editing, interaction logging, read-only controls, inline validation, permission-loss clearing, account/lodge change clearing and preserving a form when another tab changes theme. Both themes pass layout and automated WCAG A/AA checks at 375/768/1366/1440 px, including long drawers. Static guard audit, Compose configuration and diff checks pass. Scripted browser fixtures do not represent customer data, real external-message delivery or comprehensive accessibility certification.

## Still required

A unified, permission-aware timeline of stays, activities, requests, complaints and feedback; the complete connected front-office/kitchen/driver/housekeeping acceptance journey; task assignment/history relationships; the restricted guest web/QR portal; and actual selected external-message adapters. See [the current source map](REQUIREMENTS_DELIVERY.md). Guest CRM remains **partial** until that work and acceptance are finished.

The next task-history checkpoint must cover all three existing creation paths: direct creation, recurrence and guest-request conversion. Record actual assignment time and preserve reassignment/status history; do not invent timestamps for legacy rows. Add tenant-validated vehicle/maintenance links and retain the same scope/proof/checklist and confirmation behavior. These changes are not part of this guest-profile checkpoint.

Review artifacts: [desktop history](screenshots/safarios-guest-profile-desktop-dark.png), [mobile history](screenshots/safarios-guest-profile-mobile-light.png).
