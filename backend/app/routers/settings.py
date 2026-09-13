"""Organization settings: read/update the org's settings JSON. Admin only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas
from ..database import get_db

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=dict)
def get_settings(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    org = (
        db.query(models.Organization)
        .filter(models.Organization.id == user.org_id)
        .first()
    )
    return {"settings": (org.settings if org and org.settings else {})}


@router.put("", response_model=dict)
def update_settings(
    payload: schemas.SettingsUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    org = (
        db.query(models.Organization)
        .filter(models.Organization.id == user.org_id)
        .first()
    )
    before = {"settings": org.settings} if org else None
    org.settings = payload.settings
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="organizations.settings",
        entity_type="organizations", entity_id=org.id,
        before=before, after={"settings": org.settings},
    )
    db.commit()
    return {"settings": org.settings or {}}
