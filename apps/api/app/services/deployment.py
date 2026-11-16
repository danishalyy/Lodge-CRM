"""Configuration validation shared by web, worker and scheduler startup."""
from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.engine import make_url
from urllib.parse import urlsplit


def production_problems(settings, component="api"):
    if settings.app_env != 'production':
        return []
    if component not in {'api','worker','beat'}:
        raise ValueError('Unknown runtime component')
    problems = []
    try:
        url = make_url(settings.database_url)
        password = url.password or ''
        if url.get_backend_name() != 'postgresql' or len(password) < 24 or any(x in password.lower() for x in ['change-this','dev_password','changeme','replace-me','replace_with']):
            problems.append('DATABASE_URL must use PostgreSQL and a unique password of at least 24 characters')
    except Exception:
        problems.append('DATABASE_URL is invalid')
    if component == 'beat':
        # The scheduler publishes task names only; do not require or distribute
        # media, email or MFA secrets that this process does not need.
        return problems
    def https_origin(value):
        try:
            url = urlsplit(value)
            return url.scheme == 'https' and bool(url.hostname) and not url.username and not url.password and not url.query and not url.fragment
        except ValueError:
            return False
    if not settings.cookie_secure:
        problems.append('COOKIE_SECURE must be true')
    if not settings.origins or any(not https_origin(x) or urlsplit(x).path not in {'', '/'} for x in settings.origins):
        problems.append('FRONTEND_ORIGINS must contain explicit HTTPS origins')
    if not https_origin(settings.public_web_url):
        problems.append('PUBLIC_WEB_URL must use HTTPS')
    if not https_origin(settings.object_storage_public_endpoint):
        problems.append('OBJECT_STORAGE_PUBLIC_ENDPOINT must use HTTPS')
    for field in ['mfa_encryption_key', 'email_encryption_key', 'push_encryption_key']:
        key = getattr(settings, field)
        if not key and field == 'mfa_encryption_key':
            problems.append('MFA_ENCRYPTION_KEY is required')
        elif key:
            try:
                Fernet(key.encode())
            except (ValueError, TypeError):
                problems.append(field.upper() + ' must be a valid encryption key')
    if not settings.smtp_host or not settings.smtp_from_email:
        problems.append('SMTP is required for password recovery and invitations')
    if not (settings.smtp_use_tls or settings.smtp_use_ssl) or (settings.smtp_use_tls and settings.smtp_use_ssl):
        problems.append('Configure exactly one of SMTP_USE_TLS and SMTP_USE_SSL')
    secret = settings.object_storage_secret_key
    if len(secret) < 24 or any(x in secret.lower() for x in ['change-this', 'changeme', 'dev_password', 'replace-me', 'replace_with']):
        problems.append('OBJECT_STORAGE_SECRET_KEY must be a unique production secret')
    return problems


def validate_runtime(settings, engine, component="api"):
    if settings.app_env != 'production':
        return
    problems = production_problems(settings,component)
    try:
        with engine.connect() as connection:
            superuser, bypass = connection.execute(text('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
            if superuser or bypass:
                problems.append('DATABASE_URL must use a non-superuser role without BYPASSRLS')
    except Exception:
        problems.append('Database security-role validation failed')
    if problems:
        # Never include credentials, DSNs or third-party exception strings.
        raise RuntimeError('Unsafe production configuration: ' + '; '.join(problems))
