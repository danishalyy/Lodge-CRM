"""Read-time history authorization and privacy projections.

Immutable events are evidence, not an authorization bypass. Restricted actors
must still be entitled to the module and able to read its underlying record.
Legacy events without enough scope information fail closed for those actors.
"""
from sqlalchemy import String, and_, cast, false, or_, select
from .. import models as m
from ..security import entitlement_enabled, has_permission
from .feature_policy import features_for_permission

FAMILIES = {
    "task": (m.Task, "tasks.view"),
    "guest": (m.Guest, "guests.view"),
    "stay": (m.Stay, "stays.view"),
    "guest_request": (m.GuestRequest, "requests.view"),
    "guest_feedback": (m.GuestFeedback, "feedback.view"),
    "unit": (m.Unit, "units.view"),
    "vehicle": (m.Vehicle, "vehicles.view"),
    "maintenance": (m.MaintenanceTicket, "maintenance.view"),
    "housekeeping": (m.HousekeepingJob, "housekeeping.view"),
    "activity": (m.Activity, "activities.view"),
    "transfer": (m.Transfer, "transfers.view"),
    "staff": (m.StaffProfile, "staff.hr.view"),
    "staff_profile": (m.StaffProfile, "staff.hr.view"),
    "vehicle_checklist": (m.VehicleChecklist, "vehicle_checklists.view"),
    "wildlife_sighting": (m.WildlifeSighting, "wildlife.view"),
    "meal_service": (m.MealService, "fb.view"),
    "staff_leave": (m.StaffLeave, "staff.hr.view"),
    "staff_credential": (m.StaffCredential, "staff.hr.view"),
    "staff_training": (m.StaffTraining, "staff.hr.view"),
    "staff_incident": (m.StaffIncident, "staff.performance.manage"),
    "staff_performance": (m.StaffPerformanceNote, "staff.performance.manage"),
}
GLOBAL_SCOPES = {"lodge_admin", "group_admin", "front_office", "finance", "read_only"}


def can_read(db, ctx, permission):
    return has_permission(db, ctx.membership, permission) and all(
        entitlement_enabled(db, ctx.membership.lodge_id, feature)
        for feature in features_for_permission(permission)
    )


def scoped_ids(ctx, model, lodge_id):
    q = select(cast(model.id, String)).where(model.lodge_id == lodge_id)
    if ctx.role_key == "department_manager":
        if not ctx.department_id:
            return q.where(false())
        if hasattr(model, "department_id"):
            return q.where(model.department_id == ctx.department_id)
        staff = select(m.StaffProfile.id).where(
            m.StaffProfile.lodge_id == lodge_id,
            m.StaffProfile.department_id == ctx.department_id,
        )
        if hasattr(model, "staff_id"):
            return q.where(model.staff_id.in_(staff))
        if model is m.HousekeepingJob:
            return q.where(or_(model.assigned_staff_id.in_(staff), model.inspector_staff_id.in_(staff)))
        return q.where(false())
    staff_id = ctx.staff.id if ctx.staff else None
    if model is m.MaintenanceTicket:
        if ctx.role_key == "maintenance":
            return q
        return q.where(or_(model.created_by_user_id == ctx.user.id,
                           model.assigned_staff_id == staff_id if staff_id else false()))
    if not staff_id:
        return q.where(false())
    if model in {m.Task, m.GuestRequest, m.GuestFeedback}:
        return q.where(model.assigned_staff_id == staff_id)
    if model is m.HousekeepingJob:
        return q.where(or_(model.assigned_staff_id == staff_id, model.inspector_staff_id == staff_id))
    if model is m.Activity:
        return q.where(model.guide_staff_id == staff_id)
    if model is m.Transfer:
        return q.where(model.driver_staff_id == staff_id)
    return q.where(false())


def visible_events(db, ctx, lodge_id):
    clauses = []
    for resource, (model, permission) in FAMILIES.items():
        if not can_read(db, ctx, permission):
            continue
        clause = m.OperationalEvent.resource_type == resource
        if ctx.role_key not in GLOBAL_SCOPES:
            clause = and_(clause, m.OperationalEvent.resource_id.in_(scoped_ids(ctx, model, lodge_id)))
        clauses.append(clause)
    # Management-only administrative events have no operational record reader.
    # Other roles must never gain these by delegating just memory.view.
    if ctx.role_key in {"lodge_admin", "group_admin"}:
        administrative=["lodge", "subscription"]
        if can_read(db,ctx,"departments.view"):
            administrative.append("department")
        if can_read(db,ctx,"roles.custom.manage"):
            administrative.append("custom_role")
        clauses.append(m.OperationalEvent.resource_type.in_(administrative))
    query=select(m.OperationalEvent).where(
        m.OperationalEvent.lodge_id == lodge_id,
        or_(*clauses) if clauses else false(),
    )
    # Legacy events sometimes point to a parent record instead of the module's
    # own record. Parent visibility must not grant the disabled child capability.
    aliases={"fuel.recorded":"fuel.view", "guest.feedback_created":"feedback.view", "housekeeping.created":"housekeeping.view"}
    for event_type,permission in aliases.items():
        if not can_read(db,ctx,permission):
            query=query.where(m.OperationalEvent.event_type!=event_type)
    return query


def project_event(db, event):
    summary, detail = event.summary, event.detail
    family = FAMILIES.get(event.resource_type)
    if family and event.resource_type in {"guest", "stay", "guest_request", "guest_feedback", "task", "transfer"}:
        model = family[0]
        # Comparing text does not attempt to cast malformed legacy IDs to UUID.
        record = db.scalar(select(model).where(cast(model.id, String) == event.resource_id))
        guest = record if model is m.Guest else db.get(m.Guest, record.guest_id) if record and getattr(record, "guest_id", None) else None
        if guest and guest.anonymized_at:
            summary, detail = "Historical event for an anonymised guest", ""
    return {
        "id": str(event.id), "event_type": event.event_type,
        "resource_type": event.resource_type, "resource_id": event.resource_id,
        "summary": summary, "detail": detail,
        "actor_user_id": str(event.actor_user_id) if event.actor_user_id else None,
        "created_at": event.created_at.isoformat(),
    }
