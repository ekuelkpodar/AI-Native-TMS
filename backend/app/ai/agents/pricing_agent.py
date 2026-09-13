"""Pricing agent: lane-average carrier rates -> recommended customer rate at
a target margin (default 15%, configurable via the 'pricing_target_margin'
feature flag config {"value": 0.15}).
"""

from ... import models

NAME = "pricing_agent"


def _flag_value(db, org_id: str, key: str, default: float) -> float:
    flag = (
        db.query(models.FeatureFlag)
        .filter(models.FeatureFlag.org_id == org_id,
                models.FeatureFlag.key == key,
                models.FeatureFlag.enabled.is_(True))
        .first()
    )
    if flag and isinstance(flag.config, dict):
        try:
            return float(flag.config.get("value", default))
        except (TypeError, ValueError):
            pass
    return default


def run(db, org_id: str, origin_city: str, origin_state: str,
        dest_city: str, dest_state: str,
        equipment_type: str | None = None,
        target_margin: float | None = None) -> dict:
    margin = target_margin if target_margin is not None else \
        _flag_value(db, org_id, "pricing_target_margin", 0.15)

    q = (
        db.query(models.Rate)
        .filter(models.Rate.org_id == org_id,
                models.Rate.is_active.is_(True))
    )
    if origin_city:
        q = q.filter(models.Rate.origin_city.ilike(origin_city))
    if origin_state:
        q = q.filter(models.Rate.origin_state.ilike(origin_state))
    if dest_city:
        q = q.filter(models.Rate.dest_city.ilike(dest_city))
    if dest_state:
        q = q.filter(models.Rate.dest_state.ilike(dest_state))
    if equipment_type:
        q = q.filter(models.Rate.equipment_type == equipment_type)
    rates = q.all()

    lane_label = (f"{origin_city or '*'}, {origin_state or '*'} -> "
                  f"{dest_city or '*'}, {dest_state or '*'}")
    if not rates:
        return {
            "recommendation": {
                "lane": lane_label,
                "recommended_customer_rate": None,
                "note": "No lane rate history; use the spot quote endpoint.",
            },
            "reason": "No active rates matched this lane.",
            "expected_impact": "No pricing recommendation available.",
            "confidence": 0.2,
            "alternatives": ["Request a spot quote with distance_miles."],
            "risks": ["Quoting without lane history risks underpricing."],
            "approval_required": False,
        }

    carrier_rates = [float(r.carrier_rate) for r in rates]
    customer_rates = [float(r.customer_rate) for r in rates]
    lane_avg_carrier = sum(carrier_rates) / len(carrier_rates)
    lane_avg_customer = sum(customer_rates) / len(customer_rates)
    recommended = round(lane_avg_carrier / (1 - margin), 2) if margin < 1 else None

    return {
        "recommendation": {
            "lane": lane_label,
            "rates_observed": len(rates),
            "lane_avg_carrier_rate": round(lane_avg_carrier, 2),
            "lane_avg_customer_rate": round(lane_avg_customer, 2),
            "target_margin_pct": round(margin * 100, 2),
            "recommended_customer_rate": recommended,
            "expected_margin_usd": round(recommended - lane_avg_carrier, 2)
            if recommended else None,
        },
        "reason": f"Averaged {len(rates)} active lane rate(s); customer rate "
                  f"solved from carrier average at {margin*100:.1f}% target margin.",
        "expected_impact": f"Quoting ${recommended} holds a "
                           f"{margin*100:.1f}% margin on this lane." if recommended else "",
        "confidence": 0.8 if len(rates) >= 3 else 0.55,
        "alternatives": [
            "Use the contract rate card directly when one exists.",
            "Adjust the target margin for strategic lanes.",
        ],
        "risks": ["Lane averages lag fast-moving spot markets."],
        "approval_required": False,
    }
