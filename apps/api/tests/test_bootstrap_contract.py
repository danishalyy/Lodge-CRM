from pathlib import Path
import re

API_ROOT = Path(__file__).resolve().parents[1]


def test_database_role_bootstrap_does_not_bind_password_in_role_ddl():
    source = (API_ROOT / 'app' / 'bootstrap_db_role.py').read_text()
    # PostgreSQL role DDL does not accept a bind parameter for PASSWORD.
    assert 'PASSWORD %s' not in source
    assert 'sql.Literal(app_password)' in source


def test_alembic_revision_ids_fit_default_version_column():
    versions = API_ROOT / 'alembic' / 'versions'
    for path in versions.glob('*.py'):
        text = path.read_text()
        match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
        if match:
            assert len(match.group(1)) <= 32, f'{path.name}: revision id too long: {match.group(1)}'
