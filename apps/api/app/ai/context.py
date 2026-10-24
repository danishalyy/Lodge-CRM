"""Only authenticated server context determines scope. No model-supplied identity."""

import hashlib, json
from sqlalchemy import select
from fastapi import HTTPException
from ..config import settings
from ..db import set_rls_context
from ..models import (
    Permission,
    RolePermission,
    CustomRolePermission,
    CustomRole,
    PlanEntitlement,
    LodgeEntitlementOverride,
    Subscription,
    Lodge,
    User,
)
from ..security import current_user, require_permission, access_context, ensure_feature


def guard(db, user, lodge_id, request, write=False):
    db.expire_all()
    # Recheck the session, account and employment at every boundary, including after inference.
    user = current_user(
        lodge_session=request.cookies.get("lodge_session"),
        db=db,
        x_expected_user_id=str(user.id),
        x_lodge_context=str(lodge_id),
    )
    if user.is_super_admin:
        raise HTTPException(
            403,
            "Platform AI support access is not enabled. Use an explicitly assigned lodge account",
        )
    require_permission("ai.use", write=write)(
        lodge_id=str(lodge_id), request=request, user=user, db=db
    )
    ensure_feature(db, str(lodge_id), "ai")
    return access_context(db, user, str(lodge_id))


def fingerprint(db, ctx, lodge_id):
    member = ctx.membership
    if member.custom_role_id:
        permissions = db.scalars(
            select(Permission.key)
            .join(
                CustomRolePermission,
                Permission.id == CustomRolePermission.permission_id,
            )
            .where(CustomRolePermission.custom_role_id == member.custom_role_id)
        ).all()
    else:
        permissions = db.scalars(
            select(Permission.key)
            .join(RolePermission, Permission.id == RolePermission.permission_id)
            .where(RolePermission.role_id == member.role_id)
        ).all()
    sub = db.get(Subscription, lodge_id)
    lodge = db.get(Lodge, lodge_id)
    plan = db.execute(
        select(PlanEntitlement.feature_key, PlanEntitlement.enabled).where(
            PlanEntitlement.plan_key == (sub.package if sub else "")
        )
    ).all()
    overrides = db.execute(
        select(
            LodgeEntitlementOverride.feature_key, LodgeEntitlementOverride.enabled
        ).where(LodgeEntitlementOverride.lodge_id == lodge_id)
    ).all()
    data = [
        str(ctx.user.id),
        str(lodge_id),
        str(lodge.group_id),
        str(member.custom_role_id),
        ctx.role_key,
        str(ctx.department_id),
        str(ctx.staff.id) if ctx.staff else "",
        sorted(permissions),
        sorted((k, v) for k, v in plan),
        sorted((k, v) for k, v in overrides),
        str(sub.start_date) if sub else "",
        str(sub.expiry_date) if sub else "",
        sub.suspended if sub else True,
    ]
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
