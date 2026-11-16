# SafariOS production operations

This runbook prepares a single-VPS installation; it is not evidence that a live deployment or commercial acceptance has occurred. Read [the release hardening checkpoint](RELEASE_HARDENING.md) and [the requirements register](REQUIREMENTS_DELIVERY.md) before launch. Keep database/media volumes and all encryption keys through upgrades. Never use `down -v` on an installation containing real records.

## First installation

Use a supported Linux host, Docker and Compose **2.24.4 or newer**, sufficient encrypted disk space, reliable off-server backups and an operator with restricted SSH access. Point separate application and media DNS names to the VPS. Allow public 80/443 and restrict administrative SSH. The production overlay publishes only Caddy; PostgreSQL, Redis, API and storage administration stay private. Configure host security updates and time synchronisation.

Generate configuration **only for a new installation**:

```sh
python3 scripts/init_production_env.py --domain app.example.com --media-domain media.example.com --operator-email operations@example.com
```

The file is created as `infra/.env.production` with mode 600 and unique secrets; existing files are never replaced. Edit it privately. Configure the real SMTP sender, authenticated transport (TLS or SSL, not both), and sender-domain authentication. Gmail and business recipients are supported. A Gmail sender requires the appropriate Google account/app-password or a supported relay; configuring a sender is not a Gmail inbox integration. Verify delivery, spam placement, bounce handling and password-reset/invitation links before inviting customers. Do not put credentials in Git, command arguments, screenshots or chat.

For an **existing installation**, securely copy the existing configuration instead. Preserve `MFA_ENCRYPTION_KEY`, email/push encryption keys and database/storage credentials. Regenerating encryption keys makes existing encrypted data unreadable. Plan credential rotation separately. Use a tested backup before migrations and retain the previous release image/commit for recovery.

Use the following Compose prefix for every production operation; omit neither file:

```sh
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml config --quiet
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml build
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml up -d postgres redis minio
```

Initialise storage, migrate and grant runtime permissions before launching the runtime:

```sh
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml run --rm minio-init
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml run --rm migrate
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml run --rm db-grants
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml run --rm --no-deps api python -m app.ops.preflight
docker compose --env-file infra/.env.production -f infra/docker-compose.yml -f infra/compose.production.yml up -d
```

The runtime refuses unsafe production configuration, including a superuser/BYPASSRLS connection. Only migration/grant jobs use the privileged connection. API/web run as UID 10001 with read-only filesystems in the overlay. Worker and scheduler startup also validate their relevant configuration. Single-instance beat is required; do not scale the scheduler without a dedicated leader design.

Check `https://app.example.com/api/v1/health/ready` through the same-origin web proxy: it must return 200 and all checks `ok`. The scheduler heartbeat may take up to 30 seconds after startup. This endpoint tests DB, broker, worker/scheduler and storage; it does not certify email delivery or model quality. `/health` is a basic liveness check, not release acceptance.

Then verify HTTPS, cookies, invite/activation, MFA enrolment/recovery, separate platform and lodge accounts, a guest/stay/task journey, private media, notifications and actual email. Super Admin remains platform-only. Configure optional AI/push only with intended credentials and run their provider-specific acceptance; enabled flags alone are insufficient. Record the release SHA and acceptance results.

## Encrypted, authenticated backup

Install a supported `age` binary from its verified official release. On a secured recovery workstation create an age identity and store the private identity offline. Keep its public recipient on the server. Generate a separate private manifest signing key on the backup operator account:

```sh
umask 077
age-keygen -o /secure/offline/safarios.agekey
python3 -c "import os; p='/secure/safarios-backup-signing.key'; fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(fd,os.urandom(32)); os.close(fd)"
```

Store a protected off-server copy of the signing key separately from archives. Public-recipient encryption alone does not authenticate who created a database archive; the separate HMAC does. Protect both private keys, the Docker operator account and the source configuration.

```sh
python3 scripts/recovery.py backup --env-file infra/.env.production --file infra/docker-compose.yml --file infra/compose.production.yml --project infra --archive /secure/backups/release.age --recipient age1YOUR_PUBLIC_RECIPIENT --signing-key-file /secure/safarios-backup-signing.key
```

Replace the example project with the **actual existing Compose project name**, as shown by `docker compose ... config`. The script stops currently running web/API/worker/beat writers, captures PostgreSQL, all private bucket objects and configuration, then restarts those writers even after a capture failure. This is a maintenance-window backup; pause external writes and confirm jobs are drained. Files are privately staged on the operator's temp filesystem before encryption, so use an encrypted host/temp filesystem, adequate free space and restricted operator access. Copy completed archives off the VPS, restrict retention and perform regular drills. The script never overwrites an archive.

## Recovery and upgrades

First authenticate/decrypt/validate without changing any target:

```sh
python3 scripts/recovery.py recover --archive /secure/backups/release.age --identity /secure/offline/safarios.agekey --signing-key-file /secure/safarios-backup-signing.key --export-config /secure/recovered.env
```

The exported configuration includes sensitive credentials/encryption keys and is created privately without overwrite. Review it; do not automatically apply old infrastructure credentials to a different host. Prepare a **separate empty target database and bucket**, use the correct preserved encryption keys, create its runtime role/storage, and leave web/API/worker/beat stopped. Never restore over live customer records.

```sh
python3 scripts/recovery.py recover --archive /secure/backups/release.age --identity /secure/offline/safarios.agekey --signing-key-file /secure/safarios-backup-signing.key --env-file /secure/target.env --file infra/docker-compose.yml --file infra/compose.production.yml --project recovery-target --restore --confirm-project recovery-target
```

Recovery rejects nonempty targets, unsafe archive members, wrong signatures and corrupted objects before target writes. It restores the DB in one transaction, then media, migrations and grants. A media failure after DB restore requires a new empty target; it is not a cross-service atomic transaction. Do not start a partially restored target. Recovery revokes old sessions and unused password/invitation tokens, cancels pending AI actions and holds old undelivered messages to prevent replay. Issue fresh invitations/reset links and review held deliveries explicitly. Append-only audit/history remain intact.

Validate restored counts, selected private-media bytes, logins/MFA, worker readiness and a full role-scoped journey before switching traffic. Record measured backup age (RPO), outage and recovery duration (RTO); local rehearsal results do not establish VPS targets. For an upgrade, rehearse against a recovered copy first, back up production, run migrations/grants for the pinned new release, then verify readiness and acceptance. After a failed schema upgrade, recover into a separate target; rolling back an image alone may not roll back its schema.

## Monitoring and incident response

Monitor HTTPS readiness externally, host disk/inodes/memory, PostgreSQL capacity, Redis health, queue age/failures, worker heartbeat, backup success/age and certificate expiry. Logs rotate locally (5 × 10 MB per configured service); configure a protected central log/error destination and avoid guest data/secrets in alerts. Test alerts actually reach an operator. Agree maintenance windows, on-call ownership, recovery targets and retention/deletion rules with the launch lodges.

During an incident preserve relevant protected logs/audit, restrict affected access, revoke compromised sessions/credentials, repair the dependency and verify role/tenant boundaries before reopening. Never disable RLS, CSRF, MFA or feature checks to recover availability. Redis failure degrades readiness; a bounded per-process authentication limiter continues locally, but distributed capacity is reduced until Redis is repaired. Backups support recovery, not automatic high availability; a single VPS remains a single-host failure domain.
