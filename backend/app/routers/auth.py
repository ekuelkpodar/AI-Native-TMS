"""Auth: login (JWT) and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import deps, models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=dict)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = (
        db.query(models.User)
        .filter(models.User.email == payload.email)
        .order_by(models.User.created_at)
        .first()
    )
    if (
        not user
        or not user.is_active
        or not security.verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = security.create_access_token(
        user_id=user.id, org_id=user.org_id, role=user.role
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user).model_dump(),
    }


@router.get("/me", response_model=dict)
def me(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.get_current_user),
):
    org = db.query(models.Organization).filter(models.Organization.id == user.org_id).first()
    return {
        "user": schemas.UserOut.model_validate(user).model_dump(),
        "organization": schemas.OrganizationOut.model_validate(org).model_dump()
        if org
        else None,
    }
