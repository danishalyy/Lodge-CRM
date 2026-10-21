"""Transactional email transport and encrypted, database-backed account email outbox."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr
from html import escape
import json
import smtplib
import ssl
import uuid

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from sqlalchemy import select

from .config import settings
from .models import AccountEmail, Invitation, User, LodgeGroup


def email_configured():
    return bool(settings.smtp_host and settings.smtp_from_email)


def validate_email_configuration():
    if not email_configured():
        raise HTTPException(503, "Email delivery is not configured. Configure Gmail or your business SMTP server.")
    if settings.smtp_use_ssl and settings.smtp_use_tls:
        raise HTTPException(503, "Choose SMTP SSL or STARTTLS, not both.")
    if settings.app_env == "production" and not (settings.smtp_use_ssl or settings.smtp_use_tls):
        raise HTTPException(503, "Production email requires encrypted SMTP delivery.")
    if settings.smtp_host.lower() == "smtp.gmail.com":
        if not (settings.smtp_use_ssl or settings.smtp_use_tls):
            raise HTTPException(503, "Gmail requires encrypted SMTP delivery.")
        if not settings.smtp_username or not settings.smtp_password:
            raise HTTPException(503, "Gmail sender credentials are not configured.")


def _cipher():
    key = settings.email_encryption_key or settings.mfa_encryption_key
    if not key:
        raise HTTPException(503, "Email outbox encryption is not configured.")
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Email outbox encryption key is invalid.")


def render_email(title, body, action_label=None, action_url=None):
    """Only trusted server-generated links are supplied; all user-facing text is escaped."""
    action = (f'<p style="margin:28px 0"><a href="{escape(action_url, quote=True)}" '
              'style="background:#D2942D;color:#27221A;padding:14px 24px;border-radius:24px;'
              f'display:inline-block;text-decoration:none;font-weight:bold">{escape(action_label or "Open SafariOS")}</a></p>'
              f'<p style="font-size:12px;word-break:break-all">Or copy this link: {escape(action_url)}</p>') if action_url else ""
    return ('<!doctype html><html><body style="margin:0;background:#F3EDE2;color:#27221A;'
            'font-family:Arial,sans-serif;padding:32px"><div style="max-width:560px;margin:auto;'
            'padding:32px;background:#FCF6EC;border:1px solid #27221A33;border-radius:24px">'
            f'<p style="font-size:20px;font-weight:bold">SafariOS</p><h1 style="font-size:28px">{escape(title)}</h1>'
            f'<p style="line-height:1.6;white-space:pre-line">{escape(body)}</p>{action}'
            '<p style="font-size:12px;border-top:1px solid #27221A33;padding-top:20px">'
            'SafariOS · Lodge operations<br>Never share your password or one-time account links.</p></div></body></html>')


def send_email(destination, title, body, html_body=None, message_id=None):
    validate_email_configuration()
    msg = EmailMessage()
    msg["Subject"] = title
    msg["From"] = formataddr(("SafariOS", settings.smtp_from_email))
    msg["To"] = destination
    msg["Message-ID"] = message_id or f"<{uuid.uuid4()}@safarios.mail>"
    msg.set_content(body)
    msg.add_alternative(html_body or render_email(title, body), subtype="html")
    context = ssl.create_default_context()
    if settings.smtp_use_ssl:
        client = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20, context=context)
    else:
        client = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
    with client as smtp:
        if settings.smtp_use_tls:
            smtp.starttls(context=context)
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(msg)


def safe_delivery_error(exc):
    # Never persist raw SMTP responses, message content, passwords, or activation URLs.
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        return "Email provider rejected the sender credentials. Check the Gmail App Password or SMTP credentials."
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        return "Email provider rejected the recipient address."
    if isinstance(exc, (OSError, smtplib.SMTPServerDisconnected)):
        return "Email provider could not be reached. Delivery will be retried."
    return "Email delivery failed. Check the sender configuration and retry."


def queue_account_email(db, *, user, kind, title, body, action_label=None, action_url=None,
                        invitation=None, reset_token=None, created_by_user_id=None, lodge_id=None):
    validate_email_configuration()
    payload = {"title": title, "body": body, "html": render_email(title, body, action_label, action_url)}
    if action_url:
        payload["body"] += "\n\n" + action_url
    row = AccountEmail(lodge_id=lodge_id, user_id=user.id, invitation_id=invitation.id if invitation else None,
                       reset_token_id=reset_token.id if reset_token else None, kind=kind, destination=user.email,
                       encrypted_payload=_cipher().encrypt(json.dumps(payload).encode()).decode(),
                       created_by_user_id=created_by_user_id, status="pending", next_attempt_at=datetime.now(timezone.utc))
    db.add(row)
    db.flush()
    return row


def issue_invitation(db, user, *, lodge=None, creator_id=None):
    """Caller holds the user row lock; resends invalidate all older activation links."""
    from .security import new_token, token_hash
    if user.is_active:
        raise HTTPException(409, "This account is already active. The owner can use password recovery.")
    now = datetime.now(timezone.utc)
    latest = db.scalar(select(Invitation).where(Invitation.user_id == user.id).order_by(Invitation.created_at.desc()).limit(1))
    if latest and latest.created_at > now - timedelta(seconds=settings.invitation_resend_cooldown_seconds):
        raise HTTPException(429, "An invitation was recently created. Please wait before resending.")
    for old in db.scalars(select(Invitation).where(Invitation.user_id == user.id, Invitation.used_at.is_(None))).all():
        old.used_at = now
    for old in db.scalars(select(AccountEmail).where(AccountEmail.user_id == user.id, AccountEmail.kind == "invitation",
                                                    AccountEmail.status.in_(["pending", "failed", "sending", "dead"]))).all():
        old.status = "cancelled"
        old.encrypted_payload = None
    raw = new_token()
    inv = Invitation(lodge_id=lodge.id if lodge else None, user_id=user.id, token_hash=token_hash(raw),
                     expires_at=now + timedelta(hours=settings.invitation_ttl_hours), created_by_user_id=creator_id)
    db.add(inv)
    db.flush()
    result = {"activation_token": None, "activation_email_sent": False, "activation_email_queued": False,
              "activation_expires_at": inv.expires_at.isoformat(), "invitation_id": str(inv.id)}
    if not email_configured() and settings.app_env == "development":
        result["activation_token"] = raw
        result["delivery_status"] = "development_link"
        return result
    group=db.scalar(select(LodgeGroup).where(LodgeGroup.admin_user_id==user.id,LodgeGroup.is_active.is_(True))) if not lodge and not user.is_super_admin else None
    name = (lodge.brand_name or lodge.name) if lodge else (group.name+" group") if group else "SafariOS platform"
    link = f"{settings.public_web_url.rstrip('/')}/activate#token={raw}"
    row = queue_account_email(db, user=user, kind="invitation", title=f"Set up your {name} account",
                              body=f"Hello {user.full_name},\n\nYou have been invited to {name}. Set your own SafariOS password using the button below. Your inviter cannot see your password.\n\nThis one-time link expires in {settings.invitation_ttl_hours} hours. If you did not expect this invitation, ignore this email.",
                              action_label="Set my password", action_url=link, invitation=inv,
                              created_by_user_id=creator_id, lodge_id=lodge.id if lodge else None)
    result.update(activation_email_queued=True, delivery_status=row.status)
    return result


def account_email_status(db, user):
    if user.is_active:
        return {"account_status": "active", "delivery_status": None, "expires_at": None}
    inv = db.scalar(select(Invitation).where(Invitation.user_id == user.id, Invitation.used_at.is_(None))
                    .order_by(Invitation.created_at.desc()).limit(1))
    mail = db.scalar(select(AccountEmail).where(AccountEmail.user_id == user.id, AccountEmail.kind == "invitation")
                     .order_by(AccountEmail.created_at.desc()).limit(1))
    status = "pending_activation" if inv and inv.expires_at > datetime.now(timezone.utc) else "invitation_expired" if inv else "inactive"
    return {"account_status": status, "delivery_status": mail.status if mail else "development_link" if inv else None,
            "expires_at": inv.expires_at.isoformat() if inv else None}


def decrypt_payload(value):
    try:
        return json.loads(_cipher().decrypt(value.encode()))
    except (InvalidToken, ValueError, TypeError):
        raise RuntimeError("Email outbox payload could not be decrypted.") from None
