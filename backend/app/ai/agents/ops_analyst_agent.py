"""Operations analyst agent: KPI bottleneck analysis.

Finds the worst open exception type, the least profitable lane, and the
lowest on-time carrier, and narrates the bottleneck.
"""

from collections import Counter, defaultdict

from ... import models

NAME = "ops_analyst_agent"


def _lane_key(load: models.Load) -> str:
    o, d = load.origin or {}, load.destination or {}
    return (f"{o.get('city', '?')}, {o.get('state', '?')} -> "
            f"{d.get('city', '?')}, {d.get('state', '?')}")


def run(db, org_id: str) -> dict:
    exceptions = (
        db.query(models.Exception)
        .filter(models.Exception.org_id == org_id,
                models.Exception.status.in_(("open", "acknowledged")))
        .all()
    )
    loads = (
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.is_archived.is_(False))
        .all()
    )
    carriers = (
        db.query(models.Carrier)
        .filter(models.Carrier.org_id == org_id,
                models.Carrier.is_active.is_(True))
        .all()
    )

    # Worst exception type by open count.
    exc_counts = Counter(e.exception_type for e in exceptions)
    worst_exc = exc_counts.most_common(1)[0] if exc_counts else (None, 0)

    # Least profitable lane by average margin_pct.
    lane_margins: dict[str, list[float]] = defaultdict(list)
    for load in loads:
        if load.margin_pct is not None:
            lane_margins[_lane_key(load)].append(load.margin_pct)
    lane_avg = {k: sum(v) / len(v) for k, v in lane_margins.items() if v}
    worst_lane = min(lane_avg.items(), key=lambda kv: kv[1]) if lane_avg else (None, None)

    # Lowest on-time carrier.
    timed = [c for c in carriers if c.on_time_pct is not None]
    worst_carrier = min(timed, key=lambda c: c.on_time_pct) if timed else None

    bottlenecks: list[str] = []
    if worst_exc[0]:
        bottlenecks.append(
            f"Worst exception type: '{worst_exc[0]}' ({worst_exc[1]} open).")
    if worst_lane[0]:
        bottlenecks.append(
            f"Least profitable lane: {worst_lane[0]} "
            f"(avg margin {worst_lane[1]:.1f}%).")
    if worst_carrier:
        bottlenecks.append(
            f"Lowest on-time carrier: {worst_carrier.legal_name} "
            f"({worst_carrier.on_time_pct}% on-time).")
    if not bottlenecks:
        bottlenecks.append("No material bottlenecks detected in current data.")

    return {
        "recommendation": {
            "bottlenecks": bottlenecks,
            "worst_exception_type": {"type": worst_exc[0], "open_count": worst_exc[1]},
            "least_profitable_lane": {"lane": worst_lane[0],
                                      "avg_margin_pct": round(worst_lane[1], 2)
                                      if worst_lane[1] is not None else None},
            "lowest_on_time_carrier": {
                "carrier_id": worst_carrier.id,
                "carrier_name": worst_carrier.legal_name,
                "on_time_pct": worst_carrier.on_time_pct} if worst_carrier else None,
            "loads_analyzed": len(loads),
            "carriers_analyzed": len(carriers),
        },
        "reason": "Aggregated open exceptions by type, load margins by lane, "
                  "and carrier on-time percentages; ranked each to find the "
                  "binding constraint.",
        "expected_impact": "Focus operational effort on the top bottleneck first.",
        "confidence": 0.7,
        "alternatives": [],
        "risks": ["Averages hide variance; drill into the underlying loads before acting."],
        "approval_required": False,
    }
