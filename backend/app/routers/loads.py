"""Loads: CRUD + duplicate + cancel + assign + status transitions.

Status transition map is enforced server-side (422 on invalid transition).
Status changes fire the matching domain events from ARCHITECTURE.md 3.5.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .crud import make_crud

LOAD_TRANSITIONS = {
    "draft": {"quoted", "cancelled"},
    "quoted": {"tendered", "cancelled"},
    "tendered": {"available", "cancelled"},
    "available": {"assigned", "cancelled"},
    "assigned": {"confirmed", "dispatched", "cancelled"},
    "confirmed": {"dispatched"},
    "dispatched": {"at_pickup"},
    "at_pickup": {"picked_up"},
    "picked_up": {"in_transit"},
    "in_transit": {"at_delivery"},
    "at_delivery": {"delivered"},
    "delivered": {"pod_received"},
    "pod_received": {"invoiced"},
    "invoiced": {"paid"},
    "cancelled": set(),
    "paid": set(),
}

STATUS_EVENTS = {
    "assigned": "LOAD_ASSIGNED",
    "dispatched": "DRIVER_DISPATCHED",
    "picked_up": "PICKUP_COMPLETED",
    "in_transit": "SHIPMENT_IN_TRANSIT",
    "delivered": "DELIVERY_COMPLETED",
}

LOAD_READ_ROLES = (
    "admin", "broker", "dispatcher", "finance", "ops_manager",
    "carrier", "driver", "shipper",
)
LOAD_WRITE_ROLES = ("admin", "broker", "dispatcher")
LOAD_STATUS_ROLES = ("admin", "broker", "dispatcher", "carrier", "driver")


def _next_load_number(db: Session, org_id: str) -> str:
    max_n = 10000
    for (ln,) in (
        db.query(models.Load.load_number)
        .filter(models.Load.org_id == org_id)
        .all()
    ):
        try:
            n = int(str(ln).split("-")[-1])
            max_n = max(max_n, n)
        except ValueError:
            continue
    return f"LD-{max_n + 1}"


def _on_create(db: Session, data: dict, user: models.User):
    data["load_number"] = _next_load_number(db, user.org_id)
    data.setdefault("status", "draft")


def _extra_list_filters(customer_id=None, carrier_id=None, driver_id=None,
                         equipment_type=None):
    def _apply(q):
        if customer_id:
            q = q.filter(models.Load.customer_id == customer_id)
        if carrier_id:
            q = q.filter(models.Load.carrier_id == carrier_id)
        if driver_id:
            q = q.filter(models.Load.driver_id == driver_id)
        if equipment_type:
            q = q.filter(models.Load.equipment_type == equipment_type)
        return q
    return _apply


router = make_crud(
    model=models.Load,
    create_schema=schemas.LoadCreate,
    update_schema=schemas.LoadUpdate,
    out_schema=schemas.LoadOut,
    prefix="/loads",
    tags=["loads"],
    read_roles=LOAD_READ_ROLES,
    write_roles=LOAD_WRITE_ROLES,
    search_fields=("load_number", "reference_number", "commodity"),
    scope_fn=deps.scope_loads,
    soft_delete_field="is_archived",
    on_create=_on_create,
    create_event="LOAD_CREATED",
    entity_name="loads",
    include=("create", "get", "update", "delete"),  # list is custom below
)


@router.get("", response_model=dict)
def list_loads_filtered(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LOAD_READ_ROLES)),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    driver_id: str | None = Query(default=None),
    equipment_type: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
):
    # Reuse the factory list via its underlying route would double-register;
    # instead apply the same filtering here with extra params.
    from .crud import _parse_date

    q = db.query(models.Load).filter(models.Load.org_id == user.org_id)
    q = deps.scope_loads(q, user)
    if search:
        from sqlalchemy import or_
        q = q.filter(
            or_(
                models.Load.load_number.ilike(f"%{search}%"),
                models.Load.reference_number.ilike(f"%{search}%"),
                models.Load.commodity.ilike(f"%{search}%"),
            )
        )
    if status is not None:
        q = q.filter(models.Load.status == status)
    if customer_id:
        q = q.filter(models.Load.customer_id == customer_id)
    if carrier_id:
        q = q.filter(models.Load.carrier_id == carrier_id)
    if driver_id:
        q = q.filter(models.Load.driver_id == driver_id)
    if equipment_type:
        q = q.filter(models.Load.equipment_type == equipment_type)
    if not include_inactive:
        q = q.filter(models.Load.is_archived.is_(False))
    if date_from:
        q = q.filter(models.Load.created_at >= _parse_date(date_from))
    if date_to:
        q = q.filter(models.Load.created_at <= _parse_date(date_to, end_of_day=True))
    total = q.count()
    sort_col = sort_by if sort_by and sort_by in models.Load.__table__.c else "created_at"
    col = models.Load.__table__.c[sort_col]
    q = q.order_by(col.asc() if sort_dir == "asc" else col.desc())
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [schemas.LoadOut.model_validate(i).model_dump() for i in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _set_status(db: Session, load: models.Load, new_status: str,
                user: models.User, actor_type: str = "user",
                emit_event: bool = True) -> dict:
    allowed = LOAD_TRANSITIONS.get(load.status, set())
    if new_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status transition: {load.status} -> {new_status}. "
                   f"Allowed: {sorted(allowed) or 'none (terminal)'}",
        )
    before = audit.model_to_dict(load)
    old_status = load.status
    load.status = new_status
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type=actor_type, actor_id=user.id,
        actor_name=user.full_name, action="loads.status",
        entity_type="loads", entity_id=load.id,
        before=before, after=audit.model_to_dict(load),
    )
    mapped = STATUS_EVENTS.get(new_status)
    if emit_event and mapped:
        events.emit(
            db, mapped, user.org_id, "loads", load.id,
            {"load_id": load.id, "load_number": load.load_number,
             "old_status": old_status, "new_status": new_status},
        )
    return {"old_status": old_status, "new_status": new_status}


def _do_assign(db: Session, load: models.Load, carrier_id: str | None,
               driver_id: str | None, vehicle_id: str | None,
               user: models.User) -> list[str]:
    """Assign carrier/driver/vehicle to a load. Returns warnings (non-blocking)."""
    warnings: list[str] = []
    if carrier_id:
        carrier = (
            db.query(models.Carrier)
            .filter(models.Carrier.id == carrier_id,
                    models.Carrier.org_id == user.org_id)
            .first()
        )
        if not carrier:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Carrier not found")
        load.carrier_id = carrier_id
    if driver_id:
        driver = (
            db.query(models.Driver)
            .filter(models.Driver.id == driver_id,
                    models.Driver.org_id == user.org_id)
            .first()
        )
        if not driver:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Driver not found")
        if driver.status != "available":
            warnings.append(f"Driver {driver.full_name} status is '{driver.status}', not 'available'")
        other = (
            db.query(models.Assignment)
            .filter(
                models.Assignment.org_id == user.org_id,
                models.Assignment.driver_id == driver_id,
                models.Assignment.status == "active",
                models.Assignment.load_id != load.id,
            )
            .count()
        )
        if other:
            warnings.append(f"Driver {driver.full_name} already has {other} active assignment(s) (double-booking)")
        load.driver_id = driver_id
        driver.status = "assigned"
    if vehicle_id:
        vehicle = (
            db.query(models.Vehicle)
            .filter(models.Vehicle.id == vehicle_id,
                    models.Vehicle.org_id == user.org_id)
            .first()
        )
        if not vehicle:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Vehicle not found")
        if vehicle.availability_status != "available":
            warnings.append(
                f"Vehicle {vehicle.unit_number} is '{vehicle.availability_status}', not 'available'"
            )
        load.vehicle_id = vehicle_id
        vehicle.availability_status = "assigned"
    # An assignment row tracks a driver assignment. Carrier-only assignments
    # (no driver yet) must not create a row with a null driver_id.
    if load.driver_id:
        assignment = models.Assignment(
            org_id=user.org_id, load_id=load.id, driver_id=load.driver_id,
            vehicle_id=load.vehicle_id, status="active", assigned_by=user.id,
        )
        db.add(assignment)
        db.flush()
    return warnings


@router.post("/{obj_id}/assign", response_model=dict)
def assign_load(
    obj_id: str,
    payload: schemas.LoadAssignRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LOAD_WRITE_ROLES)),
):
    load = router.get_one(db, user, obj_id)
    before = audit.model_to_dict(load)
    warnings = _do_assign(
        db, load, payload.carrier_id, payload.driver_id, payload.vehicle_id, user
    )
    if load.status != "assigned":
        # Suppress _set_status's mapped LOAD_ASSIGNED: the rich event below
        # (with carrier/driver/vehicle) is the single emission.
        _set_status(db, load, "assigned", user, emit_event=False)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="loads.assign",
        entity_type="loads", entity_id=load.id,
        before=before, after=audit.model_to_dict(load),
    )
    events.emit(
        db, "LOAD_ASSIGNED", user.org_id, "loads", load.id,
        {"load_id": load.id, "load_number": load.load_number,
         "carrier_id": load.carrier_id, "driver_id": load.driver_id,
         "vehicle_id": load.vehicle_id},
    )
    db.commit()
    db.refresh(load)
    return {
        "load": schemas.LoadOut.model_validate(load).model_dump(),
        "warnings": warnings,
    }


@router.post("/{obj_id}/status", response_model=dict)
def update_load_status(
    obj_id: str,
    payload: schemas.LoadStatusUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LOAD_STATUS_ROLES)),
):
    load = router.get_one(db, user, obj_id)
    result = _set_status(db, load, payload.status, user)
    db.commit()
    db.refresh(load)
    return {
        "load": schemas.LoadOut.model_validate(load).model_dump(),
        **result,
    }


@router.post("/{obj_id}/duplicate", response_model=dict,
             status_code=status.HTTP_201_CREATED)
def duplicate_load(
    obj_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LOAD_WRITE_ROLES)),
):
    src = router.get_one(db, user, obj_id)
    skip = {
        "id", "load_number", "carrier_id", "driver_id", "vehicle_id",
        "created_at", "updated_at", "is_archived",
    }
    data = {
        c.key: getattr(src, c.key)
        for c in models.Load.__table__.columns
        if c.key not in skip
    }
    data["status"] = "draft"
    copy = models.Load(**data)
    copy.load_number = _next_load_number(db, user.org_id)
    db.add(copy)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="loads.duplicate",
        entity_type="loads", entity_id=copy.id,
        after=audit.model_to_dict(copy),
    )
    events.emit(
        db, "LOAD_CREATED", user.org_id, "loads", copy.id,
        {"id": copy.id, "load_number": copy.load_number,
         "duplicated_from": src.id, "status": "draft"},
    )
    db.commit()
    db.refresh(copy)
    return schemas.LoadOut.model_validate(copy).model_dump()


@router.post("/{obj_id}/cancel", response_model=dict)
def cancel_load(
    obj_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LOAD_WRITE_ROLES)),
):
    load = router.get_one(db, user, obj_id)
    result = _set_status(db, load, "cancelled", user)
    # cancel any active assignments
    for a in (
        db.query(models.Assignment)
        .filter(models.Assignment.org_id == user.org_id,
                models.Assignment.load_id == load.id,
                models.Assignment.status == "active")
        .all()
    ):
        a.status = "cancelled"
    db.commit()
    db.refresh(load)
    return {
        "load": schemas.LoadOut.model_validate(load).model_dump(),
        **result,
    }
