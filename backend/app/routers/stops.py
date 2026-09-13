"""Stops: nested under loads (list/create) + direct update/delete.

Stops carry no org_id of their own; tenancy is enforced through the parent
load (org + role scope).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas
from ..database import get_db

router = APIRouter(tags=["stops"])

STOP_ROLES = (
    "admin", "broker", "dispatcher", "carrier", "driver", "shipper",
)
STOP_WRITE_ROLES = ("admin", "broker", "dispatcher")


def _get_load(db: Session, user: models.User, load_id: str) -> models.Load:
    q = db.query(models.Load).filter(
        models.Load.id == load_id, models.Load.org_id == user.org_id
    )
    load = deps.scope_loads(q, user).first()
    if not load:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Load not found"
        )
    return load


def _get_stop(db: Session, user: models.User, stop_id: str) -> models.Stop:
    stop = (
        db.query(models.Stop)
        .join(models.Load, models.Stop.load_id == models.Load.id)
        .filter(
            models.Stop.id == stop_id,
            models.Load.org_id == user.org_id,
        )
        .first()
    )
    if not stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Stop not found"
        )
    # enforce role scope through the parent load
    _get_load(db, user, stop.load_id)
    return stop


@router.get("/loads/{load_id}/stops", response_model=list)
def list_stops(
    load_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*STOP_ROLES)),
):
    _get_load(db, user, load_id)
    stops = (
        db.query(models.Stop)
        .filter(models.Stop.load_id == load_id)
        .order_by(models.Stop.sequence.asc())
        .all()
    )
    return [schemas.StopOut.model_validate(s).model_dump() for s in stops]


@router.post("/loads/{load_id}/stops", response_model=dict,
             status_code=status.HTTP_201_CREATED)
def create_stop(
    load_id: str,
    payload: schemas.StopCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*STOP_WRITE_ROLES)),
):
    load = _get_load(db, user, load_id)
    stop = models.Stop(load_id=load.id, **payload.model_dump(exclude_unset=True))
    db.add(stop)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="stops.create",
        entity_type="stops", entity_id=stop.id,
        after=audit.model_to_dict(stop),
    )
    db.commit()
    db.refresh(stop)
    return schemas.StopOut.model_validate(stop).model_dump()


@router.put("/stops/{stop_id}", response_model=dict)
def update_stop(
    stop_id: str,
    payload: schemas.StopUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*STOP_WRITE_ROLES)),
):
    stop = _get_stop(db, user, stop_id)
    before = audit.model_to_dict(stop)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(stop, key, value)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="stops.update",
        entity_type="stops", entity_id=stop.id,
        before=before, after=audit.model_to_dict(stop),
    )
    db.commit()
    db.refresh(stop)
    return schemas.StopOut.model_validate(stop).model_dump()


@router.delete("/stops/{stop_id}", response_model=dict)
def delete_stop(
    stop_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*STOP_WRITE_ROLES)),
):
    stop = _get_stop(db, user, stop_id)
    before = audit.model_to_dict(stop)
    db.delete(stop)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="stops.delete",
        entity_type="stops", entity_id=stop_id, before=before,
    )
    db.commit()
    return {"id": stop_id, "deleted": True}
