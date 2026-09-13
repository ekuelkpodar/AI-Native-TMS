"""Current organization: read (any authenticated user) / update (admin)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas
from ..database import get_db

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _get_org(db: Session, user: models.User) -> models.Organization:
    org = (
        db.query(models.Organization)
        .filter(models.Organization.id == user.org_id)
        .first()
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        )
    return org


@router.get("/me", response_model=dict)
def get_my_org(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.get_current_user),
):
    return schemas.OrganizationOut.model_validate(_get_org(db, user)).model_dump()


@router.put("/me", response_model=dict)
def update_my_org(
    payload: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    org = _get_org(db, user)
    before = audit.model_to_dict(org)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(org, key, value)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="organizations.update",
        entity_type="organizations", entity_id=org.id,
        before=before, after=audit.model_to_dict(org),
    )
    db.commit()
    db.refresh(org)
    return schemas.OrganizationOut.model_validate(org).model_dump()
