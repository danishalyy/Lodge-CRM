# Runtime security regression suite

From `apps/api`, provide `TEST_DATABASE_ADMIN_URL` through the process environment and run:

```sh
python -m pytest -q -p no:cacheprovider --tb=short
```

The URL must point to a PostgreSQL administrator connection with CREATE DATABASE and CREATE ROLE rights. Configure `REDIS_URL` to a reachable Redis database dedicated to tests (CI uses database 14). Do not point tests at customer services. Without `TEST_DATABASE_ADMIN_URL`, the integration tests explicitly skip; a skipped run is not a security acceptance pass.

The fixture creates a random `lodge_test_*` database, runs all Alembic migrations, bootstraps a random least-privilege application role, and removes that database and role at teardown. Application HTTP requests run through ASGI using that real non-superuser database connection; no database or authorization behavior is mocked. Test records are confined to the temporary database. Application lifespan/storage deployment validation is deliberately outside this suite.

Coverage: PostgreSQL RLS with missing and mismatched context; foreign tenant read/update denial; successful scoped guest create/read; CSRF rejection; read-only role; expired read-only and pending/suspended subscription restrictions; enabled MFA replacement denial; password and OTP requirements for disable; password-reset session revocation without bypassing MFA; OTP reuse rejection; concurrent reset token consumption.

CI runs the suite against PostgreSQL 16 and Redis 7. Broader per-endpoint/role coverage, real storage, email, full browser workflows, load and deployment checks are still required.
