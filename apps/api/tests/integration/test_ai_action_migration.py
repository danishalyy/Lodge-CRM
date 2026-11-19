"""Upgrade the action allowlist on a separate database without losing private history."""

import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta, timezone
import psycopg
from psycopg import sql
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.models import Lodge, User, AIConversation, AIAction


def test_action_migration_preserves_old_proposals_rls_and_blocks_lossy_downgrade():
    admin_url = os.getenv("TEST_DATABASE_ADMIN_URL")
    if not admin_url:
        pytest.skip("Set TEST_DATABASE_ADMIN_URL for real migration checks")
    admin = make_url(admin_url)
    name = "ai_actions_migration_" + uuid4().hex
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

        def migrate(command, target, check=True):
            return subprocess.run(
                [sys.executable, "-m", "alembic", command, target],
                cwd=Path(__file__).resolve().parents[2],
                env=env,
                check=check,
                capture_output=True,
                text=True,
            )

        migrate("upgrade", "0028_email_sign_in")
        engine = create_engine(url)
        with Session(engine, expire_on_commit=False) as db:
            user = User(
                email="migration@example.com",
                full_name="Synthetic owner",
                password_hash="fixture",
            )
            lodge = Lodge(name="Synthetic property")
            db.add_all([user, lodge])
            db.flush()
            conv = AIConversation(
                user_id=user.id, lodge_id=lodge.id, access_fingerprint="x" * 64
            )
            db.add(conv)
            db.flush()

            def action(kind):
                return AIAction(
                    user_id=user.id,
                    lodge_id=lodge.id,
                    conversation_id=conv.id,
                    request_id=uuid4(),
                    action=kind,
                    payload={"title": "Preserve me"},
                    preview={"fields": []},
                    snapshot={},
                    access_fingerprint="x" * 64,
                    expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                )

            old = action("create_task")
            db.add(old)
            db.commit()
            old_id = old.id
        migrate("upgrade", "head")
        with Session(engine, expire_on_commit=False) as db:
            assert db.get(AIAction, old_id).payload == {"title": "Preserve me"}
            assert db.execute(
                text(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname='ai_actions'"
                )
            ).one() == (True, True)
            assert (
                db.scalar(
                    text(
                        "SELECT count(*) FROM pg_policies WHERE tablename='ai_actions' AND policyname='ai_actions_private'"
                    )
                )
                == 1
            )
            new = action("create_guest")
            db.add(new)
            db.commit()
            new_id = new.id
        failed = migrate("downgrade", "0028_email_sign_in", False)
        assert failed.returncode != 0 and "Cannot downgrade AI actions" in failed.stderr
        with Session(engine) as db:
            assert (
                db.get(AIAction, new_id) is not None
                and db.get(AIAction, old_id) is not None
            )
            db.delete(db.get(AIAction, new_id))
            db.commit()
        migrate("downgrade", "0028_email_sign_in")
        migrate("upgrade", "head")
        with Session(engine) as db:
            assert db.get(AIAction, old_id).payload == {"title": "Preserve me"}
    finally:
        if engine:
            engine.dispose()
        control.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(name)
            )
        )
        control.close()
