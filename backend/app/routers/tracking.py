"""Tracking: simulated live positions + per-load route/events/ETA.

Positions come from the latest tracking_events row per in-transit load.
Loads without any tracking events get a clearly-labeled *simulated* position
interpolated between origin and destination (deterministic, no fake precision
claims — the `simulated` flag is always set in that case).
"""

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import deps, models, schemas
from ..database import get_db

router = APIRouter(prefix="/tracking", tags=["tracking"])

TRACKING_ROLES = (
    "admin", "broker", "dispatcher", "ops_manager",
    "carrier", "driver", "shipper", "finance",
)
IN_TRANSIT_STATUSES = (
    "dispatched", "at_pickup", "picked_up", "in_transit", "at_delivery",
)


def _synthetic_position(load: models.Load) -> dict | None:
    """Deterministic midpoint-ish interpolation between origin/destination."""
    origin = load.origin or {}
    dest = load.destination or {}
    try:
        lat1, lng1 = float(origin["lat"]), float(origin["lng"])
        lat2, lng2 = float(dest["lat"]), float(dest["lng"])
    except (KeyError, TypeError, ValueError):
        return None
    # deterministic jitter from the load id so repeated calls are stable
    h = int(hashlib.md5(load.id.encode()).hexdigest()[:8], 16)
    frac = 0.35 + (h % 30) / 100.0  # 0.35 - 0.64 along the route
    jitter = ((h % 1000) / 1000.0 - 0.5) * 0.4
    return {
        "lat": round(lat1 + (lat2 - lat1) * frac + jitter, 4),
        "lng": round(lng1 + (lng2 - lng1) * frac + jitter, 4),
        "speed_mph": 55.0 + (h % 15),
    }


def _position_for_load(db: Session, load: models.Load) -> dict | None:
    latest = (
        db.query(models.TrackingEvent)
        .filter(
            models.TrackingEvent.org_id == load.org_id,
            models.TrackingEvent.load_id == load.id,
        )
        .order_by(models.TrackingEvent.recorded_at.desc())
        .first()
    )
    if latest and latest.lat is not None and latest.lng is not None:
        return {
            "lat": latest.lat, "lng": latest.lng, "city": latest.city,
            "state": (latest.meta or {}).get("state"),
            "speed_mph": latest.speed_mph,
            "recorded_at": latest.recorded_at,
            "simulated": False,
        }
    synth = _synthetic_position(load)
    if not synth:
        return None
    dest = load.destination or {}
    return {
        "lat": synth["lat"], "lng": synth["lng"],
        "city": dest.get("city"), "state": dest.get("state"),
        "speed_mph": synth["speed_mph"],
        "recorded_at": datetime.now(timezone.utc).replace(tzinfo=None),
        "simulated": True,
    }


def _eta_for_load(load: models.Load) -> str | None:
    """Best-effort ETA: delivery appointment when present, else a simple
    distance/speed projection from the simulated position. Always honest
    about being an estimate (the positions endpoint flags simulation)."""
    if load.delivery_datetime:
        return load.delivery_datetime.isoformat()
    if load.distance_miles:
        hours = load.distance_miles / 55.0
        eta = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)
        return eta.isoformat()
    return None


@router.get("/positions", response_model=list)
def live_positions(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*TRACKING_ROLES)),
):
    q = db.query(models.Load).filter(
        models.Load.org_id == user.org_id,
        models.Load.status.in_(IN_TRANSIT_STATUSES),
        models.Load.is_archived.is_(False),
    )
    q = deps.scope_loads(q, user)
    positions = []
    for load in q.all():
        pos = _position_for_load(db, load)
        if not pos:
            continue
        positions.append(
            {
                "load_id": load.id,
                "load_number": load.load_number,
                "status": load.status,
                "lat": pos["lat"],
                "lng": pos["lng"],
                "city": pos["city"],
                "state": pos["state"],
                "speed_mph": pos["speed_mph"],
                "recorded_at": pos["recorded_at"].isoformat()
                if isinstance(pos["recorded_at"], datetime)
                else pos["recorded_at"],
                "driver_id": load.driver_id,
                "simulated": pos["simulated"],
                "eta": _eta_for_load(load),
            }
        )
    return positions


@router.get("/loads/{load_id}", response_model=dict)
def load_tracking(
    load_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*TRACKING_ROLES)),
):
    q = db.query(models.Load).filter(
        models.Load.id == load_id, models.Load.org_id == user.org_id
    )
    load = deps.scope_loads(q, user).first()
    if not load:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Load not found"
        )
    route = (
        db.query(models.Route)
        .filter(models.Route.load_id == load.id)
        .order_by(models.Route.created_at.desc())
        .first()
    )
    route_data = None
    if route:
        route_data = {
            "waypoints": route.waypoints,
            "total_miles": route.total_miles,
            "total_minutes": route.total_minutes,
            "optimized": route.optimized,
        }
    elif load.origin and load.destination:
        route_data = {
            "waypoints": [load.origin, load.destination],
            "total_miles": load.distance_miles,
            "total_minutes": None,
            "optimized": False,
            "simulated": True,
        }
    events = (
        db.query(models.TrackingEvent)
        .filter(
            models.TrackingEvent.org_id == user.org_id,
            models.TrackingEvent.load_id == load.id,
        )
        .order_by(models.TrackingEvent.recorded_at.desc())
        .limit(200)
        .all()
    )
    eta = load.delivery_datetime
    if eta is None and route and route.total_minutes:
        eta = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            minutes=route.total_minutes / 2
        )
    return {
        "load": schemas.LoadOut.model_validate(load).model_dump(),
        "route": route_data,
        "events": [
            schemas.TrackingEventOut.model_validate(e).model_dump() for e in events
        ],
        "eta": eta.isoformat() if isinstance(eta, datetime) else eta,
    }
