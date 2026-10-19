"""Authoritative operational state helpers.

Room occupancy is derived from active in-house stays. Housekeeping and maintenance
must never overwrite an occupied/out-of-service state accidentally.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException
from ..models import Stay, Unit, Vehicle

UNIT_STATES = {"available", "occupied", "cleaning", "awaiting_inspection", "ready", "maintenance", "out_of_service"}
PROTECTED_UNIT_STATES = {"maintenance", "out_of_service"}


def unit_is_occupied(db: Session, unit_id) -> bool:
    return db.scalar(select(Stay.id).where(Stay.unit_id == unit_id, Stay.status == "in_house").limit(1)) is not None


def housekeeping_job_created(db: Session, unit: Unit, job_type: str) -> None:
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
    if unit_is_occupied(db, unit.id):
        unit.status = "occupied"
    elif unit.status not in PROTECTED_UNIT_STATES:
        unit.status = "awaiting_inspection"


def housekeeping_completed(db: Session, unit: Unit) -> None:
    if unit_is_occupied(db, unit.id):
        unit.status = "occupied"
    elif unit.status not in PROTECTED_UNIT_STATES:
        unit.status = "ready"


def maintenance_opened(db: Session, unit: Unit | None = None, vehicle: Vehicle | None = None, critical: bool = False) -> None:
    if unit and critical and not unit_is_occupied(db, unit.id):
        unit.status = "maintenance"
    # Occupied units remain occupied; the ticket itself is the maintenance-pending signal.
    if vehicle and critical and vehicle.status != "out_of_service":
        vehicle.status = "maintenance"


def maintenance_released(db: Session, unit: Unit | None = None, vehicle: Vehicle | None = None) -> None:
    if vehicle and vehicle.status == "maintenance":
        vehicle.status = "ready"
    if unit and unit.status == "maintenance":
        unit.status = "occupied" if unit_is_occupied(db, unit.id) else "cleaning"
