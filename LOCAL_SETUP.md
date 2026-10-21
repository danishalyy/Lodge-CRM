# Run Lodge CRM on your laptop

This is the updated web foundation source, not a completed commercial release. No real credentials, customer records or installed dependencies are included.

## 1. Prerequisites

Install Docker Desktop and start it. Windows users should enable Docker Desktop's WSL 2 backend and use Linux containers. macOS users should choose the Docker Desktop build matching their Mac. Linux users can use Docker Engine with the Compose plugin.

You do not need to install Node.js, Python, PostgreSQL or Redis separately. Docker installs/runs them. Allow several GB of free disk space and sufficient Docker memory; the first build includes compiling MinIO from source and may take considerably longer than subsequent starts. Internet access is required.

Extract the ZIP, then open a terminal **inside the extracted `lodge-crm` folder**, where `README.md`, `apps` and `infra` appear. Run every command below from that folder.

Check Docker:

```sh
docker version
docker compose version
```

## 2. Create your local configuration

Windows PowerShell:

```powershell
Copy-Item .env.example infra/.env
```

macOS/Linux:

```sh
cp .env.example infra/.env
```

Do this once; do not overwrite a configuration you have already customized.

Open `infra/.env` in a text editor. Keep `APP_ENV=development` and the local HTTP addresses for this laptop setup. The template's service passwords are for isolated local testing only. If changing the database passwords, update both the password field and its matching database URL so they agree. Never use the template credentials for a public deployment.

## 3. Generate the MFA encryption key

Build the API image:

```sh
docker compose -f infra/docker-compose.yml build api
```

Generate a key:

```sh
docker compose -f infra/docker-compose.yml run --rm --no-deps api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the generated line into `infra/.env` after `MFA_ENCRYPTION_KEY=`. Keep it private and retain the same key for this database: changing it makes existing encrypted authenticator secrets unreadable. This enables real authenticator setup for the Super Admin.

## 4. Start the application

```sh
docker compose -f infra/docker-compose.yml up -d --build
```

Check services:

```sh
docker compose -f infra/docker-compose.yml ps -a
```

The migration, role-grant and storage-initialization services are one-time jobs; `Exited (0)` is normal for them. API, web, PostgreSQL, Redis, MinIO, worker and beat should remain running. A nonzero exit or unhealthy service needs investigation.

Open `http://localhost:8000/health` in your browser. It should report:

```json
{"status":"ok","database":"ok","redis":"ok"}
```

## 5. Create your Super Admin

```sh
docker compose -f infra/docker-compose.yml exec api python -m app.bootstrap_superadmin
```

Enter the owner’s email and full name. With SMTP configured, the owner receives an invitation to choose their own password. In development without SMTP, the command prints a private activation link; open it locally and set your password. No default login is included. Run this once per administrator email. See [Gmail and invitation setup](docs/EMAIL_AND_INVITATIONS.md) to configure real email delivery.

## 6. Sign in and create a lodge

Open **http://localhost:3000** in your laptop browser and sign in using the account you just created.

Visit **http://localhost:3000/settings** to set up MFA: add the displayed secret to Google Authenticator, Microsoft Authenticator, or another TOTP app, then confirm with its current six-digit code. Platform administration requires MFA. Subsequent sign-ins require an authenticator code.

Return to **http://localhost:3000/super-admin** and register your lodge. Use a different email for the Lodge Admin; select a package and subscription dates that include today. Payments are handled outside the CRM.

Email delivery is not configured by default. In development, the lodge registration screen provides an activation link/token for the new Lodge Admin instead of requiring SMTP. Activate that account, choose its password, then sign in with it to use the lodge dashboard. Your Super Admin account and Lodge Admin account are separate logins. Clicking “Open lodge” while signed in as Super Admin does not change your identity or remove platform permissions. To test Lodge Admin permissions, activate the separate Lodge Admin account and sign in with it in a private browser window. No guest/staff/room sample data is preloaded; create your own test records.

## Stop and start again

Stop services while keeping data:

```sh
docker compose -f infra/docker-compose.yml stop
```

Resume:

```sh
docker compose -f infra/docker-compose.yml up -d
```

Apply source changes:

```sh
docker compose -f infra/docker-compose.yml up -d --build
```

Do **not** run `docker compose down -v` unless you intend to permanently delete your local database and uploaded files.

## Troubleshooting

Service logs:

```sh
docker compose -f infra/docker-compose.yml logs --tail=100 api web migrate db-grants minio minio-init
```

For build errors, capture the output of the failed build command; build failures do not necessarily appear in container logs.

- **Cannot connect to Docker:** start Docker Desktop and wait until its engine is ready.
- **Port already allocated:** stop another program using ports 3000, 8000, 9000 or 9001, then retry.
- **MFA encryption not configured:** save a valid generated key in `infra/.env`, then run `docker compose -f infra/docker-compose.yml up -d --force-recreate api`.
- **Account already exists:** sign in with that account; do not recreate the same administrator.
- **Lodge subscription denied:** use Super Admin to check subscription start/expiry and suspension status.
- **Alpine/Go/PyPI download failure:** check internet, VPN/proxy and firewall access. MinIO builds require `dl-cdn.alpinelinux.org`, GitHub and Go module/checksum services. Keep TLS and checksum verification enabled.

Validation limits: the frontend build, native API startup, database/Redis connectivity and 334 tests passed in the cloud workspace. Full Docker Compose startup was blocked there by network access during MinIO's build; it has not been verified on your laptop. Storage, live email and all business workflows are not yet fully accepted. See `docs/COMMERCIAL_RELEASE_PLAN.md` for remaining work.

## Update an existing laptop installation

If you downloaded a ZIP, download the latest GitHub `main` ZIP and update the source files. Preserve your existing `infra/.env` (especially the database passwords and MFA encryption key). Do not replace it with the template, and do not delete Docker volumes. If extracting to a new folder, copy your existing `infra/.env` there first and keep using the same Compose project name (`infra`) to retain the existing named volumes.

Rebuild and restart from the updated project root:

```sh
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

Sign out and sign back in after upgrading. Use a separate email/password for each person; a private browser window is useful when testing Lodge Admin separately from Super Admin. See `docs/ACCOUNT_ISOLATION.md` for the account, role and offline queue boundaries.

## Set up lodge branding in SafariOS

After updating the source and rebuilding with your existing `infra/.env`, sign in as Super Admin and open **Lodges**. Choose a logo during **Register lodge**, or select **Manage branding** on an existing property card. Set the workspace display name, upload the logo, and save.

Use a static PNG, JPEG or WebP file under 256 KB. SafariOS validates and normalizes it before saving. Each lodge sees its own identity in its authenticated workspace, alongside the SafariOS wordmark and “Powered by SafariOS.” Lodge administrators cannot edit these settings.

Migration `0009_lodge_branding` runs automatically during the Compose upgrade. Existing lodge records remain intact. Keep your existing database volumes and MFA encryption key; no reset is required.
