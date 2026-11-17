# Password and email verification — 18 November 2026

The owner's latest policy replaces authenticator enrolment for ordinary accounts with mandatory password + email OTP. Gmail and business email addresses are accepted. Super Admin retains authenticator MFA, one-time recovery codes and the existing platform-only access boundary.

## What changes

- Lodge Admin, Group Admin, staff and guests enter their SafariOS password, then a code sent to their registered email. Neither an existing authenticator code nor a recovery code replaces that email step.
- A successful password returns HTTP 202 with a pending challenge. No new session or lodge access is created until the code is verified. A previously signed-in identity is rotated only after successful completion.
- First activation still uses an expiring, one-time email link to prove email ownership while choosing a password. Subsequent sign-ins use email codes. Password recovery revokes old sessions and requires normal sign-in afterwards.
- Super Admin continues to use a password and authenticator/recovery code. Email codes are never issued for platform sign-in. Super Admin can configure email delivery without depending on the new factor. Platform MFA cannot be disabled.
- Ordinary account security shows the registered email and mandatory verification policy. Optional authenticator prompts/enrolment/disable controls are removed for those accounts.

## Gmail or business SMTP setup

Edit the existing, ignored `infra/.env`; keep the database passwords and existing encryption keys. For Gmail / Google Workspace:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
```

Enable Google's two-step verification on the sender account and create a Google App Password. Use that App Password, not the normal Gmail password. Workspace administrators may require an approved SMTP relay instead. Other business providers use their own SMTP host/credentials; port 465 normally requires `SMTP_USE_SSL=true` and `SMTP_USE_TLS=false`. Production requires encrypted transport. Sender authentication does not grant SafariOS access to users' email inboxes.

Preserve an existing `EMAIL_ENCRYPTION_KEY`. If blank, the existing `MFA_ENCRYPTION_KEY` remains the supported fallback for the encrypted outbox and email-code derivation. API and worker must have matching keys. Do not introduce a different email key over pending encrypted messages without a planned rotation; never regenerate the platform MFA key during an update.

From the project root:

```sh
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

The existing migration/grants services apply `0028_email_sign_in`. Keep `worker` and `beat` running: sign-in messages use the encrypted transactional outbox. Use the Super Admin email delivery screen to test your own configured sender. Real SMTP credentials and live Gmail delivery have not been provided or exercised by this change. If email is unavailable, normal-account sign-in waits for working delivery; it never accepts a password alone or returns a debug code.

## Existing accounts and rollback

The migration revokes existing non-Super-Admin sessions and erases their obsolete authenticator secrets/recovery hashes. They must sign in again using email. Existing Super Admin enrolments, recovery hashes and sessions are preserved. Lodge/group memberships, permissions, subscriptions, guest grants, RLS and immutable audit/history are retained.

Back up before upgrading. Schema downgrade cannot reconstruct erased authenticator secrets or revive revoked sessions. A deliberate rollback to the former policy requires the matching pre-upgrade database backup and application version, followed by the existing recovery checks. The isolated migration regression tests upgrade from 0027, verify both account classes, downgrade and re-upgrade; they do not operate on customer data.

## Security and delivery

- Codes contain six cryptographically random digits, expire after five minutes, and are single-use. Five wrong-code attempts exhaust a challenge; account lockout and password/IP limiting also remain active.
- A new email has a 60-second cooldown and a ten-per-account hourly cap. Issuance/consumption serialise on the account row. Resending replaces older pending proofs in that browser; concurrent resends cannot issue duplicate codes.
- The challenge is bound to its account, guest/staff realm, credential fingerprint and a separate HttpOnly, SameSite Strict browser cookie. Verification also requires the password again. Changing the password/email, deactivating access or switching realms cannot reuse a stale proof.
- Only keyed, domain-separated HMAC code digests and hashed challenge/browser tokens are stored in the challenge table. The mail payload is encrypted. Codes/passwords are not returned by the API, placed in URLs or browser storage, or written to audit events. Successful verification erases the pending code/delivery payload.
- The worker rechecks code expiry, account access and credential state before sending; expired or withdrawn jobs are cancelled. Bounded cleanup erases expired proofs and removes challenge metadata older than 24 hours while preserving the rate window. Authentication mail ignores optional notification-email opt-outs.
- The new challenge table forces RLS. Existing outbox policies remain unchanged; verified authentication uses a bounded internal transport writer. An own-account, fixed-action INSERT policy records successful email verification without relaxing immutable audit protections.
- Disaster recovery invalidates pending email challenges and clears held account-email payloads. Restoring a backup cannot replay an old sign-in code.
- Guest invitation delivery now checks the guest's active invitation/stay grant rather than incorrectly requiring staff membership. Guests still never receive a staff/group/platform membership.

## Validation and remaining acceptance

API integration checks use real PostgreSQL/RLS and Redis. Existing workflow fixtures drive both real sign-in steps by reading only synthetic encrypted test mail; dedicated authentication tests inspect the raw 202/200/401 flow with no automatic completion. Coverage includes expiry, replay, browser/realm/account isolation, attempt and resend limits, concurrent verification/resends, credential/access changes, notification opt-out, SMTP configuration failure, worker expiry/delivery, restore invalidation and guest invitation delivery. Super Admin authenticator and recovery-code regressions are retained.

Browser checks exercise staff/guest email verification, no premature authenticated lookup/navigation, invalid-code feedback, resend/expiry, private in-memory state, account reset, ordinary security settings and the retained Super Admin QR/recovery flows. Layout/automated accessibility checks cover 375/768/1366/1440 px and both themes. The production build and full API/browser suites run before publication.

Live Gmail/business SMTP delivery and latency still need acceptance using your sender configuration. This authentication phase does not complete the wider application feature/integration register or establish commercial production readiness by itself.
