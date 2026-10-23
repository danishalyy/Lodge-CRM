from datetime import date, datetime, timezone
import uuid
from sqlalchemy import LargeBinary, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    email_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_min_severity: Mapped[str] = mapped_column(String(20), default="normal")
    full_name: Mapped[str] = mapped_column(String(180))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_recovery_hashes: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    mfa_last_timestep: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Lodge(Base):
    __tablename__ = "lodges"
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lodge_groups.id", ondelete="SET NULL"), nullable=True, index=True)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    location: Mapped[str] = mapped_column(String(240), default="")
    timezone: Mapped[str] = mapped_column(String(80), default="Africa/Johannesburg")
    date_format: Mapped[str] = mapped_column(String(20), default="locale", server_default="locale")
    currency: Mapped[str] = mapped_column(String(3), default="ZAR", server_default="ZAR")
    brand_name: Mapped[str] = mapped_column(String(180), default="")
    logo_png: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True, deferred=True)
    protected_species: Mapped[str] = mapped_column(Text, default="rhino,black rhino,white rhino")
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "lodge_id", name="uq_membership_user_lodge"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id"))
    custom_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("custom_roles.id", ondelete="SET NULL"), nullable=True)
    previous_role_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), primary_key=True)
    package: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    expiry_date: Mapped[date] = mapped_column(Date)
    suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_lodge_created", "lodge_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80), default="")
    resource_id: Mapped[str] = mapped_column(String(80), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    request_id: Mapped[str] = mapped_column(String(80), default="")
    ip_address: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("lodge_id", "name", name="uq_department_lodge_name"), Index("ix_departments_lodge_active", "lodge_id", "is_active"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StaffProfile(Base):
    __tablename__ = "staff_profiles"
    __table_args__ = (UniqueConstraint("lodge_id", "employee_code", name="uq_staff_lodge_code"), Index("ix_staff_lodge_status", "lodge_id", "employment_status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    employee_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    full_name: Mapped[str] = mapped_column(String(180))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str] = mapped_column(String(80), default="")
    job_title: Mapped[str] = mapped_column(String(160), default="")
    employment_status: Mapped[str] = mapped_column(String(30), default="active")
    operational_status: Mapped[str] = mapped_column(String(30), default="available")
    supervisor_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True)
    hire_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("lodge_id", "name", name="uq_unit_lodge_name"), Index("ix_units_lodge_status", "lodge_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    unit_type: Mapped[str] = mapped_column(String(80), default="Room")
    status: Mapped[str] = mapped_column(String(40), default="available")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Guest(Base):
    __tablename__ = "guests"
    __table_args__ = (Index("ix_guests_lodge_name", "lodge_id", "last_name", "first_name"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    first_name: Mapped[str] = mapped_column(String(120))
    last_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str] = mapped_column(String(80), default="")
    nationality: Mapped[str] = mapped_column(String(120), default="")
    vip: Mapped[bool] = mapped_column(Boolean, default=False)
    dietary_requirements: Mapped[str] = mapped_column(Text, default="")
    allergies: Mapped[str] = mapped_column(Text, default="")
    preferences: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Stay(Base):
    __tablename__ = "stays"
    __table_args__ = (Index("ix_stays_lodge_dates", "lodge_id", "arrival_date", "departure_date"), CheckConstraint("departure_date >= arrival_date", name="ck_stay_dates"), CheckConstraint("party_size >= 1", name="ck_stay_party_size"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id", ondelete="RESTRICT"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    arrival_date: Mapped[date] = mapped_column(Date)
    departure_date: Mapped[date] = mapped_column(Date)
    party_size: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="upcoming")
    expected_arrival_time: Mapped[str] = mapped_column(String(10), default="")
    expected_departure_time: Mapped[str] = mapped_column(String(10), default="")
    transfer_notes: Mapped[str] = mapped_column(Text, default="")
    special_requirements: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (Index("ix_tasks_lodge_status_due", "lodge_id", "status", "due_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    guest_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id", ondelete="SET NULL"), nullable=True)
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), default="created")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurrence_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recurrence_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    proof_required: Mapped[bool] = mapped_column(Boolean, default=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class GuestRequest(Base):
    __tablename__ = "guest_requests"
    __table_args__ = (Index("ix_requests_lodge_status", "lodge_id", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id", ondelete="RESTRICT"), index=True)
    stay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stays.id", ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    request_type: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), default="open")
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"
    __table_args__ = (Index("ix_maintenance_lodge_status", "lodge_id", "status"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="general")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    status: Mapped[str] = mapped_column(String(30), default="open")
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("maintenance_assets.id", ondelete="SET NULL"), nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downtime_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    downtime_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recurrence_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution: Mapped[str] = mapped_column(Text, default="")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    __table_args__ = (Index("ix_events_lodge_created", "lodge_id", "created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(String(300))
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Vehicle(Base):
    __tablename__ = "vehicles"
    __table_args__ = (UniqueConstraint("lodge_id","registration",name="uq_vehicle_lodge_registration"), Index("ix_vehicles_lodge_status","lodge_id","status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    registration: Mapped[str] = mapped_column(String(80))
    name: Mapped[str] = mapped_column(String(160), default="")
    make: Mapped[str] = mapped_column(String(100), default="")
    model: Mapped[str] = mapped_column(String(100), default="")
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    odometer_km: Mapped[int] = mapped_column(Integer, default=0)
    fuel_capacity_litres: Mapped[float | None] = mapped_column(Numeric(10,2), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ready")
    fuel_level_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    service_due_odometer_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class VehicleChecklist(Base):
    __tablename__ = "vehicle_checklists"
    __table_args__ = (Index("ix_checklists_vehicle_created","vehicle_id","created_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id",ondelete="RESTRICT"), index=True)
    performed_by_staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id",ondelete="RESTRICT"))
    checklist_type: Mapped[str] = mapped_column(String(30), default="pre_drive")
    status: Mapped[str] = mapped_column(String(30), default="in_progress")
    odometer_km: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VehicleChecklistItem(Base):
    __tablename__ = "vehicle_checklist_items"
    __table_args__ = (UniqueConstraint("checklist_id","item_key",name="uq_checklist_item_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    checklist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicle_checklists.id",ondelete="CASCADE"), index=True)
    item_key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(180))
    result: Mapped[str] = mapped_column(String(20), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")


class FuelRecord(Base):
    __tablename__ = "fuel_records"
    __table_args__ = (Index("ix_fuel_vehicle_recorded","vehicle_id","recorded_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    vehicle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id",ondelete="RESTRICT"), index=True)
    recorded_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id",ondelete="RESTRICT"), nullable=True)
    litres: Mapped[float] = mapped_column(Numeric(10,2))
    odometer_km: Mapped[int] = mapped_column(Integer)
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier: Mapped[str] = mapped_column(String(180), default="")
    reference: Mapped[str] = mapped_column(String(180), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Activity(Base):
    __tablename__ = "activities"
    __table_args__ = (Index("ix_activities_lodge_start","lodge_id","starts_at"), Index("ix_activities_guide_start","guide_staff_id","starts_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    activity_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(180))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    guide_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id",ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id",ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id",ondelete="SET NULL"), nullable=True)
    requires_vehicle: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    meeting_point: Mapped[str] = mapped_column(String(180), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ActivityGuest(Base):
    __tablename__ = "activity_guests"
    activity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("activities.id",ondelete="CASCADE"), primary_key=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id",ondelete="RESTRICT"), primary_key=True)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    stay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stays.id",ondelete="SET NULL"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Transfer(Base):
    __tablename__ = "transfers"
    __table_args__ = (Index("ix_transfers_lodge_scheduled","lodge_id","scheduled_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    transfer_type: Mapped[str] = mapped_column(String(30))
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id",ondelete="RESTRICT"))
    stay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stays.id",ondelete="SET NULL"), nullable=True)
    driver_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id",ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id",ondelete="SET NULL"), nullable=True, index=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id",ondelete="SET NULL"), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expected_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    pickup_location: Mapped[str] = mapped_column(String(240))
    dropoff_location: Mapped[str] = mapped_column(String(240))
    flight_number: Mapped[str] = mapped_column(String(80), default="")
    flight_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    passenger_count: Mapped[int] = mapped_column(Integer, default=1)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    delay_reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WildlifeSighting(Base):
    __tablename__ = "wildlife_sightings"
    __table_args__ = (UniqueConstraint("lodge_id","client_ref",name="uq_sighting_lodge_client_ref"), Index("ix_sightings_lodge_observed","lodge_id","observed_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    client_ref: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    species: Mapped[str] = mapped_column(String(180))
    notes: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[float | None] = mapped_column(Numeric(9,6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9,6), nullable=True)
    gps_accuracy_m: Mapped[float | None] = mapped_column(Numeric(10,2), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="SET NULL"), nullable=True)
    reported_by_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id",ondelete="SET NULL"), nullable=True)
    activity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("activities.id",ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WildlifeMedia(Base):
    __tablename__ = "wildlife_media"
    __table_args__ = (UniqueConstraint("lodge_id","object_key",name="uq_wildlife_media_object_key"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id",ondelete="CASCADE"), index=True)
    sighting_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wildlife_sightings.id",ondelete="CASCADE"), index=True)
    object_key: Mapped[str] = mapped_column(String(600))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id",ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Plan(Base):
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    __tablename__ = "plans"
    key: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PlanEntitlement(Base):
    __tablename__ = "plan_entitlements"
    plan_key: Mapped[str] = mapped_column(String(30), ForeignKey("plans.key", ondelete="CASCADE"), primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class LodgeEntitlementOverride(Base):
    reason: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    __tablename__ = "lodge_entitlement_overrides"
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), primary_key=True)
    feature_key: Mapped[str] = mapped_column(String(120), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("lodge_id", "dedupe_key", name="uq_notification_lodge_dedupe"),
        Index("ix_notifications_lodge_created", "lodge_id", "created_at"),
        Index("ix_notifications_lodge_severity", "lodge_id", "severity"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    notification_type: Mapped[str] = mapped_column(String(100), index=True)
    severity: Mapped[str] = mapped_column(String(20), default="normal")
    title: Mapped[str] = mapped_column(String(240))
    body: Mapped[str] = mapped_column(Text, default="")
    resource_type: Mapped[str] = mapped_column(String(80), default="")
    resource_id: Mapped[str] = mapped_column(String(80), default="")
    dedupe_key: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_by_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("operational_events.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class NotificationRecipient(Base):
    __tablename__ = "notification_recipients"
    __table_args__ = (
        UniqueConstraint("notification_id", "user_id", name="uq_notification_recipient"),
        Index("ix_notification_recipients_user_unread", "user_id", "read_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("lodge_id", "user_id", name="uq_notification_preference_user_lodge"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_min_severity: Mapped[str] = mapped_column(String(20), default="high")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_notification_delivery_idempotency"),
        Index("ix_notification_deliveries_due", "status", "next_attempt_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="email")
    destination: Mapped[str] = mapped_column(String(320))
    idempotency_key: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class StaffLeave(Base):
    __tablename__ = "staff_leaves"
    __table_args__ = (Index("ix_staff_leaves_lodge_dates", "lodge_id", "start_date", "end_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="CASCADE"), index=True)
    leave_type: Mapped[str] = mapped_column(String(60), default="annual")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    notes: Mapped[str] = mapped_column(Text, default="")
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class StaffCredential(Base):
    __tablename__ = "staff_credentials"
    __table_args__ = (Index("ix_staff_credentials_lodge_expiry", "lodge_id", "expiry_date"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="CASCADE"), index=True)
    credential_type: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(180))
    issuer: Mapped[str] = mapped_column(String(180), default="")
    reference_number: Mapped[str] = mapped_column(String(120), default="")
    issued_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StaffTraining(Base):
    __tablename__ = "staff_training"
    __table_args__ = (Index("ix_staff_training_lodge_staff", "lodge_id", "staff_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(180), default="")
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    renewal_due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="planned")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CustomRole(Base):
    __tablename__ = "custom_roles"
    __table_args__ = (UniqueConstraint("lodge_id", "name", name="uq_custom_role_lodge_name"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    base_role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"))
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CustomRolePermission(Base):
    __tablename__ = "custom_role_permissions"
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    custom_role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("custom_roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class TaskChecklistItem(Base):
    __tablename__ = "task_checklist_items"
    __table_args__ = (Index("ix_task_checklist_task", "task_id", "position"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(240))
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class TaskComment(Base):
    __tablename__ = "task_comments"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HousekeepingJob(Base):
    __tablename__ = "housekeeping_jobs"
    __table_args__ = (Index("ix_housekeeping_lodge_status_due", "lodge_id", "status", "due_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    inspector_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(40), default="cleaning")
    status: Mapped[str] = mapped_column(String(40), default="assigned")
    linen_notes: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MaintenanceAsset(Base):
    __tablename__ = "maintenance_assets"
    __table_args__ = (UniqueConstraint("lodge_id", "asset_code", name="uq_asset_lodge_code"), Index("ix_asset_lodge_status", "lodge_id", "status"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    asset_code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(180))
    category: Mapped[str] = mapped_column(String(100), default="general")
    unit_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("units.id", ondelete="SET NULL"), nullable=True)
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active")
    service_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_service_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MaintenancePartUsage(Base):
    __tablename__ = "maintenance_part_usage"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    maintenance_ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("maintenance_tickets.id", ondelete="CASCADE"), index=True)
    part_name: Mapped[str] = mapped_column(String(180))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --- Core operations completion 1.6 ---
class GuestFeedback(Base):
    __tablename__ = "guest_feedback"
    __table_args__ = (Index("ix_guest_feedback_lodge_status", "lodge_id", "status"), Index("ix_guest_feedback_guest_created", "guest_id", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id", ondelete="RESTRICT"), index=True)
    stay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("stays.id", ondelete="SET NULL"), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_staff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="SET NULL"), nullable=True)
    feedback_type: Mapped[str] = mapped_column(String(30), default="feedback")
    category: Mapped[str] = mapped_column(String(100), default="general")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[str] = mapped_column(Text, default="")
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(30), default="open")
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class StaffShift(Base):
    __tablename__ = "staff_shifts"
    __table_args__ = (Index("ix_staff_shifts_lodge_start", "lodge_id", "starts_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class StaffIncident(Base):
    __tablename__ = "staff_incidents"
    __table_args__ = (Index("ix_staff_incidents_lodge_date", "lodge_id", "occurred_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="CASCADE"), index=True)
    incident_type: Mapped[str] = mapped_column(String(80), default="operational")
    severity: Mapped[str] = mapped_column(String(20), default="normal")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    description: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str] = mapped_column(Text, default="")
    is_confidential: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class StaffPerformanceNote(Base):
    __tablename__ = "staff_performance_notes"
    __table_args__ = (Index("ix_staff_performance_lodge_staff", "lodge_id", "staff_id"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("staff_profiles.id", ondelete="CASCADE"), index=True)
    note_type: Mapped[str] = mapped_column(String(40), default="review")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text)
    review_date: Mapped[date] = mapped_column(Date)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class MealService(Base):
    __tablename__ = "meal_services"
    __table_args__ = (Index("ix_meal_services_lodge_time", "lodge_id", "scheduled_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    meal_type: Mapped[str] = mapped_column(String(40), default="dinner")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    location: Mapped[str] = mapped_column(String(180), default="")
    expected_guest_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="scheduled")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class MealServiceGuest(Base):
    __tablename__ = "meal_service_guests"
    __table_args__ = (UniqueConstraint("meal_service_id", "guest_id", name="uq_meal_service_guest"),)
    meal_service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("meal_services.id", ondelete="CASCADE"), primary_key=True)
    guest_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("guests.id", ondelete="CASCADE"), primary_key=True)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")

class TaskAttachment(Base):
    __tablename__ = "task_attachments"
    __table_args__ = (UniqueConstraint("lodge_id", "object_key", name="uq_task_attachment_object_key"), Index("ix_task_attachments_task", "task_id", "created_at"))
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), index=True)
    object_key: Mapped[str] = mapped_column(String(600))
    file_name: Mapped[str] = mapped_column(String(240))
    content_type: Mapped[str] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountEmail(Base):
    __tablename__ = "account_emails"
    __table_args__ = (Index("ix_account_emails_due", "status", "next_attempt_at"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lodge_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("lodges.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    invitation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("invitations.id", ondelete="CASCADE"), nullable=True)
    reset_token_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("password_reset_tokens.id", ondelete="CASCADE"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))
    destination: Mapped[str] = mapped_column(String(320))
    encrypted_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LodgeGroup(Base):
    __tablename__ = 'lodge_groups'
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(180), unique=True)
    admin_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='RESTRICT'), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
