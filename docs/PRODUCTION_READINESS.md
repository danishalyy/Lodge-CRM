# Production-readiness gates

A build may be called production-ready only after all applicable gates pass:

- Fresh install migrations succeed.
- Upgrade from the previous release preserves data.
- Downgrade/restore procedure is verified in staging before any production release.
- Cross-tenant access tests pass for every API, export, object URL, worker and AI/tool path.
- Role/department/own-record tests pass.
- Basic/Standard/Premium entitlement tests pass.
- Pending/Suspended/Expired subscription tests pass.
- SMTP, object storage and workers are configured with real providers for production.
- HTTPS, secure cookies, non-default credentials and MFA encryption are configured.
- Automated PostgreSQL backups and restore drills are tested.
- Centralized logs, error reporting and uptime monitoring are configured.
- Load tests establish capacity and recovery targets.
- No placeholder, demo, fake or simulated operational record/function remains exposed as if it were live.
