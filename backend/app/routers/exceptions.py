"""Exceptions: list + acknowledge + resolve + assign.

Resolving fires EXCEPTION_RESOLVED. Creation also fires EXCEPTION_CREATED
(manual creation is allowed; the automation engine creates them too).
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .crud import make_crud

EXC_READ_ROLES = (
    "admin", "broker", "dispatcher", "ops_manager",
    "carrier", "driver", "shipper",
)
EXC_WRITE_ROLES = ("admin", "dispatcher", "ops_manager", "broker")


def _scoped_one(db: Session, user: models.User, exc_id: str) -> models.Exception:
    q = db.query(models.Exception).filter(
        models.Exception.id == exc_id,
        models.Exception.org_id == user.org_id,
    )
    exc = deps.scope_exceptions(q, db, user).first()
    if not exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found"
        )
    return exc


router = make_crud(
    model=models.Exception,
    create_schema=schemas.ExceptionCreate,
    update_schema=schemas.ExceptionUpdate,
    out_schema=schemas.ExceptionOut,
    prefix="/exceptions",
    tags=["exceptions"],
    read_roles=EXC_READ_ROLES,
    write_roles=EXC_WRITE_ROLES,
    search_fields=("title", "description", "exception_type"),
    create_event="EXCEPTION_CREATED",
    entity_name="exceptions",
    get_one_fn=_scoped_one,
    include=("create", "get", "update", "delete"),  # list is custom below (db scoping)
)


@router.get("", response_model=dict)
def list_exceptions(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*EXC_READ_ROLES)),
    search: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    exception_type: str | None = Query(default=None),
    load_id: str | None = Query(default=None),
    owner_user_id: str | None = Query(default=None),
    sort_by: str | None = Query(default=None),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    q = db.query(models.Exception).filter(models.Exception.org_id == user.org_id)
    q = deps.scope_exceptions(q, db, user)
    if search:
        from sqlalchemy import or_
        q = q.filter(
            or_(
                models.Exception.title.ilike(f"%{search}%"),
                models.Exception.description.ilike(f"%{search}%"),
                models.Exception.exception_type.ilike(f"%{search}%"),
            )
        )
    if status is not None:
        q = q.filter(models.Exception.status == status)
    if severity:
        q = q.filter(models.Exception.severity == severity)
    if exception_type:
        q = q.filter(models.Exception.exception_type == exception_type)
    if load_id:
        q = q.filter(models.Exception.load_id == load_id)
    if owner_user_id:
        q = q.filter(models.Exception.owner_user_id == owner_user_id)
    total = q.count()
    sort_col = sort_by if sort_by and sort_by in models.Exception.__table__.c else "detected_at"
    col = models.Exception.__table__.c[sort_col]
    q = q.order_by(col.asc() if sort_dir == "asc" else col.desc())
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [schemas.ExceptionOut.model_validate(e).model_dump() for e in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _append_history(exc: models.Exception, event: str):
    exc.history = (exc.history or []) + [
        {"at": datetime.now(timezone.utc).isoformat(), "event": event}
    ]


@router.post("/{exc_id}/acknowledge", response_model=dict)
def acknowledge_exception(
    exc_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*EXC_WRITE_ROLES)),
):
    exc = _scoped_one(db, user, exc_id)
    if exc.status != "open":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only open exceptions can be acknowledged (current: {exc.status})",
        )
    before = audit.model_to_dict(exc)
    exc.status = "acknowledged"
    exc.owner_user_id = exc.owner_user_id or user.id
    _append_history(exc, f"acknowledged by {user.full_name}")
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="exceptions.acknowledge",
        entity_type="exceptions", entity_id=exc.id,
        before=before, after=audit.model_to_dict(exc),
    )
    db.commit()
    db.refresh(exc)
    return schemas.ExceptionOut.model_validate(exc).model_dump()


@router.post("/{exc_id}/resolve", response_model=dict)
def resolve_exception(
    exc_id: str,
    payload: schemas.ExceptionResolveRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*EXC_WRITE_ROLES)),
):
    exc = _scoped_one(db, user, exc_id)
    if exc.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exception is already resolved",
        )
    before = audit.model_to_dict(exc)
    exc.status = "resolved"
    exc.resolution = payload.resolution
    exc.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
    _append_history(exc, f"resolved by {user.full_name}: {payload.resolution}")
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="exceptions.resolve",
        entity_type="exceptions", entity_id=exc.id,
        before=before, after=audit.model_to_dict(exc),
    )
    events.emit(
        db, "EXCEPTION_RESOLVED", user.org_id, "exceptions", exc.id,
        {"exception_id": exc.id, "load_id": exc.load_id,
         "exception_type": exc.exception_type, "resolution": payload.resolution},
    )
    db.commit()
    db.refresh(exc)
    return schemas.ExceptionOut.model_validate(exc).model_dump()


@router.post("/{exc_id}/assign", response_model=dict)
def assign_exception(
    exc_id: str,
    payload: schemas.ExceptionAssignRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*EXC_WRITE_ROLES)),
):
    exc = _scoped_one(db, user, exc_id)
    owner = (
        db.query(models.User)
        .filter(models.User.id == payload.user_id,
                models.User.org_id == user.org_id)
        .first()
    )
    if not owner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    before = audit.model_to_dict(exc)
    exc.owner_user_id = owner.id
    _append_history(exc, f"assigned to {owner.full_name} by {user.full_name}")
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="exceptions.assign",
        entity_type="exceptions", entity_id=exc.id,
        before=before, after=audit.model_to_dict(exc),
    )
    db.commit()
    db.refresh(exc)
    return schemas.ExceptionOut.model_validate(exc).model_dump()
