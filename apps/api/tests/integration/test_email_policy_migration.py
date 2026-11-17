"""Rehearse the real factor-policy upgrade on a separate, synthetic old schema."""

import os, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.models import User, AuthSession


def test_email_policy_upgrade_preserves_platform_factors_and_invalidates_other_sessions():
    admin_url = os.getenv("TEST_DATABASE_ADMIN_URL")
    if not admin_url:
        pytest.skip("Set TEST_DATABASE_ADMIN_URL for real migration checks")
    admin = make_url(admin_url)
    name = "email_policy_test_" + uuid4().hex
    url = admin.set(database=name, drivername="postgresql+psycopg")
    control = psycopg.connect(
        admin.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
    )
    engine = None
    try:
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        env = dict(
            os.environ,
            DATABASE_URL=url.render_as_string(hide_password=False),
            DATABASE_ADMIN_URL=url.render_as_string(hide_password=False),
        )

        def migrate(action, target):
            subprocess.run(
                [sys.executable, "-m", "alembic", action, target],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                check=True,
            )

        migrate("upgrade", "0027_guest_portal")
        engine = create_engine(url)
        with Session(engine, expire_on_commit=False) as db:
            users = [
                User(
                    email=kind + "@example.com",
                    full_name="Synthetic " + kind,
                    password_hash="fixture-only",
                    is_super_admin=kind == "platform",
                    is_guest=kind == "guest",
                    mfa_secret_encrypted=kind + "-ENCRYPTED",
                    mfa_enabled_at=datetime.now(timezone.utc),
                    mfa_recovery_hashes=[kind + "-HASH"],
                )
                for kind in ["staff", "guest", "platform"]
            ]
            db.add_all(users)
            db.flush()
            sessions = [
                AuthSession(
                    user_id=u.id,
                    token_hash=uuid4().hex + uuid4().hex,
                    csrf_hash="c" * 64,
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
                )
                for u in users
            ]
            db.add_all(sessions)
            db.commit()
            user_ids = [u.id for u in users]
            session_ids = [s.id for s in sessions]
        migrate("upgrade", "head")
        with Session(engine) as db:
            for uid, sid in zip(user_ids[:2], session_ids[:2]):
                user = db.get(User, uid)
                assert (
                    user.mfa_secret_encrypted is None
                    and user.mfa_enabled_at is None
                    and user.mfa_recovery_hashes == []
                )
                assert db.get(AuthSession, sid).revoked_at
            platform = db.get(User, user_ids[2])
            assert (
                platform.mfa_secret_encrypted == "platform-ENCRYPTED"
                and platform.mfa_enabled_at
                and platform.mfa_recovery_hashes == ["platform-HASH"]
            )
            assert db.get(AuthSession, session_ids[2]).revoked_at is None
            assert db.execute(
                text(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='email_login_challenges'"
                )
            ).one() == (True, True)
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM pg_policies WHERE tablename='audit_logs' AND policyname IN ('audit_account_mfa_insert','audit_account_email_login_insert')"
                    )
                )
                == 2
            )
        migrate("downgrade", "0027_guest_portal")
        migrate("upgrade", "head")
        with Session(engine) as db:
            assert (
                db.get(User, user_ids[2]).mfa_secret_encrypted == "platform-ENCRYPTED"
            )
            assert db.get(AuthSession, session_ids[2]).revoked_at is None
    finally:
        if engine:
            engine.dispose()
        control.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )
        control.close()
