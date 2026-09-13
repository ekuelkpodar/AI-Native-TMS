"""Audit log: read-only, filterable. Restricted to admin and ops_manager."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import deps, models, schemas
from ..database import get_db
from .crud import _parse_date

router = APIRouter(prefix="/audit", tags=["audit"])

AUDIT_ROLES = ("admin", "ops_manager")


@router.get("", response_model=dict)
def list_audit_logs(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AUDIT_ROLES)),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_type: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    q = db.query(models.AuditLog).filter(
        models.AuditLog.org_id == user.org_id
    )
    if entity_type:
        q = q.filter(models.AuditLog.entity_type == entity_type)
    if entity_id:
        q = q.filter(models.AuditLog.entity_id == entity_id)
    if action:
        q = q.filter(models.AuditLog.action.ilike(f"%{action}%"))
    if actor_type:
        q = q.filter(models.AuditLog.actor_type == actor_type)
    if actor_id:
        q = q.filter(models.AuditLog.actor_id == actor_id)
    if date_from:
        q = q.filter(models.AuditLog.created_at >= _parse_date(date_from))
    if date_to:
        q = q.filter(models.AuditLog.created_at <= _parse_date(date_to, end_of_day=True))
    total = q.count()
    items = (
        q.order_by(models.AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [schemas.AuditLogOut.model_validate(a).model_dump() for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
