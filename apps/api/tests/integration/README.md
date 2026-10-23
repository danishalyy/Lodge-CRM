# Runtime security regression suite

From `apps/api`, provide `TEST_DATABASE_ADMIN_URL` through the process environment and run:

```sh
python -m pytest -q -p no:cacheprovider --tb=short
```

The URL must point to a PostgreSQL administrator connection with CREATE DATABASE and CREATE ROLE rights. Configure `REDIS_URL` to a reachable Redis database dedicated to tests (CI uses database 14). Do not point tests at customer services. Without `TEST_DATABASE_ADMIN_URL`, the integration tests explicitly skip; a skipped run is not a security acceptance pass.

The fixture creates a random `lodge_test_*` database, runs all Alembic migrations, bootstraps a random least-privilege application role, and removes that database and role at teardown. Application HTTP requests run through ASGI using that real non-superuser database connection; no database or authorization behavior is mocked. Test records are confined to the temporary database. Application lifespan/storage deployment validation is deliberately outside this suite.

Coverage: PostgreSQL RLS with missing and mismatched context; foreign tenant read/update denial; successful scoped guest create/read; CSRF rejection; read-only role; expired read-only and pending/suspended subscription restrictions; enabled MFA replacement denial; password and OTP requirements for disable; password-reset session revocation without bypassing MFA; OTP reuse rejection; concurrent reset token consumption.

CI runs the suite against PostgreSQL 16 with pgvector 0.8.2 and Redis 7. Migration 0019 requires the vector extension binaries; a stock PostgreSQL image cannot apply it. Build `infra/postgres` or use a compatible PostgreSQL 16 pgvector test image before running this suite. See [AI setup](../../../../docs/AI_SETUP.md) for the image/backup/upgrade requirements. Broader per-endpoint/role coverage, real storage, email, full browser workflows, load and deployment checks are still required.

Additional account-isolation cases are in `test_account_isolation.py`, including a runtime request matrix across every tenant route declared in the API, with a real foreign lodge ID. Account ownership, private notifications, session revocation, assigned tasks, department HR, inactive-account invitations, MFA enforcement and concurrent activation are covered. Browser checks live in `e2e/account-isolation.test.cjs`; see `docs/ACCOUNT_ISOLATION.md` for commands and coverage limits.
