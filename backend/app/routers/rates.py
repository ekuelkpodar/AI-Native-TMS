"""Rates CRUD + quote engine.

Quote: matches an active rate card row (origin/destination/equipment, contract
preferred); otherwise falls back to a per-mile estimate (basis="estimated").
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .crud import make_crud

RATE_ROLES = ("admin", "broker", "dispatcher", "finance", "ops_manager")
RATE_WRITE_ROLES = ("admin", "broker", "finance")

# Fallback per-mile estimates by equipment type when no rate card matches.
PER_MILE = {
    "dry_van": (2.75, 2.10),
    "reefer": (3.10, 2.40),
    "flatbed": (3.00, 2.30),
    "step_deck": (3.05, 2.35),
    "tanker": (3.20, 2.50),
    "box_truck": (2.20, 1.70),
    "other": (2.75, 2.10),
}

router = make_crud(
    model=models.Rate,
    create_schema=schemas.RateCreate,
    update_schema=schemas.RateUpdate,
    out_schema=schemas.RateOut,
    prefix="/rates",
    tags=["rates"],
    read_roles=RATE_ROLES,
    write_roles=RATE_WRITE_ROLES,
    search_fields=("origin_city", "origin_state", "dest_city", "dest_state"),
    update_event="RATE_UPDATED",
    create_event="RATE_UPDATED",
    entity_name="rates",
)


@router.post("/quote", response_model=dict)
def quote_rate(
    payload: schemas.RateQuoteRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*RATE_ROLES)),
):
    origin = payload.origin or {}
    dest = payload.destination or {}
    oc = (origin.get("city") or "").strip()
    os_ = (origin.get("state") or "").strip()
    dc = (dest.get("city") or "").strip()
    ds = (dest.get("state") or "").strip()

    rate = None
    if oc and dc:
        q = db.query(models.Rate).filter(
            models.Rate.org_id == user.org_id,
            models.Rate.is_active.is_(True),
        )
        if os_:
            q = q.filter(models.Rate.origin_state.ilike(os_))
        else:
            q = q.filter(models.Rate.origin_city.ilike(oc))
        if ds:
            q = q.filter(models.Rate.dest_state.ilike(ds))
        else:
            q = q.filter(models.Rate.dest_city.ilike(dc))
        if payload.equipment_type:
            q = q.filter(models.Rate.equipment_type == payload.equipment_type)
        # contract rates preferred over spot
        rate = q.order_by(
            models.Rate.rate_type.desc(), models.Rate.created_at.desc()
        ).first()

    if rate:
        customer_rate = float(rate.customer_rate)
        carrier_rate = float(rate.carrier_rate)
        basis = "rate_card"
    else:
        miles = payload.distance_miles
        if not miles or miles <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No matching rate card found and distance_miles is required "
                       "for an estimate",
            )
        per_customer, per_carrier = PER_MILE.get(
            payload.equipment_type, PER_MILE["other"]
        )
        customer_rate = round(miles * per_customer, 2)
        carrier_rate = round(miles * per_carrier, 2)
        basis = "estimated"

    margin = round(customer_rate - carrier_rate, 2)
    margin_pct = round(margin / customer_rate * 100, 2) if customer_rate else 0.0
    return {
        "customer_rate": customer_rate,
        "carrier_rate": carrier_rate,
        "margin": margin,
        "margin_pct": margin_pct,
        "basis": basis,
    }
