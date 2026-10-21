from datetime import date, datetime
from uuid import UUID
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginIn(StrictModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    otp: str | None = Field(default=None, pattern="^[0-9]{6}$")
    recovery_code: str | None = Field(default=None, min_length=20, max_length=40)


class ActivateIn(StrictModel):
    token: str = Field(min_length=20, max_length=300)
    password: str = Field(min_length=12, max_length=200)


class LodgeCreate(StrictModel):
    name: str = Field(min_length=2, max_length=180)
    location: str = Field(default="", max_length=240)
    timezone: str = Field(default="Africa/Johannesburg", max_length=80)
    protected_species: str = Field(default="rhino,black rhino,white rhino", max_length=2000)
    package: str = Field(pattern="^(Basic|Standard|Premium)$")
    start_date: date
    expiry_date: date
    admin_email: EmailStr
    admin_name: str = Field(min_length=2, max_length=180)


    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls,value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try: ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError): raise ValueError('Choose a valid time zone')
        return value


class SubscriptionUpdate(StrictModel):
    package: str | None = Field(default=None, pattern="^(Basic|Standard|Premium)$")
    start_date: date | None = None
    expiry_date: date | None = None
    suspended: bool | None = None


class DepartmentCreate(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=2000)


class DepartmentUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None


class StaffCreate(StrictModel):
    invite_role_key: str | None = Field(default=None, pattern="^(department_manager|front_office|ranger|housekeeping|maintenance|driver|fb|finance|general_staff|read_only)$")
    full_name: str = Field(min_length=2, max_length=180)
    email: EmailStr | None = None
    phone: str = Field(default="", max_length=80)
    job_title: str = Field(default="", max_length=160)
    employee_code: str | None = Field(default=None, max_length=80)
    department_id: UUID | None = None
    employment_status: str = Field(default="active", pattern="^(active|inactive|leave)$")
    operational_status: str = Field(default="available", pattern="^(available|on_shift|on_drive|off_duty|leave)$")
    supervisor_staff_id: UUID | None = None
    hire_date: date | None = None


class StaffUpdate(StrictModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=180)
    email: EmailStr | None = None
    employee_code: str | None = Field(default=None, max_length=80)
    department_id: UUID | None = None
    phone: str | None = Field(default=None, max_length=80)
    job_title: str | None = Field(default=None, max_length=160)
    employment_status: str | None = Field(default=None, pattern="^(active|inactive|leave)$")
    operational_status: str | None = Field(default=None, pattern="^(available|on_shift|on_drive|off_duty|leave)$")
    supervisor_staff_id: UUID | None = None
    hire_date: date | None = None


class UnitCreate(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    unit_type: str = Field(default="Room", max_length=80)
    notes: str = Field(default="", max_length=4000)


class UnitUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    unit_type: str | None = Field(default=None, max_length=80)
    status: str | None = Field(default=None, pattern="^(available|occupied|cleaning|awaiting_inspection|ready|maintenance|out_of_service)$")
    notes: str | None = Field(default=None, max_length=4000)


class GuestCreate(StrictModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str = Field(default="", max_length=80)
    nationality: str = Field(default="", max_length=120)
    vip: bool = False
    dietary_requirements: str = Field(default="", max_length=4000)
    allergies: str = Field(default="", max_length=4000)
    preferences: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=4000)


class GuestUpdate(StrictModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=120)
    last_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=80)
    nationality: str | None = Field(default=None, max_length=120)
    vip: bool | None = None
    dietary_requirements: str | None = Field(default=None, max_length=4000)
    allergies: str | None = Field(default=None, max_length=4000)
    preferences: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=4000)


class StayCreate(StrictModel):
    guest_id: UUID
    unit_id: UUID
    arrival_date: date
    departure_date: date
    party_size: int = Field(default=1, ge=1, le=100)
    expected_arrival_time: str = Field(default="", max_length=10)
    expected_departure_time: str = Field(default="", max_length=10)
    transfer_notes: str = Field(default="", max_length=4000)
    special_requirements: str = Field(default="", max_length=4000)

    @field_validator("departure_date")
    @classmethod
    def dates_are_valid(cls, v, info):
        arrival = info.data.get("arrival_date")
        if arrival and v < arrival:
            raise ValueError("Departure date must be on or after arrival date")
        return v


class StayUpdate(StrictModel):
    unit_id: UUID | None = None
    arrival_date: date | None = None
    departure_date: date | None = None
    party_size: int | None = Field(default=None, ge=1, le=100)
    status: str | None = Field(default=None, pattern="^(upcoming|arriving|in_house|departing|completed|cancelled)$")
    expected_arrival_time: str | None = Field(default=None, max_length=10)
    expected_departure_time: str | None = Field(default=None, max_length=10)
    transfer_notes: str | None = Field(default=None, max_length=4000)
    special_requirements: str | None = Field(default=None, max_length=4000)


class TaskCreate(StrictModel):
    title: str = Field(min_length=2, max_length=240)
    description: str = Field(default="", max_length=8000)
    department_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    guest_id: UUID | None = None
    unit_id: UUID | None = None
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    due_at: datetime | None = None
    recurrence_interval_days: int | None = Field(default=None, ge=1, le=3650)
    recurrence_end_date: date | None = None
    proof_required: bool = False


class TaskUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    proof_required: bool | None = None
    status: str | None = Field(default=None, pattern="^(created|assigned|accepted|started|completed|cancelled)$")
    assigned_staff_id: UUID | None = None
    department_id: UUID | None = None
    priority: str | None = Field(default=None, pattern="^(low|normal|high|critical)$")
    due_at: datetime | None = None
    description: str | None = Field(default=None, max_length=8000)
    recurrence_interval_days: int | None = Field(default=None, ge=1, le=3650)
    recurrence_end_date: date | None = None


class GuestRequestCreate(StrictModel):
    guest_id: UUID
    stay_id: UUID | None = None
    department_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    request_type: str = Field(pattern="^(housekeeping|maintenance|transport|food_beverage|activity|amenity|concierge|other)$")
    description: str = Field(min_length=2, max_length=8000)
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")


class GuestRequestUpdate(StrictModel):
    description: str | None = Field(default=None, min_length=2, max_length=8000)
    priority: str | None = Field(default=None, pattern="^(low|normal|high|critical)$")
    status: str | None = Field(default=None, pattern="^(open|assigned|in_progress|waiting|resolved|cancelled)$")
    department_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    resolution: str | None = Field(default=None, max_length=8000)


class MaintenanceCreate(StrictModel):
    department_id: UUID | None = None
    title: str = Field(min_length=2, max_length=240)
    description: str = Field(default="", max_length=8000)
    category: str = Field(default="general", max_length=80)
    priority: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    unit_id: UUID | None = None
    asset_id: UUID | None = None
    vehicle_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    scheduled_for: datetime | None = None
    recurrence_interval_days: int | None = Field(default=None, ge=1, le=3650)


class MaintenanceUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    category: str | None = Field(default=None, max_length=80)
    department_id: UUID | None = None
    unit_id: UUID | None = None
    asset_id: UUID | None = None
    vehicle_id: UUID | None = None
    status: str | None = Field(default=None, pattern="^(open|assigned|in_progress|waiting|completed|cancelled)$")
    priority: str | None = Field(default=None, pattern="^(low|normal|high|critical)$")
    assigned_staff_id: UUID | None = None
    resolution: str | None = Field(default=None, max_length=8000)
    cost_cents: int | None = Field(default=None, ge=0)
    scheduled_for: datetime | None = None
    recurrence_interval_days: int | None = Field(default=None, ge=1, le=3650)

class VehicleCreate(StrictModel):
    registration: str = Field(min_length=1, max_length=80)
    name: str = Field(default="", max_length=160)
    make: str = Field(default="", max_length=100)
    model: str = Field(default="", max_length=100)
    year: int | None = Field(default=None, ge=1900, le=2200)
    odometer_km: int = Field(default=0, ge=0)
    fuel_capacity_litres: float | None = Field(default=None, gt=0)
    service_due_odometer_km: int | None = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=8000)

class VehicleUpdate(StrictModel):
    odometer_correction_reason: str | None = Field(default=None, max_length=1000)
    fuel_level_percent: int | None = Field(default=None, ge=0, le=100)
    name: str | None = Field(default=None, max_length=160)
    status: str | None = Field(default=None, pattern="^(ready|assigned|on_drive|maintenance|out_of_service)$")
    odometer_km: int | None = Field(default=None, ge=0)
    service_due_odometer_km: int | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=8000)

class ChecklistItemIn(StrictModel):
    item_key: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=180)
    result: str = Field(pattern="^(pass|fail|not_applicable)$")
    notes: str = Field(default="", max_length=2000)

class VehicleChecklistCreate(StrictModel):
    vehicle_id: UUID
    performed_by_staff_id: UUID
    checklist_type: str = Field(default="pre_drive", pattern="^(pre_drive|post_drive|inspection)$")
    odometer_km: int | None = Field(default=None, ge=0)
    notes: str = Field(default="", max_length=4000)
    items: list[ChecklistItemIn] = Field(min_length=1, max_length=100)

class FuelCreate(StrictModel):
    vehicle_id: UUID
    recorded_by_staff_id: UUID | None = None
    litres: float = Field(gt=0, le=10000)
    odometer_km: int = Field(ge=0)
    cost_cents: int | None = Field(default=None, ge=0)
    supplier: str = Field(default="", max_length=180)
    reference: str = Field(default="", max_length=180)
    notes: str = Field(default="", max_length=4000)
    recorded_at: datetime | None = None

class ActivityCreate(StrictModel):
    department_id: UUID | None = None
    activity_type: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=180)
    starts_at: datetime
    ends_at: datetime
    guide_staff_id: UUID | None = None
    vehicle_id: UUID | None = None
    requires_vehicle: bool = True
    guest_ids: list[UUID] = Field(default_factory=list, max_length=100)
    meeting_point: str = Field(default="", max_length=180)
    notes: str = Field(default="", max_length=8000)

    @field_validator("ends_at")
    @classmethod
    def end_after_start(cls, v, info):
        start=info.data.get("starts_at")
        if start and v <= start: raise ValueError("Activity end must be after start")
        return v

class ActivityUpdate(StrictModel):
    activity_type: str | None = Field(default=None, min_length=2, max_length=80)
    title: str | None = Field(default=None, min_length=2, max_length=180)
    status: str | None = Field(default=None, pattern="^(scheduled|confirmed|in_progress|completed|cancelled)$")
    guide_staff_id: UUID | None = None
    vehicle_id: UUID | None = None
    requires_vehicle: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    meeting_point: str | None = Field(default=None, max_length=180)
    notes: str | None = Field(default=None, max_length=8000)

class TransferCreate(StrictModel):
    department_id: UUID | None = None
    transfer_type: str = Field(pattern="^(pickup|dropoff|guest_transfer|other)$")
    guest_id: UUID
    stay_id: UUID | None = None
    driver_staff_id: UUID | None = None
    vehicle_id: UUID | None = None
    scheduled_at: datetime
    expected_end_at: datetime
    pickup_location: str = Field(min_length=2, max_length=240)
    dropoff_location: str = Field(min_length=2, max_length=240)
    flight_number: str = Field(default="", max_length=80)
    flight_time: datetime | None = None
    passenger_count: int = Field(default=1, ge=1, le=100)
    notes: str = Field(default="", max_length=8000)

class TransferUpdate(StrictModel):
    pickup_location: str | None = Field(default=None, min_length=2, max_length=240)
    dropoff_location: str | None = Field(default=None, min_length=2, max_length=240)
    flight_number: str | None = Field(default=None, max_length=80)
    flight_time: datetime | None = None
    passenger_count: int | None = Field(default=None, ge=1, le=100)
    delay_minutes: int | None = Field(default=None, ge=0, le=1440)
    delay_reason: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(default=None, pattern="^(scheduled|confirmed|en_route|arrived|completed|cancelled)$")
    driver_staff_id: UUID | None = None
    vehicle_id: UUID | None = None
    scheduled_at: datetime | None = None
    expected_end_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=8000)

class WildlifeSightingCreate(StrictModel):
    client_ref: UUID
    species: str = Field(min_length=1, max_length=180)
    notes: str = Field(default="", max_length=8000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    gps_accuracy_m: float | None = Field(default=None, ge=0)
    observed_at: datetime
    reported_by_staff_id: UUID | None = None
    activity_id: UUID | None = None

class WildlifeMediaRegister(StrictModel):
    sighting_id: UUID
    object_key: str = Field(min_length=1, max_length=600)
    content_type: str = Field(pattern="^image/(jpeg|png|webp|heic|heif)$")
    size_bytes: int = Field(gt=0, le=25_000_000)
    sha256: str = Field(pattern="^[a-fA-F0-9]{64}$")

class MediaUploadRequest(StrictModel):
    content_type: str = Field(pattern="^image/(jpeg|png|webp|heic|heif)$")
    size_bytes: int = Field(gt=0, le=25_000_000)
    sha256: str = Field(pattern="^[a-fA-F0-9]{64}$")

class StaffInvite(StrictModel):
    role_key: str = Field(pattern="^(department_manager|front_office|ranger|housekeeping|maintenance|driver|fb|finance|general_staff|read_only)$")

class NotificationPreferenceUpdate(StrictModel):
    email_enabled: bool
    email_min_severity: str = Field(default="high", pattern="^(low|normal|high|critical)$")


class PasswordResetRequestIn(StrictModel):
    email: EmailStr


class PasswordResetConfirmIn(StrictModel):
    token: str = Field(min_length=20, max_length=300)
    password: str = Field(min_length=12, max_length=200)


class MfaCodeIn(StrictModel):
    code: str = Field(pattern="^[0-9]{6}$")


class MfaDisableIn(StrictModel):
    code: str = Field(pattern="^[0-9]{6}$")
    current_password: str = Field(min_length=1, max_length=200)


class ChangePasswordIn(StrictModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=12, max_length=200)


class EntitlementOverrideIn(StrictModel):
    feature_key: str = Field(min_length=2, max_length=120)
    enabled: bool | None = None

class StaffLeaveCreate(StrictModel):
    staff_id: UUID
    leave_type: str = Field(default="annual", max_length=60)
    start_date: date
    end_date: date
    notes: str = Field(default="", max_length=4000)

class StaffLeaveUpdate(StrictModel):
    status: str = Field(pattern="^(approved|rejected|cancelled)$")

class StaffCredentialCreate(StrictModel):
    staff_id: UUID
    credential_type: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=180)
    issuer: str = Field(default="", max_length=180)
    reference_number: str = Field(default="", max_length=120)
    issued_date: date | None = None
    expiry_date: date | None = None
    notes: str = Field(default="", max_length=4000)

class StaffTrainingCreate(StrictModel):
    staff_id: UUID
    title: str = Field(min_length=2, max_length=200)
    provider: str = Field(default="", max_length=180)
    completed_date: date | None = None
    renewal_due_date: date | None = None
    status: str = Field(default="planned", pattern="^(planned|in_progress|completed|expired)$")
    notes: str = Field(default="", max_length=4000)

class CustomRoleCreate(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    base_role_key: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=2000)
    permission_keys: list[str] = Field(default_factory=list, max_length=300)

class CustomRoleUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    is_active: bool | None = None
    permission_keys: list[str] | None = Field(default=None, max_length=300)

class MembershipRoleUpdate(StrictModel):
    custom_role_id: UUID | None = None

class TaskChecklistCreate(StrictModel):
    label: str = Field(min_length=1, max_length=240)
    position: int = Field(default=0, ge=0, le=1000)
    is_required: bool = True

class TaskChecklistUpdate(StrictModel):
    completed: bool

class TaskCommentCreate(StrictModel):
    body: str = Field(min_length=1, max_length=8000)

class HousekeepingCreate(StrictModel):
    unit_id: UUID
    assigned_staff_id: UUID | None = None
    inspector_staff_id: UUID | None = None
    job_type: str = Field(default="cleaning", pattern="^(cleaning|turndown|inspection|linen|guest_request)$")
    linen_notes: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=8000)
    due_at: datetime | None = None

class HousekeepingUpdate(StrictModel):
    status: str | None = Field(default=None, pattern="^(assigned|accepted|in_progress|awaiting_inspection|completed|cancelled)$")
    assigned_staff_id: UUID | None = None
    inspector_staff_id: UUID | None = None
    linen_notes: str | None = Field(default=None, max_length=4000)
    notes: str | None = Field(default=None, max_length=8000)

class MaintenanceAssetCreate(StrictModel):
    asset_code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=180)
    category: str = Field(default="general", max_length=100)
    unit_id: UUID | None = None
    vehicle_id: UUID | None = None
    service_interval_days: int | None = Field(default=None, ge=1, le=3650)
    next_service_date: date | None = None
    notes: str = Field(default="", max_length=8000)

class MaintenancePartCreate(StrictModel):
    part_name: str = Field(min_length=1, max_length=180)
    quantity: int = Field(default=1, ge=1, le=100000)
    unit_cost_cents: int = Field(default=0, ge=0)
    notes: str = Field(default="", max_length=4000)


# --- Core operations completion 1.6 ---
class GuestFeedbackCreate(StrictModel):
    guest_id: UUID
    stay_id: UUID | None = None
    department_id: UUID | None = None
    assigned_staff_id: UUID | None = None
    feedback_type: str = Field(default="feedback", pattern="^(feedback|compliment|complaint)$")
    category: str = Field(default="general", min_length=1, max_length=100)
    rating: int | None = Field(default=None, ge=1, le=5)
    comments: str = Field(default="", max_length=12000)
    follow_up_required: bool = False

class GuestFeedbackUpdate(StrictModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    rating: int | None = Field(default=None, ge=1, le=5)
    comments: str | None = Field(default=None, max_length=12000)
    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved|closed)$")
    assigned_staff_id: UUID | None = None
    department_id: UUID | None = None
    follow_up_required: bool | None = None
    resolution: str | None = Field(default=None, max_length=12000)

class StaffShiftCreate(StrictModel):
    staff_id: UUID
    starts_at: datetime
    ends_at: datetime
    notes: str = Field(default="", max_length=4000)

class StaffShiftUpdate(StrictModel):
    status: str = Field(pattern="^(scheduled|confirmed|completed|cancelled)$")

class StaffIncidentCreate(StrictModel):
    staff_id: UUID
    incident_type: str = Field(default="operational", max_length=80)
    severity: str = Field(default="normal", pattern="^(low|normal|high|critical)$")
    occurred_at: datetime
    description: str = Field(min_length=1, max_length=12000)
    action_taken: str = Field(default="", max_length=12000)
    is_confidential: bool = True

class StaffPerformanceCreate(StrictModel):
    staff_id: UUID
    note_type: str = Field(default="review", pattern="^(review|recognition|coaching|warning|goal)$")
    rating: int | None = Field(default=None, ge=1, le=5)
    notes: str = Field(min_length=1, max_length=12000)
    review_date: date

class MealServiceCreate(StrictModel):
    department_id: UUID | None = None
    name: str = Field(min_length=2, max_length=160)
    meal_type: str = Field(default="dinner", pattern="^(breakfast|lunch|dinner|special_dinner|event|other)$")
    scheduled_at: datetime
    location: str = Field(default="", max_length=180)
    expected_guest_count: int = Field(default=0, ge=0, le=5000)
    notes: str = Field(default="", max_length=8000)
    guest_ids: list[UUID] = Field(default_factory=list, max_length=1000)

class MealServiceUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    meal_type: str | None = Field(default=None, pattern="^(breakfast|lunch|dinner|special_dinner|event|other)$")
    scheduled_at: datetime | None = None
    location: str | None = Field(default=None, max_length=180)
    status: str | None = Field(default=None, pattern="^(scheduled|preparing|serving|completed|cancelled)$")
    expected_guest_count: int | None = Field(default=None, ge=0, le=5000)
    notes: str | None = Field(default=None, max_length=8000)

class TaskAttachmentUploadRequest(StrictModel):
    file_name: str = Field(min_length=1, max_length=240)
    content_type: str = Field(pattern="^(image/(jpeg|png|webp|heic|heif)|application/pdf)$")
    size_bytes: int = Field(gt=0, le=25_000_000)
    sha256: str = Field(pattern="^[a-fA-F0-9]{64}$")

class TaskAttachmentRegister(TaskAttachmentUploadRequest):
    object_key: str = Field(min_length=1, max_length=600)


class LodgeBrandingUpdate(StrictModel):
    display_name: str = Field(min_length=1, max_length=180)
    logo_base64: str | None = Field(default=None, max_length=350000)
    remove_logo: bool = False


class PlatformInvite(StrictModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=180)


class InvitationPreviewIn(StrictModel):
    token: str = Field(min_length=20, max_length=300)


class GroupCreate(StrictModel):
    name: str = Field(min_length=2,max_length=180)
    admin_name: str = Field(min_length=2,max_length=180)
    admin_email: EmailStr
    lodge_ids: list[UUID] = Field(default_factory=list,max_length=200)

class GroupUpdate(StrictModel):
    name: str = Field(min_length=2,max_length=180)
    lodge_ids: list[UUID] = Field(max_length=200)
    is_active: bool = True

class LodgeAdminInvite(StrictModel):
    full_name: str = Field(min_length=2,max_length=180)
    email: EmailStr


class LodgePreferencesUpdate(StrictModel):
    date_format: Literal['locale','dd/MM/yyyy','MM/dd/yyyy','yyyy-MM-dd']
    currency: str = Field(pattern='^[A-Z]{3}$')

    @field_validator('currency')
    @classmethod
    def known_currency(cls,value):
        if value not in {'USD','ZAR','KES','TZS','UGX','NAD','BWP','ZMW','GBP','EUR','INR','AED','PKR','AUD','CAD','MZN','MWK','RWF','SCR','MUR','CHF','JPY','CNY','NZD','SGD','HKD','BRL','SAR','EGP','MAD','NGN','GHS','ETB','ZWL'}:
            raise ValueError('Choose a supported currency')
        return value
