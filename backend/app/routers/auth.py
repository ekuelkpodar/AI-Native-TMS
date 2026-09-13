"""Auth: login, self-serve registration, and current-user endpoints."""

import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import deps, models, schemas, security
from ..database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.RegisterRequest, db: Session = Depends(get_db)):
    """Self-serve signup: create a new organization and its first admin user."""
    email = (payload.email or "").strip().lower()
    full_name = (payload.full_name or "").strip()
    company_name = (payload.company_name or "").strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enter a valid work email.",
        )
    if not full_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Full name is required."
        )
    if not company_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Company name is required."
        )
    if len(payload.password or "") < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters.",
        )
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists. Try signing in instead.",
        )
    base_slug = _slugify(company_name)
    slug = base_slug
    suffix = 2
    while db.query(models.Organization).filter(models.Organization.slug == slug).first():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    org = models.Organization(
        name=company_name, slug=slug, plan="starter", settings={}
    )
    db.add(org)
    db.flush()
    user = models.User(
        org_id=org.id,
        email=email,
        password_hash=security.hash_password(payload.password),
        full_name=full_name,
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    token = security.create_access_token(
        user_id=user.id, org_id=user.org_id, role=user.role
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user).model_dump(),
        "organization": schemas.OrganizationOut.model_validate(org).model_dump(),
    }


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
