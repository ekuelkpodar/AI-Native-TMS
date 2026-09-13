"""Dispatch agent: match unassigned loads to available drivers.

Deterministic ranking by proximity (haversine), hours available, and
compliance state. Conflict warnings (double-booking, appointment overlap,
insufficient hours) are reported, never silently ignored.
"""

from .. import geo
from ... import models

NAME = "dispatch_agent"

_UNASSIGNED_STATUSES = {"quoted", "tendered", "available"}
_ACTIVE_DRIVER_STATUSES = {"assigned", "en_route", "at_pickup", "loading",
                           "in_transit", "at_delivery"}


def _windows_overlap(a_start, a_end, b_start, b_end) -> bool:
    if not all((a_start, a_end, b_start, b_end)):
        return False
    return max(a_start, b_start) < min(a_end, b_end)


def run(db, org_id: str, limit: int = 25) -> dict:
    loads = (
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.status.in_(_UNASSIGNED_STATUSES),
                models.Load.driver_id.is_(None),
                models.Load.is_archived.is_(False))
        .order_by(models.Load.pickup_datetime.asc().nullslast())
        .all()
    )
    drivers = (
        db.query(models.Driver)
        .filter(models.Driver.org_id == org_id,
                models.Driver.status == "available",
                models.Driver.is_active.is_(True))
        .all()
    )

    # Active assignments per driver for double-booking / overlap checks.
    active_assignments = (
        db.query(models.Assignment)
        .filter(models.Assignment.org_id == org_id,
                models.Assignment.status == "active")
        .all()
    )
    by_driver: dict[str, list] = {}
    for a in active_assignments:
        by_driver.setdefault(a.driver_id, []).append(a)
    other_loads = {
        l.id: l for l in
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.id.in_([a.load_id for a in active_assignments] or ["__none__"]))
        .all()
    }

    candidates = []
    for load in loads:
        origin = load.origin or {}
        trip_hours = (load.distance_miles / geo.AVG_SPEED_MPH) if load.distance_miles else 8.0
        for driver in drivers:
            loc = driver.current_location or {}
            dist = geo.haversine_miles(
                loc.get("lat"), loc.get("lng"),
                origin.get("lat"), origin.get("lng"))
            if dist == 0.0 and (loc.get("lat") is None or origin.get("lat") is None):
                dist = 25.0  # neutral penalty when coordinates are missing
            score = max(0.0, round(100.0 - dist * 0.5, 2))

            warnings: list[str] = []
            other = by_driver.get(driver.id, [])
            if other:
                warnings.append(
                    f"Double-booking risk: driver already has "
                    f"{len(other)} active assignment(s)")
                score -= 20
            for a in other:
                ol = other_loads.get(a.load_id)
                if ol and _windows_overlap(load.pickup_datetime,
                                           load.delivery_datetime,
                                           ol.pickup_datetime,
                                           ol.delivery_datetime):
                    warnings.append(
                        f"Appointment overlap with load {ol.load_number}")
                    score -= 15
            if driver.hours_available is not None and \
                    driver.hours_available < trip_hours:
                warnings.append(
                    f"Only {driver.hours_available}h available; trip needs "
                    f"~{trip_hours:.1f}h")
                score -= 25
            score = max(0.0, round(score, 2))
            candidates.append({
                "load_id": load.id,
                "load_number": load.load_number,
                "driver_id": driver.id,
                "driver_name": driver.full_name,
                "score": score,
                "deadhead_miles": round(dist, 1),
                "warnings": warnings,
            })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    top = candidates[:limit]
    covered = len({c["load_id"] for c in top})

    return {
        "recommendation": {
            "assignments": top,
            "unassigned_loads": len(loads),
            "available_drivers": len(drivers),
            "loads_covered": covered,
        },
        "reason": f"Ranked {len(candidates)} load-driver pairs from "
                  f"{len(loads)} unassigned loads and {len(drivers)} available "
                  f"drivers by deadhead distance, hours available, and "
                  f"conflict checks.",
        "expected_impact": f"Covers {covered} of {len(loads)} unassigned loads "
                           f"with the highest-scoring drivers.",
        "confidence": 0.75 if drivers and loads else 0.3,
        "alternatives": [
            "Leave loads unassigned and tender them to carriers via match_carriers.",
            "Split multi-stop loads before assigning.",
        ],
        "risks": [
            "Warnings (double-booking, overlap, hours) must be reviewed before assigning.",
            "Scores use straight-line distance, not road miles.",
        ],
        "approval_required": True,
    }
