"""Auth + RBAC + tenant-isolation dependencies.

- get_current_user: Bearer JWT -> User row (401 on missing/invalid/inactive).
- require_roles(*roles): 403 unless user.role is admin or in roles.
- Tenant isolation: every data query filters org_id == token org_id.
- Scoped roles (driver/carrier/shipper) additionally filter to own records
  via users.driver_id / carrier_id / customer_id.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models
from .database import get_db
from .security import decode_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login", auto_error=False
)


def get_current_user(
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme),
) -> models.User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    if payload.get("org_id") != user.org_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token org mismatch"
        )
    return user


def require_roles(*roles: str):
    """Dependency factory. Admin passes every role check (admin: all scopes)."""

    def _check(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role == "admin" or user.role in roles:
            return user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of roles: {', '.join(roles)}",
        )

    return _check


# ---------------------------------------------------------------------------
# Tenant + scope filtering helpers
# ---------------------------------------------------------------------------


def _impossible(query, model):
    return query.filter(model.id == "__no_such_id__")


def scope_loads(query, user: models.User):
    """Scoped roles see only their own loads."""
    if user.role == "driver":
        if not user.driver_id:
            return _impossible(query, models.Load)
        return query.filter(models.Load.driver_id == user.driver_id)
    if user.role == "carrier":
        if not user.carrier_id:
            return _impossible(query, models.Load)
        return query.filter(models.Load.carrier_id == user.carrier_id)
    if user.role == "shipper":
        if not user.customer_id:
            return _impossible(query, models.Load)
        return query.filter(models.Load.customer_id == user.customer_id)
    return query


def _own_load_ids(db: Session, user: models.User):
    q = db.query(models.Load.id).filter(models.Load.org_id == user.org_id)
    return [row[0] for row in scope_loads(q, user).all()]


def scope_shipments(query, user: models.User):
    if user.role == "shipper":
        if not user.customer_id:
            return _impossible(query, models.Shipment)
        return query.filter(models.Shipment.customer_id == user.customer_id)
    if user.role in ("driver", "carrier"):
        # Shipments belong to customers; drivers/carriers work through loads.
        return _impossible(query, models.Shipment)
    return query


def scope_invoices(query, user: models.User):
    if user.role == "shipper":
        if not user.customer_id:
            return _impossible(query, models.Invoice)
        return query.filter(models.Invoice.customer_id == user.customer_id)
    return query


def scope_customers(query, user: models.User):
    if user.role == "shipper":
        if not user.customer_id:
            return _impossible(query, models.Customer)
        return query.filter(models.Customer.id == user.customer_id)
    return query


def scope_carriers(query, user: models.User):
    if user.role == "carrier":
        if not user.carrier_id:
            return _impossible(query, models.Carrier)
        return query.filter(models.Carrier.id == user.carrier_id)
    return query


def scope_drivers(query, user: models.User):
    if user.role == "driver":
        if not user.driver_id:
            return _impossible(query, models.Driver)
        return query.filter(models.Driver.id == user.driver_id)
    if user.role == "carrier":
        if not user.carrier_id:
            return _impossible(query, models.Driver)
        return query.filter(models.Driver.carrier_id == user.carrier_id)
    return query


def scope_exceptions(query, db: Session, user: models.User):
    if user.role in ("driver", "carrier", "shipper"):
        load_ids = _own_load_ids(db, user)
        if not load_ids:
            return _impossible(query, models.Exception)
        return query.filter(models.Exception.load_id.in_(load_ids))
    return query


def scope_documents(query, db: Session, user: models.User):
    if user.role in ("driver", "carrier", "shipper"):
        load_ids = _own_load_ids(db, user)
        clauses = []
        if load_ids:
            clauses.append(
                (models.Document.entity_type == "loads")
                & (models.Document.entity_id.in_(load_ids))
            )
        if user.role == "driver" and user.driver_id:
            clauses.append(
                (models.Document.entity_type == "drivers")
                & (models.Document.entity_id == user.driver_id)
            )
        if user.role == "carrier" and user.carrier_id:
            clauses.append(
                (models.Document.entity_type == "carriers")
                & (models.Document.entity_id == user.carrier_id)
            )
        if user.role == "shipper" and user.customer_id:
            clauses.append(
                (models.Document.entity_type == "customers")
                & (models.Document.entity_id == user.customer_id)
            )
        if not clauses:
            return _impossible(query, models.Document)
        return query.filter(or_(*clauses))
    return query


def scope_communications(query, user: models.User):
    if user.role == "driver" and user.driver_id:
        return query.filter(
            models.Communication.thread_type == "driver",
            models.Communication.thread_id == user.driver_id,
        )
    if user.role == "carrier" and user.carrier_id:
        return query.filter(
            models.Communication.thread_type == "carrier",
            models.Communication.thread_id == user.carrier_id,
        )
    if user.role == "shipper" and user.customer_id:
        return query.filter(
            models.Communication.thread_type == "customer",
            models.Communication.thread_id == user.customer_id,
        )
    if user.role in ("driver", "carrier", "shipper"):
        return _impossible(query, models.Communication)
    return query


def scope_notifications(query, user: models.User):
    """Users see their own notifications plus org-wide broadcasts."""
    return query.filter(
        or_(
            models.Notification.user_id == user.id,
            models.Notification.user_id.is_(None),
        )
    )
