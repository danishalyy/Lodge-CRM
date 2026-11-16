"""Authoritative operational state helpers.

Room occupancy is derived from active in-house stays. Housekeeping and maintenance
must never overwrite an occupied/out-of-service state accidentally.
"""
from sqlalchemy import select, text, or_, and_
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models import Stay, Unit, Vehicle, MaintenanceTicket, Activity, Transfer
from datetime import datetime, timezone

UNIT_STATES = {"available", "occupied", "cleaning", "awaiting_inspection", "ready", "maintenance", "out_of_service"}
PROTECTED_UNIT_STATES = {"maintenance", "out_of_service"}
OCCUPYING_STAY_STATES = {"in_house", "departing"}


def lock_asset_state(db: Session, *assets) -> None:
    """Serialize related workflows using transaction-local, stable asset locks.

    Room locks use the same key as stay overlap checks. Sorting avoids lock-order
    inversions when an operation involves both a room and a vehicle.
    """
    rows = [asset for asset in assets if asset is not None]
    for asset in sorted(rows, key=lambda a: (a.__tablename__, str(a.id))):
        kind = "unit" if isinstance(asset, Unit) else "vehicle"
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
                   {"key": f"{asset.lodge_id}:{kind}:{asset.id}"})
        db.refresh(asset)


def unit_is_occupied(db: Session, unit_id) -> bool:
    return db.scalar(select(Stay.id).where(Stay.unit_id == unit_id, Stay.status.in_(OCCUPYING_STAY_STATES)).limit(1)) is not None


def housekeeping_job_created(db: Session, unit: Unit, job_type: str) -> None:
    lock_asset_state(db, unit)
    if unit.status == "out_of_service":
        raise HTTPException(409, "Housekeeping cannot be scheduled while this unit is out of service")
    if unit_is_occupied(db, unit.id):
        # Turndown/guest service while occupied is valid; occupancy remains authoritative.
        unit.status = "occupied"
        return
    if unit.status == "maintenance":
        # Do not erase maintenance state; job may exist for post-maintenance cleanup.
        return
    unit.status = "awaiting_inspection" if job_type == "inspection" else "cleaning"


def housekeeping_awaiting_inspection(db: Session, unit: Unit) -> None:
    lock_asset_state(db, unit)
    if unit_is_occupied(db, unit.id):
        unit.status = "occupied"
    elif unit.status not in PROTECTED_UNIT_STATES:
        unit.status = "awaiting_inspection"


def housekeeping_completed(db: Session, unit: Unit) -> None:
    lock_asset_state(db, unit)
    if unit_is_occupied(db, unit.id):
        unit.status = "occupied"
    elif unit.status not in PROTECTED_UNIT_STATES:
        unit.status = "ready"


def blocking_fault(db: Session, asset) -> bool:
    column = MaintenanceTicket.unit_id if isinstance(asset, Unit) else MaintenanceTicket.vehicle_id
    due_critical = and_(MaintenanceTicket.priority == "critical", or_(MaintenanceTicket.scheduled_for.is_(None), MaintenanceTicket.scheduled_for <= datetime.now(timezone.utc)))
    return db.scalar(select(MaintenanceTicket.id).where(
        MaintenanceTicket.lodge_id == asset.lodge_id, column == asset.id,
        MaintenanceTicket.status.notin_(("completed", "cancelled")),
        or_(due_critical, MaintenanceTicket.status.in_(("in_progress", "waiting"))),
    ).limit(1)) is not None


def require_room_readiness(db: Session, unit: Unit) -> None:
    if unit_is_occupied(db, unit.id):
        raise HTTPException(409, "The previous guest must complete checkout before this room can be used")
    if unit.status not in {"available", "ready"} or blocking_fault(db, unit):
        raise HTTPException(409, "The room must be ready and free of blocking maintenance before check-in")


def room_checked_out(db: Session, unit: Unit) -> None:
    db.flush()
    lock_asset_state(db, unit)
    if unit.status == "out_of_service":
        return
    unit.status = "maintenance" if blocking_fault(db, unit) else "cleaning"


def vehicle_in_use(db: Session, vehicle: Vehicle) -> bool:
    activity = db.scalar(select(Activity.id).where(Activity.lodge_id == vehicle.lodge_id, Activity.vehicle_id == vehicle.id, Activity.status == "in_progress").limit(1))
    transfer = db.scalar(select(Transfer.id).where(Transfer.lodge_id == vehicle.lodge_id, Transfer.vehicle_id == vehicle.id, Transfer.status.in_(("en_route", "arrived"))).limit(1))
    return activity is not None or transfer is not None


def vehicle_returned(db: Session, vehicle: Vehicle) -> None:
    db.flush()
    lock_asset_state(db, vehicle)
    if vehicle.status == "out_of_service":
        return
    vehicle.status = "maintenance" if blocking_fault(db, vehicle) else "on_drive" if vehicle_in_use(db, vehicle) else "ready"


def require_asset_release(db: Session, asset) -> None:
    if isinstance(asset, Vehicle) and vehicle_in_use(db, asset):
        raise HTTPException(409, "Complete the active drive or transfer before marking this vehicle ready")
    require_asset_fault_clear(db, asset)


def require_asset_fault_clear(db: Session, asset) -> None:
    if blocking_fault(db, asset):
        raise HTTPException(409, "Resolve all blocking maintenance before using this asset")


def maintenance_opened(db: Session, unit: Unit | None = None, vehicle: Vehicle | None = None, critical: bool = False) -> None:
    db.flush()
    lock_asset_state(db, unit, vehicle)
    if unit and blocking_fault(db, unit) and not unit_is_occupied(db, unit.id) and unit.status != "out_of_service":
        unit.status = "maintenance"
    # Scheduled future faults do not take an asset out of service early. Occupied
    # rooms retain occupancy, and checkout rechecks their still-open faults.
    if vehicle and blocking_fault(db, vehicle) and vehicle.status != "out_of_service":
        vehicle.status = "maintenance"


def maintenance_released(db: Session, unit: Unit | None = None, vehicle: Vehicle | None = None) -> None:
    db.flush()
    lock_asset_state(db, unit, vehicle)
    if vehicle and vehicle.status == "maintenance" and not blocking_fault(db, vehicle):
        vehicle.status = "on_drive" if vehicle_in_use(db, vehicle) else "ready"
    if unit and unit.status == "maintenance" and not blocking_fault(db, unit):
        unit.status = "occupied" if unit_is_occupied(db, unit.id) else "cleaning"
