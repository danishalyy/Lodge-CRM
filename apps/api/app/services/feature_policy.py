"""Shared server-side capability policy; permissions never imply a subscription."""

PERMISSION_FEATURES = {
    "dashboard": ("dashboard",),
    "guests": ("guests",),
    "guest_portal": ("guest_mobile",),
    "stays": ("stays",),
    "units": ("units",),
    "staff": ("staff",),
    "staff.hr": ("staff", "staff_hr"),
    "staff.roster": ("staff", "staff_hr", "staff_roster"),
    "staff.performance": ("staff", "staff_hr", "staff_performance"),
    "departments": ("departments",),
    "roles.custom": ("custom_roles",),
    "tasks": ("tasks",),
    "requests": ("guest_requests",),
    "feedback": ("guest_feedback",),
    "housekeeping": ("housekeeping",),
    "maintenance": ("maintenance",),
    "maintenance.assets": ("maintenance", "maintenance_workshop"),
    "vehicles": ("fleet",),
    "vehicle_checklists": ("fleet", "vehicle_checklists"),
    "fuel": ("fuel",),
    "activities": ("activities",),
    "transfers": ("transfers",),
    "wildlife": ("wildlife",),
    "ranger": ("ranger",),
    "fb": ("fb_operations",),
    "reports": ("reports",),
    "audit": ("audit",),
    "memory": (),
    "notifications": ("notifications",),
    "ai": ("ai",),
    "ai.actions": ("ai", "ai_actions"),
    "ai.group": ("ai", "advanced_ai"),
    "knowledge": ("ai_knowledge", "document_knowledge"),
    # Lodge preferences are account administration, not a paid module.
    "lodge.settings": (),
}


def features_for_permission(permission: str) -> tuple[str, ...]:
    """Longest namespace match also covers new actions in an existing module.

    Unknown namespaces fail closed, preventing a new permission from silently
    omitting its feature policy. Declare new modules here alongside their grant.
    """
    parts = permission.split(".")
    while parts:
        prefix = ".".join(parts)
        if prefix in PERMISSION_FEATURES:
            return PERMISSION_FEATURES[prefix]
        parts.pop()
    raise ValueError("Permission has no declared feature policy")
