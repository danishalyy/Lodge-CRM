#!/usr/bin/env python3
"""Create a new-install production template; never rotate an existing installation."""
import argparse
import base64
import os
import re
from pathlib import Path
import secrets
from urllib.parse import urlsplit


def domain(value):
    if not re.fullmatch(r'(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}', value):
        raise argparse.ArgumentTypeError('Use a public hostname without a scheme or path')
    return value.lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--domain', type=domain, required=True)
    parser.add_argument('--media-domain', type=domain, required=True)
    parser.add_argument('--operator-email', required=True)
    parser.add_argument('--output', default='infra/.env.production')
    args = parser.parse_args()
    if args.domain == args.media_domain:
        parser.error('Application and media require distinct hostnames')
    if not re.fullmatch(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}', args.operator_email):
        parser.error('Enter an operator email address')
    root = Path(__file__).resolve().parents[1]
    text = (root / '.env.example').read_text()
    db_password, app_password = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
    key = lambda: base64.urlsafe_b64encode(os.urandom(32)).decode()
    values = {
        'APP_DOMAIN': args.domain, 'MEDIA_DOMAIN': args.media_domain, 'ACME_EMAIL': args.operator_email,
        'APP_ENV': 'production', 'COOKIE_SECURE': 'true',
        'POSTGRES_PASSWORD': db_password, 'APP_DATABASE_PASSWORD': app_password,
        'DATABASE_ADMIN_URL': f'postgresql+psycopg://lodge:{db_password}@postgres:5432/lodge_crm',
        'APP_DATABASE_URL': f'postgresql+psycopg://lodge_app:{app_password}@postgres:5432/lodge_crm',
        'FRONTEND_ORIGINS': 'https://' + args.domain, 'PUBLIC_WEB_URL': 'https://' + args.domain,
        'OBJECT_STORAGE_PUBLIC_ENDPOINT': 'https://' + args.media_domain,
        'OBJECT_STORAGE_ACCESS_KEY': secrets.token_urlsafe(18), 'OBJECT_STORAGE_SECRET_KEY': secrets.token_urlsafe(48),
        'MFA_ENCRYPTION_KEY': key(), 'EMAIL_ENCRYPTION_KEY': key(), 'PUSH_ENCRYPTION_KEY': key(),
    }
    result = []
    for line in text.splitlines():
        name = line.split('=', 1)[0]
        if name in values:
            result.append(name + '=' + values.pop(name))
        else:
            result.append(line)
    result.extend(name + '=' + value for name, value in values.items())
    path = Path(args.output)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        output.write('\n'.join(result) + '\n')
    print('New-install configuration written privately. Configure SMTP and optional AI/push, preserve encryption keys, then run preflight.')


if __name__ == '__main__':
    main()
