"""Invalidate restored credentials and deliveries before a recovered app starts."""
from datetime import datetime, timezone
from sqlalchemy import update
from ..models import AuthSession, Invitation, PasswordResetToken, AccountEmail, NotificationDelivery, PushDelivery, AIAction


def invalidate_restored_access(db):
    now = datetime.now(timezone.utc)
    db.execute(update(AuthSession).where(AuthSession.revoked_at.is_(None)).values(revoked_at=now))
    db.execute(update(Invitation).where(Invitation.used_at.is_(None)).values(used_at=now))
    db.execute(update(PasswordResetToken).where(PasswordResetToken.used_at.is_(None)).values(used_at=now))
    db.execute(update(AIAction).where(AIAction.status == 'pending').values(status='cancelled', token_hash=None))
    # A backup cannot know which external deliveries succeeded after its snapshot.
    # Hold old work instead of replaying private mail or push after disaster recovery.
    for model in [AccountEmail, NotificationDelivery, PushDelivery]:
        values = {'status': 'dead', 'lease_expires_at': None}
        values.update({'last_error_code': 'recovery_hold'} if model is PushDelivery else {'last_error': 'Held after disaster recovery; review before retry'})
        db.execute(update(model).where(model.status.in_(['pending', 'failed', 'sending'])).values(**values))
    db.commit()


def main():
    from ..db import SessionLocal, set_rls_context
    with SessionLocal() as db:
        set_rls_context(db, None, True)
        invalidate_restored_access(db)
    print('Restored sessions, account links and pending AI actions invalidated; historical external deliveries held for operator review.')


if __name__ == '__main__':
    main()
