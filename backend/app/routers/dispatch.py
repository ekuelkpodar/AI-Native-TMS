"""Dispatch board + assignment with non-blocking conflict warnings."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .loads import _do_assign, _set_status

router = APIRouter(prefix="/dispatch", tags=["dispatch"])

DISPATCH_ROLES = ("admin", "dispatcher", "broker")
UNASSIGNED_STATUSES = ("quoted", "tendered", "available")


@router.get("/board", response_model=dict)
def dispatch_board(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*DISPATCH_ROLES)),
):
    unassigned = (
        db.query(models.Load)
        .filter(
            models.Load.org_id == user.org_id,
            models.Load.status.in_(UNASSIGNED_STATUSES),
            models.Load.driver_id.is_(None),
            models.Load.is_archived.is_(False),
        )
        .order_by(models.Load.pickup_datetime.asc())
        .all()
    )
    available_drivers = (
        db.query(models.Driver)
        .filter(
            models.Driver.org_id == user.org_id,
            models.Driver.status == "available",
            models.Driver.is_active.is_(True),
        )
        .all()
    )
    available_vehicles = (
        db.query(models.Vehicle)
        .filter(
            models.Vehicle.org_id == user.org_id,
            models.Vehicle.availability_status == "available",
            models.Vehicle.is_active.is_(True),
        )
        .all()
    )

    conflicts: list[dict] = []

    # Double-booked drivers: more than one active assignment.
    from sqlalchemy import func

    dupes = (
        db.query(
            models.Assignment.driver_id, func.count(models.Assignment.id)
        )
        .filter(
            models.Assignment.org_id == user.org_id,
            models.Assignment.status == "active",
        )
        .group_by(models.Assignment.driver_id)
        .having(func.count(models.Assignment.id) > 1)
        .all()
    )
    for driver_id, count in dupes:
        driver = (
            db.query(models.Driver)
            .filter(models.Driver.id == driver_id).first()
        )
        name = driver.full_name if driver else driver_id
        conflicts.append(
            {
                "type": "double_booking",
                "message": f"Driver {name} has {count} active assignments",
                "driver_id": driver_id,
            }
        )

    # Overdue pickups: pickup time passed but load not yet dispatched.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    overdue = (
        db.query(models.Load)
        .filter(
            models.Load.org_id == user.org_id,
            models.Load.pickup_datetime.isnot(None),
            models.Load.pickup_datetime < now,
            models.Load.status.in_(
                ("draft", "quoted", "tendered", "available", "assigned", "confirmed")
            ),
            models.Load.is_archived.is_(False),
        )
        .all()
    )
    for load in overdue:
        conflicts.append(
            {
                "type": "overdue_pickup",
                "message": f"Load {load.load_number} pickup was due "
                           f"{load.pickup_datetime.isoformat()} and is still '{load.status}'",
                "load_id": load.id,
            }
        )

    return {
        "unassigned_loads": [
            schemas.LoadOut.model_validate(l).model_dump() for l in unassigned
        ],
        "available_drivers": [
            schemas.DriverOut.model_validate(d).model_dump()
            for d in available_drivers
        ],
        "available_vehicles": [
            schemas.VehicleOut.model_validate(v).model_dump()
            for v in available_vehicles
        ],
        "conflicts": conflicts,
    }


@router.post("/assign", response_model=dict)
def dispatch_assign(
    payload: schemas.DispatchAssignRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*DISPATCH_ROLES)),
):
    load = (
        db.query(models.Load)
        .filter(
            models.Load.id == payload.load_id,
            models.Load.org_id == user.org_id,
        )
        .first()
    )
    if not load:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Load not found"
        )
    had_driver = bool(load.driver_id)
    before = audit.model_to_dict(load)
    warnings = _do_assign(
        db, load, None, payload.driver_id, payload.vehicle_id, user
    )
    if had_driver:
        warnings.append(
            f"Load {load.load_number} already had a driver assigned; it was reassigned"
        )
    if load.status != "assigned":
        # Suppress _set_status's mapped LOAD_ASSIGNED: the rich event below
        # is the single emission.
        _set_status(db, load, "assigned", user, emit_event=False)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="dispatch.assign",
        entity_type="loads", entity_id=load.id,
        before=before, after=audit.model_to_dict(load),
    )
    events.emit(
        db, "LOAD_ASSIGNED", user.org_id, "loads", load.id,
        {"load_id": load.id, "load_number": load.load_number,
         "driver_id": load.driver_id, "vehicle_id": load.vehicle_id,
         "via": "dispatch_board"},
    )
    db.commit()
    db.refresh(load)
    return {
        "load": schemas.LoadOut.model_validate(load).model_dump(),
        "warnings": warnings,
    }
