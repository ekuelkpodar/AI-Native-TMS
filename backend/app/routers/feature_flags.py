"""Feature flags: list all (GET), upsert one (PUT). Admin only."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas
from ..database import get_db

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


@router.get("", response_model=list)
def list_flags(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    flags = (
        db.query(models.FeatureFlag)
        .filter(models.FeatureFlag.org_id == user.org_id)
        .order_by(models.FeatureFlag.key.asc())
        .all()
    )
    return [schemas.FeatureFlagOut.model_validate(f).model_dump() for f in flags]


@router.put("", response_model=dict)
def upsert_flag(
    payload: schemas.FeatureFlagUpsert,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    flag = (
        db.query(models.FeatureFlag)
        .filter(
            models.FeatureFlag.org_id == user.org_id,
            models.FeatureFlag.key == payload.key,
        )
        .first()
    )
    if flag:
        before = audit.model_to_dict(flag)
        flag.enabled = payload.enabled
        if payload.config is not None:
            flag.config = payload.config
        action = "feature_flags.update"
    else:
        before = None
        flag = models.FeatureFlag(
            org_id=user.org_id, key=payload.key,
            enabled=payload.enabled, config=payload.config,
        )
        db.add(flag)
        action = "feature_flags.create"
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action=action,
        entity_type="feature_flags", entity_id=flag.id,
        before=before, after=audit.model_to_dict(flag),
    )
    db.commit()
    db.refresh(flag)
    return schemas.FeatureFlagOut.model_validate(flag).model_dump()
