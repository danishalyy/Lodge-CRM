"""Read-only production configuration check; never prints configured secrets."""
from ..config import settings
from ..db import engine
from ..services.deployment import validate_runtime
from ..email_service import validate_email_configuration

if settings.app_env != 'production':
    raise SystemExit('Preflight requires APP_ENV=production')
validate_runtime(settings, engine)
validate_email_configuration()
print('Production configuration and database-role checks passed. Live service and recovery acceptance are still required.')
