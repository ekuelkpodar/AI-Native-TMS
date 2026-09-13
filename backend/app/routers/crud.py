"""Generic tenant-isolated CRUD router factory.

Every route:
- requires authentication (get_current_user)
- filters by org_id from the JWT (tenant isolation — no exceptions)
- applies an optional scope_fn(query, user) for scoped roles
- writes audit_logs rows on every mutation
- emits the configured domain event on create/update/delete

List responses: {items, total, page, page_size} with support for
search, status, sort_by, sort_dir, page, page_size, date_from, date_to.
"""

from datetime import datetime, time
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import audit, deps, events, models
from ..database import get_db


def _parse_date(value: str | None, end_of_day: bool = False):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except ValueError:
        pass
    try:
        d = datetime.strptime(value[:10], "%Y-%m-%d").date()
        return datetime.combine(d, time.max if end_of_day else time.min)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid date: {value}",
        )


def make_crud(
    *,
    model,
    create_schema,
    update_schema,
    out_schema,
    prefix: str,
    tags: list,
    read_roles: tuple,
    write_roles: tuple,
    search_fields: tuple = (),
    create_event: str | None = None,
    update_event: str | None = None,
    delete_event: str | None = None,
    scope_fn: Callable | None = None,
    soft_delete_field: str | None = None,
    on_create: Callable | None = None,
    entity_name: str | None = None,
    extra_list: Callable | None = None,
    get_one_fn: Callable | None = None,
    include: tuple = ("list", "create", "get", "update", "delete"),
) -> APIRouter:
    """on_create(db, data, user) mutates the create payload dict BEFORE the
    model is constructed (e.g. to hash passwords or assign numbers).
    get_one_fn(db, user, obj_id) overrides single-record fetching, e.g. when
    scoped-role visibility needs the db session (scope_exceptions)."""
    entity = entity_name or model.__tablename__
    router = APIRouter(prefix=prefix, tags=tags)

    def base_query(db: Session, user: models.User):
        q = db.query(model).filter(model.org_id == user.org_id)
        if scope_fn is not None:
            q = scope_fn(q, user)
        return q

    def _default_get_one(db: Session, user: models.User, obj_id: str):
        obj = base_query(db, user).filter(model.id == obj_id).first()
        if obj is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"{entity} not found"
            )
        return obj

    get_one = get_one_fn or _default_get_one

    @router.get("", response_model=dict)
    def list_items(
        db: Session = Depends(get_db),
        user: models.User = Depends(deps.require_roles(*read_roles)),
        search: str | None = Query(default=None),
        status: str | None = Query(default=None),
        sort_by: str | None = Query(default=None),
        sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
        page: int = Query(default=1, ge=1),
        page_size: int = Query(default=50, ge=1, le=500),
        date_from: str | None = Query(default=None),
        date_to: str | None = Query(default=None),
        include_inactive: bool = Query(default=False),
    ):
        q = base_query(db, user)
        if search and search_fields:
            from sqlalchemy import or_

            clauses = [
                getattr(model, f).ilike(f"%{search}%") for f in search_fields
            ]
            q = q.filter(or_(*clauses))
        if status is not None and hasattr(model, "status"):
            q = q.filter(model.status == status)
        if (
            not include_inactive
            and hasattr(model, "is_active")
            and soft_delete_field != "is_active"
        ):
            q = q.filter(model.is_active.is_(True))
        if soft_delete_field == "is_archived" and not include_inactive:
            q = q.filter(model.is_archived.is_(False))
        if date_from and hasattr(model, "created_at"):
            q = q.filter(model.created_at >= _parse_date(date_from))
        if date_to and hasattr(model, "created_at"):
            q = q.filter(model.created_at <= _parse_date(date_to, end_of_day=True))
        if extra_list is not None:
            q = extra_list(q)
        total = q.count()
        sort_col = (
            sort_by
            if sort_by and sort_by in model.__table__.c
            else ("created_at" if "created_at" in model.__table__.c else "id")
        )
        col = model.__table__.c[sort_col]
        q = q.order_by(col.asc() if sort_dir == "asc" else col.desc())
        items = q.offset((page - 1) * page_size).limit(page_size).all()
        return {
            "items": [out_schema.model_validate(i).model_dump() for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
    def create_item(
        payload: create_schema,
        db: Session = Depends(get_db),
        user: models.User = Depends(deps.require_roles(*write_roles)),
    ):
        data = payload.model_dump(exclude_unset=True)
        if on_create is not None:
            on_create(db, data, user)
        obj = model(org_id=user.org_id, **data)
        db.add(obj)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{entity} already exists (duplicate unique field)",
            )
        audit.log(
            db, org_id=user.org_id, actor_type="user", actor_id=user.id,
            actor_name=user.full_name, action=f"{entity}.create",
            entity_type=entity, entity_id=obj.id,
            after=audit.model_to_dict(obj),
        )
        if create_event:
            events.emit(
                db, create_event, user.org_id, entity, obj.id,
                {"id": obj.id, **_event_extra(obj)},
            )
        db.commit()
        db.refresh(obj)
        return out_schema.model_validate(obj).model_dump()

    @router.get("/{obj_id}", response_model=dict)
    def get_item(
        obj_id: str,
        db: Session = Depends(get_db),
        user: models.User = Depends(deps.require_roles(*read_roles)),
    ):
        obj = get_one(db, user, obj_id)
        return out_schema.model_validate(obj).model_dump()

    @router.put("/{obj_id}", response_model=dict)
    def update_item(
        obj_id: str,
        payload: update_schema,
        db: Session = Depends(get_db),
        user: models.User = Depends(deps.require_roles(*write_roles)),
    ):
        obj = get_one(db, user, obj_id)
        before = audit.model_to_dict(obj)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(obj, key, value)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{entity} update conflicts with an existing record",
            )
        audit.log(
            db, org_id=user.org_id, actor_type="user", actor_id=user.id,
            actor_name=user.full_name, action=f"{entity}.update",
            entity_type=entity, entity_id=obj.id, before=before,
            after=audit.model_to_dict(obj),
        )
        if update_event:
            events.emit(
                db, update_event, user.org_id, entity, obj.id,
                {"id": obj.id, **_event_extra(obj)},
            )
        db.commit()
        db.refresh(obj)
        return out_schema.model_validate(obj).model_dump()

    @router.delete("/{obj_id}", response_model=dict)
    def delete_item(
        obj_id: str,
        db: Session = Depends(get_db),
        user: models.User = Depends(deps.require_roles(*write_roles)),
    ):
        obj = get_one(db, user, obj_id)
        before = audit.model_to_dict(obj)
        if soft_delete_field and hasattr(obj, soft_delete_field):
            setattr(obj, soft_delete_field, False if soft_delete_field == "is_active" else True)
            db.flush()
            action = f"{entity}.archive"
        else:
            db.delete(obj)
            db.flush()
            action = f"{entity}.delete"
        audit.log(
            db, org_id=user.org_id, actor_type="user", actor_id=user.id,
            actor_name=user.full_name, action=action,
            entity_type=entity, entity_id=obj_id, before=before,
        )
        if delete_event:
            events.emit(
                db, delete_event, user.org_id, entity, obj_id, {"id": obj_id}
            )
        db.commit()
        return {"id": obj_id, "deleted": True}

    # expose helpers for routers that add custom endpoints
    router.base_query = base_query  # type: ignore[attr-defined]
    router.get_one = get_one  # type: ignore[attr-defined]

    # Optionally drop some of the standard routes (e.g. when a router
    # provides its own custom update/delete implementation).
    _route_kinds = {
        "list": ("GET", ""),
        "create": ("POST", ""),
        "get": ("GET", "/{obj_id}"),
        "update": ("PUT", "/{obj_id}"),
        "delete": ("DELETE", "/{obj_id}"),
    }
    keep = {
        (_route_kinds[kind][0], prefix + _route_kinds[kind][1])
        for kind in include
        if kind in _route_kinds
    }
    router.routes = [
        r
        for r in router.routes
        if (sorted(getattr(r, "methods", []) or [""])[0], getattr(r, "path", ""))
        in keep
    ]

    return router


def _event_extra(obj: Any) -> dict:
    extra = {}
    for key in ("load_number", "invoice_number", "status", "customer_id"):
        if hasattr(obj, key):
            extra[key] = getattr(obj, key)
    return extra
