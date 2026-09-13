"""Carrier agent: rank carriers for a load with per-factor explanations.

Reuses the deterministic score from routers/carriers.py (weights overridable
via the 'carrier_score_weights' feature flag).
"""

from fastapi import HTTPException, status

from ... import models

NAME = "carrier_agent"


def _eligible(carriers: list[models.Carrier], load: models.Load) -> list[models.Carrier]:
    origin = load.origin or {}
    dest = load.destination or {}
    states = {origin.get("state"), dest.get("state")} - {None, ""}
    out = []
    for c in carriers:
        if load.equipment_type and c.equipment_types and \
                load.equipment_type not in c.equipment_types:
            continue
        if states and c.service_areas and not (states & set(c.service_areas)):
            continue
        if c.compliance_status == "expired":
            continue  # compliance agent block-list
        out.append(c)
    return out


_FACTOR_NOTES = {
    "rate_competitiveness": "fewer claims/cancellations = more competitive",
    "on_time": "carrier on-time pickup/delivery percentage",
    "acceptance": "tender acceptance rate",
    "lane_history": "historical performance score on lanes",
    "compliance": "authority/insurance compliance standing",
    "equipment_match": "has suitable equipment types on file",
}


def run(db, org_id: str, load_id: str, top_n: int = 5) -> dict:
    from ...routers.carriers import compute_carrier_score, get_score_weights

    load = (
        db.query(models.Load)
        .filter(models.Load.id == load_id, models.Load.org_id == org_id)
        .first()
    )
    if load is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Load not found")

    carriers = (
        db.query(models.Carrier)
        .filter(models.Carrier.org_id == org_id,
                models.Carrier.is_active.is_(True))
        .all()
    )
    weights = get_score_weights(db, org_id)
    eligible = _eligible(carriers, load)

    rankings = []
    for carrier in eligible:
        scored = compute_carrier_score(carrier, weights)
        factors = []
        for f in scored["factors"]:
            factors.append({
                **f,
                "explanation": f"{f['name']}={f['value']} "
                               f"(weight {f['weight']}): "
                               f"{_FACTOR_NOTES.get(f['name'], '')}",
            })
        rankings.append({
            "carrier_id": carrier.id,
            "carrier_name": carrier.legal_name,
            "mc_number": carrier.mc_number,
            "score": scored["score"],
            "factors": factors,
            "explanation": scored["explanation"],
        })
    rankings.sort(key=lambda r: r["score"], reverse=True)
    top = rankings[:max(1, top_n)]

    return {
        "recommendation": {
            "load_id": load.id,
            "load_number": load.load_number,
            "rankings": top,
            "carriers_considered": len(eligible),
            "carriers_filtered_out": len(carriers) - len(eligible),
        },
        "reason": "Deterministic weighted score per ARCHITECTURE.md section 6; "
                  "carriers missing equipment/service-area fit or with expired "
                  "compliance are filtered out before scoring.",
        "expected_impact": f"Top pick {top[0]['carrier_name']} scores "
                           f"{top[0]['score']}/100." if top else "No eligible carriers.",
        "confidence": 0.85 if top else 0.2,
        "alternatives": [
            "Tender to the load board instead of direct assignment.",
            "Adjust weights via the 'carrier_score_weights' feature flag.",
        ],
        "risks": [
            "Scores reflect historical data; verify insurance is current before tendering.",
        ],
        "approval_required": False,  # ranking only; assignment is a separate action
    }
