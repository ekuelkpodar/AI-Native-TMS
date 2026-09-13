"""Lanes: aggregated lane statistics from loads.

A lane is the origin city/state -> destination city/state pair. The lane id
is a URL-safe base64 encoding of those four parts.
"""

import base64
import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import deps, models, schemas
from ..database import get_db

router = APIRouter(prefix="/lanes", tags=["lanes"])

LANE_ROLES = ("admin", "broker", "dispatcher", "ops_manager")


def _lane_id(origin: dict, destination: dict) -> str:
    raw = json.dumps([
        (origin.get("city") or "").strip(),
        (origin.get("state") or "").strip(),
        (destination.get("city") or "").strip(),
        (destination.get("state") or "").strip(),
    ])
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _lane_parts(lane_id: str) -> tuple:
    padded = lane_id + "=" * (-len(lane_id) % 4)
    try:
        parts = json.loads(base64.urlsafe_b64decode(padded).decode())
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found"
        )
    if not isinstance(parts, list) or len(parts) != 4:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found"
        )
    return tuple(parts)


def _aggregate(db: Session, user: models.User):
    q = db.query(models.Load).filter(
        models.Load.org_id == user.org_id,
        models.Load.status != "cancelled",
        models.Load.is_archived.is_(False),
    )
    q = deps.scope_loads(q, user)
    groups: dict[str, dict] = {}
    for load in q.all():
        origin = load.origin or {}
        dest = load.destination or {}
        oc, os_ = (origin.get("city") or ""), (origin.get("state") or "")
        dc, ds = (dest.get("city") or ""), (dest.get("state") or "")
        if not oc or not dc:
            continue
        lid = _lane_id(origin, dest)
        g = groups.setdefault(lid, {
            "id": lid,
            "origin": {"city": oc, "state": os_},
            "destination": {"city": dc, "state": ds},
            "loads": [],
        })
        g["loads"].append(load)
    return groups


def _summarize(lid: str, g: dict) -> dict:
    loads = g["loads"]
    cust_rates = [l.customer_rate for l in loads if l.customer_rate]
    carr_rates = [l.carrier_rate for l in loads if l.carrier_rate]
    margins = [
        l.customer_rate - l.carrier_rate for l in loads
        if l.customer_rate is not None and l.carrier_rate is not None
    ]
    equipment = sorted({l.equipment_type for l in loads if l.equipment_type})
    last = max((l.created_at for l in loads if l.created_at), default=None)
    return {
        "id": lid,
        "origin": g["origin"],
        "destination": g["destination"],
        "load_count": len(loads),
        "total_revenue": round(sum(cust_rates), 2),
        "avg_customer_rate": round(sum(cust_rates) / len(cust_rates), 2) if cust_rates else None,
        "avg_carrier_rate": round(sum(carr_rates) / len(carr_rates), 2) if carr_rates else None,
        "avg_margin": round(sum(margins) / len(margins), 2) if margins else None,
        "equipment_types": equipment,
        "last_load_date": last.isoformat() if last else None,
    }


@router.get("", response_model=list)
def list_lanes(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LANE_ROLES)),
    search: str | None = Query(default=None),
):
    groups = _aggregate(db, user)
    summaries = [_summarize(lid, g) for lid, g in groups.items()]
    if search:
        s = search.lower()
        summaries = [
            x for x in summaries
            if s in x["origin"]["city"].lower()
            or s in x["destination"]["city"].lower()
            or s in (x["origin"]["state"] or "").lower()
            or s in (x["destination"]["state"] or "").lower()
        ]
    summaries.sort(key=lambda x: -x["load_count"])
    return summaries


@router.get("/{lane_id}", response_model=dict)
def lane_detail(
    lane_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*LANE_ROLES)),
):
    oc, os_, dc, ds = _lane_parts(lane_id)
    q = db.query(models.Load).filter(
        models.Load.org_id == user.org_id,
        models.Load.status != "cancelled",
        models.Load.is_archived.is_(False),
    )
    q = deps.scope_loads(q, user)
    matches = []
    for load in q.all():
        origin = load.origin or {}
        dest = load.destination or {}
        if (
            (origin.get("city") or "") == oc
            and (origin.get("state") or "") == os_
            and (dest.get("city") or "") == dc
            and (dest.get("state") or "") == ds
        ):
            matches.append(load)
    if not matches:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found"
        )
    matches.sort(key=lambda l: l.created_at or "", reverse=True)
    summary = _summarize(
        lane_id,
        {"origin": {"city": oc, "state": os_},
         "destination": {"city": dc, "state": ds}, "loads": matches},
    )
    summary["recent_loads"] = [
        schemas.LoadOut.model_validate(l).model_dump() for l in matches[:20]
    ]
    return summary
