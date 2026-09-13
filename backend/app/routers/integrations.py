"""Integrations: list adapter statuses, update status/config.

External integrations are adapter interfaces; providers run as 'mock'
unless credentials are configured (documented per-provider in README).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas
from ..database import get_db
from .crud import make_crud

router = make_crud(
    model=models.Integration,
    create_schema=schemas.IntegrationCreate,
    update_schema=schemas.IntegrationUpdate,
    out_schema=schemas.IntegrationOut,
    prefix="/integrations",
    tags=["integrations"],
    read_roles=("admin", "ops_manager"),
    write_roles=("admin",),
    search_fields=("provider",),
    entity_name="integrations",
    include=("list",),  # contract: GET /integrations (+ custom PUT /integrations/{id} below)
)


@router.put("/{obj_id}", response_model=dict)
def update_integration(
    obj_id: str,
    payload: schemas.IntegrationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    integration = router.get_one(db, user, obj_id)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in ("mock", "connected", "disabled"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be one of: mock|connected|disabled",
        )
    before = audit.model_to_dict(integration)
    for key, value in data.items():
        setattr(integration, key, value)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="integrations.update",
        entity_type="integrations", entity_id=integration.id,
        before=before, after=audit.model_to_dict(integration),
    )
    db.commit()
    db.refresh(integration)
    return schemas.IntegrationOut.model_validate(integration).model_dump()
