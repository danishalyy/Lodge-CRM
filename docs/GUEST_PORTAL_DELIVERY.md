# Guest web/QR and guest assistant — 17 November 2026

This phase implements the guest-facing web experience required by workflow §§4.13 and 20.2. It does not declare all 63 package requirements commercially accepted. Native apps remain deferred; guest wildlife capture, live delivery/model acceptance and the other gaps in [the requirements register](REQUIREMENTS_DELIVERY.md) remain open.

## Using it

1. Apply migration `0027_guest_portal` and refresh the application database grants through the existing Compose migration/grants services. Preserve the database volumes and encryption keys. Back up a production database before upgrading; downgrade deletes the new guest portal data.
2. As a separate Lodge Admin, Group Admin in an explicitly assigned lodge, or authorised Front Office account, open **Guests → guest profile → Guest portal**. The account needs `guest_portal.manage`, the guest portal feature and a current/upcoming stay. Add a valid email address to the profile first.
3. Choose the stay and invite the guest. Production queues the existing encrypted account-email outbox; the email owner follows the expiring, one-time setup link and chooses their own password. An already activated guest keeps their own password. Gmail and business addresses are accepted. Existing staff/platform identities cannot double as guest accounts.
4. **Show sign-in QR** opens `/guest?access=…`. This is a sign-in destination, never a password, activation token or bearer credential. The signed-in guest must actually own that stay. Revocation ends that grant without touching the guest's other authorised stays.
5. Use **Guests → Guest information** to add and publish lodge information, contacts, services, announcements or FAQs. Drafts are private. Published content is explicitly guest-facing; never place internal SOPs, staff instructions or sensitive operational notes there.
6. Guests see their own stay, assigned itinerary, published lodge information, own requests/status updates and their private assistant where enabled. Guest requests enter the existing staff workflow; status changes and linked task completion generate private guest updates.
7. Guest AI requires the `guest_ai` entitlement (Standard/Premium by default) and the existing configured model service. It uses only published guest information and that guest's itinerary, with no staff tools or internal document retrieval. An unavailable model displays an honest unavailable state. The existing local LM Studio/vLLM-compatible setup is reused; this phase does not provision a GPU or certify a live model.

In development without SMTP, the existing account workflow can return a private setup link for local testing. The UI names the action clearly and never exposes the raw `development_link` status. Production does not return that token. Real sender credentials, delivery and recovery emails still need operational acceptance.

## Confidentiality and encapsulation

- Guest accounts use the shared secure identity/session, invitation, reset and optional MFA/recovery mechanisms, plus a distinct guest login endpoint. They receive no staff, group or platform membership. A database trigger rejects internal assignments for guest identities.
- Staff/platform APIs reject guest identities. Guest APIs reject staff/platform identities. Super Admin remains platform-only; no impersonation or Open lodge path is introduced.
- Guest RLS leaves the staff tenant setting empty. Separate guest settings and explicit own-record policies constrain the authorised stay/profile, own activity/transfer links, published content, requests, notices and chat. Other operational tables remain denied. Existing tenant policies are retained.
- Guest DTOs whitelist their fields. Internal guest/stay/activity notes, staff assignments, request resolution notes, other guests and management history are excluded. The original guest-authored request description is stored separately from staff edits.
- Private chat/notices have owner/access RLS; staff and platform readers cannot inspect them. Platform account/email lists exclude guest identities, failed guest emails cannot be retried through the platform endpoint, and platform audit identity projections mask guest names/emails. The underlying audit evidence is preserved.
- Access is checked against the current account, matching guest email, anonymisation, stay dates/status, lodge status, subscription and feature controls. Checkout, cancellation, expiry of the stay or revocation ends access. Expired subscriptions preserve permitted reads and personal acknowledgements/chat erasure, while operational writes remain blocked.
- Browser scope assertions and in-memory state guards discard late account/stay responses. Private API responses and protected pages are not added to service-worker caches or persistent browser storage. The QR contains only a noncredential sign-in URL.

## Integrity and availability

- Guest request commands use stable client references, database uniqueness and transaction-scoped resource locks. Lost responses can be retried without duplicating the request; conflicting reuse returns a conflict.
- Audit, operational events and staff notifications remain transactional. Existing deferred invalidation triggers execute within the bounded internal writer context before guest scope is restored. Immutable audit/history protections remain intact.
- AI shares the existing bounded Redis admission, provider deadlines and context/output limits. It has no operational actions. Cookie/session, account, grant, stay, entitlement and source versions are rechecked after inference. Withdrawn or changed sources invalidate older answers.
- Clearing chat erases the content and leaves a private, empty version marker. Short transaction locks fence final answer persistence against erasure; an answer already in flight cannot recreate erased history. No database row/transaction lock is held across the model call.
- Guest password recovery revokes old sessions and returns to guest sign-in, retaining enrolled MFA. Existing staff recovery still returns to staff sign-in. Active-account invitation emails have a resend cooldown.
- Guest screens reuse SafariOS tokens, local fonts, labels/forms, password/OTP controls, notifications, confirmations, theme toggle and shared account security. Drawers retain focus management. Conversational views use bounded scroll, safe Markdown and no model-authored tracking images or active links.

## Verification

The phase runs the full API suite against real PostgreSQL/RLS and Redis, the production frontend build, static route guards and the browser regression suite. New integration cases cover identity realms, direct-route/SQL denial, guest/guest isolation, own itinerary projection, CSRF, idempotence, request/status notices, package/subscription states, checkout/revocation/profile changes, encrypted email cooldown, MFA/recovery, private source grounding, withdrawn authority/sources, chat erasure during inference and guest password recovery. Browser checks cover invitations/publishing/QR/revocation, guest login/MFA, requests/conversation, disabled-feature call avoidance, account changes and account security/recovery. The complete browser regression run passed 108 cases before the final recovery case was added; all nine final guest/recovery/draft-preservation cases passed against the rebuilt production frontend. The local full API checkpoint passed 962 cases, followed by all 39 guest integration cases on the final source (including the additional revocation-after-erasure regression).

Layouts are checked at 375, 768, 1366 and 1440 px in both themes, with screenshots and WCAG A/AA automated scans of the guest conversational view. New migration upgrade → downgrade to 0026 → re-upgrade and FORCE RLS checks pass in an isolated database. Browser HTTP fixtures prove UI behaviour; the real API tests prove the backend boundaries. Neither substitutes for real SMTP/model delivery, device testing or comprehensive accessibility certification. Exact final suite counts are available in GitHub Verify.

## Still required

- Guest safari/wildlife capture where separately enabled; it is not exposed through staff wildlife APIs.
- Real invitation/reset email delivery and live guest-model grounding, refusal, latency and concurrency acceptance for the launch lodge.
- Product/legal decisions for private chat retention and global guest identity erasure across independently administered lodges; profile anonymisation immediately denies that lodge's access, while identity/private-history retention remains a separate controlled lifecycle. Clearing an active stay's chat is already supported.
- The wider reporting, connected workflow, premium analytics/API, selected integrations and production acceptance items tracked in the original delivery register. No provider was selected, no customer service was purchased and no production deployment occurred in this phase.
