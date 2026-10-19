"""Idempotently create/refresh the least-privilege application database role.

Run after Alembic migrations with a database-owner/admin connection. The API, worker
and scheduler must connect as the resulting role so PostgreSQL RLS cannot be bypassed.
"""
import os
import psycopg
from psycopg import sql

admin_url=os.environ.get('DATABASE_ADMIN_URL','postgresql://lodge:lodge_dev_password@postgres:5432/lodge_crm').replace('postgresql+psycopg://','postgresql://')
app_role=os.environ.get('APP_DATABASE_ROLE','lodge_app')
app_password=os.environ.get('APP_DATABASE_PASSWORD','lodge_app_dev_password')
if not app_password:
    raise SystemExit('APP_DATABASE_PASSWORD is required')

with psycopg.connect(admin_url,autocommit=True) as conn:
    with conn.cursor() as cur:
        cur.execute('SELECT current_user, current_database()')
        owner,dbname=cur.fetchone()
        cur.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(app_role,))
        exists=cur.fetchone() is not None
        if exists:
            cur.execute(sql.SQL('ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(sql.Identifier(app_role), sql.Literal(app_password)))
        else:
            cur.execute(sql.SQL('CREATE ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD {}').format(sql.Identifier(app_role), sql.Literal(app_password)))
        cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(dbname),sql.Identifier(app_role)))
        cur.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(app_role)))
        cur.execute(sql.SQL('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(app_role)))
        cur.execute(sql.SQL('REVOKE UPDATE, DELETE ON TABLE operational_events, audit_logs FROM {}').format(sql.Identifier(app_role)))
        cur.execute(sql.SQL('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}').format(sql.Identifier(app_role)))
        cur.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO {}').format(sql.Identifier(owner),sql.Identifier(app_role)))
        # History tables are append-only. Re-apply after broad grants so future bootstrap runs cannot weaken them.
        cur.execute(sql.SQL('REVOKE UPDATE, DELETE ON TABLE operational_events, audit_logs FROM {}').format(sql.Identifier(app_role)))
        cur.execute(sql.SQL('ALTER DEFAULT PRIVILEGES FOR ROLE {} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {}').format(sql.Identifier(owner),sql.Identifier(app_role)))
        cur.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=%s',(app_role,))
        superuser,bypass=cur.fetchone()
        if superuser or bypass:
            raise RuntimeError('Application role must not be superuser or BYPASSRLS')
print(f'Application DB role {app_role} is ready with RLS enforcement enabled.')
