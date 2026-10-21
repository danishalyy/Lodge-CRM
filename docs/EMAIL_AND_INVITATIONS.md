# Gmail, invitations and notifications

SafariOS accepts Gmail and business email addresses. These are individual application accounts: the recipient chooses a separate SafariOS password. Connecting the sender does not give SafariOS access to anyone’s Gmail inbox.

## Configure the sender

Edit your existing, ignored `infra/.env` on the machine running Docker. For Gmail or Google Workspace:

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-sender@gmail.com
SMTP_PASSWORD=your-google-app-password
SMTP_FROM_EMAIL=your-sender@gmail.com
SMTP_USE_TLS=true
SMTP_USE_SSL=false
PUBLIC_WEB_URL=http://localhost:3000
```

Enable Google two-step verification for the sender and create a Google **App Password**. Use that password above, not the normal Google password. A Workspace administrator may restrict App Passwords; in that case use an approved Workspace SMTP relay or another business SMTP service. The sender must be the authenticated address or an approved sender alias. Never commit `.env` or share passwords in chat.

For business email, use the provider’s SMTP host, port, username and password. Port 587 normally uses STARTTLS. For implicit TLS on port 465, set `SMTP_USE_SSL=true` and `SMTP_USE_TLS=false`. Only one transport mode may be enabled. Set `PUBLIC_WEB_URL` to the address recipients can actually open; `localhost` only works on the same computer. Use your HTTPS domain for a real deployment.

The encrypted email outbox uses `EMAIL_ENCRYPTION_KEY`, falling back to `MFA_ENCRYPTION_KEY`. Retain existing keys. API and worker must receive the same key. Do not regenerate an existing MFA key. For a new installation, follow the Fernet key generation step in [local setup](../LOCAL_SETUP.md).

From the project root, apply the migration and updated environment:

```sh
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

Keep both `worker` and `beat` running. Migration and database grants must finish successfully. In **Super Admin → Settings → Email delivery**, send a test to your own account and check its status. Credentials cannot be read or changed through the browser. Gmail quotas and spam filtering apply; “sent” records SMTP acceptance, not proof of inbox delivery. A dedicated business sender is preferable as customer volume grows.

## Create accounts

- **First Super Admin:** run `docker compose --env-file infra/.env -f infra/docker-compose.yml exec api python -m app.bootstrap_superadmin`. Enter the owner’s email and name. A setup invitation is queued; the owner sets the password and then enrolls in MFA.
- **Other Super Admins:** use **Super Admin → Platform Users → Invite Super Admin**. These accounts have platform-wide access and must enroll in MFA before managing the platform.
- **Group Admin:** use **Super Admin → Lodge groups → Create group**, then assign the lodges. The owner receives a password-setup invitation and signs in to their group overview. See [group setup and access controls](LODGE_GROUPS_AND_FEEDBACK.md).
- **Lodge Admin:** register the lodge using a separate Lodge Admin email. Registration creates an inactive account and queues its setup invitation.
- **Managers and staff:** use **Staff → Staff member**, choose **Invite to SafariOS**, and select the permitted role. Existing staff profiles without a login can also be invited. Department Managers must belong to a department.

No administrator enters or receives another owner’s password. New accounts cannot sign in until activated. Invitations expire after 72 hours by default. Resending invalidates older links and preserves the assigned role; requests have a 60-second cooldown. Pending/expired accounts and mail status appear in Staff, Platform Users and lodge administration. A link can be used once. Deactivated memberships or former employees cannot activate accounts.

Only in `APP_ENV=development`, with no SMTP sender configured, the creator receives a private development link instead. The bootstrap command prints that link locally. Share it only with the intended owner. Once SMTP is configured, links are sent by email and are not returned to the creator. Production requires configured email and encryption. Invitation and recovery links use URL fragments and are removed from the address bar by the setup screen.

## Notifications and recovery

The bell shows your unread count. Open Notifications to filter by priority, mark messages read, archive messages, and choose the minimum priority for operational emails. Invitations and password recovery remain transactional and are unaffected by operational email preferences. Operational email requires a verified address: activation verifies a new account; existing owners can verify through the password recovery flow.

Notifications are addressed to individual accounts and restricted by current lodge membership, role, department and assignment where applicable. Tasks generate assignment/overdue alerts; overdue tasks escalate after 60 minutes by default. Critical maintenance, service dates, room readiness, credentials and subscription expiry have scheduled alerts. This is the built-in rule set; a configurable rules editor and browser push notifications are not included.

Account emails and notification deliveries are stored durably and retried after temporary failures. Workers reclaim expired sending leases after a restart. Delivery retries use exponential backoff and stop after eight attempts. Super Admin Settings shows account email failures and retry controls; expired invitations require a fresh invitation. Setup links are encrypted in queued payloads and removed after acceptance or cancellation. SMTP cannot guarantee exactly-once delivery if a worker dies immediately after the provider accepts a message; repeated mail still points to the same single-use link.

Defaults: `INVITATION_TTL_HOURS=72`, `INVITATION_RESEND_COOLDOWN_SECONDS=60`, `NOTIFICATION_ESCALATION_MINUTES=60`. Password recovery expires after `PASSWORD_RESET_TTL_MINUTES` (30 by default) and revokes existing sessions after a successful reset. It does not disable MFA.

## Implementation validation

The change was checked with a real PostgreSQL migration/RLS suite, mocked SMTP transport and retry tests, a production frontend build, and Chromium account/invitation/notification interactions. SMTP tests do not send real mail. Real Gmail acceptance still needs the configured sender test described above.

[Password setup preview](screenshots/safarios-invitation-light.png) · [Notification inbox preview](screenshots/safarios-notifications-light.png) · [Mobile dark preview](screenshots/safarios-notifications-mobile-dark.png)
