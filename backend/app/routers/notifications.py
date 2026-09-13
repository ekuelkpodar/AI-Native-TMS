"""Notifications: list (own + org broadcasts), mark read, mark all read."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas
from ..database import get_db

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _scoped_one(db: Session, user: models.User, notif_id: str) -> models.Notification:
    q = db.query(models.Notification).filter(
        models.Notification.id == notif_id,
        models.Notification.org_id == user.org_id,
    )
    notif = deps.scope_notifications(q, user).first()
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
        )
    return notif


@router.get("", response_model=dict)
def list_notifications(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.get_current_user),
    is_read: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    q = db.query(models.Notification).filter(
        models.Notification.org_id == user.org_id
    )
    q = deps.scope_notifications(q, user)
    if is_read is not None:
        q = q.filter(models.Notification.is_read.is_(is_read))
    total = q.count()
    items = (
        q.order_by(models.Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    unread = deps.scope_notifications(
        db.query(models.Notification).filter(
            models.Notification.org_id == user.org_id,
            models.Notification.is_read.is_(False),
        ),
        user,
    ).count()
    return {
        "items": [schemas.NotificationOut.model_validate(n).model_dump() for n in items],
        "total": total,
        "unread": unread,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{notif_id}/read", response_model=dict)
def mark_read(
    notif_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.get_current_user),
):
    notif = _scoped_one(db, user, notif_id)
    notif.is_read = True
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="notifications.read",
        entity_type="notifications", entity_id=notif.id,
    )
    db.commit()
    return {"id": notif_id, "is_read": True}


@router.post("/read-all", response_model=dict)
def mark_all_read(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.get_current_user),
):
    q = db.query(models.Notification).filter(
        models.Notification.org_id == user.org_id,
        models.Notification.is_read.is_(False),
    )
    q = deps.scope_notifications(q, user)
    count = 0
    for notif in q.all():
        notif.is_read = True
        count += 1
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="notifications.read_all",
        entity_type="notifications", entity_id=None,
        after={"marked_read": count},
    )
    db.commit()
    return {"marked_read": count}
