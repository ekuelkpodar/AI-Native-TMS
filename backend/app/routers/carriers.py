"""Carriers CRUD + deterministic carrier score.

Score formula (ARCHITECTURE.md section 6):
  0.30*rate_competitiveness + 0.25*on_time + 0.15*acceptance
  + 0.15*lane_history + 0.10*compliance + 0.05*equipment_match
Weights are overridable via the feature flag key "carrier_score_weights"
(config holds the weights dict, or {"weights": {...}}).
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .crud import make_crud

router = make_crud(
    model=models.Carrier,
    create_schema=schemas.CarrierCreate,
    update_schema=schemas.CarrierUpdate,
    out_schema=schemas.CarrierOut,
    prefix="/carriers",
    tags=["carriers"],
    read_roles=("admin", "broker", "dispatcher", "ops_manager", "carrier"),
    write_roles=("admin", "broker", "dispatcher"),
    search_fields=("legal_name", "dba", "mc_number", "dot_number", "city", "state"),
    scope_fn=deps.scope_carriers,
    soft_delete_field="is_active",
    entity_name="carriers",
)

DEFAULT_WEIGHTS = {
    "rate_competitiveness": 0.30,
    "on_time": 0.25,
    "acceptance": 0.15,
    "lane_history": 0.15,
    "compliance": 0.10,
    "equipment_match": 0.05,
}

_COMPLIANCE_SCORES = {"compliant": 100.0, "warning": 60.0, "expired": 20.0}


def get_score_weights(db: Session, org_id: str) -> dict:
    flag = (
        db.query(models.FeatureFlag)
        .filter(
            models.FeatureFlag.org_id == org_id,
            models.FeatureFlag.key == "carrier_score_weights",
        )
        .first()
    )
    weights = dict(DEFAULT_WEIGHTS)
    if flag and flag.enabled and isinstance(flag.config, dict):
        cfg = flag.config.get("weights", flag.config)
        if isinstance(cfg, dict):
            for key in weights:
                if key in cfg:
                    try:
                        weights[key] = float(cfg[key])
                    except (TypeError, ValueError):
                        pass
            total = sum(weights.values())
            if total > 0:
                weights = {k: v / total for k, v in weights.items()}
    return weights


def compute_carrier_score(carrier: models.Carrier, weights: dict) -> dict:
    """Deterministic, explainable score. Each factor normalized 0-100."""
    values = {
        "rate_competitiveness": max(
            0.0,
            min(
                100.0,
                100.0
                - (carrier.claims_count or 0) * 8
                - (carrier.cancellations_count or 0) * 4,
            ),
        ),
        "on_time": float(carrier.on_time_pct) if carrier.on_time_pct is not None else 85.0,
        "acceptance": float(carrier.acceptance_rate)
        if carrier.acceptance_rate is not None
        else 90.0,
        "lane_history": float(carrier.performance_score)
        if carrier.performance_score is not None
        else 80.0,
        "compliance": _COMPLIANCE_SCORES.get(
            (carrier.compliance_status or "compliant").lower(), 60.0
        ),
        "equipment_match": 100.0 if carrier.equipment_types else 50.0,
    }
    factors = []
    score = 0.0
    for name, weight in weights.items():
        value = round(values[name], 2)
        contribution = round(weight * value, 2)
        score += weight * value
        factors.append(
            {"name": name, "weight": round(weight, 4), "value": value,
             "contribution": contribution}
        )
    score = round(score, 2)
    explanation = (
        f"Weighted carrier score {score}/100 = "
        + " + ".join(f"{f['weight']:.2f}*{f['name']}({f['value']})" for f in factors)
        + ". Weights from feature flag 'carrier_score_weights' (defaults per spec)."
    )
    return {"score": score, "factors": factors, "explanation": explanation}


@router.get("/{obj_id}/score", response_model=dict)
def carrier_score(
    obj_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(
        deps.require_roles("admin", "broker", "dispatcher", "ops_manager", "carrier")
    ),
):
    carrier = router.get_one(db, user, obj_id)
    weights = get_score_weights(db, user.org_id)
    result = compute_carrier_score(carrier, weights)
    before = carrier.performance_score
    carrier.performance_score = result["score"]
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="carriers.score",
        entity_type="carriers", entity_id=carrier.id,
        before={"performance_score": before},
        after={"performance_score": result["score"]},
    )
    events.emit(
        db, "CARRIER_SCORED", user.org_id, "carriers", carrier.id,
        {"carrier_id": carrier.id, "score": result["score"]},
    )
    db.commit()
    return {
        "carrier_id": carrier.id,
        "score": result["score"],
        "factors": result["factors"],
        "explanation": result["explanation"],
    }
