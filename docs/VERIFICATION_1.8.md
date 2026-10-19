# Lodge CRM 1.8 hardening verification

- Included API/source/regression tests: 323 passed on 2026-10-19 in the build environment.
- Python source and Alembic migration files compile successfully.
- Next.js security configuration syntax was checked with Node.
- Full live Docker/PostgreSQL/Redis/Celery/MinIO/browser acceptance could not be executed in the build environment because Docker/runtime dependencies are not available here.
- Run `./scripts/runtime_acceptance.sh` on the deployment machine. It preserves volumes and fails visibly on runtime errors.
