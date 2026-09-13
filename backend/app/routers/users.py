"""Users CRUD (admin only). Passwords are bcrypt-hashed; never returned."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, models, schemas, security
from ..database import get_db
from .crud import make_crud


def _hash_on_create(db: Session, data: dict, user: models.User):
    data["password_hash"] = security.hash_password(data.pop("password"))


router = make_crud(
    model=models.User,
    create_schema=schemas.UserCreate,
    update_schema=schemas.UserUpdate,
    out_schema=schemas.UserOut,
    prefix="/users",
    tags=["users"],
    read_roles=("admin",),
    write_roles=("admin",),
    search_fields=("email", "full_name"),
    on_create=_hash_on_create,
    entity_name="users",
    include=("list", "create", "get"),
)

# NOTE: update/delete are custom below (password hashing, self-delete guard).


@router.put("/{obj_id}", response_model=dict)
def update_user(
    obj_id: str,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    target = router.get_one(db, user, obj_id)
    before = audit.model_to_dict(target)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        target.password_hash = security.hash_password(data.pop("password"))
    for key, value in data.items():
        setattr(target, key, value)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="users.update",
        entity_type="users", entity_id=target.id,
        before=before, after=audit.model_to_dict(target),
    )
    db.commit()
    db.refresh(target)
    return schemas.UserOut.model_validate(target).model_dump()


@router.delete("/{obj_id}", response_model=dict)
def delete_user(
    obj_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles("admin")),
):
    if obj_id == user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )
    target = router.get_one(db, user, obj_id)
    before = audit.model_to_dict(target)
    target.is_active = False
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="users.archive",
        entity_type="users", entity_id=target.id, before=before,
    )
    db.commit()
    return {"id": obj_id, "deleted": True}
