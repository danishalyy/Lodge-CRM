import hashlib, secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Cookie, Depends, Header, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import get_db, set_rls_context
from .models import (
    Lodge, LodgeGroup, AuditLog, AuthSession, LodgeEntitlementOverride, Membership, Permission, PlanEntitlement,
    Role, RolePermission, StaffProfile, Subscription, User, CustomRole, CustomRolePermission,
)

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_token() -> str:
    return secrets.token_urlsafe(32)


def _fernet() -> Fernet:
    if not settings.mfa_encryption_key:
        raise HTTPException(503, "MFA encryption is not configured")
    try:
        return Fernet(settings.mfa_encryption_key.encode())
    except Exception:
        raise HTTPException(503, "MFA encryption key is invalid")


def encrypt_mfa_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_mfa_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        raise HTTPException(500, "MFA secret could not be decrypted")


def create_session(db: Session, user: User, response: Response):
    raw, csrf = new_token(), new_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=settings.session_ttl_hours)
    s = AuthSession(user_id=user.id, token_hash=token_hash(raw), csrf_hash=token_hash(csrf), expires_at=expires)
    db.add(s)
    db.commit()
    response.set_cookie("lodge_session", raw, httponly=True, secure=settings.cookie_secure, samesite="lax", max_age=settings.session_ttl_hours*3600, path="/")
    response.set_cookie("lodge_csrf", csrf, httponly=False, secure=settings.cookie_secure, samesite="lax", max_age=settings.session_ttl_hours*3600, path="/")


def current_user(lodge_session: str | None = Cookie(None), db: Session = Depends(get_db), x_expected_user_id: str | None = Header(None), x_lodge_context: str | None = Header(None)) -> User:
    if not lodge_session:
        raise HTTPException(401, "Authentication required")
    now = datetime.now(timezone.utc)
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(lodge_session), AuthSession.revoked_at.is_(None), AuthSession.expires_at > now))
    if not s:
        raise HTTPException(401, "Session expired")
    user = db.get(User, s.user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account unavailable")
    # This optional client assertion can only restrict an authenticated session.
    # It prevents stale browser tabs from writing as a newly signed-in account.
    if x_expected_user_id is not None and x_expected_user_id != str(user.id):
        raise HTTPException(409, "Signed-in account changed; reload before continuing")
    # Persist session activity first, then establish transaction-local RLS context.
    # Non-platform users must retain an active lodge membership and active employment.
    s.last_seen_at = now
    db.commit()
    set_rls_context(db, None, user.is_super_admin, str(user.id))
    if not user.is_super_admin:
        memberships = db.scalars(select(Membership).where(Membership.user_id == user.id, Membership.is_active.is_(True))).all()
        groups=db.scalars(select(LodgeGroup).where(LodgeGroup.admin_user_id==user.id,LodgeGroup.is_active.is_(True))).all()
        if groups:
            valid=[m for m in memberships if membership_for(db,user,str(m.lodge_id))]
            if any(db.get(Role,m.role_id).key!='group_admin' for m in valid):raise HTTPException(403,'Account assignment requires administrator review')
            selected=next((m for m in valid if str(m.lodge_id)==x_lodge_context),None) if x_lodge_context else (valid[0] if valid else None)
            if x_lodge_context and not selected:raise HTTPException(403,'You do not have access to this lodge')
            set_rls_context(db,str(selected.lodge_id) if selected else None,False,str(user.id))
            return user
        if not memberships:
            raise HTTPException(401, "Lodge access has been revoked")
        if len(memberships) != 1:
            raise HTTPException(403, "Account lodge assignment requires administrator review")
        membership = membership_for(db,user,str(memberships[0].lodge_id))
        if not membership:raise HTTPException(401,"Lodge access has been revoked")
        set_rls_context(db, str(membership.lodge_id), False, str(user.id))
        staff = db.scalar(select(StaffProfile).where(StaffProfile.lodge_id == membership.lodge_id, StaffProfile.user_id == user.id))
        if staff and staff.employment_status != "active":
            raise HTTPException(401, "Staff access is inactive")
    return user


def require_csrf(request: Request, x_csrf_token: str | None = Header(None), lodge_session: str | None = Cookie(None), db: Session = Depends(get_db)):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not lodge_session or not x_csrf_token:
        raise HTTPException(403, "CSRF token required")
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(lodge_session), AuthSession.revoked_at.is_(None), AuthSession.expires_at > datetime.now(timezone.utc)))
    if not s or not secrets.compare_digest(s.csrf_hash, token_hash(x_csrf_token)):
        raise HTTPException(403, "Invalid CSRF token")


def require_super_admin(user: User = Depends(current_user)) -> User:
    if not user.is_super_admin:
        raise HTTPException(403, "Super Admin access required")
    if not user.mfa_enabled_at:
        raise HTTPException(403, "Super Admin MFA setup is required")
    return user


def membership_for(db: Session, user: User, lodge_id: str):
    member=db.scalar(select(Membership).where(Membership.user_id==user.id,Membership.lodge_id==lodge_id,Membership.is_active.is_(True)))
    if member and db.get(Role,member.role_id).key=='group_admin':
        lodge=db.get(Lodge,lodge_id)
        group=db.get(LodgeGroup,lodge.group_id) if lodge and lodge.group_id else None
        if not group or not group.is_active or group.admin_user_id!=user.id:return None
    return member


@dataclass
class AccessContext:
    user: User
    membership: Membership | None
    role_key: str
    department_id: object | None
    staff: StaffProfile | None
    super_admin: bool


def access_context(db: Session, user: User, lodge_id: str) -> AccessContext:
    if user.is_super_admin:
        return AccessContext(user, None, "super_admin", None, None, True)
    m = membership_for(db, user, lodge_id)
    if not m:
        raise HTTPException(403, "You do not have access to this lodge")
    role = db.get(Role, m.role_id)
    staff = db.scalar(select(StaffProfile).where(StaffProfile.lodge_id == lodge_id, StaffProfile.user_id == user.id))
    dept = m.department_id or (staff.department_id if staff else None)
    return AccessContext(user, m, role.key if role else "", dept, staff, False)


def subscription_state(db: Session, lodge_id: str) -> tuple[Subscription | None, str]:
    sub = db.get(Subscription, lodge_id)
    if not sub:
        return None, "Unavailable"
    today = date.today()
    if sub.suspended:
        return sub, "Suspended"
    if today < sub.start_date:
        return sub, "Pending"
    if today > sub.expiry_date:
        return sub, "Expired"
    if (sub.expiry_date - today).days <= 30:
        return sub, "Expiring Soon"
    return sub, "Active"


def ensure_subscription_read_allowed(db: Session, lodge_id: str):
    _, state = subscription_state(db, lodge_id)
    if state == "Unavailable":
        raise HTTPException(403, "Lodge subscription is not configured")
    if state == "Suspended":
        raise HTTPException(403, "Lodge access is suspended by the platform administrator")
    if state == "Pending":
        raise HTTPException(403, "Lodge subscription has not started yet")
    # Expired remains readable by design; writes are blocked below.


def ensure_subscription_write_allowed(db: Session, lodge_id: str):
    sub, state = subscription_state(db, lodge_id)
    if state == "Unavailable":
        raise HTTPException(403, "Lodge subscription is not configured")
    if state == "Suspended":
        raise HTTPException(403, "Lodge access is suspended by the platform administrator")
    if state == "Pending":
        raise HTTPException(403, "Lodge subscription has not started yet")
    if state == "Expired":
        raise HTTPException(403, "Lodge subscription has expired; access is read-only")


def entitlement_enabled(db: Session, lodge_id: str, feature_key: str) -> bool:
    from .feature_catalog import BUILT
    if feature_key not in BUILT:return False
    override = db.get(LodgeEntitlementOverride, {"lodge_id": lodge_id, "feature_key": feature_key})
    if override is not None:
        return bool(override.enabled)
    sub = db.get(Subscription, lodge_id)
    if not sub:
        return False
    row = db.get(PlanEntitlement, {"plan_key": sub.package, "feature_key": feature_key})
    return bool(row and row.enabled)


def ensure_feature(db: Session, lodge_id: str, feature_key: str):
    if not entitlement_enabled(db, lodge_id, feature_key):
        raise HTTPException(403, f"Feature '{feature_key}' is not enabled for this lodge subscription")


def require_lodge_access(lodge_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if user.is_super_admin:
        require_super_admin(user)
        set_rls_context(db, lodge_id, True, str(user.id))
        return user
    if not membership_for(db, user, lodge_id):
        raise HTTPException(403, "You do not have access to this lodge")
    set_rls_context(db, lodge_id, False, str(user.id))
    ensure_subscription_read_allowed(db, lodge_id)
    return user


def has_permission(db: Session, membership: Membership, permission_key: str) -> bool:
    permission_id = db.scalar(select(Permission.id).where(Permission.key == permission_key))
    if not permission_id:
        return False
    if membership.custom_role_id:
        custom = db.get(CustomRole, membership.custom_role_id)
        if not custom or not custom.is_active or custom.lodge_id != membership.lodge_id:
            return False
        return bool(db.scalar(select(CustomRolePermission.permission_id).where(CustomRolePermission.custom_role_id == custom.id, CustomRolePermission.permission_id == permission_id)))
    return bool(db.scalar(select(RolePermission.permission_id).where(RolePermission.role_id == membership.role_id, RolePermission.permission_id == permission_id)))


def require_permission(permission_key: str, write: bool = False):
    def dependency(lodge_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
        if user.is_super_admin:
            require_super_admin(user)
            set_rls_context(db, lodge_id, True, str(user.id))
            if write:
                ensure_subscription_write_allowed(db, lodge_id)
            db.add(AuditLog(lodge_id=lodge_id,actor_user_id=user.id,action="support.write" if write else "support.read",resource_type="endpoint",resource_id=request.url.path,request_id=request.headers.get("x-request-id",""),ip_address=request.client.host if request.client else ""))
            db.commit();set_rls_context(db,lodge_id,True,str(user.id))
            return user
        m = membership_for(db, user, lodge_id)
        if not m:
            raise HTTPException(403, "You do not have access to this lodge")
        set_rls_context(db, lodge_id, False, str(user.id))
        ensure_subscription_read_allowed(db, lodge_id)
        if not has_permission(db, m, permission_key):
            raise HTTPException(403, "Your role does not permit this action")
        if write:
            ensure_subscription_write_allowed(db, lodge_id)
        return user
    return dependency
