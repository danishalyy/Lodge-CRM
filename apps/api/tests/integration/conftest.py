"""Real PostgreSQL fixture. Creates and removes only a uniquely named test database/role."""

import os
import secrets
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient


from threading import RLock

_signin_transport_lock = RLock()


class SignInClient(TestClient):
    """Existing workflow fixtures drive the real email challenge, never bypass it.

    New authentication tests set auto_email_login=False to inspect both steps.
    Only synthetic queued mail is decrypted; no SMTP delivery occurs in fixtures.
    """

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.auto_email_login = True

    def post(self, url, *args, **kwargs):
        with _signin_transport_lock:
            return self._email_post(url, *args, **kwargs)

    def _email_post(self, url, *args, **kwargs):
        if not self.auto_email_login or str(url) not in [
            "/api/v1/auth/login",
            "/api/v1/guest/auth/login",
        ]:
            return super().post(url, *args, **kwargs)
        from app.config import settings
        from app.models import AccountEmail, EmailLoginChallenge
        from app.email_service import decrypt_payload
        from app.security import token_hash
        from sqlalchemy import select, delete
        import re

        original = {
            key: getattr(settings, key) for key in ["smtp_host", "smtp_from_email"]
        }
        # Keep mail tests' explicit provider settings; supply only a test transport
        # for workflow fixtures that previously needed no configured email sender.
        if not settings.smtp_host:
            settings.smtp_host = "smtp.fixture.invalid"
        if not settings.smtp_from_email:
            settings.smtp_from_email = "sender@example.com"
        try:
            response = super().post(url, *args, **kwargs)
            if (
                response.status_code != 202
                or response.json().get("status") != "email_otp_required"
            ):
                return response
            token = response.json()["challenge_token"]
            with self.owner() as db:
                challenge = db.scalar(
                    select(EmailLoginChallenge).where(
                        EmailLoginChallenge.token_hash == token_hash(token)
                    )
                )
                mail = db.scalar(
                    select(AccountEmail).where(
                        AccountEmail.login_challenge_id == challenge.id
                    )
                )
                code = re.search(
                    r"code is ([0-9]{6})",
                    decrypt_payload(mail.encrypted_payload)["body"],
                ).group(1)
                challenge_id = challenge.id
            result = super().post(
                url,
                *args,
                **{
                    **kwargs,
                    "json": {
                        **kwargs["json"],
                        "email_challenge": token,
                        "email_code": code,
                    },
                }
            )
            with self.owner() as db:
                db.execute(
                    delete(AccountEmail).where(
                        AccountEmail.login_challenge_id == challenge_id
                    )
                )
                db.execute(
                    delete(EmailLoginChallenge).where(
                        EmailLoginChallenge.id == challenge_id
                    )
                )
                db.commit()
            return result
        finally:
            for key, value in original.items():
                setattr(settings, key, value)


@pytest.fixture(scope="session")
def database():
    url = os.getenv("TEST_DATABASE_ADMIN_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_ADMIN_URL to run real PostgreSQL security tests")
    admin = make_url(url)
    if not admin.host:
        pytest.fail("TEST_DATABASE_ADMIN_URL must include a reachable database host")
    dbname = "lodge_test_" + uuid4().hex
    role = "lodge_test_" + uuid4().hex
    password = secrets.token_urlsafe(32)
    control = psycopg.connect(
        admin.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
    )
    owner_url = admin.set(drivername="postgresql+psycopg", database=dbname)
    app_url = owner_url.set(username=role, password=password)
    owner_engine = app_engine = None
    try:
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
        child = dict(
            os.environ,
            DATABASE_URL=owner_url.render_as_string(hide_password=False),
            DATABASE_ADMIN_URL=owner_url.render_as_string(hide_password=False),
            APP_DATABASE_ROLE=role,
            APP_DATABASE_PASSWORD=password,
        )
        root = Path(__file__).resolve().parents[2]
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=root,
            env=child,
            check=True,
        )
        subprocess.run(
            [sys.executable, "-m", "app.bootstrap_db_role"],
            cwd=root,
            env=child,
            check=True,
        )
        owner_engine = create_engine(owner_url)
        app_engine = create_engine(app_url)
        yield sessionmaker(owner_engine, expire_on_commit=False), sessionmaker(
            app_engine, expire_on_commit=False
        )
    finally:
        if app_engine is not None:
            app_engine.dispose()
        if owner_engine is not None:
            owner_engine.dispose()
        control.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(dbname)
            )
        )
        control.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
        control.close()


@pytest.fixture
def api(database, monkeypatch):
    from app import main
    from app.db import get_db

    owner, application = database
    monkeypatch.setattr(
        main.settings, "mfa_encryption_key", Fernet.generate_key().decode()
    )

    def session():
        with application() as db:
            yield db

    main.app.dependency_overrides[get_db] = session
    # No lifespan: object-store CORS and production deployment validation are separate checks.
    client = SignInClient(main.app, owner=owner)
    try:
        yield client, owner, application
    finally:
        client.close()
        main.app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def account(api):
    from datetime import date, timedelta
    from sqlalchemy import select
    from app.models import User, Lodge, Membership, Subscription, Role
    from app.security import hash_password

    client, owner, application = api
    password = secrets.token_urlsafe(24)
    with owner() as db:
        user = User(
            email=uuid4().hex + "@example.com",
            full_name="Security Test",
            password_hash=hash_password(password),
        )
        lodge = Lodge(name="Security Test " + uuid4().hex)
        db.add_all([user, lodge])
        db.flush()
        role = db.scalar(select(Role).where(Role.key == "lodge_admin"))
        db.add_all(
            [
                Membership(user_id=user.id, lodge_id=lodge.id, role_id=role.id),
                Subscription(
                    lodge_id=lodge.id,
                    package="Standard",
                    start_date=date.today() - timedelta(days=1),
                    expiry_date=date.today() + timedelta(days=90),
                ),
            ]
        )
        db.commit()
    response = client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": password}
    )
    assert response.status_code == 200, response.text
    return {
        "client": client,
        "owner": owner,
        "application": application,
        "user": user,
        "lodge": lodge,
        "password": password,
        "csrf": {"X-CSRF-Token": client.cookies["lodge_csrf"]},
    }
