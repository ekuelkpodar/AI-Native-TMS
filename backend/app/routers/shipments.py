"""Shipments CRUD + status transitions + loads belonging to a shipment.

Note: the data model links loads to shipments through the shared customer
(ARCHITECTURE.md 3.3 defines no direct load<->shipment FK), so
GET /shipments/{id}/loads returns the shipment customer's loads.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .crud import make_crud

SHIPMENT_TRANSITIONS = {
    "draft": {"booked", "cancelled"},
    "booked": {"in_progress", "cancelled"},
    "in_progress": {"delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}

SHIPMENT_ROLES = ("admin", "broker", "dispatcher", "shipper")


router = make_crud(
    model=models.Shipment,
    create_schema=schemas.ShipmentCreate,
    update_schema=schemas.ShipmentUpdate,
    out_schema=schemas.ShipmentOut,
    prefix="/shipments",
    tags=["shipments"],
    read_roles=SHIPMENT_ROLES,
    write_roles=("admin", "broker", "dispatcher"),
    search_fields=("reference_number",),
    scope_fn=deps.scope_shipments,
    entity_name="shipments",
    include=("list", "create", "get", "update", "delete"),
)


@router.post("/{obj_id}/status", response_model=dict)
def update_shipment_status(
    obj_id: str,
    payload: schemas.ShipmentStatusUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin", "broker", "dispatcher")),
):
    shipment = router.get_one(db, user, obj_id)
    allowed = SHIPMENT_TRANSITIONS.get(shipment.status, set())
    if payload.status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid status transition: {shipment.status} -> {payload.status}. "
                   f"Allowed: {sorted(allowed) or 'none (terminal)'}",
        )
    before = audit.model_to_dict(shipment)
    old = shipment.status
    shipment.status = payload.status
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="shipments.status",
        entity_type="shipments", entity_id=shipment.id,
        before=before, after=audit.model_to_dict(shipment),
    )
    if payload.status == "in_progress":
        events.emit(
            db, "SHIPMENT_IN_TRANSIT", user.org_id, "shipments", shipment.id,
            {"shipment_id": shipment.id, "old_status": old,
             "new_status": payload.status},
        )
    db.commit()
    db.refresh(shipment)
    return schemas.ShipmentOut.model_validate(shipment).model_dump()


@router.get("/{obj_id}/loads", response_model=dict)
def shipment_loads(
    obj_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*SHIPMENT_ROLES)),
):
    shipment = router.get_one(db, user, obj_id)
    q = (
        db.query(models.Load)
        .filter(
            models.Load.org_id == user.org_id,
            models.Load.customer_id == shipment.customer_id,
            models.Load.is_archived.is_(False),
        )
        .order_by(models.Load.created_at.desc())
    )
    q = deps.scope_loads(q, user)
    loads = q.all()
    return {
        "shipment": schemas.ShipmentOut.model_validate(shipment).model_dump(),
        "loads": [schemas.LoadOut.model_validate(l).model_dump() for l in loads],
    }
