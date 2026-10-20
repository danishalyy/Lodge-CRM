from datetime import date, datetime, timedelta, timezone
import base64
import binascii
from io import BytesIO
from PIL import Image, ImageOps, UnidentifiedImageError
import uuid
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
import redis
import boto3
import pyotp
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from .config import settings
from .db import engine, get_db, set_rls_context
from .models import (
    AuditLog, AuthSession, Department, Guest, GuestRequest, Invitation, Lodge,
    MaintenanceTicket, Membership, OperationalEvent, Permission, Role, RolePermission,
    StaffProfile, Stay, Subscription, Task, Unit, User, Vehicle, VehicleChecklist, VehicleChecklistItem, FuelRecord, Activity, ActivityGuest, Transfer, WildlifeSighting, WildlifeMedia,
    Notification, NotificationRecipient, NotificationPreference, NotificationDelivery,
    LodgeEntitlementOverride, Plan, PlanEntitlement, PasswordResetToken,
    StaffLeave, StaffCredential, StaffTraining, CustomRole, CustomRolePermission,
    TaskChecklistItem, TaskComment, HousekeepingJob, MaintenanceAsset, MaintenancePartUsage,
    GuestFeedback, StaffShift, StaffIncident, StaffPerformanceNote, MealService, MealServiceGuest, TaskAttachment,
)
from .schemas import (
    LodgeBrandingUpdate, ActivateIn, DepartmentCreate, DepartmentUpdate, GuestCreate, GuestRequestCreate,
    GuestRequestUpdate, GuestUpdate, LodgeCreate, LoginIn, MaintenanceCreate,
    MaintenanceUpdate, StaffCreate, StaffUpdate, StayCreate, StayUpdate,
    SubscriptionUpdate, TaskCreate, TaskUpdate, UnitCreate, UnitUpdate, VehicleCreate, VehicleUpdate, VehicleChecklistCreate, FuelCreate, ActivityCreate, ActivityUpdate, TransferCreate, TransferUpdate, WildlifeSightingCreate, WildlifeMediaRegister, MediaUploadRequest, StaffInvite, NotificationPreferenceUpdate, PasswordResetRequestIn, PasswordResetConfirmIn, MfaCodeIn, EntitlementOverrideIn,
    StaffLeaveCreate, StaffLeaveUpdate, StaffCredentialCreate, StaffTrainingCreate,
    CustomRoleCreate, CustomRoleUpdate, MembershipRoleUpdate,
    TaskChecklistCreate, TaskChecklistUpdate, TaskCommentCreate,
    HousekeepingCreate, HousekeepingUpdate, MaintenanceAssetCreate, MaintenancePartCreate,
    GuestFeedbackCreate, GuestFeedbackUpdate, StaffShiftCreate, StaffShiftUpdate, StaffIncidentCreate, StaffPerformanceCreate,
    MealServiceCreate, MealServiceUpdate, TaskAttachmentUploadRequest, TaskAttachmentRegister, MfaDisableIn, ChangePasswordIn,
)
from .security import (
    create_session, current_user, hash_password, new_token, require_csrf,
    require_lodge_access, require_permission, require_super_admin, token_hash,
    verify_password, access_context, has_permission, ensure_feature, entitlement_enabled,
    encrypt_mfa_secret, decrypt_mfa_secret,
)
from .services.state import housekeeping_job_created, housekeeping_awaiting_inspection, housekeeping_completed, maintenance_opened, maintenance_released, unit_is_occupied
from .notification_service import create_notification, staff_user_id, user_ids_with_permission

app = FastAPI(
    title="SafariOS API",
    version="1.8.0-security-integrity",
    docs_url="/docs" if settings.app_env == "development" else None,
    redoc_url="/redoc" if settings.app_env == "development" else None,
    openapi_url="/openapi.json" if settings.app_env == "development" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID", "X-Expected-User-Id"],
)

redis_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)

def _s3(endpoint: str):
    return boto3.client("s3", endpoint_url=endpoint, aws_access_key_id=settings.object_storage_access_key, aws_secret_access_key=settings.object_storage_secret_key, region_name=settings.object_storage_region, config=BotoConfig(signature_version="s3v4"))

s3_internal = _s3(settings.object_storage_endpoint)
s3_public = _s3(settings.object_storage_public_endpoint)

@app.on_event("startup")
def validate_production_configuration():
    if settings.app_env != "production":
        return
    problems=[]
    if not settings.cookie_secure: problems.append("COOKIE_SECURE must be true")
    if not settings.mfa_encryption_key: problems.append("MFA_ENCRYPTION_KEY is required")
    if not settings.smtp_host or not settings.smtp_from_email: problems.append("SMTP is required for password recovery and invitations")
    if "change-this" in settings.object_storage_secret_key: problems.append("OBJECT_STORAGE_SECRET_KEY must be replaced")
    if any(o.startswith("http://") for o in settings.origins): problems.append("FRONTEND_ORIGINS must use HTTPS")
    if settings.public_web_url.startswith("http://"): problems.append("PUBLIC_WEB_URL must use HTTPS")
    try:
        with engine.connect() as conn:
            row=conn.execute(text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")).one()
            if row[0] or row[1]: problems.append("DATABASE_URL must use a non-superuser role without BYPASSRLS")
    except Exception as exc:
        problems.append(f"database security-role validation failed: {exc}")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


@app.on_event("startup")
def configure_local_object_storage_cors():
    if settings.app_env == "production":
        return
    try:
        s3_internal.put_bucket_cors(Bucket=settings.object_storage_bucket,CORSConfiguration={"CORSRules":[{"AllowedHeaders":["*"],"AllowedMethods":["GET","PUT","HEAD"],"AllowedOrigins":settings.origins,"ExposeHeaders":["ETag"],"MaxAgeSeconds":3600}]})
    except (BotoCoreError, ClientError, OSError):
        # Object storage is not a prerequisite for API startup; media endpoints will fail explicitly if unavailable.
        pass


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "The requested change conflicts with an existing record or booking"})


@app.exception_handler(DataError)
async def data_error_handler(request: Request, exc: DataError):
    return JSONResponse(status_code=422, content={"detail": "One or more identifiers or values are invalid"})


@app.middleware("http")
async def request_id(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = rid
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(self)"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    if settings.app_env == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    try:
        redis_client.ping()
        redis_ok = True
    except redis.RedisError:
        redis_ok = False
    return {"status": "ok" if redis_ok else "degraded", "database": "ok", "redis": "ok" if redis_ok else "unavailable"}


def rate_limit_login(request: Request, email: str):
    ip = request.client.host if request.client else "unknown"
    key = f"login:{ip}:{email.lower()}"
    try:
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, settings.login_rate_window_seconds)
        if count > settings.login_rate_limit:
            raise HTTPException(429, "Too many login attempts. Please try again later.")
    except HTTPException:
        raise
    except redis.RedisError:
        # Authentication remains available if Redis is temporarily unavailable; /health exposes degradation.
        pass


def clear_login_limit(request: Request, email: str):
    ip = request.client.host if request.client else "unknown"
    try:
        redis_client.delete(f"login:{ip}:{email.lower()}")
    except redis.RedisError:
        pass


def send_activation_email(to_email:str, full_name:str, lodge_name:str, token:str):
    if not settings.smtp_host or not settings.smtp_from_email:
        if settings.app_env == "production":
            raise HTTPException(503,"Email delivery is not configured")
        return False
    msg=EmailMessage()
    msg["Subject"]=f"Activate your {lodge_name} SafariOS account"
    msg["From"]=settings.smtp_from_email
    msg["To"]=to_email
    link=f"{settings.public_web_url.rstrip('/')}/activate?token={token}"
    msg.set_content(f"Hello {full_name},\n\nYou have been invited to {lodge_name} on Lodge CRM. Activate your account using this secure link:\n{link}\n\nThis link expires in 72 hours.")
    try:
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
            if settings.smtp_use_tls:smtp.starttls()
            if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password)
            smtp.send_message(msg)
    except Exception as exc:
        raise HTTPException(503,"Invitation email could not be delivered") from exc
    return True


def send_password_reset_email(to_email:str, full_name:str, token:str):
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(503,"Password reset email delivery is not configured")
    msg=EmailMessage()
    msg["Subject"]="Reset your SafariOS password"
    msg["From"]=settings.smtp_from_email
    msg["To"]=to_email
    link=f"{settings.public_web_url.rstrip('/')}/reset-password?token={token}"
    msg.set_content(f"Hello {full_name},\n\nA password reset was requested for your SafariOS account. Use this secure link:\n{link}\n\nThis link expires in {settings.password_reset_ttl_minutes} minutes. If you did not request this, you can ignore this email.")
    try:
        with smtplib.SMTP(settings.smtp_host,settings.smtp_port,timeout=15) as smtp:
            if settings.smtp_use_tls:smtp.starttls()
            if settings.smtp_username:smtp.login(settings.smtp_username,settings.smtp_password)
            smtp.send_message(msg)
    except Exception as exc:
        raise HTTPException(503,"Password reset email could not be delivered") from exc
    return True


def audit(db: Session, request: Request, lodge_id, user_id, action: str, resource_type: str, resource_id: str, detail: str = ""):
    db.add(AuditLog(
        lodge_id=lodge_id, actor_user_id=user_id, action=action,
        resource_type=resource_type, resource_id=resource_id, detail=detail,
        request_id=request.headers.get("x-request-id", ""),
        ip_address=request.client.host if request.client else "",
    ))


def event(db: Session, lodge_id, user_id, event_type: str, resource_type: str, resource_id: str, summary: str, detail: str = ""):
    db.add(OperationalEvent(
        lodge_id=lodge_id, actor_user_id=user_id, event_type=event_type,
        resource_type=resource_type, resource_id=resource_id, summary=summary, detail=detail,
    ))


def tenant_get(db: Session, model, record_id, lodge_id, label: str):
    try:
        record_id = uuid.UUID(str(record_id))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(422, f"Invalid {label.lower()} identifier")
    row = db.get(model, record_id)
    if not row or str(row.lodge_id) != str(lodge_id):
        raise HTTPException(404, f"{label} not found")
    return row


def ensure_fk(db: Session, model, record_id, lodge_id, label: str):
    if record_id is None:
        return None
    return tenant_get(db, model, record_id, lodge_id, label)


def commit_or_conflict(db: Session, message: str = "A record with these values already exists"):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, message)


def subscription_status(sub: Subscription | None):
    if not sub:
        return "Unavailable"
    today = date.today()
    if sub.suspended:
        return "Suspended"
    if today < sub.start_date:
        return "Pending"
    if sub.expiry_date < today:
        return "Expired"
    if (sub.expiry_date - today).days <= 30:
        return "Expiring Soon"
    return "Active"


def _ctx(db:Session,user:User,lodge_id:str):
    ctx=access_context(db,user,lodge_id)
    if ctx.role_key=='department_manager' and not ctx.department_id:
        raise HTTPException(403,"Department Manager access requires an assigned department")
    return ctx

def _require_own_staff(ctx):
    if not ctx.staff:
        raise HTTPException(403,"Your account is not linked to a staff profile for this lodge")
    return ctx.staff

def _ensure_department_scope(ctx, department_id, label='record'):
    if ctx.role_key=='department_manager' and str(department_id or '')!=str(ctx.department_id or ''):
        raise HTTPException(403,f"Department Manager can only access {label}s in their assigned department")

def _may(db:Session,ctx,permission_key:str)->bool:
    return bool(ctx.super_admin or (ctx.membership and has_permission(db,ctx.membership,permission_key)))

def _set_department_from_staff_or_context(ctx, staff, supplied_department):
    derived = supplied_department or (staff.department_id if staff else None)
    if ctx.role_key=='department_manager':
        if derived and str(derived)!=str(ctx.department_id):
            raise HTTPException(403,"Cannot assign work outside your department")
        return ctx.department_id
    return derived

COMMON_PASSWORDS={"password","password123","123456789012","qwerty123456","letmein123456","admin123456","welcome123456"}
DUMMY_PASSWORD_HASH=hash_password("LodgeCRM-dummy-password-never-used-2026")

def _validate_password_policy(password:str):
    if len(password)<12: raise HTTPException(422,"Password must be at least 12 characters")
    lowered=password.lower().strip()
    if lowered in COMMON_PASSWORDS or len(set(lowered))<5:
        raise HTTPException(422,"Choose a less common password with more character variety")

def _verify_totp_once(user:User, code:str)->bool:
    if not user.mfa_secret_encrypted:return False
    totp=pyotp.TOTP(decrypt_mfa_secret(user.mfa_secret_encrypted));now=datetime.now(timezone.utc)
    for offset in (-1,0,1):
        when=now+timedelta(seconds=offset*totp.interval)
        if secrets.compare_digest(totp.at(when),code):
            step=totp.timecode(when)
            if user.mfa_last_timestep is not None and step<=user.mfa_last_timestep:return False
            user.mfa_last_timestep=step
            return True
    return False


@app.post("/api/v1/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit_login(request, body.email)
    now=datetime.now(timezone.utc)
    user = db.scalar(select(User).where(User.email == body.email.lower()).with_for_update())
    # Always perform an Argon2 verification to reduce account-enumeration timing differences.
    password_ok = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user and user.locked_until and user.locked_until>now:
        raise HTTPException(429,"Account temporarily locked after repeated failed sign-in attempts")
    if not user or not password_ok:
        if user:
            user.failed_login_count=(user.failed_login_count or 0)+1
            if user.failed_login_count>=5:
                user.locked_until=now+timedelta(minutes=15);user.failed_login_count=0
            db.commit()
        raise HTTPException(401, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(403, "Account is not activated")
    # A non-platform account must still have active lodge access and active employment.
    if not user.is_super_admin:
        set_rls_context(db,None,False,str(user.id))
        memberships=db.scalars(select(Membership).where(Membership.user_id==user.id,Membership.is_active.is_(True))).all()
        if not memberships: raise HTTPException(403,"Account access is unavailable")
        if len(memberships)!=1: raise HTTPException(403,"Account lodge assignment requires administrator review")
        membership=memberships[0]
        set_rls_context(db,str(membership.lodge_id),False,str(user.id))
        staff=db.scalar(select(StaffProfile).where(StaffProfile.lodge_id==membership.lodge_id,StaffProfile.user_id==user.id))
        if staff and staff.employment_status!="active": raise HTTPException(403,"Account access is unavailable")
    if user.mfa_enabled_at:
        if not body.otp: raise HTTPException(401, "MFA_REQUIRED")
        if not _verify_totp_once(user,body.otp): raise HTTPException(401, "Invalid or already-used MFA code")
    user.failed_login_count=0;user.locked_until=None;db.commit()
    clear_login_limit(request, body.email)
    create_session(db, user, response)
    return {"ok": True,"mfa_setup_required":bool(user.is_super_admin and not user.mfa_enabled_at)}


@app.post("/api/v1/auth/activate")
def activate(body: ActivateIn, response: Response, db: Session = Depends(get_db)):
    set_rls_context(db, None, True)
    now = datetime.now(timezone.utc)
    invitation = db.scalar(select(Invitation).where(
        Invitation.token_hash == token_hash(body.token), Invitation.used_at.is_(None), Invitation.expires_at > now
    ).with_for_update())
    if not invitation:
        raise HTTPException(400, "Activation link is invalid or has expired")
    user = db.get(User, invitation.user_id)
    if not user:
        raise HTTPException(400, "Invitation user no longer exists")
    if user.is_active:
        raise HTTPException(400, "Account is already activated; sign in or use password recovery")
    _validate_password_policy(body.password)
    user.password_hash = hash_password(body.password)
    user.is_active = True
    user.email_verified_at = now
    invitation.used_at = now
    db.add(AuditLog(lodge_id=invitation.lodge_id, actor_user_id=user.id, action="account.activated", resource_type="user", resource_id=str(user.id)))
    db.commit()
    create_session(db, user, response)
    return {"ok": True}


@app.post("/api/v1/auth/password-reset/request")
def request_password_reset(body: PasswordResetRequestIn, request: Request, db: Session = Depends(get_db)):
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(503,"Password reset is unavailable because email delivery is not configured")
    rate_limit_login(request, f"reset:{body.email}")
    user=db.scalar(select(User).where(User.email==body.email.lower(),User.is_active.is_(True)))
    if user:
        now=datetime.now(timezone.utc)
        for old in db.scalars(select(PasswordResetToken).where(PasswordResetToken.user_id==user.id,PasswordResetToken.used_at.is_(None))).all():
            old.used_at=now
        raw=new_token()
        row=PasswordResetToken(user_id=user.id,token_hash=token_hash(raw),expires_at=now+timedelta(minutes=settings.password_reset_ttl_minutes))
        db.add(row);db.flush()
        send_password_reset_email(user.email,user.full_name,raw)
        db.commit()
    return {"ok":True,"message":"If an active account exists for that email, a reset link has been sent."}


@app.post("/api/v1/auth/password-reset/confirm")
def confirm_password_reset(body: PasswordResetConfirmIn, response: Response, db: Session = Depends(get_db)):
    now=datetime.now(timezone.utc)
    row=db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash==token_hash(body.token),PasswordResetToken.used_at.is_(None),PasswordResetToken.expires_at>now).with_for_update())
    if not row: raise HTTPException(400,"Password reset link is invalid or has expired")
    user=db.get(User,row.user_id)
    if not user or not user.is_active: raise HTTPException(400,"Account is unavailable")
    _validate_password_policy(body.password)
    user.password_hash=hash_password(body.password);row.used_at=now
    sessions=db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None))).all()
    for sess in sessions:sess.revoked_at=now
    db.commit()
    # Recovery proves email ownership, not possession of an enrolled authenticator.
    # Require the normal sign-in flow (including MFA) after changing a password.
    response.delete_cookie("lodge_session", path="/")
    response.delete_cookie("lodge_csrf", path="/")
    return {"ok":True}


@app.post("/api/v1/auth/mfa/setup",dependencies=[Depends(require_csrf)])
def mfa_setup(user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.refresh(user, with_for_update=True)
    if user.mfa_enabled_at:
        raise HTTPException(409,"MFA is already enabled; disable it with your password and authenticator before enrolling again")
    secret=pyotp.random_base32()
    user.mfa_secret_encrypted=encrypt_mfa_secret(secret);user.mfa_last_timestep=None;db.commit()
    uri=pyotp.TOTP(secret).provisioning_uri(name=user.email,issuer_name="SafariOS")
    return {"secret":secret,"otpauth_uri":uri,"enabled":False}


@app.post("/api/v1/auth/mfa/confirm",dependencies=[Depends(require_csrf)])
def mfa_confirm(body:MfaCodeIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.refresh(user, with_for_update=True)
    if not user.mfa_secret_encrypted: raise HTTPException(409,"MFA setup has not been started")
    if not _verify_totp_once(user,body.code): raise HTTPException(422,"Invalid or already-used MFA code")
    user.mfa_enabled_at=datetime.now(timezone.utc);db.commit();return {"enabled":True}


@app.post("/api/v1/auth/mfa/disable",dependencies=[Depends(require_csrf)])
def mfa_disable(body:MfaDisableIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.refresh(user, with_for_update=True)
    if user.is_super_admin: raise HTTPException(409,"Super Admin MFA cannot be disabled")
    if not user.mfa_enabled_at or not user.mfa_secret_encrypted: return {"enabled":False}
    if not verify_password(body.current_password,user.password_hash): raise HTTPException(403,"Current password is incorrect")
    if not _verify_totp_once(user,body.code): raise HTTPException(422,"Invalid or already-used MFA code")
    user.mfa_enabled_at=None;user.mfa_secret_encrypted=None;user.mfa_last_timestep=None;db.commit();return {"enabled":False}

@app.post("/api/v1/auth/change-password",dependencies=[Depends(require_csrf)])
def change_password(body:ChangePasswordIn,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if not verify_password(body.current_password,user.password_hash): raise HTTPException(403,"Current password is incorrect")
    _validate_password_policy(body.new_password)
    user.password_hash=hash_password(body.new_password);now=datetime.now(timezone.utc)
    current_hash=token_hash(request.cookies.get("lodge_session",""))
    for sess in db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None))).all():
        if sess.token_hash!=current_hash:sess.revoked_at=now
    db.commit();return {"ok":True}

@app.get("/api/v1/auth/sessions")
def auth_sessions(request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    current_hash=token_hash(request.cookies.get("lodge_session",""))
    rows=db.scalars(select(AuthSession).where(AuthSession.user_id==user.id,AuthSession.revoked_at.is_(None),AuthSession.expires_at>datetime.now(timezone.utc)).order_by(AuthSession.created_at.desc())).all()
    return [{"id":str(x.id),"created_at":x.created_at.isoformat(),"last_seen_at":x.last_seen_at.isoformat(),"expires_at":x.expires_at.isoformat(),"current":x.token_hash==current_hash} for x in rows]

@app.delete("/api/v1/auth/sessions/{session_id}",dependencies=[Depends(require_csrf)])
def revoke_auth_session(session_id:uuid.UUID,request:Request,user:User=Depends(current_user),db:Session=Depends(get_db)):
    row=db.get(AuthSession,session_id)
    if not row or row.user_id!=user.id: raise HTTPException(404,"Session not found")
    row.revoked_at=datetime.now(timezone.utc);db.commit();return {"ok":True}


@app.post("/api/v1/auth/logout", dependencies=[Depends(require_csrf)])
def logout(response: Response, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    raw = request.cookies.get("lodge_session")
    if raw:
        s = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(raw), AuthSession.revoked_at.is_(None)))
        if s:
            s.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie("lodge_session", path="/")
    response.delete_cookie("lodge_csrf", path="/")
    return {"ok": True}


@app.get("/api/v1/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    memberships = []
    member_rows = db.scalars(select(Membership).where(Membership.user_id == user.id, Membership.is_active.is_(True))).all()
    for m in member_rows:
        lodge = db.get(Lodge, m.lodge_id)
        role = db.get(Role, m.role_id)
        if not user.is_super_admin:
            set_rls_context(db, str(m.lodge_id), False, str(user.id))
        sub = db.get(Subscription, m.lodge_id)
        if lodge:
            if m.custom_role_id:
                custom_role=db.get(CustomRole,m.custom_role_id)
                perm_keys = db.scalars(select(Permission.key).join(CustomRolePermission, Permission.id == CustomRolePermission.permission_id).where(CustomRolePermission.custom_role_id == m.custom_role_id)).all() if custom_role and custom_role.is_active else []
                display_role=custom_role.name if custom_role else (role.name if role else "")
            else:
                perm_keys = db.scalars(select(Permission.key).join(RolePermission, Permission.id == RolePermission.permission_id).where(RolePermission.role_id == m.role_id)).all()
                display_role=role.name if role else ""
            plan_features=[]
            if sub:
                plan_features=list(db.scalars(select(PlanEntitlement.feature_key).where(PlanEntitlement.plan_key==sub.package,PlanEntitlement.enabled.is_(True))).all())
                overrides=db.scalars(select(LodgeEntitlementOverride).where(LodgeEntitlementOverride.lodge_id==lodge.id)).all()
                state=set(plan_features)
                for ov in overrides:
                    if ov.enabled: state.add(ov.feature_key)
                    else: state.discard(ov.feature_key)
                plan_features=sorted(state)
            memberships.append({
                "lodge_id": str(lodge.id), "lodge_name": lodge.name, "branding":lodge_branding(lodge),
                "role": display_role, "role_key": role.key if role else "", "custom_role_id": str(m.custom_role_id) if m.custom_role_id else None,
                "department_id": str(m.department_id) if m.department_id else None,
                "permissions": list(perm_keys), "subscription_status": subscription_status(sub),
                "package": sub.package if sub else None, "entitlements":plan_features,
            })
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name, "is_super_admin": user.is_super_admin, "mfa_enabled":bool(user.mfa_enabled_at), "memberships": memberships}


@app.get("/api/v1/lodges/{lodge_id}/dashboard")
def dashboard(lodge_id: str, user: User = Depends(require_permission("dashboard.view")), db: Session = Depends(get_db)):
    ensure_feature(db,lodge_id,"dashboard")
    lodge = db.get(Lodge, lodge_id)
    if not lodge:
        raise HTTPException(404, "Lodge not found")
    sub = db.get(Subscription, lodge.id)
    ctx=_ctx(db,user,lodge_id)
    from zoneinfo import ZoneInfo
    try: lodge_tz=ZoneInfo(lodge.timezone)
    except Exception: lodge_tz=ZoneInfo("Africa/Johannesburg")
    local_now=datetime.now(lodge_tz); today=local_now.date()
    day_start=local_now.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    day_end=(local_now.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).astimezone(timezone.utc)
    now = datetime.now(timezone.utc)

    # Department supervisors receive a command centre scoped strictly to their department.
    if ctx.role_key=="department_manager":
        if not ctx.department_id: raise HTTPException(409,"Department Manager membership is not assigned to a department")
        guests_in_house=arrivals=departures=None
        open_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.lodge_id==lodge.id,Task.department_id==ctx.department_id,Task.status.not_in(["completed","cancelled"]))) or 0
        overdue = db.scalar(select(func.count()).select_from(Task).where(Task.lodge_id==lodge.id,Task.department_id==ctx.department_id,Task.status.not_in(["completed","cancelled"]),Task.due_at.is_not(None),Task.due_at<now)) or 0
        maintenance_open = db.scalar(select(func.count()).select_from(MaintenanceTicket).where(MaintenanceTicket.lodge_id==lodge.id,MaintenanceTicket.department_id==ctx.department_id,MaintenanceTicket.status.not_in(["completed","cancelled"]))) or 0
        activities_today = db.scalar(select(func.count()).select_from(Activity).where(Activity.lodge_id==lodge.id,Activity.department_id==ctx.department_id,Activity.starts_at>=day_start,Activity.starts_at<day_end,Activity.status!="cancelled")) or 0
        transfers_today = db.scalar(select(func.count()).select_from(Transfer).where(Transfer.lodge_id==lodge.id,Transfer.department_id==ctx.department_id,Transfer.scheduled_at>=day_start,Transfer.scheduled_at<day_end,Transfer.status!="cancelled")) or 0
        vehicles_unavailable=None
        attention=[]
        for t in db.scalars(select(Task).where(Task.lodge_id==lodge.id,Task.department_id==ctx.department_id,Task.status.not_in(["completed","cancelled"]),Task.due_at.is_not(None),Task.due_at<now).order_by(Task.due_at).limit(10)).all():
            attention.append({"id":str(t.id),"type":"task","title":f"Overdue task: {t.title}","priority":t.priority})
        for mt in db.scalars(select(MaintenanceTicket).where(MaintenanceTicket.lodge_id==lodge.id,MaintenanceTicket.department_id==ctx.department_id,MaintenanceTicket.status.not_in(["completed","cancelled"]),MaintenanceTicket.priority=="critical").order_by(MaintenanceTicket.created_at.desc()).limit(10)).all():
            attention.append({"id":str(mt.id),"type":"maintenance","title":f"Critical maintenance: {mt.title}","priority":mt.priority})
        events=[]  # Operational memory is intentionally not exposed lodge-wide to department managers.
        scope={"type":"department","department_id":str(ctx.department_id)}
    else:
        guests_in_house = db.scalar(select(func.count()).select_from(Stay).where(Stay.lodge_id == lodge.id, Stay.status == "in_house")) or 0
        arrivals = db.scalar(select(func.count()).select_from(Stay).where(Stay.lodge_id == lodge.id, Stay.arrival_date == today, Stay.status != "cancelled")) or 0
        departures = db.scalar(select(func.count()).select_from(Stay).where(Stay.lodge_id == lodge.id, Stay.departure_date == today, Stay.status.not_in(["cancelled", "completed"]))) or 0
        open_tasks = db.scalar(select(func.count()).select_from(Task).where(Task.lodge_id == lodge.id, Task.status.not_in(["completed", "cancelled"]))) or 0
        overdue = db.scalar(select(func.count()).select_from(Task).where(Task.lodge_id == lodge.id, Task.status.not_in(["completed", "cancelled"]), Task.due_at.is_not(None), Task.due_at < now)) or 0
        maintenance_open = db.scalar(select(func.count()).select_from(MaintenanceTicket).where(MaintenanceTicket.lodge_id == lodge.id, MaintenanceTicket.status.not_in(["completed", "cancelled"]))) or 0
        activities_today = db.scalar(select(func.count()).select_from(Activity).where(Activity.lodge_id==lodge.id,Activity.starts_at>=day_start,Activity.starts_at<day_end,Activity.status!="cancelled")) or 0
        transfers_today = db.scalar(select(func.count()).select_from(Transfer).where(Transfer.lodge_id==lodge.id,Transfer.scheduled_at>=day_start,Transfer.scheduled_at<day_end,Transfer.status!="cancelled")) or 0
        vehicles_unavailable = db.scalar(select(func.count()).select_from(Vehicle).where(Vehicle.lodge_id==lodge.id,Vehicle.status.in_(["maintenance","out_of_service"]))) or 0
        attention=[]
        for t in db.scalars(select(Task).where(Task.lodge_id == lodge.id, Task.status.not_in(["completed", "cancelled"]), Task.due_at.is_not(None), Task.due_at < now).order_by(Task.due_at).limit(10)).all():
            attention.append({"id": str(t.id), "type": "task", "title": f"Overdue task: {t.title}", "priority": t.priority})
        for mt in db.scalars(select(MaintenanceTicket).where(MaintenanceTicket.lodge_id == lodge.id, MaintenanceTicket.status.not_in(["completed", "cancelled"]), MaintenanceTicket.priority == "critical").order_by(MaintenanceTicket.created_at.desc()).limit(10)).all():
            attention.append({"id": str(mt.id), "type": "maintenance", "title": f"Critical maintenance: {mt.title}", "priority": mt.priority})
        events=[{"id":str(e.id),"type":e.event_type,"summary":e.summary,"created_at":e.created_at.isoformat()} for e in db.scalars(select(OperationalEvent).where(OperationalEvent.lodge_id==lodge.id).order_by(OperationalEvent.created_at.desc()).limit(20)).all()]
        scope={"type":"lodge"}
    return {
        "lodge":{"id":str(lodge.id),"name":lodge.name,"location":lodge.location,"branding":lodge_branding(lodge)},
        "scope":scope,
        "subscription":{"package":sub.package if sub else None,"status":subscription_status(sub),"expiry_date":sub.expiry_date.isoformat() if sub else None},
        "metrics":{"guests_in_house":guests_in_house,"arrivals_today":arrivals,"departures_today":departures,"open_tasks":open_tasks,"overdue_tasks":overdue,"maintenance_open":maintenance_open,"activities_today":activities_today,"transfers_today":transfers_today,"vehicles_unavailable":vehicles_unavailable},
        "attention":attention,"events":events,
    }


def lodge_branding(lodge: Lodge):
    return {"lodge_id":str(lodge.id),"display_name":lodge.brand_name or lodge.name,
            "logo_url":f"/api/v1/lodges/{lodge.id}/branding/logo?v={lodge.updated_at.isoformat()}" if lodge.logo_png else None,
            "platform_name":"SafariOS"}


def normalize_lodge_logo(encoded: str) -> bytes:
    try:
        raw=base64.b64decode(encoded,validate=True)
        if not raw or len(raw)>256*1024:raise ValueError()
        with Image.open(BytesIO(raw)) as image:
            if image.format not in {"PNG","JPEG","WEBP"} or image.width*image.height>4_000_000 or getattr(image,"n_frames",1)!=1:raise ValueError()
            image.load()
            clean=ImageOps.exif_transpose(image).convert("RGBA")
            clean.info.clear()
            clean.thumbnail((512,512))
            out=BytesIO();clean.save(out,format="PNG")
            result=out.getvalue()
            if len(result)>512*1024:raise ValueError()
            return result
    except (ValueError,binascii.Error,UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,"Use a valid PNG, JPEG or WebP logo under 256 KB and four megapixels")


@app.get("/api/v1/lodges/{lodge_id}/branding")
def get_lodge_branding(lodge_id:uuid.UUID,user:User=Depends(require_lodge_access),db:Session=Depends(get_db)):
    lodge=db.get(Lodge,lodge_id)
    if not lodge:raise HTTPException(404,"Lodge not found")
    return lodge_branding(lodge)


@app.get("/api/v1/lodges/{lodge_id}/branding/logo")
def get_lodge_logo(lodge_id:uuid.UUID,user:User=Depends(require_lodge_access),db:Session=Depends(get_db)):
    lodge=db.get(Lodge,lodge_id)
    if not lodge or not lodge.logo_png:raise HTTPException(404,"Logo not found")
    return Response(content=lodge.logo_png,media_type="image/png",headers={"X-Content-Type-Options":"nosniff"})


@app.patch("/api/v1/platform/lodges/{lodge_id}/branding",dependencies=[Depends(require_csrf)])
def update_lodge_branding(lodge_id:uuid.UUID,body:LodgeBrandingUpdate,request:Request,user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    lodge=db.get(Lodge,lodge_id)
    if not lodge:raise HTTPException(404,"Lodge not found")
    name=body.display_name.strip()
    if not name:raise HTTPException(422,"Display name cannot be blank")
    if body.remove_logo and body.logo_base64 is not None:raise HTTPException(422,"Choose a replacement logo or removal, not both")
    logo=normalize_lodge_logo(body.logo_base64) if body.logo_base64 is not None else None
    lodge.brand_name=name
    if body.remove_logo:lodge.logo_png=None
    elif logo is not None:lodge.logo_png=logo
    audit(db,request,lodge.id,user.id,"lodge.branding_updated","lodge",str(lodge.id))
    db.commit()
    return lodge_branding(lodge)


# Platform administration
@app.get("/api/v1/platform/lodges")
def list_lodges(user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    set_rls_context(db, None, True, str(user.id))
    out = []
    for l in db.scalars(select(Lodge).order_by(Lodge.name)).all():
        s = db.get(Subscription, l.id)
        out.append({"id": str(l.id), "name": l.name, "branding":lodge_branding(l), "location": l.location, "status": l.status, "subscription_status": subscription_status(s), "subscription": ({"package": s.package, "start_date": s.start_date.isoformat(), "expiry_date": s.expiry_date.isoformat(), "suspended": s.suspended} if s else None)})
    return out


@app.post("/api/v1/platform/lodges", dependencies=[Depends(require_csrf)])
def create_lodge(body: LodgeCreate, request: Request, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    set_rls_context(db, None, True, str(user.id))
    if body.expiry_date < body.start_date:
        raise HTTPException(422, "Expiry date must be on or after start date")
    if db.scalar(select(Lodge).where(func.lower(Lodge.name) == body.name.lower())):
        raise HTTPException(409, "A lodge with this name already exists")
    lodge = Lodge(name=body.name.strip(), location=body.location.strip(), timezone=body.timezone, protected_species=body.protected_species)
    db.add(lodge); db.flush()
    db.add(Subscription(lodge_id=lodge.id, package=body.package, start_date=body.start_date, expiry_date=body.expiry_date))
    admin = db.scalar(select(User).where(User.email == body.admin_email.lower()))
    activation_token = None
    if admin:raise HTTPException(409,"This administrator email cannot be assigned to a new lodge")
    if not admin:
        admin = User(email=body.admin_email.lower(), full_name=body.admin_name.strip(), password_hash=hash_password(new_token()+new_token()), is_active=False)
        db.add(admin); db.flush()
    role = db.scalar(select(Role).where(Role.key == "lodge_admin"))
    if not role:
        raise HTTPException(500, "Default roles are not installed")
    existing = db.scalar(select(Membership).where(Membership.user_id == admin.id, Membership.lodge_id == lodge.id))
    if not existing:
        db.add(Membership(user_id=admin.id, lodge_id=lodge.id, role_id=role.id, is_active=True))
    if not admin.is_active:
        activation_token = new_token()
        db.add(Invitation(lodge_id=lodge.id, user_id=admin.id, token_hash=token_hash(activation_token), expires_at=datetime.now(timezone.utc)+timedelta(hours=72), created_by_user_id=user.id))
        send_activation_email(admin.email, admin.full_name, lodge.name, activation_token)
    audit(db, request, lodge.id, user.id, "lodge.created", "lodge", str(lodge.id), f"Package {body.package}")
    event(db, lodge.id, user.id, "lodge.created", "lodge", str(lodge.id), f"Lodge {lodge.name} registered")
    db.commit()
    return {"id": str(lodge.id), "name": lodge.name, "activation_token": activation_token if settings.app_env != "production" else None, "activation_expires_hours": 72 if activation_token else None, "activation_email_sent": bool(activation_token and settings.smtp_host and settings.smtp_from_email)}


@app.patch("/api/v1/platform/lodges/{lodge_id}/subscription", dependencies=[Depends(require_csrf)])
def update_subscription(lodge_id: str, body: SubscriptionUpdate, request: Request, user: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    set_rls_context(db, None, True, str(user.id))
    sub = db.get(Subscription, lodge_id)
    if not sub:
        raise HTTPException(404, "Subscription not found")
    for field in ["package", "start_date", "expiry_date", "suspended"]:
        value = getattr(body, field)
        if value is not None:
            setattr(sub, field, value)
    if sub.expiry_date < sub.start_date:
        raise HTTPException(422, "Expiry date must be on or after start date")
    audit(db, request, sub.lodge_id, user.id, "subscription.updated", "subscription", str(sub.lodge_id))
    event(db, sub.lodge_id, user.id, "subscription.updated", "subscription", str(sub.lodge_id), f"Subscription changed to {sub.package}; status {subscription_status(sub)}")
    db.commit()
    return {"ok": True, "status": subscription_status(sub)}


@app.get("/api/v1/platform/plans")
def list_plans(user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    set_rls_context(db,None,True,str(user.id));out=[]
    for plan in db.scalars(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.key)).all():
        features=list(db.scalars(select(PlanEntitlement.feature_key).where(PlanEntitlement.plan_key==plan.key,PlanEntitlement.enabled.is_(True)).order_by(PlanEntitlement.feature_key)).all())
        out.append({"key":plan.key,"name":plan.name,"features":features})
    return out


@app.get("/api/v1/platform/lodges/{lodge_id}/entitlements")
def get_lodge_entitlements(lodge_id:str,user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    set_rls_context(db,None,True,str(user.id));sub=db.get(Subscription,lodge_id)
    if not sub:raise HTTPException(404,"Subscription not found")
    base=set(db.scalars(select(PlanEntitlement.feature_key).where(PlanEntitlement.plan_key==sub.package,PlanEntitlement.enabled.is_(True))).all())
    overrides=db.scalars(select(LodgeEntitlementOverride).where(LodgeEntitlementOverride.lodge_id==lodge_id).order_by(LodgeEntitlementOverride.feature_key)).all()
    effective=set(base)
    for ov in overrides:
        if ov.enabled:effective.add(ov.feature_key)
        else:effective.discard(ov.feature_key)
    return {"package":sub.package,"base":sorted(base),"overrides":[{"feature_key":x.feature_key,"enabled":x.enabled} for x in overrides],"effective":sorted(effective)}


@app.patch("/api/v1/platform/lodges/{lodge_id}/entitlements",dependencies=[Depends(require_csrf)])
def set_lodge_entitlement(lodge_id:str,body:EntitlementOverrideIn,request:Request,user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    set_rls_context(db,None,True,str(user.id))
    if not db.get(Subscription,lodge_id):raise HTTPException(404,"Subscription not found")
    known=db.scalar(select(PlanEntitlement.feature_key).where(PlanEntitlement.feature_key==body.feature_key).limit(1))
    if not known:raise HTTPException(422,"Unknown feature entitlement")
    row=db.get(LodgeEntitlementOverride,{"lodge_id":lodge_id,"feature_key":body.feature_key})
    if body.enabled is None:
        if row:db.delete(row)
    elif row:
        row.enabled=body.enabled;row.updated_at=datetime.now(timezone.utc)
    else:
        db.add(LodgeEntitlementOverride(lodge_id=lodge_id,feature_key=body.feature_key,enabled=body.enabled))
    audit(db,request,lodge_id,user.id,"entitlement.override","subscription",lodge_id,f"{body.feature_key}={body.enabled}");db.commit()
    return get_lodge_entitlements(lodge_id,user,db)


# Departments
@app.get("/api/v1/lodges/{lodge_id}/departments")
def departments(lodge_id: str, user: User = Depends(require_permission("departments.view")), db: Session = Depends(get_db)):
    ensure_feature(db,lodge_id,"departments");ctx=_ctx(db,user,lodge_id);q=select(Department).where(Department.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(Department.id==ctx.department_id)
    return [{"id":str(x.id),"name":x.name,"description":x.description,"is_active":x.is_active} for x in db.scalars(q.order_by(Department.name)).all()]


@app.post("/api/v1/lodges/{lodge_id}/departments", dependencies=[Depends(require_csrf)])
def create_department(lodge_id: str, body: DepartmentCreate, request: Request, user: User = Depends(require_permission("departments.manage", write=True)), db: Session = Depends(get_db)):
    ensure_feature(db,lodge_id,"departments");row = Department(lodge_id=lodge_id, name=body.name.strip(), description=body.description.strip())
    db.add(row); db.flush(); audit(db, request, row.lodge_id, user.id, "department.created", "department", str(row.id)); event(db, row.lodge_id, user.id, "department.created", "department", str(row.id), f"Department {row.name} created"); commit_or_conflict(db, "A department with this name already exists")
    return {"id": str(row.id), "name": row.name, "description": row.description, "is_active": row.is_active}


@app.patch("/api/v1/lodges/{lodge_id}/departments/{record_id}", dependencies=[Depends(require_csrf)])
def update_department(lodge_id: str, record_id: str, body: DepartmentUpdate, request: Request, user: User = Depends(require_permission("departments.manage", write=True)), db: Session = Depends(get_db)):
    ensure_feature(db,lodge_id,"departments");row = tenant_get(db, Department, record_id, lodge_id, "Department")
    for f in ["name", "description", "is_active"]:
        v = getattr(body, f)
        if v is not None: setattr(row, f, v.strip() if isinstance(v, str) else v)
    audit(db, request, row.lodge_id, user.id, "department.updated", "department", str(row.id)); commit_or_conflict(db, "A department with this name already exists")
    return {"id": str(row.id), "name": row.name, "description": row.description, "is_active": row.is_active}


# Staff
@app.get("/api/v1/lodges/{lodge_id}/staff")
def staff(lodge_id: str, user: User = Depends(require_permission("staff.view")), db: Session = Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);can_contact=_may(db,ctx,"staff.contact.view");out=[];q=select(StaffProfile).where(StaffProfile.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(StaffProfile.department_id==ctx.department_id)
    for x in db.scalars(q.order_by(StaffProfile.full_name)).all():
        dep=db.get(Department,x.department_id) if x.department_id else None
        membership=db.scalar(select(Membership).where(Membership.lodge_id==lodge_id,Membership.user_id==x.user_id,Membership.is_active.is_(True))) if x.user_id else None
        custom=db.get(CustomRole,membership.custom_role_id) if membership and membership.custom_role_id else None
        out.append({"id":str(x.id),"full_name":x.full_name,"email":x.email if can_contact else None,"phone":x.phone if can_contact else "","job_title":x.job_title,"employee_code":x.employee_code if can_contact else None,"department_id":str(x.department_id) if x.department_id else None,"department_name":dep.name if dep else None,"employment_status":x.employment_status,"operational_status":x.operational_status,"supervisor_staff_id":str(x.supervisor_staff_id) if x.supervisor_staff_id else None,"supervisor_name":_name_staff(db,x.supervisor_staff_id),"hire_date":x.hire_date.isoformat() if x.hire_date else None,"has_login":bool(x.user_id),"custom_role_id":str(custom.id) if custom else None,"custom_role_name":custom.name if custom else None})
    return out


@app.post("/api/v1/lodges/{lodge_id}/staff", dependencies=[Depends(require_csrf)])
def create_staff(lodge_id: str, body: StaffCreate, request: Request, user: User = Depends(require_permission("staff.manage", write=True)), db: Session = Depends(get_db)):
    ensure_fk(db, Department, body.department_id, lodge_id, "Department");ensure_fk(db,StaffProfile,body.supervisor_staff_id,lodge_id,"Supervisor")
    row=StaffProfile(lodge_id=lodge_id,full_name=body.full_name.strip(),email=str(body.email).lower() if body.email else None,phone=body.phone.strip(),job_title=body.job_title.strip(),employee_code=body.employee_code.strip() if body.employee_code else None,department_id=body.department_id,employment_status=body.employment_status,operational_status=body.operational_status,supervisor_staff_id=body.supervisor_staff_id,hire_date=body.hire_date)
    db.add(row);db.flush();audit(db,request,row.lodge_id,user.id,"staff.created","staff",str(row.id));event(db,row.lodge_id,user.id,"staff.created","staff",str(row.id),f"Staff profile {row.full_name} created");commit_or_conflict(db,"Employee code already exists for this lodge")
    return {"id":str(row.id),"full_name":row.full_name,"email":row.email,"phone":row.phone,"job_title":row.job_title,"employee_code":row.employee_code,"department_id":str(row.department_id) if row.department_id else None,"employment_status":row.employment_status,"operational_status":row.operational_status}


@app.patch("/api/v1/lodges/{lodge_id}/staff/{record_id}", dependencies=[Depends(require_csrf)])
def update_staff(lodge_id:str,record_id:str,body:StaffUpdate,request:Request,user:User=Depends(require_permission("staff.manage",write=True)),db:Session=Depends(get_db)):
    row=tenant_get(db,StaffProfile,record_id,lodge_id,"Staff profile")
    if body.department_id is not None: ensure_fk(db,Department,body.department_id,lodge_id,"Department");row.department_id=body.department_id
    if body.supervisor_staff_id is not None: ensure_fk(db,StaffProfile,body.supervisor_staff_id,lodge_id,"Supervisor");row.supervisor_staff_id=body.supervisor_staff_id
    if body.hire_date is not None: row.hire_date=body.hire_date
    for f in ["full_name","email","employee_code","phone","job_title","employment_status","operational_status"]:
        v=getattr(body,f)
        if v is not None:setattr(row,f,v.strip() if isinstance(v,str) else v)
    audit(db,request,row.lodge_id,user.id,"staff.updated","staff",str(row.id));db.commit()
    return {"id":str(row.id),"full_name":row.full_name,"department_id":str(row.department_id) if row.department_id else None,"employment_status":row.employment_status,"operational_status":row.operational_status}


@app.post("/api/v1/lodges/{lodge_id}/staff/{record_id}/invite",dependencies=[Depends(require_csrf)])
def invite_staff_user(lodge_id:str,record_id:str,body:StaffInvite,request:Request,user:User=Depends(require_permission("staff.manage",write=True)),db:Session=Depends(get_db)):
    staff=tenant_get(db,StaffProfile,record_id,lodge_id,"Staff profile")
    if not staff.email: raise HTTPException(422,"An email address is required before inviting this staff member")
    role=db.scalar(select(Role).where(Role.key==body.role_key))
    if not role: raise HTTPException(422,"Selected role is not installed")
    role_features={"department_manager":"departments","ranger":"ranger","driver":"transfers","fb":"fb"}
    if body.role_key in role_features:ensure_feature(db,lodge_id,role_features[body.role_key])
    account=db.scalar(select(User).where(func.lower(User.email)==staff.email.lower()))
    new_account=account is None
    if not account:
        account=User(email=staff.email.lower(),full_name=staff.full_name,password_hash=hash_password(new_token()+new_token()),is_active=False)
        db.add(account);db.flush()
    existing=db.scalar(select(Membership).where(Membership.user_id==account.id,Membership.lodge_id==lodge_id))
    if not new_account and (not existing or account.is_super_admin):
        # One account belongs to one lodge only; do not reveal where an existing account belongs.
        raise HTTPException(409,"This email cannot be invited to this lodge")
    if db.scalar(select(StaffProfile.id).where(StaffProfile.lodge_id==lodge_id,StaffProfile.user_id==account.id,StaffProfile.id!=staff.id)):
        raise HTTPException(409,"This login is already linked to a staff profile")
    if existing:
        existing.role_id=role.id;existing.custom_role_id=None;existing.previous_role_id=None;existing.is_active=True;existing.department_id=staff.department_id
    else:
        db.add(Membership(user_id=account.id,lodge_id=lodge_id,role_id=role.id,department_id=staff.department_id,is_active=True))
    staff.user_id=account.id
    activation_token=None;email_sent=False
    if not account.is_active:
        prior=db.scalars(select(Invitation).where(Invitation.lodge_id==lodge_id,Invitation.user_id==account.id,Invitation.used_at.is_(None))).all()
        for inv in prior: inv.used_at=datetime.now(timezone.utc)
        activation_token=new_token()
        db.add(Invitation(lodge_id=lodge_id,user_id=account.id,token_hash=token_hash(activation_token),expires_at=datetime.now(timezone.utc)+timedelta(hours=72),created_by_user_id=user.id))
        lodge=db.get(Lodge,lodge_id)
        email_sent=send_activation_email(account.email,account.full_name,lodge.name if lodge else "Lodge CRM",activation_token)
    audit(db,request,lodge_id,user.id,"staff.invited","staff_profile",str(staff.id),f"Role {body.role_key}")
    event(db,lodge_id,user.id,"staff.invited","staff_profile",str(staff.id),f"{staff.full_name} invited to Lodge CRM")
    db.commit()
    return {"staff_id":str(staff.id),"user_id":str(account.id),"role_key":body.role_key,"activation_token":activation_token if settings.app_env!="production" else None,"activation_email_sent":email_sent}


@app.post("/api/v1/lodges/{lodge_id}/staff/{record_id}/revoke-access",dependencies=[Depends(require_csrf)])
def revoke_staff_access(lodge_id:str,record_id:str,request:Request,user:User=Depends(require_permission("staff.manage",write=True)),db:Session=Depends(get_db)):
    staff=tenant_get(db,StaffProfile,record_id,lodge_id,"Staff profile")
    staff.employment_status="inactive";staff.operational_status="off_duty"
    revoked=0
    if staff.user_id:
        membership=db.scalar(select(Membership).where(Membership.lodge_id==lodge_id,Membership.user_id==staff.user_id))
        if membership: membership.is_active=False
        now=datetime.now(timezone.utc)
        sessions=db.scalars(select(AuthSession).where(AuthSession.user_id==staff.user_id,AuthSession.revoked_at.is_(None))).all()
        for sess in sessions:sess.revoked_at=now;revoked+=1
    audit(db,request,lodge_id,user.id,"staff.access_revoked","staff",str(staff.id))
    event(db,lodge_id,user.id,"staff.access_revoked","staff",str(staff.id),f"Access revoked for {staff.full_name}")
    db.commit();return {"id":str(staff.id),"access":"revoked","sessions_revoked":revoked}

@app.post("/api/v1/lodges/{lodge_id}/staff/{record_id}/reactivate-access",dependencies=[Depends(require_csrf)])
def reactivate_staff_access(lodge_id:str,record_id:str,request:Request,user:User=Depends(require_permission("staff.manage",write=True)),db:Session=Depends(get_db)):
    staff=tenant_get(db,StaffProfile,record_id,lodge_id,"Staff profile")
    if not staff.user_id: raise HTTPException(409,"Staff member does not have a login account")
    membership=db.scalar(select(Membership).where(Membership.lodge_id==lodge_id,Membership.user_id==staff.user_id))
    if not membership: raise HTTPException(409,"Lodge membership not found")
    membership.is_active=True;staff.employment_status="active"
    if staff.operational_status in {"off_duty","leave"}:staff.operational_status="available"
    audit(db,request,lodge_id,user.id,"staff.access_reactivated","staff",str(staff.id))
    event(db,lodge_id,user.id,"staff.access_reactivated","staff",str(staff.id),f"Access reactivated for {staff.full_name}")
    db.commit();return {"id":str(staff.id),"access":"active"}


# Units / rooms
@app.get("/api/v1/lodges/{lodge_id}/rooms")
def rooms(lodge_id:str,user:User=Depends(require_permission("units.view")),db:Session=Depends(get_db)):
    out=[]
    for x in db.scalars(select(Unit).where(Unit.lodge_id==lodge_id).order_by(Unit.name)).all():
        active_stay=db.scalar(select(Stay).where(Stay.unit_id==x.id,Stay.status=="in_house").limit(1))
        guest=db.get(Guest,active_stay.guest_id) if active_stay else None
        out.append({"id":str(x.id),"name":x.name,"unit_type":x.unit_type,"status":x.status,"notes":x.notes,"current_guest":f"{guest.first_name} {guest.last_name}" if guest else None})
    return out


@app.post("/api/v1/lodges/{lodge_id}/rooms",dependencies=[Depends(require_csrf)])
def create_room(lodge_id:str,body:UnitCreate,request:Request,user:User=Depends(require_permission("units.manage",write=True)),db:Session=Depends(get_db)):
    row=Unit(lodge_id=lodge_id,name=body.name.strip(),unit_type=body.unit_type.strip(),notes=body.notes.strip())
    db.add(row);db.flush();audit(db,request,row.lodge_id,user.id,"unit.created","unit",str(row.id));event(db,row.lodge_id,user.id,"unit.created","unit",str(row.id),f"Unit {row.name} created");commit_or_conflict(db,"A room or unit with this name already exists")
    return {"id":str(row.id),"name":row.name,"unit_type":row.unit_type,"status":row.status,"notes":row.notes,"current_guest":None}


@app.patch("/api/v1/lodges/{lodge_id}/rooms/{record_id}",dependencies=[Depends(require_csrf)])
def update_room(lodge_id:str,record_id:str,body:UnitUpdate,request:Request,user:User=Depends(require_permission("units.view",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);row=tenant_get(db,Unit,record_id,lodge_id,"Unit")
    can_config=_may(db,ctx,"units.manage");can_status=can_config or _may(db,ctx,"units.status.manage")
    if body.name is not None or body.unit_type is not None:
        if not can_config:raise HTTPException(403,"Only lodge management can edit room configuration")
        if body.name is not None:row.name=body.name.strip()
        if body.unit_type is not None:row.unit_type=body.unit_type.strip()
    if body.status is not None:
        if not can_status:raise HTTPException(403,"Your role cannot change room operational status")
        active=db.scalar(select(Stay).where(Stay.unit_id==row.id,Stay.status=="in_house").limit(1))
        if active and body.status!="occupied":raise HTTPException(409,"This unit has an in-house stay; occupancy is authoritative until checkout")
        row.status=body.status
    if body.notes is not None:
        if not can_config:raise HTTPException(403,"Only lodge management can edit room configuration notes")
        row.notes=body.notes
    audit(db,request,row.lodge_id,user.id,"unit.updated","unit",str(row.id));event(db,row.lodge_id,user.id,"unit.status_changed","unit",str(row.id),f"{row.name} status is {row.status}");db.commit()
    return {"id":str(row.id),"name":row.name,"unit_type":row.unit_type,"status":row.status,"notes":row.notes}


# Guests
@app.get("/api/v1/lodges/{lodge_id}/guests")
def guests(lodge_id:str,limit:int=Query(50,ge=1,le=250),offset:int=Query(0,ge=0),user:User=Depends(require_permission("guests.view")),db:Session=Depends(get_db)):
    out=[]
    for g in db.scalars(select(Guest).where(Guest.lodge_id==lodge_id).order_by(Guest.last_name,Guest.first_name).offset(offset).limit(limit)).all():
        current=db.scalar(select(Stay).where(Stay.guest_id==g.id,Stay.status.in_(["arriving","in_house","departing"])).order_by(Stay.arrival_date.desc()).limit(1))
        unit=db.get(Unit,current.unit_id) if current else None
        stay_count=db.scalar(select(func.count()).select_from(Stay).where(Stay.guest_id==g.id,Stay.status=="completed")) or 0
        out.append({"id":str(g.id),"first_name":g.first_name,"last_name":g.last_name,"name":f"{g.first_name} {g.last_name}","email":g.email,"phone":g.phone,"nationality":g.nationality,"vip":g.vip,"dietary_requirements":g.dietary_requirements,"allergies":g.allergies,"preferences":g.preferences,"notes":g.notes,"current_unit":unit.name if unit else None,"stay_status":current.status if current else None,"completed_stays":stay_count})
    return out


@app.get("/api/v1/lodges/{lodge_id}/guest-dietary")
def guest_dietary(lodge_id:str,user:User=Depends(require_permission("guests.dietary.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"guests")
    # Need-to-know: only guests whose stay overlaps the current service window (+/- one day).
    today=date.today();window_start=today-timedelta(days=1);window_end=today+timedelta(days=1)
    rows=db.scalars(select(Guest).join(Stay,Stay.guest_id==Guest.id).where(Guest.lodge_id==lodge_id,Stay.status!="cancelled",Stay.arrival_date<=window_end,Stay.departure_date>=window_start).distinct().order_by(Guest.last_name,Guest.first_name)).all()
    return [{"id":str(g.id),"name":f"{g.first_name} {g.last_name}","dietary_requirements":g.dietary_requirements,"allergies":g.allergies} for g in rows if g.dietary_requirements or g.allergies]


@app.post("/api/v1/lodges/{lodge_id}/guests",dependencies=[Depends(require_csrf)])
def create_guest(lodge_id:str,body:GuestCreate,request:Request,user:User=Depends(require_permission("guests.manage",write=True)),db:Session=Depends(get_db)):
    if body.email:
        duplicate=db.scalar(select(Guest.id).where(Guest.lodge_id==lodge_id,func.lower(Guest.first_name)==body.first_name.strip().lower(),func.lower(Guest.last_name)==body.last_name.strip().lower(),func.lower(Guest.email)==str(body.email).lower()))
        if duplicate:raise HTTPException(409,"A guest with the same name and email already exists")
    g=Guest(lodge_id=lodge_id,first_name=body.first_name.strip(),last_name=body.last_name.strip(),email=str(body.email).lower() if body.email else None,phone=body.phone.strip(),nationality=body.nationality.strip(),vip=body.vip,dietary_requirements=body.dietary_requirements,allergies=body.allergies,preferences=body.preferences,notes=body.notes)
    db.add(g);db.flush();audit(db,request,g.lodge_id,user.id,"guest.created","guest",str(g.id));event(db,g.lodge_id,user.id,"guest.created","guest",str(g.id),f"Guest {g.first_name} {g.last_name} added to CRM");db.commit()
    return {"id":str(g.id),"first_name":g.first_name,"last_name":g.last_name,"name":f"{g.first_name} {g.last_name}","email":g.email,"phone":g.phone,"nationality":g.nationality,"vip":g.vip,"dietary_requirements":g.dietary_requirements,"allergies":g.allergies,"preferences":g.preferences,"notes":g.notes,"current_unit":None,"stay_status":None,"completed_stays":0}


@app.patch("/api/v1/lodges/{lodge_id}/guests/{record_id}",dependencies=[Depends(require_csrf)])
def update_guest(lodge_id:str,record_id:str,body:GuestUpdate,request:Request,user:User=Depends(require_permission("guests.manage",write=True)),db:Session=Depends(get_db)):
    g=tenant_get(db,Guest,record_id,lodge_id,"Guest")
    for f in ["first_name","last_name","email","phone","nationality","vip","dietary_requirements","allergies","preferences","notes"]:
        v=getattr(body,f)
        if v is not None:setattr(g,f,str(v).strip() if isinstance(v,str) else v)
    audit(db,request,g.lodge_id,user.id,"guest.updated","guest",str(g.id));db.commit()
    return {"id":str(g.id),"first_name":g.first_name,"last_name":g.last_name,"name":f"{g.first_name} {g.last_name}","email":g.email,"phone":g.phone,"nationality":g.nationality,"vip":g.vip,"dietary_requirements":g.dietary_requirements,"allergies":g.allergies,"preferences":g.preferences,"notes":g.notes}


@app.get("/api/v1/lodges/{lodge_id}/guests/{record_id}/export")
def export_guest_data(lodge_id:str,record_id:str,user:User=Depends(require_permission("guests.manage")),db:Session=Depends(get_db)):
    guest=tenant_get(db,Guest,record_id,lodge_id,"Guest")
    stays_rows=db.scalars(select(Stay).where(Stay.guest_id==guest.id).order_by(Stay.arrival_date)).all()
    requests_rows=db.scalars(select(GuestRequest).where(GuestRequest.guest_id==guest.id).order_by(GuestRequest.created_at)).all()
    return {"guest":{"id":str(guest.id),"first_name":guest.first_name,"last_name":guest.last_name,"email":guest.email,"phone":guest.phone,"nationality":guest.nationality,"vip":guest.vip,"dietary_requirements":guest.dietary_requirements,"allergies":guest.allergies,"preferences":guest.preferences,"notes":guest.notes},"stays":[{"id":str(x.id),"arrival_date":x.arrival_date.isoformat(),"departure_date":x.departure_date.isoformat(),"status":x.status,"unit_id":str(x.unit_id)} for x in stays_rows],"requests":[{"id":str(x.id),"type":x.request_type,"status":x.status,"description":x.description,"resolution":x.resolution} for x in requests_rows]}

@app.post("/api/v1/lodges/{lodge_id}/guests/{record_id}/anonymize",dependencies=[Depends(require_csrf)])
def anonymize_guest(lodge_id:str,record_id:str,request:Request,user:User=Depends(require_permission("guests.manage",write=True)),db:Session=Depends(get_db)):
    guest=tenant_get(db,Guest,record_id,lodge_id,"Guest")
    active=db.scalar(select(Stay.id).where(Stay.guest_id==guest.id,Stay.status.in_(["upcoming","arriving","in_house","departing"])).limit(1))
    if active:raise HTTPException(409,"Guest data cannot be anonymised while an active or upcoming stay exists")
    suffix=str(guest.id).split("-")[0];guest.first_name="Anonymised";guest.last_name=f"Guest {suffix}";guest.email=None;guest.phone="";guest.nationality="";guest.dietary_requirements="";guest.allergies="";guest.preferences="";guest.notes="";guest.vip=False
    audit(db,request,lodge_id,user.id,"guest.anonymized","guest",str(guest.id));event(db,lodge_id,user.id,"guest.anonymized","guest",str(guest.id),"Guest personal data anonymised under retention rules");db.commit();return {"id":str(guest.id),"anonymized":True}


# Stays
@app.get("/api/v1/lodges/{lodge_id}/stays")
def stays(lodge_id:str,limit:int=Query(50,ge=1,le=250),offset:int=Query(0,ge=0),user:User=Depends(require_permission("stays.view")),db:Session=Depends(get_db)):
    out=[]
    for s in db.scalars(select(Stay).where(Stay.lodge_id==lodge_id).order_by(Stay.arrival_date.desc()).offset(offset).limit(limit)).all():
        g=db.get(Guest,s.guest_id);u=db.get(Unit,s.unit_id)
        out.append({"id":str(s.id),"guest_id":str(s.guest_id),"guest_name":f"{g.first_name} {g.last_name}" if g else "","unit_id":str(s.unit_id),"unit_name":u.name if u else "","arrival_date":s.arrival_date.isoformat(),"departure_date":s.departure_date.isoformat(),"party_size":s.party_size,"status":s.status,"expected_arrival_time":s.expected_arrival_time,"expected_departure_time":s.expected_departure_time,"transfer_notes":s.transfer_notes,"special_requirements":s.special_requirements})
    return out


def check_unit_conflict(db:Session,lodge_id,unit_id,arrival,departure,exclude_id=None):
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{"key":f"{lodge_id}:unit:{unit_id}"})
    q=select(Stay).where(Stay.lodge_id==lodge_id,Stay.unit_id==unit_id,Stay.status!="cancelled",Stay.arrival_date<departure,Stay.departure_date>arrival)
    if exclude_id:q=q.where(Stay.id!=exclude_id)
    if db.scalar(q.limit(1)):
        raise HTTPException(409,"This unit already has an overlapping stay")


@app.post("/api/v1/lodges/{lodge_id}/stays",dependencies=[Depends(require_csrf)])
def create_stay(lodge_id:str,body:StayCreate,request:Request,user:User=Depends(require_permission("stays.manage",write=True)),db:Session=Depends(get_db)):
    ensure_fk(db,Guest,body.guest_id,lodge_id,"Guest");unit=ensure_fk(db,Unit,body.unit_id,lodge_id,"Unit")
    if unit.status in {"maintenance","out_of_service"}:raise HTTPException(409,"This unit is not available for a stay")
    check_unit_conflict(db,lodge_id,body.unit_id,body.arrival_date,body.departure_date)
    s=Stay(lodge_id=lodge_id,guest_id=body.guest_id,unit_id=body.unit_id,arrival_date=body.arrival_date,departure_date=body.departure_date,party_size=body.party_size,expected_arrival_time=body.expected_arrival_time,expected_departure_time=body.expected_departure_time,transfer_notes=body.transfer_notes,special_requirements=body.special_requirements,status="upcoming")
    db.add(s);db.flush();audit(db,request,s.lodge_id,user.id,"stay.created","stay",str(s.id));event(db,s.lodge_id,user.id,"stay.created","stay",str(s.id),f"Stay created for {s.arrival_date.isoformat()} to {s.departure_date.isoformat()}");db.commit()
    return {"id":str(s.id),"status":s.status}


STAY_TRANSITIONS={"upcoming":{"arriving","cancelled"},"arriving":{"in_house","cancelled"},"in_house":{"departing"},"departing":{"completed"},"completed":set(),"cancelled":set()}


@app.patch("/api/v1/lodges/{lodge_id}/stays/{record_id}",dependencies=[Depends(require_csrf)])
def update_stay(lodge_id:str,record_id:str,body:StayUpdate,request:Request,user:User=Depends(require_permission("stays.manage",write=True)),db:Session=Depends(get_db)):
    s=tenant_get(db,Stay,record_id,lodge_id,"Stay");data=body.model_dump(exclude_unset=True)
    new_unit_id=data.get("unit_id",s.unit_id);new_arrival=data.get("arrival_date",s.arrival_date);new_departure=data.get("departure_date",s.departure_date)
    if new_departure<new_arrival:raise HTTPException(422,"Departure date must be on or after arrival date")
    if s.status in {"in_house","departing","completed"} and ("unit_id" in data or "arrival_date" in data):raise HTTPException(409,"Unit and arrival date cannot be changed after check-in")
    unit=ensure_fk(db,Unit,new_unit_id,lodge_id,"Unit")
    if unit.status in {"maintenance","out_of_service"} and new_unit_id!=s.unit_id:raise HTTPException(409,"Unit is unavailable")
    if any(k in data for k in ["unit_id","arrival_date","departure_date"]):check_unit_conflict(db,lodge_id,new_unit_id,new_arrival,new_departure,s.id)
    s.unit_id=new_unit_id;s.arrival_date=new_arrival;s.departure_date=new_departure
    if "party_size" in data:s.party_size=data["party_size"]
    if body.status is not None and body.status!=s.status:
        if body.status not in STAY_TRANSITIONS.get(s.status,set()):raise HTTPException(409,f"Stay cannot transition from {s.status} to {body.status}")
        if body.status=="in_house":
            if unit.status in {"maintenance","out_of_service"}:raise HTTPException(409,"Unit is unavailable")
            unit.status="occupied"
        elif body.status=="completed": unit.status="cleaning"
        s.status=body.status;event(db,s.lodge_id,user.id,"stay.status_changed","stay",str(s.id),f"Stay status changed to {s.status}")
    for f in ["expected_arrival_time","expected_departure_time","transfer_notes","special_requirements"]:
        if f in data:setattr(s,f,data[f])
    audit(db,request,s.lodge_id,user.id,"stay.updated","stay",str(s.id));db.commit();return {"id":str(s.id),"status":s.status}


@app.get("/api/v1/lodges/{lodge_id}/stays/{record_id}/transfer-proposal")
def stay_transfer_proposal(lodge_id:str,record_id:str,user:User=Depends(require_permission("transfers.manage")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"transfers");stay=tenant_get(db,Stay,record_id,lodge_id,"Stay");lodge=db.get(Lodge,lodge_id)
    if not stay.transfer_notes.strip():raise HTTPException(404,"This stay has no transfer information to propose")
    notes=stay.transfer_notes.strip();lowered=notes.lower();kind="dropoff" if "depart" in lowered or "drop" in lowered else "pickup"
    return {"stay_id":str(stay.id),"guest_id":str(stay.guest_id),"transfer_type":kind,"scheduled_date":(stay.departure_date if kind=="dropoff" else stay.arrival_date).isoformat(),"pickup_location":(lodge.name if kind=="dropoff" and lodge else notes),"dropoff_location":(notes if kind=="dropoff" else (lodge.name if lodge else "Lodge")),"transfer_notes":notes,"requires_manager_confirmation":True}


# Tasks
@app.get("/api/v1/lodges/{lodge_id}/tasks")
def tasks(lodge_id:str,status:str|None=None,assignee_id:uuid.UUID|None=None,limit:int=Query(50,ge=1,le=250),offset:int=Query(0,ge=0),user:User=Depends(require_permission("tasks.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);q=select(Task).where(Task.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(Task.department_id==ctx.department_id)
    elif ctx.role_key in {"housekeeping","ranger","maintenance","driver","fb","general_staff"}:
        staff=_require_own_staff(ctx);q=q.where(Task.assigned_staff_id==staff.id)
    if status:q=q.where(Task.status==status)
    if assignee_id:q=q.where(Task.assigned_staff_id==assignee_id)
    out=[]
    for t in db.scalars(q.order_by(Task.created_at.desc()).offset(offset).limit(limit)).all():
        staff=db.get(StaffProfile,t.assigned_staff_id) if t.assigned_staff_id else None;dep=db.get(Department,t.department_id) if t.department_id else None;unit=db.get(Unit,t.unit_id) if t.unit_id else None
        out.append({"id":str(t.id),"title":t.title,"description":t.description,"department_id":str(t.department_id) if t.department_id else None,"department_name":dep.name if dep else None,"assigned_staff_id":str(t.assigned_staff_id) if t.assigned_staff_id else None,"assigned_staff_name":staff.full_name if staff else None,"unit_id":str(t.unit_id) if t.unit_id else None,"unit_name":unit.name if unit else None,"priority":t.priority,"status":t.status,"due_at":t.due_at.isoformat() if t.due_at else None,"accepted_at":t.accepted_at.isoformat() if t.accepted_at else None,"started_at":t.started_at.isoformat() if t.started_at else None,"completed_at":t.completed_at.isoformat() if t.completed_at else None,"recurrence_interval_days":t.recurrence_interval_days,"recurrence_end_date":t.recurrence_end_date.isoformat() if t.recurrence_end_date else None})
    return out

@app.post("/api/v1/lodges/{lodge_id}/tasks",dependencies=[Depends(require_csrf)])
def create_task(lodge_id:str,body:TaskCreate,request:Request,user:User=Depends(require_permission("tasks.manage",write=True)),db:Session=Depends(get_db)):
    if body.recurrence_interval_days or body.recurrence_end_date: ensure_feature(db,lodge_id,"advanced_tasks")
    if body.recurrence_interval_days and body.due_at is None: raise HTTPException(422,"Recurring tasks require a due date")
    ctx=_ctx(db,user,lodge_id);dep=ensure_fk(db,Department,body.department_id,lodge_id,"Department");staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile");ensure_fk(db,Guest,body.guest_id,lodge_id,"Guest");ensure_fk(db,Unit,body.unit_id,lodge_id,"Unit")
    department_id=_set_department_from_staff_or_context(ctx,staff,body.department_id)
    if staff and department_id and staff.department_id and str(staff.department_id)!=str(department_id):raise HTTPException(409,"Assigned staff member is not in the selected department")
    status="assigned" if body.assigned_staff_id else "created"
    t=Task(lodge_id=lodge_id,title=body.title.strip(),description=body.description,department_id=department_id,assigned_staff_id=body.assigned_staff_id,guest_id=body.guest_id,unit_id=body.unit_id,priority=body.priority,status=status,due_at=body.due_at,recurrence_interval_days=body.recurrence_interval_days,recurrence_end_date=body.recurrence_end_date,proof_required=body.proof_required,created_by_user_id=user.id)
    db.add(t);db.flush()
    if t.assigned_staff_id:
        recipient=staff_user_id(db,lodge_id,t.assigned_staff_id)
        create_notification(db,lodge_id=lodge_id,notification_type="task.assigned",severity="high" if t.priority in {"high","critical"} else "normal",title="Task assigned",body=t.title,resource_type="task",resource_id=t.id,dedupe_key=f"task-assigned:{t.id}:{t.assigned_staff_id}",recipient_user_ids=[recipient] if recipient else [])
    audit(db,request,t.lodge_id,user.id,"task.created","task",str(t.id));event(db,t.lodge_id,user.id,"task.created","task",str(t.id),f"Task created: {t.title}");db.commit();return {"id":str(t.id),"status":t.status}

TASK_TRANSITIONS={"created":{"assigned","cancelled"},"assigned":{"accepted","cancelled"},"accepted":{"started","cancelled"},"started":{"completed","cancelled"},"completed":set(),"cancelled":set()}

@app.patch("/api/v1/lodges/{lodge_id}/tasks/{record_id}",dependencies=[Depends(require_csrf)])
def update_task(lodge_id:str,record_id:str,body:TaskUpdate,request:Request,user:User=Depends(require_permission("tasks.view",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);t=tenant_get(db,Task,record_id,lodge_id,"Task");_ensure_department_scope(ctx,t.department_id,"task")
    full=_may(db,ctx,"tasks.manage");own=_may(db,ctx,"tasks.own.manage") and ctx.staff and t.assigned_staff_id==ctx.staff.id
    if not full and not own:raise HTTPException(403,"You may only update tasks assigned to you")
    if not full:
        if any(getattr(body,f) is not None for f in ["assigned_staff_id","department_id","priority","due_at","description","title","proof_required","recurrence_interval_days","recurrence_end_date"]):raise HTTPException(403,"Assigned staff can only transition their own task status")
        if body.status not in {"accepted","started","completed"}:raise HTTPException(403,"Assigned staff can only accept, start or complete their task")
    if body.assigned_staff_id is not None:
        staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile")
        dep=body.department_id or t.department_id
        _ensure_department_scope(ctx,dep,"task")
        if dep and staff.department_id and str(dep)!=str(staff.department_id):raise HTTPException(409,"Assigned staff member is not in the task department")
        changed_assignee=t.assigned_staff_id!=body.assigned_staff_id
        t.assigned_staff_id=body.assigned_staff_id
        if changed_assignee:
            t.status="assigned";t.accepted_at=None;t.started_at=None;t.completed_at=None
            recipient=staff_user_id(db,lodge_id,t.assigned_staff_id)
            create_notification(db,lodge_id=lodge_id,notification_type="task.assigned",severity="high" if t.priority in {"high","critical"} else "normal",title="Task assigned",body=t.title,resource_type="task",resource_id=t.id,dedupe_key=f"task-reassigned:{t.id}:{t.assigned_staff_id}:{datetime.now(timezone.utc).date()}",recipient_user_ids=[recipient] if recipient else [])
        elif t.status=="created":t.status="assigned"
    if body.department_id is not None:
        ensure_fk(db,Department,body.department_id,lodge_id,"Department");_ensure_department_scope(ctx,body.department_id,"task");t.department_id=body.department_id
    if body.status is not None and body.status!=t.status:
        if body.status not in TASK_TRANSITIONS.get(t.status,set()):raise HTTPException(409,f"Task cannot transition from {t.status} to {body.status}")
        t.status=body.status;now=datetime.now(timezone.utc)
        if t.status=="accepted":t.accepted_at=now
        elif t.status=="started":t.started_at=now
        elif t.status=="completed":
            required_open=db.scalar(select(func.count()).select_from(TaskChecklistItem).where(TaskChecklistItem.task_id==t.id,TaskChecklistItem.is_required.is_(True),TaskChecklistItem.completed_at.is_(None))) or 0
            if required_open: raise HTTPException(409,"Complete all required checklist items before completing this task")
            if t.proof_required and not db.scalar(select(TaskAttachment.id).where(TaskAttachment.task_id==t.id).limit(1)):raise HTTPException(409,"Proof attachment is required before completing this task")
            t.completed_at=now
            linked_request=db.scalar(select(GuestRequest).where(GuestRequest.task_id==t.id))
            if linked_request and linked_request.status not in {"resolved","cancelled"}:
                linked_request.status="resolved";linked_request.resolution=linked_request.resolution or "Resolved by linked task completion";linked_request.resolved_at=now
            if t.recurrence_interval_days and t.due_at:
                next_due=t.due_at+timedelta(days=t.recurrence_interval_days)
                if not t.recurrence_end_date or next_due.date()<=t.recurrence_end_date:
                    nxt=Task(lodge_id=t.lodge_id,title=t.title,description=t.description,department_id=t.department_id,assigned_staff_id=t.assigned_staff_id,guest_id=t.guest_id,unit_id=t.unit_id,priority=t.priority,status="assigned" if t.assigned_staff_id else "created",due_at=next_due,recurrence_interval_days=t.recurrence_interval_days,recurrence_end_date=t.recurrence_end_date,proof_required=t.proof_required,created_by_user_id=user.id)
                    db.add(nxt);db.flush()
                    for ci in db.scalars(select(TaskChecklistItem).where(TaskChecklistItem.task_id==t.id).order_by(TaskChecklistItem.position)).all():
                        db.add(TaskChecklistItem(lodge_id=t.lodge_id,task_id=nxt.id,label=ci.label,position=ci.position,is_required=ci.is_required))
                    event(db,t.lodge_id,user.id,"task.recurrence_created","task",str(nxt.id),f"Recurring task created from {t.title}")
        event(db,t.lodge_id,user.id,"task.status_changed","task",str(t.id),f"Task '{t.title}' changed to {t.status}")
    for f in ["title","priority","due_at","description","proof_required","recurrence_interval_days","recurrence_end_date"]:
        v=getattr(body,f)
        if v is not None:setattr(t,f,v)
    if t.recurrence_interval_days and not t.due_at: raise HTTPException(422,"Recurring tasks require a due date")
    audit(db,request,t.lodge_id,user.id,"task.updated","task",str(t.id));db.commit();return {"id":str(t.id),"status":t.status}


# Guest requests
@app.get("/api/v1/lodges/{lodge_id}/requests")
def requests_list(lodge_id:str,user:User=Depends(require_permission("requests.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);q=select(GuestRequest).where(GuestRequest.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(GuestRequest.department_id==ctx.department_id)
    elif ctx.role_key in {"housekeeping","fb"}:
        staff=_require_own_staff(ctx);q=q.where(or_(GuestRequest.assigned_staff_id==staff.id,GuestRequest.department_id==staff.department_id))
    elif ctx.role_key=="general_staff":
        staff=_require_own_staff(ctx);q=q.where(GuestRequest.assigned_staff_id==staff.id)
    out=[]
    for r in db.scalars(q.order_by(GuestRequest.created_at.desc())).all():
        g=db.get(Guest,r.guest_id);staff=db.get(StaffProfile,r.assigned_staff_id) if r.assigned_staff_id else None;dep=db.get(Department,r.department_id) if r.department_id else None
        out.append({"id":str(r.id),"guest_id":str(r.guest_id),"guest_name":f"{g.first_name} {g.last_name}" if g else "","stay_id":str(r.stay_id) if r.stay_id else None,"department_id":str(r.department_id) if r.department_id else None,"department_name":dep.name if dep else None,"assigned_staff_id":str(r.assigned_staff_id) if r.assigned_staff_id else None,"assigned_staff_name":staff.full_name if staff else None,"task_id":str(r.task_id) if r.task_id else None,"request_type":r.request_type,"description":r.description,"priority":r.priority,"status":r.status,"resolution":r.resolution,"created_at":r.created_at.isoformat()})
    return out

@app.post("/api/v1/lodges/{lodge_id}/requests",dependencies=[Depends(require_csrf)])
def create_request(lodge_id:str,body:GuestRequestCreate,request:Request,user:User=Depends(require_permission("requests.manage",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);ensure_fk(db,Guest,body.guest_id,lodge_id,"Guest");ensure_fk(db,Stay,body.stay_id,lodge_id,"Stay");ensure_fk(db,Department,body.department_id,lodge_id,"Department");staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile")
    department_id=_set_department_from_staff_or_context(ctx,staff,body.department_id)
    if staff and department_id and staff.department_id and str(staff.department_id)!=str(department_id):raise HTTPException(409,"Assigned staff member is not in the selected department")
    status="assigned" if body.assigned_staff_id else "open"
    r=GuestRequest(lodge_id=lodge_id,guest_id=body.guest_id,stay_id=body.stay_id,department_id=department_id,assigned_staff_id=body.assigned_staff_id,request_type=body.request_type.strip(),description=body.description.strip(),priority=body.priority,status=status,created_by_user_id=user.id)
    db.add(r);db.flush()
    if r.assigned_staff_id:
        recipient=staff_user_id(db,lodge_id,r.assigned_staff_id)
        create_notification(db,lodge_id=lodge_id,notification_type="guest_request.assigned",severity="high" if r.priority in {"high","critical"} else "normal",title="Guest request assigned",body=r.description[:240],resource_type="guest_request",resource_id=r.id,dedupe_key=f"request-assigned:{r.id}:{r.assigned_staff_id}",recipient_user_ids=[recipient] if recipient else [])
    audit(db,request,r.lodge_id,user.id,"guest_request.created","guest_request",str(r.id));event(db,r.lodge_id,user.id,"guest_request.created","guest_request",str(r.id),f"Guest request created: {r.request_type}");db.commit();return {"id":str(r.id),"status":r.status}

REQUEST_TRANSITIONS={"open":{"assigned","in_progress","cancelled"},"assigned":{"in_progress","waiting","cancelled"},"in_progress":{"waiting","resolved","cancelled"},"waiting":{"in_progress","resolved","cancelled"},"resolved":set(),"cancelled":set()}

@app.patch("/api/v1/lodges/{lodge_id}/requests/{record_id}",dependencies=[Depends(require_csrf)])
def update_request(lodge_id:str,record_id:str,body:GuestRequestUpdate,request:Request,user:User=Depends(require_permission("requests.view",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);r=tenant_get(db,GuestRequest,record_id,lodge_id,"Guest request");_ensure_department_scope(ctx,r.department_id,"guest request")
    full=_may(db,ctx,"requests.manage")
    if ctx.role_key=="general_staff":
        own=_may(db,ctx,"requests.own.manage") and ctx.staff and r.assigned_staff_id==ctx.staff.id
    else:
        own=_may(db,ctx,"requests.own.manage") and ctx.staff and (r.assigned_staff_id==ctx.staff.id or (r.assigned_staff_id is None and r.department_id==ctx.staff.department_id))
    if not full and not own:raise HTTPException(403,"You may only update guest requests relevant to you")
    if not full and any(getattr(body,f) is not None for f in ["department_id","assigned_staff_id","description","priority"]):raise HTTPException(403,"Assigned staff cannot change request ownership, description or priority")
    if body.department_id is not None:ensure_fk(db,Department,body.department_id,lodge_id,"Department");_ensure_department_scope(ctx,body.department_id,"guest request");r.department_id=body.department_id
    if body.assigned_staff_id is not None:
        staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile")
        if r.department_id and staff.department_id and str(r.department_id)!=str(staff.department_id):raise HTTPException(409,"Assigned staff member is not in the request department")
        r.assigned_staff_id=body.assigned_staff_id
        if r.status=="open":r.status="assigned"
        recipient=staff_user_id(db,lodge_id,r.assigned_staff_id)
        create_notification(db,lodge_id=lodge_id,notification_type="guest_request.assigned",severity="high" if r.priority in {"high","critical"} else "normal",title="Guest request assigned",body=r.description[:240],resource_type="guest_request",resource_id=r.id,dedupe_key=f"request-assigned:{r.id}:{r.assigned_staff_id}",recipient_user_ids=[recipient] if recipient else [])
    if body.status is not None and body.status!=r.status:
        if body.status not in REQUEST_TRANSITIONS.get(r.status,set()):raise HTTPException(409,f"Request cannot transition from {r.status} to {body.status}")
        if not full and body.status not in {"in_progress","waiting","resolved"}:raise HTTPException(403,"Assigned staff cannot perform that request transition")
        if body.status=="resolved" and not (body.resolution or r.resolution):raise HTTPException(422,"Resolution notes are required before resolving a guest request")
        r.status=body.status
        if r.status=="resolved":
            r.resolved_at=datetime.now(timezone.utc)
            if r.task_id:
                linked=db.get(Task,r.task_id)
                if linked and linked.status not in {"completed","cancelled"}:
                    required_open=db.scalar(select(func.count()).select_from(TaskChecklistItem).where(TaskChecklistItem.task_id==linked.id,TaskChecklistItem.is_required.is_(True),TaskChecklistItem.completed_at.is_(None))) or 0
                    if required_open:raise HTTPException(409,"Complete the linked task checklist before resolving this request")
                    if linked.proof_required and not db.scalar(select(TaskAttachment.id).where(TaskAttachment.task_id==linked.id).limit(1)):raise HTTPException(409,"Linked task requires proof before this request can be resolved")
                    linked.status="completed";linked.completed_at=r.resolved_at
        event(db,r.lodge_id,user.id,"guest_request.status_changed","guest_request",str(r.id),f"Guest request changed to {r.status}")
    if body.description is not None:r.description=body.description.strip()
    if body.priority is not None:r.priority=body.priority
    if body.resolution is not None:r.resolution=body.resolution
    audit(db,request,r.lodge_id,user.id,"guest_request.updated","guest_request",str(r.id));db.commit();return {"id":str(r.id),"status":r.status}

@app.post("/api/v1/lodges/{lodge_id}/requests/{record_id}/create-task",dependencies=[Depends(require_csrf)])
def request_to_task(lodge_id:str,record_id:str,request:Request,user:User=Depends(require_permission("requests.manage",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);r=tenant_get(db,GuestRequest,record_id,lodge_id,"Guest request");_ensure_department_scope(ctx,r.department_id,"guest request")
    if r.task_id:raise HTTPException(409,"This guest request already has a task")
    t=Task(lodge_id=lodge_id,title=f"Guest request: {r.request_type}",description=r.description,department_id=r.department_id,assigned_staff_id=r.assigned_staff_id,guest_id=r.guest_id,priority=r.priority,status="assigned" if r.assigned_staff_id else "created",created_by_user_id=user.id)
    db.add(t);db.flush();r.task_id=t.id
    audit(db,request,r.lodge_id,user.id,"guest_request.task_created","guest_request",str(r.id));event(db,r.lodge_id,user.id,"guest_request.task_created","guest_request",str(r.id),f"Task created from guest request: {r.request_type}");db.commit();return {"task_id":str(t.id)}


# Maintenance
@app.get("/api/v1/lodges/{lodge_id}/maintenance")
def maintenance_list(lodge_id:str,user:User=Depends(require_permission("maintenance.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);q=select(MaintenanceTicket).where(MaintenanceTicket.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(MaintenanceTicket.department_id==ctx.department_id)
    elif ctx.role_key in {"housekeeping","ranger","driver","general_staff"}:
        staff=ctx.staff;q=q.where(or_(MaintenanceTicket.created_by_user_id==user.id,MaintenanceTicket.assigned_staff_id==(staff.id if staff else None)))
    out=[]
    for m in db.scalars(q.order_by(MaintenanceTicket.created_at.desc())).all():
        unit=db.get(Unit,m.unit_id) if m.unit_id else None;staff=db.get(StaffProfile,m.assigned_staff_id) if m.assigned_staff_id else None;vehicle=db.get(Vehicle,m.vehicle_id) if m.vehicle_id else None;dep=db.get(Department,m.department_id) if m.department_id else None
        out.append({"id":str(m.id),"title":m.title,"description":m.description,"category":m.category,"priority":m.priority,"status":m.status,"department_id":str(m.department_id) if m.department_id else None,"department_name":dep.name if dep else None,"unit_id":str(m.unit_id) if m.unit_id else None,"unit_name":unit.name if unit else None,"vehicle_id":str(m.vehicle_id) if m.vehicle_id else None,"vehicle_name":(vehicle.name or vehicle.registration) if vehicle else None,"assigned_staff_id":str(m.assigned_staff_id) if m.assigned_staff_id else None,"assigned_staff_name":staff.full_name if staff else None,"cost_cents":m.cost_cents,"asset_id":str(m.asset_id) if m.asset_id else None,"scheduled_for":m.scheduled_for.isoformat() if m.scheduled_for else None,"downtime_started_at":m.downtime_started_at.isoformat() if m.downtime_started_at else None,"downtime_ended_at":m.downtime_ended_at.isoformat() if m.downtime_ended_at else None,"recurrence_interval_days":m.recurrence_interval_days,"resolution":m.resolution,"created_at":m.created_at.isoformat()})
    return out

@app.post("/api/v1/lodges/{lodge_id}/maintenance",dependencies=[Depends(require_csrf)])
def create_maintenance(lodge_id:str,body:MaintenanceCreate,request:Request,user:User=Depends(require_permission("maintenance.view",write=True)),db:Session=Depends(get_db)):
    if body.asset_id or body.scheduled_for or body.recurrence_interval_days: ensure_feature(db,lodge_id,"maintenance_workshop")
    ctx=_ctx(db,user,lodge_id);full=_may(db,ctx,"maintenance.manage");report=_may(db,ctx,"maintenance.report")
    if not full and not report:raise HTTPException(403,"Your role cannot report maintenance issues")
    unit=ensure_fk(db,Unit,body.unit_id,lodge_id,"Unit");vehicle=ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle");ensure_fk(db,MaintenanceAsset,body.asset_id,lodge_id,"Maintenance asset");staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile")
    if not full and body.assigned_staff_id is not None:raise HTTPException(403,"Issue reporters cannot assign maintenance work")
    department_id=_set_department_from_staff_or_context(ctx,staff,body.department_id)
    status="assigned" if body.assigned_staff_id else "open"
    m=MaintenanceTicket(lodge_id=lodge_id,title=body.title.strip(),description=body.description,category=body.category.strip(),priority=body.priority,status=status,department_id=department_id,unit_id=body.unit_id,asset_id=body.asset_id,vehicle_id=body.vehicle_id,assigned_staff_id=body.assigned_staff_id,scheduled_for=body.scheduled_for,recurrence_interval_days=body.recurrence_interval_days,created_by_user_id=user.id)
    db.add(m);db.flush();audit(db,request,m.lodge_id,user.id,"maintenance.created","maintenance",str(m.id));event(db,m.lodge_id,user.id,"maintenance.created","maintenance",str(m.id),f"Maintenance ticket created: {m.title}")
    maintenance_opened(db,unit,vehicle,body.priority=="critical")
    db.commit();return {"id":str(m.id),"status":m.status}

MAINT_TRANSITIONS={"open":{"assigned","in_progress","cancelled"},"assigned":{"in_progress","waiting","cancelled"},"in_progress":{"waiting","completed","cancelled"},"waiting":{"in_progress","completed","cancelled"},"completed":set(),"cancelled":set()}

@app.patch("/api/v1/lodges/{lodge_id}/maintenance/{record_id}",dependencies=[Depends(require_csrf)])
def update_maintenance(lodge_id:str,record_id:str,body:MaintenanceUpdate,request:Request,user:User=Depends(require_permission("maintenance.view",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);m=tenant_get(db,MaintenanceTicket,record_id,lodge_id,"Maintenance ticket");_ensure_department_scope(ctx,m.department_id,"maintenance ticket")
    full=_may(db,ctx,"maintenance.manage");own=ctx.staff and m.assigned_staff_id==ctx.staff.id
    if not full and not own:raise HTTPException(403,"You may only update maintenance assigned to you")
    if not full and any(getattr(body,f) is not None for f in ["assigned_staff_id","title","description","category","department_id","unit_id","asset_id","vehicle_id"]):raise HTTPException(403,"Assigned staff cannot change maintenance ownership or ticket structure")
    if body.department_id is not None:ensure_fk(db,Department,body.department_id,lodge_id,"Department");_ensure_department_scope(ctx,body.department_id,"maintenance ticket");m.department_id=body.department_id
    if body.unit_id is not None:ensure_fk(db,Unit,body.unit_id,lodge_id,"Unit");m.unit_id=body.unit_id
    if body.vehicle_id is not None:ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle");m.vehicle_id=body.vehicle_id
    if body.asset_id is not None:ensure_fk(db,MaintenanceAsset,body.asset_id,lodge_id,"Maintenance asset");m.asset_id=body.asset_id
    for f in ["title","description","category"]:
        v=getattr(body,f)
        if v is not None:setattr(m,f,v.strip())
    if body.assigned_staff_id is not None:
        staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile")
        if m.department_id and staff.department_id and str(m.department_id)!=str(staff.department_id):raise HTTPException(409,"Assigned staff member is not in the maintenance department")
        m.assigned_staff_id=body.assigned_staff_id
    if body.status is not None and body.status!=m.status:
        if body.status not in MAINT_TRANSITIONS.get(m.status,set()):raise HTTPException(409,f"Maintenance ticket cannot transition from {m.status} to {body.status}")
        if body.status=="completed" and not (body.resolution or m.resolution):raise HTTPException(422,"Resolution notes are required before completing maintenance")
        m.status=body.status
        now=datetime.now(timezone.utc)
        if m.status=="in_progress" and not m.downtime_started_at:m.downtime_started_at=now
        if m.status in {"completed","cancelled"}:
            if m.status=="completed":m.completed_at=now
            m.downtime_ended_at=now if m.downtime_started_at else m.downtime_ended_at
            maintenance_released(db,db.get(Unit,m.unit_id) if m.unit_id else None,db.get(Vehicle,m.vehicle_id) if m.vehicle_id else None)
        if m.status=="completed":
            if m.recurrence_interval_days:
                next_when=(m.scheduled_for or now)+timedelta(days=m.recurrence_interval_days)
                follow=MaintenanceTicket(lodge_id=m.lodge_id,title=m.title,description=m.description,category=m.category,priority=m.priority,status="open",department_id=m.department_id,unit_id=m.unit_id,asset_id=m.asset_id,vehicle_id=m.vehicle_id,scheduled_for=next_when,recurrence_interval_days=m.recurrence_interval_days,created_by_user_id=user.id)
                db.add(follow);db.flush();event(db,m.lodge_id,user.id,"maintenance.recurrence_created","maintenance",str(follow.id),f"Recurring maintenance scheduled: {m.title}")
        event(db,m.lodge_id,user.id,"maintenance.status_changed","maintenance",str(m.id),f"Maintenance '{m.title}' changed to {m.status}")
    for f in ["priority","resolution","cost_cents","scheduled_for","recurrence_interval_days"]:
        v=getattr(body,f)
        if v is not None:
            if not full and f in {"priority","cost_cents"}:raise HTTPException(403,"Assigned staff cannot change maintenance priority or cost")
            setattr(m,f,v)
    audit(db,request,m.lodge_id,user.id,"maintenance.updated","maintenance",str(m.id));db.commit();return {"id":str(m.id),"status":m.status}

# --- Safari operations: production workflows ---
PACKAGE_LEVEL={"Basic":1,"Standard":2,"Premium":3}

def ensure_package(db:Session,lodge_id:str,minimum:str):
    # Backward-compatible guard for any remaining routes; new code should use named entitlements.
    sub=db.get(Subscription,lodge_id)
    if not sub or PACKAGE_LEVEL.get(sub.package,0)<PACKAGE_LEVEL[minimum]:raise HTTPException(403,f"This feature requires the {minimum} package or higher")

def _name_staff(db, sid):
    s=db.get(StaffProfile,sid) if sid else None
    return s.full_name if s else None

def _name_vehicle(db, vid):
    v=db.get(Vehicle,vid) if vid else None
    return (v.name or v.registration) if v else None

def _assert_staff_operational(staff:StaffProfile,label="Staff member"):
    if staff.employment_status!="active" or staff.operational_status in {"leave","off_duty"}:
        raise HTTPException(409,f"{label} is not operationally available")

def _lock_schedule_resources(db:Session,lodge_id,*resources):
    keys=sorted({f"{lodge_id}:{kind}:{rid}" for kind,rid in resources if rid})
    for key in keys:db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{"key":key})

def _activity_conflicts(db:Session,lodge_id,starts,ends,guide_id=None,vehicle_id=None,exclude_id=None):
    _lock_schedule_resources(db,lodge_id,("staff",guide_id),("vehicle",vehicle_id))
    q=select(Activity).where(Activity.lodge_id==lodge_id,Activity.status.notin_(["completed","cancelled"]),Activity.starts_at < ends,Activity.ends_at > starts)
    if exclude_id:q=q.where(Activity.id!=exclude_id)
    conflicts=db.scalars(q).all()
    for x in conflicts:
        if guide_id and x.guide_staff_id==guide_id: raise HTTPException(409,"Guide/ranger already has an overlapping activity")
        if vehicle_id and x.vehicle_id==vehicle_id: raise HTTPException(409,"Vehicle already has an overlapping activity")
    tq=select(Transfer).where(Transfer.lodge_id==lodge_id,Transfer.status.notin_(["completed","cancelled"]),Transfer.scheduled_at < ends,Transfer.expected_end_at > starts)
    for x in db.scalars(tq).all():
        if guide_id and x.driver_staff_id==guide_id: raise HTTPException(409,"Staff member already has an overlapping transfer")
        if vehicle_id and x.vehicle_id==vehicle_id: raise HTTPException(409,"Vehicle already has an overlapping transfer")

def _transfer_conflicts(db:Session,lodge_id,starts,ends,driver_id=None,vehicle_id=None,exclude_id=None):
    _lock_schedule_resources(db,lodge_id,("staff",driver_id),("vehicle",vehicle_id))
    q=select(Transfer).where(Transfer.lodge_id==lodge_id,Transfer.status.notin_(["completed","cancelled"]),Transfer.scheduled_at < ends,Transfer.expected_end_at > starts)
    if exclude_id:q=q.where(Transfer.id!=exclude_id)
    for x in db.scalars(q).all():
        if driver_id and x.driver_staff_id==driver_id: raise HTTPException(409,"Driver already has an overlapping transfer")
        if vehicle_id and x.vehicle_id==vehicle_id: raise HTTPException(409,"Vehicle already has an overlapping transfer")
    aq=select(Activity).where(Activity.lodge_id==lodge_id,Activity.status.notin_(["completed","cancelled"]),Activity.starts_at < ends,Activity.ends_at > starts)
    for x in db.scalars(aq).all():
        if driver_id and x.guide_staff_id==driver_id: raise HTTPException(409,"Staff member already has an overlapping activity")
        if vehicle_id and x.vehicle_id==vehicle_id: raise HTTPException(409,"Vehicle already has an overlapping activity")

@app.get("/api/v1/lodges/{lodge_id}/vehicles")
def list_vehicles(lodge_id:str,user:User=Depends(require_permission("vehicles.view")),db:Session=Depends(get_db)):
    rows=db.scalars(select(Vehicle).where(Vehicle.lodge_id==lodge_id).order_by(Vehicle.registration)).all()
    return [{"id":str(v.id),"registration":v.registration,"name":v.name,"make":v.make,"model":v.model,"year":v.year,"odometer_km":v.odometer_km,"fuel_capacity_litres":float(v.fuel_capacity_litres) if v.fuel_capacity_litres is not None else None,"fuel_level_percent":v.fuel_level_percent,"status":v.status,"service_due_odometer_km":v.service_due_odometer_km,"service_due_in_km":(v.service_due_odometer_km-v.odometer_km) if v.service_due_odometer_km is not None else None,"notes":v.notes} for v in rows]

@app.post("/api/v1/lodges/{lodge_id}/vehicles",dependencies=[Depends(require_csrf)])
def create_vehicle(lodge_id:str,body:VehicleCreate,request:Request,user:User=Depends(require_permission("vehicles.manage",write=True)),db:Session=Depends(get_db)):
    v=Vehicle(lodge_id=lodge_id,**body.model_dump())
    db.add(v);db.flush();audit(db,request,v.lodge_id,user.id,"vehicle.created","vehicle",str(v.id));event(db,v.lodge_id,user.id,"vehicle.created","vehicle",str(v.id),f"Vehicle {v.registration} added to fleet");commit_or_conflict(db,"A vehicle with this registration already exists")
    return {"id":str(v.id),"registration":v.registration,"status":v.status}

@app.patch("/api/v1/lodges/{lodge_id}/vehicles/{record_id}",dependencies=[Depends(require_csrf)])
def update_vehicle(lodge_id:str,record_id:str,body:VehicleUpdate,request:Request,user:User=Depends(require_permission("vehicles.manage",write=True)),db:Session=Depends(get_db)):
    v=tenant_get(db,Vehicle,record_id,lodge_id,"Vehicle")
    data=body.model_dump(exclude_unset=True)
    if "odometer_km" in data and data["odometer_km"] < v.odometer_km and not (data.get("odometer_correction_reason") or "").strip(): raise HTTPException(422,"A correction reason is required when reducing the odometer")
    correction_reason=data.pop("odometer_correction_reason",None)
    for k,val in data.items():setattr(v,k,val)
    if v.fuel_level_percent is not None and v.fuel_level_percent<20:
        recipients=user_ids_with_permission(db,lodge_id,"vehicles.manage")
        create_notification(db,lodge_id=lodge_id,notification_type="vehicle.low_fuel",severity="high",title="Low fuel",body=f"{v.registration} fuel level is {v.fuel_level_percent}%",resource_type="vehicle",resource_id=v.id,dedupe_key=f"low-fuel:{v.id}:{v.fuel_level_percent//5}",recipient_user_ids=recipients)
    audit(db,request,v.lodge_id,user.id,"vehicle.updated","vehicle",str(v.id),correction_reason or "");event(db,v.lodge_id,user.id,"vehicle.updated","vehicle",str(v.id),f"Vehicle {v.registration} updated");db.commit()
    return {"id":str(v.id),"registration":v.registration,"status":v.status,"odometer_km":v.odometer_km}

@app.get("/api/v1/lodges/{lodge_id}/vehicle-checklists")
def list_vehicle_checklists(lodge_id:str,user:User=Depends(require_permission("vehicle_checklists.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"vehicle_checklists")
    ctx=_ctx(db,user,lodge_id);q=select(VehicleChecklist).where(VehicleChecklist.lodge_id==lodge_id)
    if ctx.role_key in {"ranger","driver"}:
        staff=_require_own_staff(ctx);q=q.where(VehicleChecklist.performed_by_staff_id==staff.id)
    rows=db.scalars(q.order_by(VehicleChecklist.created_at.desc()).limit(200)).all()
    return [{"id":str(c.id),"vehicle_id":str(c.vehicle_id),"vehicle_name":_name_vehicle(db,c.vehicle_id),"performed_by_staff_id":str(c.performed_by_staff_id),"performed_by":_name_staff(db,c.performed_by_staff_id),"checklist_type":c.checklist_type,"status":c.status,"odometer_km":c.odometer_km,"notes":c.notes,"started_at":c.started_at.isoformat(),"completed_at":c.completed_at.isoformat() if c.completed_at else None,"items":[{"item_key":i.item_key,"label":i.label,"result":i.result,"notes":i.notes} for i in db.scalars(select(VehicleChecklistItem).where(VehicleChecklistItem.checklist_id==c.id)).all()]} for c in rows]

@app.post("/api/v1/lodges/{lodge_id}/vehicle-checklists",dependencies=[Depends(require_csrf)])
def create_vehicle_checklist(lodge_id:str,body:VehicleChecklistCreate,request:Request,user:User=Depends(require_permission("vehicle_checklists.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"vehicle_checklists")
    ctx=_ctx(db,user,lodge_id);v=ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle");staff=ensure_fk(db,StaffProfile,body.performed_by_staff_id,lodge_id,"Staff member");_assert_staff_operational(staff)
    if ctx.role_key in {"ranger","driver"} and (not ctx.staff or staff.id!=ctx.staff.id):raise HTTPException(403,"You can only submit your own vehicle checklist")
    if body.odometer_km is not None and body.odometer_km < v.odometer_km: raise HTTPException(409,"Checklist odometer cannot be lower than vehicle odometer")
    if body.checklist_type=="pre_drive":
        mandatory={"brakes","tyres","lights","fuel","water","first_aid","recovery_gear"};provided={i.item_key for i in body.items}
        missing=sorted(mandatory-provided)
        if missing:raise HTTPException(422,"Missing mandatory safety checks: "+", ".join(missing))
        unsafe=[i.item_key for i in body.items if i.item_key in mandatory and i.result!="pass"]
        if unsafe:raise HTTPException(409,"Mandatory safety checks must pass: "+", ".join(sorted(unsafe)))
    c=VehicleChecklist(lodge_id=lodge_id,vehicle_id=v.id,performed_by_staff_id=staff.id,checklist_type=body.checklist_type,status="in_progress",odometer_km=body.odometer_km,notes=body.notes,started_at=datetime.now(timezone.utc))
    db.add(c);db.flush();failed=[]
    for item in body.items:
        db.add(VehicleChecklistItem(lodge_id=lodge_id,checklist_id=c.id,**item.model_dump()))
        if item.result=="fail":failed.append(item.label)
    c.status="failed" if failed else "passed";c.completed_at=datetime.now(timezone.utc)
    if body.odometer_km is not None:v.odometer_km=max(v.odometer_km,body.odometer_km)
    if failed:
        v.status="maintenance"
        mt=MaintenanceTicket(lodge_id=lodge_id,title=f"Vehicle checklist failed — {v.registration}",description="Failed checks: "+", ".join(failed),category="vehicle",priority="high",status="open",vehicle_id=v.id,created_by_user_id=user.id)
        db.add(mt);db.flush();event(db,lodge_id,user.id,"maintenance.created","maintenance",str(mt.id),f"Maintenance ticket created from failed checklist for {v.registration}")
    audit(db,request,lodge_id,user.id,"vehicle_checklist.completed","vehicle_checklist",str(c.id),f"Result: {c.status}");event(db,lodge_id,user.id,"vehicle_checklist.completed","vehicle_checklist",str(c.id),f"{body.checklist_type.replace('_',' ').title()} {c.status} for {v.registration}");db.commit()
    return {"id":str(c.id),"status":c.status,"vehicle_status":v.status,"maintenance_created":bool(failed)}

@app.get("/api/v1/lodges/{lodge_id}/fuel")
def list_fuel(lodge_id:str,user:User=Depends(require_permission("fuel.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"fuel")
    ctx=_ctx(db,user,lodge_id);q=select(FuelRecord).where(FuelRecord.lodge_id==lodge_id)
    if ctx.role_key in {"ranger","driver"}:
        staff=_require_own_staff(ctx);q=q.where(FuelRecord.recorded_by_staff_id==staff.id)
    rows=db.scalars(q.order_by(FuelRecord.recorded_at.desc()).limit(500)).all()
    return [{"id":str(r.id),"vehicle_id":str(r.vehicle_id),"vehicle_name":_name_vehicle(db,r.vehicle_id),"recorded_by_staff_id":str(r.recorded_by_staff_id) if r.recorded_by_staff_id else None,"recorded_by":_name_staff(db,r.recorded_by_staff_id),"litres":float(r.litres),"odometer_km":r.odometer_km,"cost_cents":r.cost_cents,"supplier":r.supplier,"reference":r.reference,"notes":r.notes,"recorded_at":r.recorded_at.isoformat()} for r in rows]

@app.post("/api/v1/lodges/{lodge_id}/fuel",dependencies=[Depends(require_csrf)])
def create_fuel(lodge_id:str,body:FuelCreate,request:Request,user:User=Depends(require_permission("fuel.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"fuel")
    ctx=_ctx(db,user,lodge_id);v=ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle")
    recorder=ensure_fk(db,StaffProfile,body.recorded_by_staff_id,lodge_id,"Staff member") if body.recorded_by_staff_id else None
    if ctx.role_key in {"ranger","driver"}:
        own=_require_own_staff(ctx)
        if recorder and recorder.id!=own.id:raise HTTPException(403,"You can only record fuel under your own staff profile")
        recorder=own
    if body.odometer_km < v.odometer_km: raise HTTPException(409,"Fuel record odometer cannot be lower than the vehicle odometer")
    if v.fuel_capacity_litres is not None and body.litres>float(v.fuel_capacity_litres):raise HTTPException(422,"Fuel litres cannot exceed the vehicle tank capacity")
    r=FuelRecord(lodge_id=lodge_id,vehicle_id=v.id,recorded_by_staff_id=recorder.id if recorder else body.recorded_by_staff_id,litres=body.litres,odometer_km=body.odometer_km,cost_cents=body.cost_cents,supplier=body.supplier,reference=body.reference,notes=body.notes,recorded_at=body.recorded_at or datetime.now(timezone.utc),created_by_user_id=user.id)
    db.add(r);v.odometer_km=body.odometer_km;db.flush();audit(db,request,lodge_id,user.id,"fuel.recorded","fuel_record",str(r.id));event(db,lodge_id,user.id,"fuel.recorded","vehicle",str(v.id),f"{body.litres:g} L fuel recorded for {v.registration}");db.commit()
    return {"id":str(r.id),"vehicle_id":str(v.id),"odometer_km":v.odometer_km}

@app.get("/api/v1/lodges/{lodge_id}/activities")
def list_activities(lodge_id:str,user:User=Depends(require_permission("activities.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"activities")
    ctx=_ctx(db,user,lodge_id);q=select(Activity).where(Activity.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(Activity.department_id==ctx.department_id)
    elif ctx.role_key=="ranger":q=q.where(Activity.guide_staff_id==_require_own_staff(ctx).id)
    rows=db.scalars(q.order_by(Activity.starts_at.desc()).limit(500)).all();out=[];show_guests=ctx.role_key not in {"general_staff","fb"}
    for a in rows:
        ag=db.scalars(select(ActivityGuest).where(ActivityGuest.activity_id==a.id)).all();guest_ids=[x.guest_id for x in ag];guests={g.id:f"{g.first_name} {g.last_name}" for g in db.scalars(select(Guest).where(Guest.id.in_(guest_ids))).all()} if guest_ids else {}
        out.append({"id":str(a.id),"activity_type":a.activity_type,"title":a.title,"starts_at":a.starts_at.isoformat(),"ends_at":a.ends_at.isoformat(),"guide_staff_id":str(a.guide_staff_id) if a.guide_staff_id else None,"guide_name":_name_staff(db,a.guide_staff_id),"vehicle_id":str(a.vehicle_id) if a.vehicle_id else None,"vehicle_name":_name_vehicle(db,a.vehicle_id),"requires_vehicle":a.requires_vehicle,"status":a.status,"meeting_point":a.meeting_point,"notes":a.notes,"guests":[{"id":str(x.guest_id),"name":guests.get(x.guest_id,"")} for x in ag] if show_guests else []})
    return out

@app.post("/api/v1/lodges/{lodge_id}/activities",dependencies=[Depends(require_csrf)])
def create_activity(lodge_id:str,body:ActivityCreate,request:Request,user:User=Depends(require_permission("activities.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"activities")
    ctx=_ctx(db,user,lodge_id);guide=ensure_fk(db,StaffProfile,body.guide_staff_id,lodge_id,"Guide/ranger") if body.guide_staff_id else None
    vehicle=ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle") if body.vehicle_id else None
    if guide:_assert_staff_operational(guide,"Guide/ranger")
    if vehicle and vehicle.status in {"maintenance","out_of_service"}: raise HTTPException(409,"Vehicle is not available for an activity")
    for gid in body.guest_ids:
        ensure_fk(db,Guest,gid,lodge_id,"Guest");_lock_schedule_resources(db,lodge_id,("guest",gid))
        overlap=db.scalar(select(ActivityGuest.activity_id).join(Activity,Activity.id==ActivityGuest.activity_id).where(ActivityGuest.guest_id==gid,Activity.lodge_id==lodge_id,Activity.status.notin_(["completed","cancelled"]),Activity.starts_at<body.ends_at,Activity.ends_at>body.starts_at).limit(1))
        if overlap:raise HTTPException(409,"A guest is already assigned to an overlapping activity")
    _activity_conflicts(db,lodge_id,body.starts_at,body.ends_at,body.guide_staff_id,body.vehicle_id)
    department_id=_set_department_from_staff_or_context(ctx,guide,body.department_id)
    a=Activity(lodge_id=lodge_id,activity_type=body.activity_type,title=body.title,starts_at=body.starts_at,ends_at=body.ends_at,guide_staff_id=body.guide_staff_id,department_id=department_id,vehicle_id=body.vehicle_id,requires_vehicle=body.requires_vehicle,meeting_point=body.meeting_point,notes=body.notes,created_by_user_id=user.id)
    db.add(a);db.flush()
    for gid in dict.fromkeys(body.guest_ids):db.add(ActivityGuest(activity_id=a.id,guest_id=gid,lodge_id=lodge_id))
    audit(db,request,lodge_id,user.id,"activity.created","activity",str(a.id));event(db,lodge_id,user.id,"activity.created","activity",str(a.id),f"Activity {a.title} scheduled");db.commit();return {"id":str(a.id),"status":a.status}

@app.patch("/api/v1/lodges/{lodge_id}/activities/{record_id}",dependencies=[Depends(require_csrf)])
def update_activity(lodge_id:str,record_id:str,body:ActivityUpdate,request:Request,user:User=Depends(require_permission("activities.view",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"activities");ctx=_ctx(db,user,lodge_id);a=tenant_get(db,Activity,record_id,lodge_id,"Activity");_ensure_department_scope(ctx,a.department_id,"activity")
    full=_may(db,ctx,"activities.manage");own=_may(db,ctx,"activities.own.manage") and ctx.staff and a.guide_staff_id==ctx.staff.id
    if not full and not own:raise HTTPException(403,"You may only update activities assigned to you")
    data=body.model_dump(exclude_unset=True)
    if not full and any(k in data for k in ["activity_type","title","guide_staff_id","vehicle_id","requires_vehicle","starts_at","ends_at","meeting_point"]):raise HTTPException(403,"Assigned guides can only update activity status and notes")
    starts=data.get("starts_at",a.starts_at);ends=data.get("ends_at",a.ends_at);guide_id=data.get("guide_staff_id",a.guide_staff_id);vehicle_id=data.get("vehicle_id",a.vehicle_id)
    if ends<=starts:raise HTTPException(422,"Activity end must be after start")
    guide=ensure_fk(db,StaffProfile,guide_id,lodge_id,"Guide/ranger") if guide_id else None;vehicle=ensure_fk(db,Vehicle,vehicle_id,lodge_id,"Vehicle") if vehicle_id else None
    _activity_conflicts(db,lodge_id,starts,ends,guide_id,vehicle_id,a.id)
    if "starts_at" in data or "ends_at" in data:
        for link in db.scalars(select(ActivityGuest).where(ActivityGuest.activity_id==a.id)).all():
            _lock_schedule_resources(db,lodge_id,("guest",link.guest_id))
            overlap=db.scalar(select(ActivityGuest.activity_id).join(Activity,Activity.id==ActivityGuest.activity_id).where(ActivityGuest.guest_id==link.guest_id,ActivityGuest.activity_id!=a.id,Activity.status.notin_(["completed","cancelled"]),Activity.starts_at<ends,Activity.ends_at>starts).limit(1))
            if overlap:raise HTTPException(409,"A guest is already assigned to an overlapping activity")
    target=data.get("status",a.status);allowed={"scheduled":{"confirmed","cancelled"},"confirmed":{"in_progress","cancelled"},"in_progress":{"completed","cancelled"},"completed":set(),"cancelled":set()}
    if "status" in data and target!=a.status and target not in allowed.get(a.status,set()): raise HTTPException(409,f"Activity cannot move from {a.status} to {target}")
    if target=="in_progress" and a.status!="in_progress":
        if not guide:raise HTTPException(409,"A guide/ranger must be assigned before starting")
        requires_vehicle=data.get("requires_vehicle",a.requires_vehicle)
        if requires_vehicle and not vehicle:raise HTTPException(409,"A vehicle must be assigned before starting this activity")
        _assert_staff_operational(guide,"Guide/ranger")
        if vehicle and vehicle.status not in {"ready","assigned"}:raise HTTPException(409,"Vehicle is not ready")
        if vehicle and entitlement_enabled(db,lodge_id,"vehicle_checklists"):
            cutoff=datetime.now(timezone.utc)-timedelta(hours=12)
            passed=db.scalar(select(VehicleChecklist).where(VehicleChecklist.vehicle_id==vehicle.id,VehicleChecklist.checklist_type=="pre_drive",VehicleChecklist.status=="passed",VehicleChecklist.completed_at>=cutoff).order_by(VehicleChecklist.completed_at.desc()))
            if not passed:raise HTTPException(409,"A passed pre-drive checklist from the last 12 hours is required")
        if vehicle:vehicle.status="on_drive"
        guide.operational_status="on_drive"
    if target in {"completed","cancelled"} and a.status=="in_progress":
        if vehicle and vehicle.status=="on_drive":vehicle.status="ready"
        if guide and guide.operational_status=="on_drive":guide.operational_status="available"
    for k,val in data.items():setattr(a,k,val)
    audit(db,request,lodge_id,user.id,"activity.updated","activity",str(a.id),f"Status: {a.status}");event(db,lodge_id,user.id,"activity.updated","activity",str(a.id),f"Activity {a.title} is {a.status.replace('_',' ')}");db.commit();return {"id":str(a.id),"status":a.status}

@app.get("/api/v1/lodges/{lodge_id}/transfers")
def list_transfers(lodge_id:str,user:User=Depends(require_permission("transfers.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"transfers")
    ctx=_ctx(db,user,lodge_id);q=select(Transfer).where(Transfer.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(Transfer.department_id==ctx.department_id)
    elif ctx.role_key=="driver":q=q.where(Transfer.driver_staff_id==_require_own_staff(ctx).id)
    rows=db.scalars(q.order_by(Transfer.scheduled_at.desc()).limit(500)).all();out=[]
    for t in rows:
        g=db.get(Guest,t.guest_id)
        out.append({"id":str(t.id),"transfer_type":t.transfer_type,"guest_id":str(t.guest_id),"guest_name":f"{g.first_name} {g.last_name}" if g else "","stay_id":str(t.stay_id) if t.stay_id else None,"driver_staff_id":str(t.driver_staff_id) if t.driver_staff_id else None,"driver_name":_name_staff(db,t.driver_staff_id),"vehicle_id":str(t.vehicle_id) if t.vehicle_id else None,"vehicle_name":_name_vehicle(db,t.vehicle_id),"scheduled_at":t.scheduled_at.isoformat(),"expected_end_at":t.expected_end_at.isoformat(),"pickup_location":t.pickup_location,"dropoff_location":t.dropoff_location,"flight_number":t.flight_number,"flight_time":t.flight_time.isoformat() if t.flight_time else None,"passenger_count":t.passenger_count,"delay_minutes":t.delay_minutes,"delay_reason":t.delay_reason,"status":t.status,"notes":t.notes})
    return out

@app.post("/api/v1/lodges/{lodge_id}/transfers",dependencies=[Depends(require_csrf)])
def create_transfer(lodge_id:str,body:TransferCreate,request:Request,user:User=Depends(require_permission("transfers.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"transfers")
    ctx=_ctx(db,user,lodge_id)
    if body.expected_end_at<=body.scheduled_at:raise HTTPException(422,"Transfer end must be after start")
    ensure_fk(db,Guest,body.guest_id,lodge_id,"Guest")
    if body.stay_id:
        st=ensure_fk(db,Stay,body.stay_id,lodge_id,"Stay")
        if st.guest_id!=body.guest_id:raise HTTPException(409,"Stay does not belong to the selected guest")
    driver=ensure_fk(db,StaffProfile,body.driver_staff_id,lodge_id,"Driver") if body.driver_staff_id else None;vehicle=ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle") if body.vehicle_id else None
    if driver:_assert_staff_operational(driver,"Driver")
    if vehicle and vehicle.status in {"maintenance","out_of_service"}:raise HTTPException(409,"Vehicle is not available")
    _transfer_conflicts(db,lodge_id,body.scheduled_at,body.expected_end_at,body.driver_staff_id,body.vehicle_id)
    department_id=_set_department_from_staff_or_context(ctx,driver,body.department_id)
    t=Transfer(lodge_id=lodge_id,transfer_type=body.transfer_type,guest_id=body.guest_id,stay_id=body.stay_id,driver_staff_id=body.driver_staff_id,department_id=department_id,vehicle_id=body.vehicle_id,scheduled_at=body.scheduled_at,expected_end_at=body.expected_end_at,pickup_location=body.pickup_location,dropoff_location=body.dropoff_location,flight_number=body.flight_number,flight_time=body.flight_time,passenger_count=body.passenger_count,notes=body.notes,created_by_user_id=user.id)
    db.add(t);db.flush()
    if t.driver_staff_id:
        recipient=staff_user_id(db,lodge_id,t.driver_staff_id)
        create_notification(db,lodge_id=lodge_id,notification_type="transfer.assigned",severity="normal",title="Transfer assigned",body=f"{t.pickup_location} to {t.dropoff_location}",resource_type="transfer",resource_id=t.id,dedupe_key=f"transfer-assigned:{t.id}:{t.driver_staff_id}",recipient_user_ids=[recipient] if recipient else [])
    audit(db,request,lodge_id,user.id,"transfer.created","transfer",str(t.id));event(db,lodge_id,user.id,"transfer.created","transfer",str(t.id),f"Transfer scheduled from {t.pickup_location} to {t.dropoff_location}");db.commit();return {"id":str(t.id),"status":t.status}

@app.patch("/api/v1/lodges/{lodge_id}/transfers/{record_id}",dependencies=[Depends(require_csrf)])
def update_transfer(lodge_id:str,record_id:str,body:TransferUpdate,request:Request,user:User=Depends(require_permission("transfers.view",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"transfers");ctx=_ctx(db,user,lodge_id);t=tenant_get(db,Transfer,record_id,lodge_id,"Transfer");_ensure_department_scope(ctx,t.department_id,"transfer")
    full=_may(db,ctx,"transfers.manage");own=_may(db,ctx,"transfers.own.manage") and ctx.staff and t.driver_staff_id==ctx.staff.id
    if not full and not own:raise HTTPException(403,"You may only update transfers assigned to you")
    data=body.model_dump(exclude_unset=True)
    if not full and any(k in data for k in ["driver_staff_id","vehicle_id","scheduled_at","expected_end_at","pickup_location","dropoff_location","flight_number","flight_time","passenger_count"]):raise HTTPException(403,"Assigned drivers can only update transfer status and notes")
    starts=data.get("scheduled_at",t.scheduled_at);ends=data.get("expected_end_at",t.expected_end_at);driver_id=data.get("driver_staff_id",t.driver_staff_id);vehicle_id=data.get("vehicle_id",t.vehicle_id)
    if ends<=starts:raise HTTPException(422,"Transfer end must be after start")
    driver=ensure_fk(db,StaffProfile,driver_id,lodge_id,"Driver") if driver_id else None;vehicle=ensure_fk(db,Vehicle,vehicle_id,lodge_id,"Vehicle") if vehicle_id else None
    _transfer_conflicts(db,lodge_id,starts,ends,driver_id,vehicle_id,t.id)
    target=data.get("status",t.status);allowed={"scheduled":{"confirmed","cancelled"},"confirmed":{"en_route","cancelled"},"en_route":{"arrived","cancelled"},"arrived":{"completed"},"completed":set(),"cancelled":set()}
    if "status" in data and target!=t.status and target not in allowed.get(t.status,set()):raise HTTPException(409,f"Transfer cannot move from {t.status} to {target}")
    if target=="en_route" and t.status!="en_route":
        if not driver or not vehicle:raise HTTPException(409,"Driver and vehicle are required before departure")
        _assert_staff_operational(driver,"Driver")
        if vehicle.status not in {"ready","assigned"}:raise HTTPException(409,"Vehicle is not ready")
        if entitlement_enabled(db,lodge_id,"vehicle_checklists"):
            cutoff=datetime.now(timezone.utc)-timedelta(hours=12)
            passed=db.scalar(select(VehicleChecklist).where(VehicleChecklist.vehicle_id==vehicle.id,VehicleChecklist.checklist_type=="pre_drive",VehicleChecklist.status=="passed",VehicleChecklist.completed_at>=cutoff).order_by(VehicleChecklist.completed_at.desc()))
            if not passed:raise HTTPException(409,"A passed pre-drive checklist from the last 12 hours is required")
        vehicle.status="on_drive";driver.operational_status="on_drive"
    if target in {"completed","cancelled"} and t.status in {"en_route","arrived"}:
        if vehicle and vehicle.status=="on_drive":vehicle.status="ready"
        if driver and driver.operational_status=="on_drive":driver.operational_status="available"
    for k,val in data.items():setattr(t,k,val)
    if t.driver_staff_id and data:
        recipient=staff_user_id(db,lodge_id,t.driver_staff_id)
        create_notification(db,lodge_id=lodge_id,notification_type="transfer.updated",severity="high" if t.delay_minutes else "normal",title="Transfer updated",body=f"{t.pickup_location} to {t.dropoff_location} — {t.status}",resource_type="transfer",resource_id=t.id,dedupe_key=f"transfer-update:{t.id}:{t.updated_at.isoformat() if t.updated_at else datetime.now(timezone.utc).isoformat()}:{t.status}:{t.delay_minutes}",recipient_user_ids=[recipient] if recipient else [])
    audit(db,request,lodge_id,user.id,"transfer.updated","transfer",str(t.id),f"Status: {t.status}");event(db,lodge_id,user.id,"transfer.updated","transfer",str(t.id),f"Transfer is {t.status.replace('_',' ')}");db.commit();return {"id":str(t.id),"status":t.status}

@app.get("/api/v1/lodges/{lodge_id}/wildlife")
def list_wildlife(lodge_id:str,user:User=Depends(require_permission("wildlife.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"wildlife");ctx=_ctx(db,user,lodge_id);lodge=db.get(Lodge,lodge_id)
    protected={x.strip().lower() for x in (lodge.protected_species if lodge else "rhino,black rhino,white rhino").split(",") if x.strip()}
    precise=_may(db,ctx,"wildlife.precise");cutoff=datetime.now(timezone.utc)-timedelta(hours=24)
    rows=db.scalars(select(WildlifeSighting).where(WildlifeSighting.lodge_id==lodge_id).order_by(WildlifeSighting.observed_at.desc()).limit(500)).all();out=[]
    for sighting in rows:
        is_protected=sighting.species.strip().lower() in protected
        if is_protected and not precise and sighting.observed_at>cutoff:continue
        media=db.scalars(select(WildlifeMedia).where(WildlifeMedia.sighting_id==sighting.id)).all()
        lat=float(sighting.latitude) if sighting.latitude is not None else None;lon=float(sighting.longitude) if sighting.longitude is not None else None
        if is_protected and not precise:
            lat=round(lat,2) if lat is not None else None;lon=round(lon,2) if lon is not None else None
        out.append({"id":str(sighting.id),"client_ref":str(sighting.client_ref),"species":sighting.species,"notes":sighting.notes,"latitude":lat,"longitude":lon,"gps_accuracy_m":float(sighting.gps_accuracy_m) if sighting.gps_accuracy_m is not None else None,"observed_at":sighting.observed_at.isoformat(),"protected_location_obscured":bool(is_protected and not precise),"reported_by_staff_id":str(sighting.reported_by_staff_id) if sighting.reported_by_staff_id else None,"reported_by":_name_staff(db,sighting.reported_by_staff_id),"activity_id":str(sighting.activity_id) if sighting.activity_id else None,"media":[{"id":str(m.id),"content_type":m.content_type,"size_bytes":m.size_bytes} for m in media]})
    return out

@app.post("/api/v1/lodges/{lodge_id}/wildlife",dependencies=[Depends(require_csrf)])
def create_wildlife(lodge_id:str,body:WildlifeSightingCreate,request:Request,user:User=Depends(require_permission("wildlife.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"wildlife");ctx=_ctx(db,user,lodge_id)
    if body.observed_at>datetime.now(timezone.utc)+timedelta(minutes=5):raise HTTPException(422,"Wildlife observation time cannot be more than five minutes in the future")
    existing=db.scalar(select(WildlifeSighting).where(WildlifeSighting.lodge_id==lodge_id,WildlifeSighting.client_ref==body.client_ref))
    if existing:return {"id":str(existing.id),"client_ref":str(existing.client_ref),"duplicate":True}
    data=body.model_dump()
    if not (ctx.super_admin or ctx.role_key in {"lodge_admin","department_manager"}):
        staff=_require_own_staff(ctx);data["reported_by_staff_id"]=staff.id
    elif data.get("reported_by_staff_id"):
        ensure_fk(db,StaffProfile,data["reported_by_staff_id"],lodge_id,"Staff member")
    if data.get("activity_id"):ensure_fk(db,Activity,data["activity_id"],lodge_id,"Activity")
    sighting=WildlifeSighting(lodge_id=lodge_id,reported_by_user_id=user.id,**data)
    db.add(sighting);db.flush();audit(db,request,lodge_id,user.id,"wildlife_sighting.created","wildlife_sighting",str(sighting.id));event(db,lodge_id,user.id,"wildlife_sighting.created","wildlife_sighting",str(sighting.id),f"{sighting.species} sighting recorded");db.commit();return {"id":str(sighting.id),"client_ref":str(sighting.client_ref),"duplicate":False}


@app.post("/api/v1/lodges/{lodge_id}/wildlife/media/upload-url",dependencies=[Depends(require_csrf)])
def wildlife_upload_url(lodge_id:str,body:MediaUploadRequest,user:User=Depends(require_permission("wildlife.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"wildlife")
    ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp","image/heic":"heic","image/heif":"heif"}[body.content_type]
    key=f"lodges/{lodge_id}/wildlife/{uuid.uuid4()}.{ext}"
    params={"Bucket":settings.object_storage_bucket,"Key":key,"ContentType":body.content_type,"Metadata":{"sha256":body.sha256.lower()}}
    url=s3_public.generate_presigned_url("put_object",Params=params,ExpiresIn=900,HttpMethod="PUT")
    return {"object_key":key,"upload_url":url,"expires_in_seconds":900,"required_headers":{"Content-Type":body.content_type,"x-amz-meta-sha256":body.sha256.lower()}}

@app.post("/api/v1/lodges/{lodge_id}/wildlife/media",dependencies=[Depends(require_csrf)])
def register_wildlife_media(lodge_id:str,body:WildlifeMediaRegister,request:Request,user:User=Depends(require_permission("wildlife.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"wildlife")
    prefix=f"lodges/{lodge_id}/wildlife/"
    if not body.object_key.startswith(prefix):raise HTTPException(400,"Invalid media object key")
    ensure_fk(db,WildlifeSighting,body.sighting_id,lodge_id,"Wildlife sighting")
    try:head=s3_internal.head_object(Bucket=settings.object_storage_bucket,Key=body.object_key)
    except ClientError:raise HTTPException(409,"Uploaded object was not found in object storage")
    if int(head.get("ContentLength",0))!=body.size_bytes:raise HTTPException(409,"Uploaded file size does not match")
    if head.get("ContentType")!=body.content_type:raise HTTPException(409,"Uploaded content type does not match")
    try:
        obj=s3_internal.get_object(Bucket=settings.object_storage_bucket,Key=body.object_key)
        digest=hashlib.sha256()
        for chunk in iter(lambda: obj["Body"].read(1024*1024), b""): digest.update(chunk)
        obj["Body"].close()
    except ClientError: raise HTTPException(409,"Uploaded object could not be verified")
    if digest.hexdigest().lower()!=body.sha256.lower():raise HTTPException(409,"Uploaded file checksum does not match")
    m=WildlifeMedia(lodge_id=lodge_id,sighting_id=body.sighting_id,object_key=body.object_key,content_type=body.content_type,size_bytes=body.size_bytes,sha256=body.sha256.lower(),uploaded_by_user_id=user.id)
    db.add(m);db.flush();audit(db,request,lodge_id,user.id,"wildlife_media.registered","wildlife_media",str(m.id));commit_or_conflict(db,"This media object has already been registered");return {"id":str(m.id),"sighting_id":str(m.sighting_id)}

@app.get("/api/v1/lodges/{lodge_id}/wildlife/media/{media_id}/download-url")
def wildlife_download_url(lodge_id:str,media_id:str,user:User=Depends(require_permission("wildlife.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"wildlife");m=tenant_get(db,WildlifeMedia,media_id,lodge_id,"Media")
    return {"url":s3_public.generate_presigned_url("get_object",Params={"Bucket":settings.object_storage_bucket,"Key":m.object_key},ExpiresIn=600),"expires_in_seconds":600}

@app.get("/api/v1/lodges/{lodge_id}/ranger/today")
def ranger_today(lodge_id:str,user:User=Depends(require_permission("ranger.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"ranger")
    from zoneinfo import ZoneInfo
    lodge=db.get(Lodge,lodge_id)
    try:tz=ZoneInfo(lodge.timezone if lodge else "Africa/Johannesburg")
    except Exception:tz=ZoneInfo("Africa/Johannesburg")
    now=datetime.now(tz);start=now.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc);end=(now.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=1)).astimezone(timezone.utc)
    staff=db.scalar(select(StaffProfile).where(StaffProfile.lodge_id==lodge_id,StaffProfile.user_id==user.id))
    if not staff:raise HTTPException(409,"Your user account is not linked to a staff profile for this lodge")
    acts=db.scalars(select(Activity).where(Activity.lodge_id==lodge_id,Activity.guide_staff_id==staff.id,Activity.starts_at>=start,Activity.starts_at<end).order_by(Activity.starts_at)).all()
    tasks=db.scalars(select(Task).where(Task.lodge_id==lodge_id,Task.assigned_staff_id==staff.id,Task.status.notin_(["completed","cancelled"])).order_by(Task.due_at.asc().nullslast())).all()
    activity_ids=[a.id for a in acts]
    links=db.scalars(select(ActivityGuest).where(ActivityGuest.activity_id.in_(activity_ids))).all() if activity_ids else []
    guest_ids=list({x.guest_id for x in links})
    assigned_guests=db.scalars(select(Guest).where(Guest.lodge_id==lodge_id,Guest.id.in_(guest_ids))).all() if guest_ids else []
    return {"staff":{"id":str(staff.id),"name":staff.full_name,"operational_status":staff.operational_status},"activities":[{"id":str(a.id),"title":a.title,"activity_type":a.activity_type,"starts_at":a.starts_at.isoformat(),"ends_at":a.ends_at.isoformat(),"status":a.status,"vehicle_id":str(a.vehicle_id) if a.vehicle_id else None,"vehicle_name":_name_vehicle(db,a.vehicle_id),"vehicle_status":db.get(Vehicle,a.vehicle_id).status if a.vehicle_id and db.get(Vehicle,a.vehicle_id) else None,"fuel_level_percent":db.get(Vehicle,a.vehicle_id).fuel_level_percent if a.vehicle_id and db.get(Vehicle,a.vehicle_id) else None,"pre_drive_checklist_status":(db.scalar(select(VehicleChecklist.status).where(VehicleChecklist.vehicle_id==a.vehicle_id,VehicleChecklist.checklist_type=="pre_drive").order_by(VehicleChecklist.completed_at.desc()).limit(1)) if a.vehicle_id else None),"meeting_point":a.meeting_point} for a in acts],"assigned_guests":[{"id":str(g.id),"name":f"{g.first_name} {g.last_name}","dietary_requirements":g.dietary_requirements,"allergies":g.allergies} for g in assigned_guests],"tasks":[{"id":str(t.id),"title":t.title,"priority":t.priority,"status":t.status,"due_at":t.due_at.isoformat() if t.due_at else None} for t in tasks]}

# Operations intelligence: notifications, delivery records, operational memory and live reports.
@app.get("/api/v1/lodges/{lodge_id}/notifications")
def list_notifications(lodge_id:str, unread_only:bool=False, limit:int=Query(100,ge=1,le=250), user:User=Depends(require_permission("notifications.view")), db:Session=Depends(get_db)):
    q=(select(NotificationRecipient,Notification)
       .join(Notification,Notification.id==NotificationRecipient.notification_id)
       .where(NotificationRecipient.lodge_id==lodge_id,NotificationRecipient.user_id==user.id,NotificationRecipient.archived_at.is_(None))
       .order_by(Notification.created_at.desc()).limit(limit))
    if unread_only:q=q.where(NotificationRecipient.read_at.is_(None))
    rows=db.execute(q).all()
    return [{
        "id":str(n.id),"recipient_id":str(r.id),"type":n.notification_type,"severity":n.severity,"title":n.title,"body":n.body,
        "resource_type":n.resource_type,"resource_id":n.resource_id,"created_at":n.created_at.isoformat(),
        "read_at":r.read_at.isoformat() if r.read_at else None
    } for r,n in rows]

@app.post("/api/v1/lodges/{lodge_id}/notifications/{notification_id}/read",dependencies=[Depends(require_csrf)])
def mark_notification_read(lodge_id:str,notification_id:str,user:User=Depends(require_permission("notifications.manage",write=True)),db:Session=Depends(get_db)):
    row=db.scalar(select(NotificationRecipient).where(NotificationRecipient.lodge_id==lodge_id,NotificationRecipient.notification_id==notification_id,NotificationRecipient.user_id==user.id))
    if not row:raise HTTPException(404,"Notification not found")
    if not row.read_at:row.read_at=datetime.now(timezone.utc);db.commit()
    return {"ok":True,"read_at":row.read_at.isoformat()}

@app.get("/api/v1/lodges/{lodge_id}/notification-preferences")
def get_notification_preferences(lodge_id:str,user:User=Depends(require_permission("notifications.view")),db:Session=Depends(get_db)):
    pref=db.scalar(select(NotificationPreference).where(NotificationPreference.lodge_id==lodge_id,NotificationPreference.user_id==user.id))
    return {"email_enabled":pref.email_enabled if pref else False,"email_min_severity":pref.email_min_severity if pref else "high"}

@app.patch("/api/v1/lodges/{lodge_id}/notification-preferences",dependencies=[Depends(require_csrf)])
def update_notification_preferences(lodge_id:str,body:NotificationPreferenceUpdate,user:User=Depends(require_permission("notifications.manage",write=True)),db:Session=Depends(get_db)):
    pref=db.scalar(select(NotificationPreference).where(NotificationPreference.lodge_id==lodge_id,NotificationPreference.user_id==user.id))
    if not pref:
        pref=NotificationPreference(lodge_id=lodge_id,user_id=user.id,email_enabled=body.email_enabled,email_min_severity=body.email_min_severity);db.add(pref)
    else:
        pref.email_enabled=body.email_enabled;pref.email_min_severity=body.email_min_severity
    db.commit()
    return {"email_enabled":pref.email_enabled,"email_min_severity":pref.email_min_severity}

@app.get("/api/v1/lodges/{lodge_id}/notification-deliveries")
def notification_deliveries(lodge_id:str,limit:int=Query(100,ge=1,le=250),user:User=Depends(require_permission("notifications.delivery.view")),db:Session=Depends(get_db)):
    rows=db.scalars(select(NotificationDelivery).where(NotificationDelivery.lodge_id==lodge_id).order_by(NotificationDelivery.created_at.desc()).limit(limit)).all()
    return [{"id":str(x.id),"notification_id":str(x.notification_id),"user_id":str(x.user_id),"channel":x.channel,"destination":x.destination,"status":x.status,"attempts":x.attempts,"last_error":x.last_error,"sent_at":x.sent_at.isoformat() if x.sent_at else None,"created_at":x.created_at.isoformat()} for x in rows]

@app.get("/api/v1/lodges/{lodge_id}/operational-memory")
def operational_memory(lodge_id:str,event_type:str|None=None,resource_type:str|None=None,start:date|None=None,end:date|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),user:User=Depends(require_permission("memory.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);q=select(OperationalEvent).where(OperationalEvent.lodge_id==lodge_id)
    if not _may(db,ctx,"staff.hr.view"):
        q=q.where(~OperationalEvent.event_type.like("staff.%"),OperationalEvent.resource_type.notin_(["staff","staff_leave","staff_credential","staff_training","staff_incident","staff_performance"]))
    if event_type:q=q.where(OperationalEvent.event_type==event_type)
    if resource_type:q=q.where(OperationalEvent.resource_type==resource_type)
    if start:q=q.where(OperationalEvent.created_at>=datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc))
    if end:q=q.where(OperationalEvent.created_at<datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc))
    rows=db.scalars(q.order_by(OperationalEvent.created_at.desc()).offset(offset).limit(limit)).all()
    return [{"id":str(e.id),"event_type":e.event_type,"resource_type":e.resource_type,"resource_id":e.resource_id,"summary":e.summary,"detail":e.detail,"actor_user_id":str(e.actor_user_id) if e.actor_user_id else None,"created_at":e.created_at.isoformat()} for e in rows]

@app.get("/api/v1/lodges/{lodge_id}/reports/summary")
def reports_summary(lodge_id:str,start:date|None=None,end:date|None=None,user:User=Depends(require_permission("reports.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"reports")
    end=end or date.today();start=start or (end-timedelta(days=29))
    if end<start:raise HTTPException(422,"End date must be on or after start date")
    start_dt=datetime.combine(start,datetime.min.time(),tzinfo=timezone.utc);end_dt=datetime.combine(end+timedelta(days=1),datetime.min.time(),tzinfo=timezone.utc)
    ctx=_ctx(db,user,lodge_id)
    dept=ctx.department_id if ctx.role_key=="department_manager" else None
    if ctx.role_key=="department_manager" and not dept:raise HTTPException(409,"Department Manager membership is not assigned to a department")
    tq=select(Task).where(Task.lodge_id==lodge_id,Task.created_at>=start_dt,Task.created_at<end_dt)
    mq=select(MaintenanceTicket).where(MaintenanceTicket.lodge_id==lodge_id,MaintenanceTicket.created_at>=start_dt,MaintenanceTicket.created_at<end_dt)
    rq=select(GuestRequest).where(GuestRequest.lodge_id==lodge_id,GuestRequest.created_at>=start_dt,GuestRequest.created_at<end_dt)
    if dept:
        tq=tq.where(Task.department_id==dept);mq=mq.where(MaintenanceTicket.department_id==dept);rq=rq.where(GuestRequest.department_id==dept)
    task_rows=db.scalars(tq).all();completed=[x for x in task_rows if x.status=="completed"]
    durations=[(x.completed_at-x.created_at).total_seconds()/3600 for x in completed if x.completed_at]
    maint=db.scalars(mq).all();requests=db.scalars(rq).all()
    base={
        "period":{"start":start.isoformat(),"end":end.isoformat()},
        "scope":{"type":"department","department_id":str(dept)} if dept else {"type":"lodge"},
        "tasks":{"created":len(task_rows),"completed":len(completed),"completion_rate":round(len(completed)/len(task_rows)*100,1) if task_rows else 0,"average_completion_hours":round(sum(durations)/len(durations),2) if durations else None},
        "maintenance":{"created":len(maint),"completed":sum(1 for x in maint if x.status=="completed"),"critical":sum(1 for x in maint if x.priority=="critical"),"cost_cents":sum(x.cost_cents or 0 for x in maint)},
        "guest_requests":{"created":len(requests),"resolved":sum(1 for x in requests if x.status=="resolved")},
    }
    if dept:
        activities=db.scalar(select(func.count()).select_from(Activity).where(Activity.lodge_id==lodge_id,Activity.department_id==dept,Activity.starts_at>=start_dt,Activity.starts_at<end_dt,Activity.status!="cancelled")) or 0
        transfers=db.scalar(select(func.count()).select_from(Transfer).where(Transfer.lodge_id==lodge_id,Transfer.department_id==dept,Transfer.scheduled_at>=start_dt,Transfer.scheduled_at<end_dt,Transfer.status!="cancelled")) or 0
        base.update({"stays":None,"fleet":None,"safari":{"activities":activities,"transfers":transfers,"wildlife_sightings":None},"rooms":None})
        return base
    fuel=db.scalars(select(FuelRecord).where(FuelRecord.lodge_id==lodge_id,FuelRecord.recorded_at>=start_dt,FuelRecord.recorded_at<end_dt)).all()
    stays=db.scalars(select(Stay).where(Stay.lodge_id==lodge_id,Stay.arrival_date<=end,Stay.departure_date>=start,Stay.status!="cancelled")).all()
    activities=db.scalar(select(func.count()).select_from(Activity).where(Activity.lodge_id==lodge_id,Activity.starts_at>=start_dt,Activity.starts_at<end_dt,Activity.status!="cancelled")) or 0
    transfers=db.scalar(select(func.count()).select_from(Transfer).where(Transfer.lodge_id==lodge_id,Transfer.scheduled_at>=start_dt,Transfer.scheduled_at<end_dt,Transfer.status!="cancelled")) or 0
    sightings=db.scalar(select(func.count()).select_from(WildlifeSighting).where(WildlifeSighting.lodge_id==lodge_id,WildlifeSighting.observed_at>=start_dt,WildlifeSighting.observed_at<end_dt)) or 0
    unit_counts=dict(db.execute(select(Unit.status,func.count()).where(Unit.lodge_id==lodge_id).group_by(Unit.status)).all())
    base.update({
        "stays":{"overlapping_period":len(stays),"completed":sum(1 for x in stays if x.status=="completed")},
        "fleet":{"fuel_litres":round(sum(float(x.litres) for x in fuel),2),"fuel_cost_cents":sum(x.cost_cents or 0 for x in fuel),"fuel_records":len(fuel)},
        "safari":{"activities":activities,"transfers":transfers,"wildlife_sightings":sightings},
        "rooms":{"by_status":unit_counts},
    })
    return base


@app.get("/api/v1/lodges/{lodge_id}/reports/summary.csv")
def reports_summary_csv(lodge_id:str,start:date|None=None,end:date|None=None,user:User=Depends(require_permission("reports.view")),db:Session=Depends(get_db)):
    report=reports_summary(lodge_id,start,end,user,db)
    rows=["section,metric,value"]
    for section,values in report.items():
        if isinstance(values,dict):
            for metric,value in values.items():
                safe=str(value if value is not None else "").replace('"','""')
                rows.append(f'"{section}","{metric}","{safe}"')
    return Response(content="\n".join(rows)+"\n",media_type="text/csv",headers={"Content-Disposition":"attachment; filename=lodge-crm-summary.csv"})

@app.get("/api/v1/lodges/{lodge_id}/audit")
def lodge_audit_log(lodge_id:str,action:str|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0),user:User=Depends(require_permission("audit.view")),db:Session=Depends(get_db)):
    q=select(AuditLog).where(AuditLog.lodge_id==lodge_id)
    if action:q=q.where(AuditLog.action==action)
    rows=db.scalars(q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)).all()
    return [{"id":str(x.id),"actor_user_id":str(x.actor_user_id) if x.actor_user_id else None,"action":x.action,"resource_type":x.resource_type,"resource_id":x.resource_id,"detail":x.detail,"created_at":x.created_at.isoformat()} for x in rows]

@app.get("/api/v1/platform/audit")
def platform_audit(limit:int=Query(200,ge=1,le=500),user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    set_rls_context(db,None,True,str(user.id))
    rows=db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all();out=[]
    for row in rows:
        lodge=db.get(Lodge,row.lodge_id) if row.lodge_id else None
        actor=db.get(User,row.actor_user_id) if row.actor_user_id else None
        out.append({"id":str(row.id),"lodge_id":str(row.lodge_id) if row.lodge_id else None,"lodge_name":lodge.name if lodge else None,"actor_user_id":str(row.actor_user_id) if row.actor_user_id else None,"actor_name":actor.full_name if actor else None,"actor_email":actor.email if actor else None,"action":row.action,"resource_type":row.resource_type,"resource_id":row.resource_id,"detail":row.detail,"request_id":row.request_id,"ip_address":row.ip_address,"created_at":row.created_at.isoformat()})
    return out


@app.get("/api/v1/platform/users")
def platform_users(user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    set_rls_context(db,None,True,str(user.id));rows=db.scalars(select(User).order_by(User.full_name,User.email)).all();out=[]
    for row in rows:
        memberships=db.execute(select(Membership,Lodge,Role).join(Lodge,Lodge.id==Membership.lodge_id).join(Role,Role.id==Membership.role_id).where(Membership.user_id==row.id,Membership.is_active.is_(True))).all()
        out.append({"id":str(row.id),"email":row.email,"full_name":row.full_name,"is_active":row.is_active,"is_super_admin":row.is_super_admin,"mfa_enabled":bool(row.mfa_enabled_at),"created_at":row.created_at.isoformat(),"memberships":[{"lodge_id":str(m.lodge_id),"lodge_name":l.name,"role":r.name,"role_key":r.key} for m,l,r in memberships]})
    return out


@app.get("/api/v1/platform/notifications")
def platform_notifications(limit:int=Query(100,ge=1,le=250),user:User=Depends(require_super_admin),db:Session=Depends(get_db)):
    set_rls_context(db,None,True,str(user.id))
    rows=db.execute(select(NotificationRecipient,Notification,Lodge).join(Notification,Notification.id==NotificationRecipient.notification_id).join(Lodge,Lodge.id==Notification.lodge_id).where(NotificationRecipient.user_id==user.id).order_by(Notification.created_at.desc()).limit(limit)).all()
    return [{"id":str(n.id),"lodge_id":str(n.lodge_id),"lodge_name":l.name,"type":n.notification_type,"severity":n.severity,"title":n.title,"body":n.body,"created_at":n.created_at.isoformat(),"read_at":r.read_at.isoformat() if r.read_at else None} for r,n,l in rows]

# --- Production operational workflows 1.5 ---

def _assert_staff_scope(ctx, staff: StaffProfile):
    if ctx.role_key == "department_manager" and ctx.department_id and staff.department_id != ctx.department_id:
        raise HTTPException(403, "Department Manager can only manage staff in their department")

@app.get("/api/v1/lodges/{lodge_id}/hr/leaves")
def list_staff_leaves(lodge_id:str,user:User=Depends(require_permission("staff.hr.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id)
    q=select(StaffLeave).where(StaffLeave.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":
        q=q.join(StaffProfile,StaffProfile.id==StaffLeave.staff_id).where(StaffProfile.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(StaffLeave.start_date.desc())).all()
    return [{"id":str(x.id),"staff_id":str(x.staff_id),"staff_name":_name_staff(db,x.staff_id),"leave_type":x.leave_type,"start_date":x.start_date.isoformat(),"end_date":x.end_date.isoformat(),"status":x.status,"notes":x.notes} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/hr/leaves",dependencies=[Depends(require_csrf)])
def create_staff_leave(lodge_id:str,body:StaffLeaveCreate,request:Request,user:User=Depends(require_permission("staff.hr.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id);staff=ensure_fk(db,StaffProfile,body.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    if body.end_date<body.start_date:raise HTTPException(422,"Leave end date must be on or after start date")
    overlap=db.scalar(select(StaffLeave.id).where(StaffLeave.lodge_id==lodge_id,StaffLeave.staff_id==staff.id,StaffLeave.status.in_(["pending","approved"]),StaffLeave.start_date<=body.end_date,StaffLeave.end_date>=body.start_date))
    if overlap:raise HTTPException(409,"Staff member already has overlapping leave")
    row=StaffLeave(lodge_id=lodge_id,staff_id=staff.id,leave_type=body.leave_type,start_date=body.start_date,end_date=body.end_date,status="pending",notes=body.notes)
    db.add(row);db.flush();audit(db,request,lodge_id,user.id,"staff_leave.created","staff_leave",str(row.id));event(db,lodge_id,user.id,"staff.leave_requested","staff",str(staff.id),f"Leave requested for {staff.full_name}: {body.start_date} to {body.end_date}");db.commit();return {"id":str(row.id),"status":row.status}

@app.patch("/api/v1/lodges/{lodge_id}/hr/leaves/{record_id}",dependencies=[Depends(require_csrf)])
def update_staff_leave(lodge_id:str,record_id:str,body:StaffLeaveUpdate,request:Request,user:User=Depends(require_permission("staff.hr.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id);row=tenant_get(db,StaffLeave,record_id,lodge_id,"Leave record");staff=tenant_get(db,StaffProfile,row.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    if row.status not in {"pending","approved"}:raise HTTPException(409,"This leave record can no longer be changed")
    if body.status in {"approved","rejected"} and staff.user_id==user.id:raise HTTPException(403,"You cannot approve or reject your own leave")
    row.status=body.status;row.approved_by_user_id=user.id if body.status in {"approved","rejected"} else row.approved_by_user_id
    if body.status=="approved" and row.start_date<=date.today()<=row.end_date:staff.operational_status="leave"
    audit(db,request,lodge_id,user.id,"staff_leave.updated","staff_leave",str(row.id),body.status);event(db,lodge_id,user.id,"staff.leave_status","staff",str(staff.id),f"Leave {body.status} for {staff.full_name}");db.commit();return {"id":str(row.id),"status":row.status}

@app.get("/api/v1/lodges/{lodge_id}/hr/credentials")
def list_staff_credentials(lodge_id:str,user:User=Depends(require_permission("staff.hr.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id);q=select(StaffCredential).where(StaffCredential.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.join(StaffProfile,StaffProfile.id==StaffCredential.staff_id).where(StaffProfile.department_id==ctx.department_id)
    return [{"id":str(x.id),"staff_id":str(x.staff_id),"staff_name":_name_staff(db,x.staff_id),"credential_type":x.credential_type,"name":x.name,"issuer":x.issuer,"reference_number":x.reference_number,"issued_date":x.issued_date.isoformat() if x.issued_date else None,"expiry_date":x.expiry_date.isoformat() if x.expiry_date else None,"notes":x.notes} for x in db.scalars(q.order_by(StaffCredential.expiry_date.asc().nullslast())).all()]

@app.post("/api/v1/lodges/{lodge_id}/hr/credentials",dependencies=[Depends(require_csrf)])
def create_staff_credential(lodge_id:str,body:StaffCredentialCreate,request:Request,user:User=Depends(require_permission("staff.hr.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id);staff=ensure_fk(db,StaffProfile,body.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    row=StaffCredential(lodge_id=lodge_id,**body.model_dump());db.add(row);db.flush();audit(db,request,lodge_id,user.id,"staff_credential.created","staff_credential",str(row.id));db.commit();return {"id":str(row.id)}

@app.get("/api/v1/lodges/{lodge_id}/hr/training")
def list_staff_training(lodge_id:str,user:User=Depends(require_permission("staff.hr.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id);q=select(StaffTraining).where(StaffTraining.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.join(StaffProfile,StaffProfile.id==StaffTraining.staff_id).where(StaffProfile.department_id==ctx.department_id)
    return [{"id":str(x.id),"staff_id":str(x.staff_id),"staff_name":_name_staff(db,x.staff_id),"title":x.title,"provider":x.provider,"completed_date":x.completed_date.isoformat() if x.completed_date else None,"renewal_due_date":x.renewal_due_date.isoformat() if x.renewal_due_date else None,"status":x.status,"notes":x.notes} for x in db.scalars(q.order_by(StaffTraining.renewal_due_date.asc().nullslast())).all()]

@app.post("/api/v1/lodges/{lodge_id}/hr/training",dependencies=[Depends(require_csrf)])
def create_staff_training(lodge_id:str,body:StaffTrainingCreate,request:Request,user:User=Depends(require_permission("staff.hr.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_hr");ctx=_ctx(db,user,lodge_id);staff=ensure_fk(db,StaffProfile,body.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    row=StaffTraining(lodge_id=lodge_id,**body.model_dump());db.add(row);db.flush();audit(db,request,lodge_id,user.id,"staff_training.created","staff_training",str(row.id));db.commit();return {"id":str(row.id)}

SENSITIVE_CUSTOM_ROLE_PERMISSIONS={"staff.manage","roles.custom.manage","departments.manage","notifications.delivery.view"}

def _validate_custom_permissions(keys:list[str]):
    denied=sorted(set(keys)&SENSITIVE_CUSTOM_ROLE_PERMISSIONS)
    if denied:raise HTTPException(422,"Custom roles cannot delegate privileged permissions: "+", ".join(denied))

@app.get("/api/v1/lodges/{lodge_id}/custom-roles")
def list_custom_roles(lodge_id:str,user:User=Depends(require_permission("roles.custom.manage")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"custom_roles")
    rows=db.scalars(select(CustomRole).where(CustomRole.lodge_id==lodge_id).order_by(CustomRole.name)).all();out=[]
    for r in rows:
        base=db.get(Role,r.base_role_id);perms=list(db.scalars(select(Permission.key).join(CustomRolePermission,Permission.id==CustomRolePermission.permission_id).where(CustomRolePermission.custom_role_id==r.id)).all())
        out.append({"id":str(r.id),"name":r.name,"description":r.description,"base_role_key":base.key if base else None,"base_role_name":base.name if base else None,"is_active":r.is_active,"permission_keys":perms})
    return out

@app.get("/api/v1/lodges/{lodge_id}/available-permissions")
def available_permissions(lodge_id:str,user:User=Depends(require_permission("roles.custom.manage")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"custom_roles");return [{"key":p.key,"description":p.description} for p in db.scalars(select(Permission).order_by(Permission.key)).all()]

@app.post("/api/v1/lodges/{lodge_id}/custom-roles",dependencies=[Depends(require_csrf)])
def create_custom_role(lodge_id:str,body:CustomRoleCreate,request:Request,user:User=Depends(require_permission("roles.custom.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"custom_roles");base=db.scalar(select(Role).where(Role.key==body.base_role_key))
    if not base or body.base_role_key in {"lodge_admin"}:raise HTTPException(422,"Choose an operational base role; Lodge Admin cannot be cloned")
    _validate_custom_permissions(body.permission_keys)
    row=CustomRole(lodge_id=lodge_id,name=body.name.strip(),base_role_id=base.id,description=body.description,is_active=True);db.add(row);db.flush()
    perms=db.scalars(select(Permission).where(Permission.key.in_(body.permission_keys))).all() if body.permission_keys else []
    if len(perms)!=len(set(body.permission_keys)):raise HTTPException(422,"One or more permission keys are invalid")
    for p in perms:db.add(CustomRolePermission(lodge_id=lodge_id,custom_role_id=row.id,permission_id=p.id))
    audit(db,request,lodge_id,user.id,"custom_role.created","custom_role",str(row.id));commit_or_conflict(db,"A custom role with this name already exists");return {"id":str(row.id)}

@app.patch("/api/v1/lodges/{lodge_id}/custom-roles/{record_id}",dependencies=[Depends(require_csrf)])
def update_custom_role(lodge_id:str,record_id:str,body:CustomRoleUpdate,request:Request,user:User=Depends(require_permission("roles.custom.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"custom_roles");row=tenant_get(db,CustomRole,record_id,lodge_id,"Custom role")
    if body.name is not None:row.name=body.name.strip()
    if body.description is not None:row.description=body.description
    if body.is_active is not None:
        row.is_active=body.is_active
        if body.is_active is False:
            assigned=db.scalars(select(Membership).where(Membership.lodge_id==lodge_id,Membership.custom_role_id==row.id)).all()
            for membership in assigned:
                membership.custom_role_id=None
                if membership.previous_role_id: membership.role_id=membership.previous_role_id
                membership.previous_role_id=None
    if body.permission_keys is not None:
        _validate_custom_permissions(body.permission_keys)
        perms=db.scalars(select(Permission).where(Permission.key.in_(body.permission_keys))).all() if body.permission_keys else []
        if len(perms)!=len(set(body.permission_keys)):raise HTTPException(422,"One or more permission keys are invalid")
        db.query(CustomRolePermission).filter(CustomRolePermission.custom_role_id==row.id).delete(synchronize_session=False)
        for p in perms:db.add(CustomRolePermission(lodge_id=lodge_id,custom_role_id=row.id,permission_id=p.id))
    audit(db,request,lodge_id,user.id,"custom_role.updated","custom_role",str(row.id));commit_or_conflict(db,"A custom role with this name already exists");return {"id":str(row.id)}

@app.patch("/api/v1/lodges/{lodge_id}/staff/{record_id}/custom-role",dependencies=[Depends(require_csrf)])
def assign_custom_role(lodge_id:str,record_id:str,body:MembershipRoleUpdate,request:Request,user:User=Depends(require_permission("roles.custom.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"custom_roles");staff=tenant_get(db,StaffProfile,record_id,lodge_id,"Staff profile")
    if not staff.user_id:raise HTTPException(409,"Staff member must have a login account before assigning a custom role")
    membership=db.scalar(select(Membership).where(Membership.lodge_id==lodge_id,Membership.user_id==staff.user_id,Membership.is_active.is_(True)))
    if not membership:raise HTTPException(409,"Active lodge membership not found")
    if body.custom_role_id:
        role=tenant_get(db,CustomRole,body.custom_role_id,lodge_id,"Custom role")
        if not role.is_active:raise HTTPException(409,"Custom role is inactive")
        if not membership.custom_role_id: membership.previous_role_id=membership.role_id
        membership.custom_role_id=role.id;membership.role_id=role.base_role_id
    else:
        membership.custom_role_id=None
        if membership.previous_role_id: membership.role_id=membership.previous_role_id
        membership.previous_role_id=None
    audit(db,request,lodge_id,user.id,"staff.custom_role_updated","staff",str(staff.id));db.commit();return {"staff_id":str(staff.id),"custom_role_id":str(membership.custom_role_id) if membership.custom_role_id else None}

@app.get("/api/v1/lodges/{lodge_id}/tasks/{record_id}/checklist")
def task_checklist(lodge_id:str,record_id:str,user:User=Depends(require_permission("tasks.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,record_id,lodge_id,"Task");_assert_task_visible(db,ctx,task)
    return [{"id":str(x.id),"label":x.label,"position":x.position,"is_required":x.is_required,"completed":bool(x.completed_at),"completed_at":x.completed_at.isoformat() if x.completed_at else None} for x in db.scalars(select(TaskChecklistItem).where(TaskChecklistItem.task_id==task.id).order_by(TaskChecklistItem.position)).all()]

@app.post("/api/v1/lodges/{lodge_id}/tasks/{record_id}/checklist",dependencies=[Depends(require_csrf)])
def add_task_checklist(lodge_id:str,record_id:str,body:TaskChecklistCreate,request:Request,user:User=Depends(require_permission("tasks.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"advanced_tasks");ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,record_id,lodge_id,"Task");_ensure_department_scope(ctx,task.department_id,"task")
    row=TaskChecklistItem(lodge_id=lodge_id,task_id=task.id,label=body.label,position=body.position,is_required=body.is_required);db.add(row);db.flush();audit(db,request,lodge_id,user.id,"task.checklist_added","task",str(task.id));db.commit();return {"id":str(row.id)}

@app.patch("/api/v1/lodges/{lodge_id}/tasks/{record_id}/checklist/{item_id}",dependencies=[Depends(require_csrf)])
def update_task_checklist(lodge_id:str,record_id:str,item_id:str,body:TaskChecklistUpdate,request:Request,user:User=Depends(require_permission("tasks.view",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,record_id,lodge_id,"Task");_ensure_department_scope(ctx,task.department_id,"task");full=_may(db,ctx,"tasks.manage");own=_may(db,ctx,"tasks.own.manage") and ctx.staff and task.assigned_staff_id==ctx.staff.id
    if not full and not own:raise HTTPException(403,"You may only update checklist items on tasks assigned to you")
    item=tenant_get(db,TaskChecklistItem,item_id,lodge_id,"Checklist item")
    if item.task_id!=task.id:raise HTTPException(404,"Checklist item not found")
    item.completed_at=datetime.now(timezone.utc) if body.completed else None;item.completed_by_user_id=user.id if body.completed else None;audit(db,request,lodge_id,user.id,"task.checklist_updated","task",str(task.id));db.commit();return {"id":str(item.id),"completed":body.completed}

@app.get("/api/v1/lodges/{lodge_id}/tasks/{record_id}/comments")
def task_comments(lodge_id:str,record_id:str,user:User=Depends(require_permission("tasks.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,record_id,lodge_id,"Task");_assert_task_visible(db,ctx,task)
    rows=db.scalars(select(TaskComment).where(TaskComment.task_id==task.id).order_by(TaskComment.created_at)).all();return [{"id":str(x.id),"user_id":str(x.user_id),"author":db.get(User,x.user_id).full_name if db.get(User,x.user_id) else "User","body":x.body,"created_at":x.created_at.isoformat()} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/tasks/{record_id}/comments",dependencies=[Depends(require_csrf)])
def add_task_comment(lodge_id:str,record_id:str,body:TaskCommentCreate,request:Request,user:User=Depends(require_permission("tasks.view",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"advanced_tasks");ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,record_id,lodge_id,"Task");_ensure_department_scope(ctx,task.department_id,"task")
    full=_may(db,ctx,"tasks.manage");own=_may(db,ctx,"tasks.own.manage") and ctx.staff and task.assigned_staff_id==ctx.staff.id
    if not full and not own:raise HTTPException(403,"You may only comment on tasks you are authorised to manage")
    if not body.body.strip():raise HTTPException(422,"Comment cannot be empty")
    row=TaskComment(lodge_id=lodge_id,task_id=task.id,user_id=user.id,body=body.body.strip());db.add(row);db.flush();audit(db,request,lodge_id,user.id,"task.comment_added","task",str(task.id));db.commit();return {"id":str(row.id)}

@app.get("/api/v1/lodges/{lodge_id}/housekeeping-jobs")
def list_housekeeping_jobs(lodge_id:str,user:User=Depends(require_permission("housekeeping.view")),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);q=select(HousekeepingJob).where(HousekeepingJob.lodge_id==lodge_id)
    if ctx.role_key=="housekeeping":q=q.where(HousekeepingJob.assigned_staff_id==_require_own_staff(ctx).id)
    elif ctx.role_key=="department_manager":q=q.join(StaffProfile,StaffProfile.id==HousekeepingJob.assigned_staff_id).where(StaffProfile.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(HousekeepingJob.due_at.asc().nullslast(),HousekeepingJob.created_at.desc())).all()
    return [{"id":str(x.id),"unit_id":str(x.unit_id),"unit_name":db.get(Unit,x.unit_id).name if db.get(Unit,x.unit_id) else "","assigned_staff_id":str(x.assigned_staff_id) if x.assigned_staff_id else None,"assigned_staff_name":_name_staff(db,x.assigned_staff_id),"inspector_staff_id":str(x.inspector_staff_id) if x.inspector_staff_id else None,"job_type":x.job_type,"status":x.status,"linen_notes":x.linen_notes,"notes":x.notes,"due_at":x.due_at.isoformat() if x.due_at else None} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/housekeeping-jobs",dependencies=[Depends(require_csrf)])
def create_housekeeping_job(lodge_id:str,body:HousekeepingCreate,request:Request,user:User=Depends(require_permission("housekeeping.manage",write=True)),db:Session=Depends(get_db)):
    full_workflow=entitlement_enabled(db,lodge_id,"housekeeping_full")
    if not full_workflow and (body.job_type not in {"cleaning","guest_request"} or body.inspector_staff_id or body.linen_notes):
        raise HTTPException(403,"Turndown, inspections and linen workflows require Standard or Premium")
    ctx=_ctx(db,user,lodge_id);unit=ensure_fk(db,Unit,body.unit_id,lodge_id,"Unit");staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile");inspector=ensure_fk(db,StaffProfile,body.inspector_staff_id,lodge_id,"Inspector")
    if ctx.role_key=="department_manager":
        if staff and staff.department_id!=ctx.department_id:raise HTTPException(403,"Department Manager can only assign housekeeping within their department")
        if inspector and inspector.department_id!=ctx.department_id:raise HTTPException(403,"Department Manager can only select inspectors within their department")
    housekeeping_job_created(db,unit,body.job_type)
    row=HousekeepingJob(lodge_id=lodge_id,unit_id=unit.id,assigned_staff_id=staff.id if staff else None,inspector_staff_id=inspector.id if inspector else None,job_type=body.job_type,status="assigned",linen_notes=body.linen_notes,notes=body.notes,due_at=body.due_at,created_by_user_id=user.id);db.add(row);db.flush();audit(db,request,lodge_id,user.id,"housekeeping.created","housekeeping",str(row.id));event(db,lodge_id,user.id,"housekeeping.created","unit",str(unit.id),f"{body.job_type} assigned for {unit.name}");db.commit();return {"id":str(row.id),"status":row.status}

HK_TRANSITIONS={"assigned":{"accepted","in_progress","cancelled"},"accepted":{"in_progress","cancelled"},"in_progress":{"awaiting_inspection","completed","cancelled"},"awaiting_inspection":{"completed","in_progress","cancelled"},"completed":set(),"cancelled":set()}
@app.patch("/api/v1/lodges/{lodge_id}/housekeeping-jobs/{record_id}",dependencies=[Depends(require_csrf)])
def update_housekeeping_job(lodge_id:str,record_id:str,body:HousekeepingUpdate,request:Request,user:User=Depends(require_permission("housekeeping.view",write=True)),db:Session=Depends(get_db)):
    ctx=_ctx(db,user,lodge_id);row=tenant_get(db,HousekeepingJob,record_id,lodge_id,"Housekeeping job");full=_may(db,ctx,"housekeeping.manage");own=_may(db,ctx,"housekeeping.own.manage") and ctx.staff and row.assigned_staff_id==ctx.staff.id;inspector=bool(ctx.staff and row.inspector_staff_id==ctx.staff.id)
    inspector_completion=inspector and row.status=="awaiting_inspection" and body.status=="completed"
    if not full and not own and not inspector_completion:raise HTTPException(403,"You may only update housekeeping assigned to you or inspections assigned to you")
    if not full and (body.assigned_staff_id is not None or body.inspector_staff_id is not None):raise HTTPException(403,"Assigned housekeeping staff cannot reassign jobs")
    if body.assigned_staff_id is not None:row.assigned_staff_id=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile").id
    if body.inspector_staff_id is not None:row.inspector_staff_id=ensure_fk(db,StaffProfile,body.inspector_staff_id,lodge_id,"Inspector").id
    if body.linen_notes is not None:row.linen_notes=body.linen_notes
    if body.notes is not None:row.notes=body.notes
    if body.status and body.status!=row.status:
        if body.status not in HK_TRANSITIONS.get(row.status,set()):raise HTTPException(409,f"Housekeeping job cannot transition from {row.status} to {body.status}")
        if row.inspector_staff_id and row.status=="in_progress" and body.status=="completed":raise HTTPException(409,"This job must move to awaiting inspection before completion")
        now=datetime.now(timezone.utc);previous_status=row.status;row.status=body.status
        if body.status=="accepted":row.accepted_at=now
        elif body.status=="in_progress":row.started_at=row.started_at or now
        elif body.status=="awaiting_inspection":row.completed_at=now;housekeeping_awaiting_inspection(db,db.get(Unit,row.unit_id))
        elif body.status=="completed":
            if row.inspector_staff_id and previous_status!="awaiting_inspection":raise HTTPException(409,"This job requires inspection before completion")
            if previous_status=="awaiting_inspection" and row.inspector_staff_id and not (full or inspector):raise HTTPException(403,"Only the named inspector or a housekeeping manager can complete this inspection")
            row.completed_at=row.completed_at or now;row.inspected_at=now if row.inspector_staff_id else row.inspected_at;housekeeping_completed(db,db.get(Unit,row.unit_id))
        event(db,lodge_id,user.id,"housekeeping.status_changed","housekeeping",str(row.id),f"Housekeeping changed to {row.status}")
    audit(db,request,lodge_id,user.id,"housekeeping.updated","housekeeping",str(row.id));db.commit();return {"id":str(row.id),"status":row.status}

@app.get("/api/v1/lodges/{lodge_id}/maintenance-assets")
def list_maintenance_assets(lodge_id:str,user:User=Depends(require_permission("maintenance.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"maintenance_workshop");rows=db.scalars(select(MaintenanceAsset).where(MaintenanceAsset.lodge_id==lodge_id).order_by(MaintenanceAsset.asset_code)).all();return [{"id":str(x.id),"asset_code":x.asset_code,"name":x.name,"category":x.category,"unit_id":str(x.unit_id) if x.unit_id else None,"vehicle_id":str(x.vehicle_id) if x.vehicle_id else None,"status":x.status,"service_interval_days":x.service_interval_days,"next_service_date":x.next_service_date.isoformat() if x.next_service_date else None,"notes":x.notes} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/maintenance-assets",dependencies=[Depends(require_csrf)])
def create_maintenance_asset(lodge_id:str,body:MaintenanceAssetCreate,request:Request,user:User=Depends(require_permission("maintenance.assets.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"maintenance_workshop");ensure_fk(db,Unit,body.unit_id,lodge_id,"Unit");ensure_fk(db,Vehicle,body.vehicle_id,lodge_id,"Vehicle")
    row=MaintenanceAsset(lodge_id=lodge_id,**body.model_dump(),status="active");db.add(row);db.flush();audit(db,request,lodge_id,user.id,"maintenance_asset.created","maintenance_asset",str(row.id));commit_or_conflict(db,"Asset code already exists for this lodge");return {"id":str(row.id)}

@app.get("/api/v1/lodges/{lodge_id}/maintenance/{record_id}/parts")
def list_maintenance_parts(lodge_id:str,record_id:str,user:User=Depends(require_permission("maintenance.view")),db:Session=Depends(get_db)):
    ticket=tenant_get(db,MaintenanceTicket,record_id,lodge_id,"Maintenance ticket");rows=db.scalars(select(MaintenancePartUsage).where(MaintenancePartUsage.maintenance_ticket_id==ticket.id).order_by(MaintenancePartUsage.created_at)).all();return [{"id":str(x.id),"part_name":x.part_name,"quantity":x.quantity,"unit_cost_cents":x.unit_cost_cents,"total_cost_cents":x.quantity*x.unit_cost_cents,"notes":x.notes} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/maintenance/{record_id}/parts",dependencies=[Depends(require_csrf)])
def add_maintenance_part(lodge_id:str,record_id:str,body:MaintenancePartCreate,request:Request,user:User=Depends(require_permission("maintenance.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"maintenance_workshop");ticket=tenant_get(db,MaintenanceTicket,record_id,lodge_id,"Maintenance ticket");row=MaintenancePartUsage(lodge_id=lodge_id,maintenance_ticket_id=ticket.id,**body.model_dump());db.add(row);ticket.cost_cents=(ticket.cost_cents or 0)+(body.quantity*body.unit_cost_cents);db.flush();audit(db,request,lodge_id,user.id,"maintenance.part_added","maintenance",str(ticket.id));db.commit();return {"id":str(row.id),"ticket_cost_cents":ticket.cost_cents}

# --- Core operations completion 1.6 ---

def _assert_task_visible(db:Session,ctx,task:Task):
    if ctx.role_key=="department_manager":
        _ensure_department_scope(ctx,task.department_id,"task")
    elif ctx.role_key in {"housekeeping","ranger","maintenance","driver","fb","general_staff"}:
        staff=_require_own_staff(ctx)
        if task.assigned_staff_id!=staff.id:
            raise HTTPException(403,"You can only access tasks assigned to you")

def _department_scoped_query(ctx, model, q):
    if ctx.role_key == "department_manager" and ctx.department_id and hasattr(model, "department_id"):
        q=q.where(model.department_id==ctx.department_id)
    return q

@app.get("/api/v1/lodges/{lodge_id}/feedback")
def list_guest_feedback(lodge_id:str,user:User=Depends(require_permission("feedback.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"guest_feedback");ctx=_ctx(db,user,lodge_id)
    q=select(GuestFeedback).where(GuestFeedback.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(GuestFeedback.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(GuestFeedback.created_at.desc()).limit(500)).all()
    return [{"id":str(x.id),"guest_id":str(x.guest_id),"guest_name":_name_guest(db,x.guest_id),"stay_id":str(x.stay_id) if x.stay_id else None,"department_id":str(x.department_id) if x.department_id else None,"assigned_staff_id":str(x.assigned_staff_id) if x.assigned_staff_id else None,"assigned_staff_name":_name_staff(db,x.assigned_staff_id),"feedback_type":x.feedback_type,"category":x.category,"rating":x.rating,"comments":x.comments,"follow_up_required":x.follow_up_required,"status":x.status,"resolution":x.resolution,"resolved_at":x.resolved_at.isoformat() if x.resolved_at else None,"created_at":x.created_at.isoformat()} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/feedback",dependencies=[Depends(require_csrf)])
def create_guest_feedback(lodge_id:str,body:GuestFeedbackCreate,request:Request,user:User=Depends(require_permission("feedback.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"guest_feedback");ctx=_ctx(db,user,lodge_id)
    ensure_fk(db,Guest,body.guest_id,lodge_id,"Guest")
    if body.stay_id:
        stay=ensure_fk(db,Stay,body.stay_id,lodge_id,"Stay")
        if stay.guest_id!=body.guest_id:raise HTTPException(422,"Stay does not belong to this guest")
    if body.department_id:ensure_fk(db,Department,body.department_id,lodge_id,"Department")
    if ctx.role_key=="department_manager" and body.department_id!=ctx.department_id:raise HTTPException(403,"Department Manager can only create feedback for their department")
    if body.assigned_staff_id:
        staff=ensure_fk(db,StaffProfile,body.assigned_staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
        if body.department_id and staff.department_id!=body.department_id:raise HTTPException(422,"Assigned staff must belong to the selected department")
    row=GuestFeedback(lodge_id=lodge_id,created_by_user_id=user.id,**body.model_dump());db.add(row);db.flush()
    audit(db,request,lodge_id,user.id,"guest_feedback.created","guest_feedback",str(row.id),body.feedback_type);event(db,lodge_id,user.id,"guest.feedback_created","guest",str(body.guest_id),f"{body.feedback_type.title()} recorded for {_name_guest(db,body.guest_id)}")
    db.commit();return {"id":str(row.id),"status":row.status}

@app.patch("/api/v1/lodges/{lodge_id}/feedback/{record_id}",dependencies=[Depends(require_csrf)])
def update_guest_feedback(lodge_id:str,record_id:str,body:GuestFeedbackUpdate,request:Request,user:User=Depends(require_permission("feedback.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"guest_feedback");ctx=_ctx(db,user,lodge_id);row=tenant_get(db,GuestFeedback,record_id,lodge_id,"Guest feedback")
    if ctx.role_key=="department_manager" and row.department_id!=ctx.department_id:raise HTTPException(403,"Department Manager can only manage feedback for their department")
    data=body.model_dump(exclude_unset=True)
    if "department_id" in data and data["department_id"]:
        ensure_fk(db,Department,data["department_id"],lodge_id,"Department")
        if ctx.role_key=="department_manager" and data["department_id"]!=ctx.department_id:raise HTTPException(403,"Department Manager cannot move feedback outside their department")
    if "assigned_staff_id" in data and data["assigned_staff_id"]:
        staff=ensure_fk(db,StaffProfile,data["assigned_staff_id"],lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    target=data.get("status",row.status);feedback_transitions={"open":{"in_progress","resolved","closed"},"in_progress":{"resolved","closed","open"},"resolved":{"closed","in_progress"},"closed":set()}
    if "status" in data and target!=row.status and target not in feedback_transitions.get(row.status,set()):raise HTTPException(409,f"Feedback cannot transition from {row.status} to {target}")
    if target in {"resolved","closed"} and not (data.get("resolution") or row.resolution).strip():raise HTTPException(422,"Resolution is required before resolving feedback")
    previous_status=row.status
    for k,v in data.items():setattr(row,k,v)
    if row.status in {"resolved","closed"} and previous_status not in {"resolved","closed"}:row.resolved_at=datetime.now(timezone.utc)
    elif row.status not in {"resolved","closed"}:row.resolved_at=None
    audit(db,request,lodge_id,user.id,"guest_feedback.updated","guest_feedback",str(row.id),row.status);event(db,lodge_id,user.id,"guest.feedback_updated","guest_feedback",str(row.id),f"Guest feedback is {row.status.replace('_',' ')}")
    db.commit();return {"id":str(row.id),"status":row.status}

@app.get("/api/v1/lodges/{lodge_id}/hr/shifts")
def list_staff_shifts(lodge_id:str,user:User=Depends(require_permission("staff.hr.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_roster");ctx=_ctx(db,user,lodge_id);q=select(StaffShift).where(StaffShift.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.join(StaffProfile,StaffProfile.id==StaffShift.staff_id).where(StaffProfile.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(StaffShift.starts_at.desc()).limit(1000)).all()
    return [{"id":str(x.id),"staff_id":str(x.staff_id),"staff_name":_name_staff(db,x.staff_id),"starts_at":x.starts_at.isoformat(),"ends_at":x.ends_at.isoformat(),"status":x.status,"notes":x.notes} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/hr/shifts",dependencies=[Depends(require_csrf)])
def create_staff_shift(lodge_id:str,body:StaffShiftCreate,request:Request,user:User=Depends(require_permission("staff.roster.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_roster");ctx=_ctx(db,user,lodge_id);staff=ensure_fk(db,StaffProfile,body.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    if body.ends_at<=body.starts_at:raise HTTPException(422,"Shift end must be after shift start")
    overlap=db.scalar(select(StaffShift.id).where(StaffShift.lodge_id==lodge_id,StaffShift.staff_id==body.staff_id,StaffShift.status.in_(["scheduled","confirmed"]),StaffShift.starts_at<body.ends_at,StaffShift.ends_at>body.starts_at))
    if overlap:raise HTTPException(409,"Staff member already has an overlapping shift")
    row=StaffShift(lodge_id=lodge_id,created_by_user_id=user.id,staff_id=body.staff_id,starts_at=body.starts_at,ends_at=body.ends_at,notes=body.notes);db.add(row);db.flush();audit(db,request,lodge_id,user.id,"staff_shift.created","staff_shift",str(row.id));db.commit();return {"id":str(row.id),"status":row.status}

@app.patch("/api/v1/lodges/{lodge_id}/hr/shifts/{record_id}",dependencies=[Depends(require_csrf)])
def update_staff_shift(lodge_id:str,record_id:str,body:StaffShiftUpdate,request:Request,user:User=Depends(require_permission("staff.roster.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_roster");ctx=_ctx(db,user,lodge_id);row=tenant_get(db,StaffShift,record_id,lodge_id,"Staff shift");staff=tenant_get(db,StaffProfile,row.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff)
    transitions={"scheduled":{"confirmed","cancelled"},"confirmed":{"completed","cancelled"},"completed":set(),"cancelled":set()}
    if body.status!=row.status and body.status not in transitions.get(row.status,set()):raise HTTPException(409,f"Invalid shift transition from {row.status} to {body.status}")
    row.status=body.status;audit(db,request,lodge_id,user.id,"staff_shift.updated","staff_shift",str(row.id),row.status);db.commit();return {"id":str(row.id),"status":row.status}

@app.get("/api/v1/lodges/{lodge_id}/hr/incidents")
def list_staff_incidents(lodge_id:str,user:User=Depends(require_permission("staff.performance.manage")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_performance");ctx=_ctx(db,user,lodge_id);q=select(StaffIncident).where(StaffIncident.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.join(StaffProfile,StaffProfile.id==StaffIncident.staff_id).where(StaffProfile.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(StaffIncident.occurred_at.desc()).limit(500)).all();return [{"id":str(x.id),"staff_id":str(x.staff_id),"staff_name":_name_staff(db,x.staff_id),"incident_type":x.incident_type,"severity":x.severity,"occurred_at":x.occurred_at.isoformat(),"description":x.description,"action_taken":x.action_taken,"is_confidential":x.is_confidential} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/hr/incidents",dependencies=[Depends(require_csrf)])
def create_staff_incident(lodge_id:str,body:StaffIncidentCreate,request:Request,user:User=Depends(require_permission("staff.performance.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_performance");ctx=_ctx(db,user,lodge_id);staff=ensure_fk(db,StaffProfile,body.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff);row=StaffIncident(lodge_id=lodge_id,created_by_user_id=user.id,**body.model_dump());db.add(row);db.flush();audit(db,request,lodge_id,user.id,"staff_incident.created","staff_incident",str(row.id),body.severity);db.commit();return {"id":str(row.id)}

@app.get("/api/v1/lodges/{lodge_id}/hr/performance")
def list_staff_performance(lodge_id:str,user:User=Depends(require_permission("staff.performance.manage")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_performance");ctx=_ctx(db,user,lodge_id);q=select(StaffPerformanceNote).where(StaffPerformanceNote.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.join(StaffProfile,StaffProfile.id==StaffPerformanceNote.staff_id).where(StaffProfile.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(StaffPerformanceNote.review_date.desc()).limit(500)).all();return [{"id":str(x.id),"staff_id":str(x.staff_id),"staff_name":_name_staff(db,x.staff_id),"note_type":x.note_type,"rating":x.rating,"notes":x.notes,"review_date":x.review_date.isoformat()} for x in rows]

@app.post("/api/v1/lodges/{lodge_id}/hr/performance",dependencies=[Depends(require_csrf)])
def create_staff_performance(lodge_id:str,body:StaffPerformanceCreate,request:Request,user:User=Depends(require_permission("staff.performance.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"staff_performance");ctx=_ctx(db,user,lodge_id);staff=ensure_fk(db,StaffProfile,body.staff_id,lodge_id,"Staff profile");_assert_staff_scope(ctx,staff);row=StaffPerformanceNote(lodge_id=lodge_id,created_by_user_id=user.id,**body.model_dump());db.add(row);db.flush();audit(db,request,lodge_id,user.id,"staff_performance.created","staff_performance",str(row.id),body.note_type);db.commit();return {"id":str(row.id)}

@app.get("/api/v1/lodges/{lodge_id}/food-beverage/meals")
def list_meal_services(lodge_id:str,user:User=Depends(require_permission("fb.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"fb_operations");ctx=_ctx(db,user,lodge_id);q=select(MealService).where(MealService.lodge_id==lodge_id)
    if ctx.role_key=="department_manager":q=q.where(MealService.department_id==ctx.department_id)
    rows=db.scalars(q.order_by(MealService.scheduled_at.desc()).limit(500)).all();out=[];now=datetime.now(timezone.utc)
    for x in rows:
        service_window=abs((x.scheduled_at-now).total_seconds())<=86400
        gs=db.scalars(select(MealServiceGuest).where(MealServiceGuest.meal_service_id==x.id)).all();guest_rows=[]
        for link in gs:
            g=tenant_get(db,Guest,link.guest_id,lodge_id,"Guest");guest_rows.append({"guest_id":str(g.id),"guest_name":f"{g.first_name} {g.last_name}".strip(),"dietary_requirements":g.dietary_requirements if service_window else "","allergies":g.allergies if service_window else "","notes":link.notes})
        out.append({"id":str(x.id),"department_id":str(x.department_id) if x.department_id else None,"name":x.name,"meal_type":x.meal_type,"scheduled_at":x.scheduled_at.isoformat(),"location":x.location,"expected_guest_count":x.expected_guest_count,"status":x.status,"notes":x.notes,"guests":guest_rows})
    return out

@app.post("/api/v1/lodges/{lodge_id}/food-beverage/meals",dependencies=[Depends(require_csrf)])
def create_meal_service(lodge_id:str,body:MealServiceCreate,request:Request,user:User=Depends(require_permission("fb.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"fb_operations");ctx=_ctx(db,user,lodge_id);guest_ids=list(dict.fromkeys(body.guest_ids))
    for gid in guest_ids:ensure_fk(db,Guest,gid,lodge_id,"Guest")
    data=body.model_dump(exclude={"guest_ids"})
    if ctx.role_key=="department_manager":
        if data.get("department_id") and data["department_id"]!=ctx.department_id:raise HTTPException(403,"Department Manager can only create meal services for their department")
        data["department_id"]=ctx.department_id
    elif data.get("department_id"):ensure_fk(db,Department,data["department_id"],lodge_id,"Department")
    row=MealService(lodge_id=lodge_id,created_by_user_id=user.id,**data);db.add(row);db.flush()
    for gid in guest_ids:db.add(MealServiceGuest(lodge_id=lodge_id,meal_service_id=row.id,guest_id=gid,notes=""))
    audit(db,request,lodge_id,user.id,"meal_service.created","meal_service",str(row.id),row.meal_type);event(db,lodge_id,user.id,"fb.meal_scheduled","meal_service",str(row.id),f"{row.name} scheduled");db.commit();return {"id":str(row.id),"status":row.status}

@app.patch("/api/v1/lodges/{lodge_id}/food-beverage/meals/{record_id}",dependencies=[Depends(require_csrf)])
def update_meal_service(lodge_id:str,record_id:str,body:MealServiceUpdate,request:Request,user:User=Depends(require_permission("fb.manage",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"fb_operations");ctx=_ctx(db,user,lodge_id);row=tenant_get(db,MealService,record_id,lodge_id,"Meal service")
    if ctx.role_key=="department_manager" and row.department_id!=ctx.department_id:raise HTTPException(403,"Department Manager can only manage meal services in their department")
    data=body.model_dump(exclude_unset=True)
    transitions={"scheduled":{"preparing","cancelled"},"preparing":{"serving","cancelled"},"serving":{"completed"},"completed":set(),"cancelled":set()}
    if "status" in data and data["status"]!=row.status and data["status"] not in transitions.get(row.status,set()):raise HTTPException(409,f"Invalid meal service transition from {row.status} to {data['status']}")
    for k,v in data.items():setattr(row,k,v)
    audit(db,request,lodge_id,user.id,"meal_service.updated","meal_service",str(row.id),row.status);db.commit();return {"id":str(row.id),"status":row.status}

@app.post("/api/v1/lodges/{lodge_id}/tasks/{task_id}/attachments/upload-url",dependencies=[Depends(require_csrf)])
def task_attachment_upload_url(lodge_id:str,task_id:str,body:TaskAttachmentUploadRequest,user:User=Depends(require_permission("tasks.view",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"task_attachments");ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,task_id,lodge_id,"Task");_assert_task_visible(db,ctx,task)
    can_upload=_may(db,ctx,"tasks.manage") or (_may(db,ctx,"tasks.own.manage") and ctx.staff and task.assigned_staff_id==ctx.staff.id)
    if not can_upload: raise HTTPException(403,"Your role cannot upload files to this task")
    ext={"image/jpeg":"jpg","image/png":"png","image/webp":"webp","image/heic":"heic","image/heif":"heif","application/pdf":"pdf"}[body.content_type]
    key=f"lodges/{lodge_id}/tasks/{task_id}/{uuid.uuid4()}.{ext}";params={"Bucket":settings.object_storage_bucket,"Key":key,"ContentType":body.content_type,"Metadata":{"sha256":body.sha256.lower()}}
    return {"object_key":key,"upload_url":s3_public.generate_presigned_url("put_object",Params=params,ExpiresIn=900,HttpMethod="PUT"),"expires_in_seconds":900,"required_headers":{"Content-Type":body.content_type,"x-amz-meta-sha256":body.sha256.lower()}}

@app.post("/api/v1/lodges/{lodge_id}/tasks/{task_id}/attachments",dependencies=[Depends(require_csrf)])
def register_task_attachment(lodge_id:str,task_id:str,body:TaskAttachmentRegister,request:Request,user:User=Depends(require_permission("tasks.view",write=True)),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"task_attachments");ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,task_id,lodge_id,"Task");_assert_task_visible(db,ctx,task)
    if not (_may(db,ctx,"tasks.manage") or (_may(db,ctx,"tasks.own.manage") and ctx.staff and task.assigned_staff_id==ctx.staff.id)):raise HTTPException(403,"Only task managers or the assigned staff member can add attachments")
    prefix=f"lodges/{lodge_id}/tasks/{task_id}/"
    if not body.object_key.startswith(prefix):raise HTTPException(400,"Invalid attachment object key")
    try:head=s3_internal.head_object(Bucket=settings.object_storage_bucket,Key=body.object_key)
    except ClientError:raise HTTPException(409,"Uploaded object was not found in object storage")
    if int(head.get("ContentLength",0))!=body.size_bytes or head.get("ContentType")!=body.content_type:raise HTTPException(409,"Uploaded file metadata does not match")
    obj=s3_internal.get_object(Bucket=settings.object_storage_bucket,Key=body.object_key);digest=hashlib.sha256()
    for chunk in iter(lambda: obj["Body"].read(1024*1024),b""):digest.update(chunk)
    obj["Body"].close()
    if digest.hexdigest().lower()!=body.sha256.lower():raise HTTPException(409,"Uploaded file checksum does not match")
    row=TaskAttachment(lodge_id=lodge_id,task_id=task.id,uploaded_by_user_id=user.id,**body.model_dump());db.add(row);db.flush();audit(db,request,lodge_id,user.id,"task_attachment.registered","task_attachment",str(row.id),row.file_name);commit_or_conflict(db,"This task attachment has already been registered");return {"id":str(row.id)}

@app.get("/api/v1/lodges/{lodge_id}/tasks/{task_id}/attachments")
def list_task_attachments(lodge_id:str,task_id:str,user:User=Depends(require_permission("tasks.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"task_attachments");ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,task_id,lodge_id,"Task");_assert_task_visible(db,ctx,task);rows=db.scalars(select(TaskAttachment).where(TaskAttachment.task_id==task.id).order_by(TaskAttachment.created_at)).all();return [{"id":str(x.id),"file_name":x.file_name,"content_type":x.content_type,"size_bytes":x.size_bytes,"created_at":x.created_at.isoformat()} for x in rows]

@app.get("/api/v1/lodges/{lodge_id}/tasks/{task_id}/attachments/{attachment_id}/download-url")
def task_attachment_download_url(lodge_id:str,task_id:str,attachment_id:str,user:User=Depends(require_permission("tasks.view")),db:Session=Depends(get_db)):
    ensure_feature(db,lodge_id,"task_attachments");ctx=_ctx(db,user,lodge_id);task=tenant_get(db,Task,task_id,lodge_id,"Task");_assert_task_visible(db,ctx,task);row=tenant_get(db,TaskAttachment,attachment_id,lodge_id,"Task attachment")
    if row.task_id!=task.id:raise HTTPException(404,"Task attachment not found")
    return {"url":s3_public.generate_presigned_url("get_object",Params={"Bucket":settings.object_storage_bucket,"Key":row.object_key},ExpiresIn=600),"expires_in_seconds":600}
