"""Routing agent: nearest-neighbor stop reorder with haversine miles.

Returns current vs optimized stop orders with miles/minutes/fuel_usd/cost_usd
and the savings between them. Pure geometry — deterministic.
"""

from fastapi import HTTPException, status

from .. import geo
from ... import models

NAME = "routing_agent"


def _waypoints(db, load: models.Load) -> list[dict]:
    points: list[dict] = []
    origin = load.origin or {}
    points.append({"label": f"Origin: {origin.get('city', '')}, "
                            f"{origin.get('state', '')}".strip(", "),
                   "lat": origin.get("lat"), "lng": origin.get("lng")})
    stops = (
        db.query(models.Stop)
        .filter(models.Stop.load_id == load.id)
        .order_by(models.Stop.sequence.asc())
        .all()
    )
    for s in stops:
        loc = s.location or {}
        points.append({"label": f"{s.stop_type}: {loc.get('city', '')}, "
                                f"{loc.get('state', '')}".strip(", "),
                       "lat": loc.get("lat"), "lng": loc.get("lng")})
    dest = load.destination or {}
    points.append({"label": f"Destination: {dest.get('city', '')}, "
                            f"{dest.get('state', '')}".strip(", "),
                   "lat": dest.get("lat"), "lng": dest.get("lng")})
    return points


def run(db, org_id: str, load_id: str) -> dict:
    load = (
        db.query(models.Load)
        .filter(models.Load.id == load_id, models.Load.org_id == org_id)
        .first()
    )
    if load is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Load not found")

    points = _waypoints(db, load)
    if len(points) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="Load has no route geometry to optimize.")

    current_miles = geo.total_miles(points)
    order = geo.nearest_neighbor_order(points)
    optimized_miles = geo.total_miles(points, order)

    current = geo.trip_costs(current_miles)
    optimized = geo.trip_costs(optimized_miles)
    savings = {k: round(current[k] - optimized[k], 2) for k in current}

    current["stop_order"] = [points[i]["label"] for i in range(len(points))]
    optimized["stop_order"] = [points[i]["label"] for i in order]
    optimized["waypoints"] = [
        {"label": points[i]["label"], "lat": points[i].get("lat"),
         "lng": points[i].get("lng")} for i in order
    ]

    return {
        "recommendation": {
            "load_id": load.id,
            "load_number": load.load_number,
            "current": current,
            "optimized": optimized,
            "savings": savings,
        },
        "reason": f"Nearest-neighbor reorder of {len(points)} waypoints "
                  f"starting at origin; geometry is haversine (straight-line) "
                  f"miles.",
        "expected_impact": f"Saves {savings['miles']} miles "
                           f"(${savings['cost_usd']} operating cost) per trip.",
        "confidence": 0.8 if all(p.get("lat") is not None for p in points) else 0.4,
        "alternatives": [
            "Keep the current stop order.",
            "Re-sequence manually in the stops editor.",
        ],
        "risks": [
            "Haversine miles understate real road miles; savings are directional.",
            "Appointment windows are not considered in the reorder.",
        ],
        "approval_required": True,  # persisting a route mutates operations data
    }
