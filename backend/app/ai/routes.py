"""AI control-plane HTTP API (mounted at /api/v1/ai by main.py).

POST /command            natural-language command -> structured response
POST /match-carriers     rank carriers for a load
POST /optimize-route     route optimization (policy-gated persistence)
POST /exceptions/scan    run exception detection now
POST /forecast           heuristic moving-average + trend forecast
POST /actions/propose    propose an AI action through the policy engine
GET  /usage              AI token/cost usage + budget check
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import audit, deps, models
from ..database import get_db
from . import approvals as ai_approvals
from .agents import AGENT_RUNNERS
from .agents import carrier_agent as _carrier_agent
from .agents import compliance_agent as _compliance_agent
from .agents import customer_service_agent as _cs_agent
from .agents import dispatch_agent as _dispatch_agent
from .agents import exception_agent as _exception_agent
from .agents import finance_agent as _finance_agent
from .agents import ops_analyst_agent as _ops_agent
from .agents import routing_agent as _routing_agent
from .providers import get_provider, utcnow
from .registry import execute_tool

router = APIRouter()

AI_ROLES = ("admin", "broker", "dispatcher", "ops_manager", "finance")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CommandRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)


class MatchCarriersRequest(BaseModel):
    load_id: str
    top_n: int = Field(default=5, ge=1, le=20)


class OptimizeRouteRequest(BaseModel):
    load_id: str


class ForecastRequest(BaseModel):
    type: str = Field(default="volume")  # volume|cost|lane_pricing|driver_demand
    periods: int = Field(default=3, ge=1, le=12)


class ProposeRequest(BaseModel):
    agent: str
    action_type: str
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict = Field(default_factory=dict)
    reason: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_load(db: Session, org_id: str, load_number: str) -> models.Load | None:
    return (
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.load_number == load_number.upper())
        .first()
    )


def _log_command(db: Session, user: models.User, message: str, intent: str,
                 output: dict) -> None:
    """Every AI action (including /command) gets an ai_actions + audit row."""
    agent = ai_approvals.ensure_agent(db, user.org_id, "ops_analyst_agent")
    row = models.AIAction(
        org_id=user.org_id, agent_id=agent.id, agent_name="command_router",
        action_type="command", input={"message": message, "intent": intent},
        output=output, decision="auto",
        result={"intent": intent},
    )
    db.add(row)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=agent.id,
              actor_name="command_router", action="ai.command",
              entity_type="ai_actions", entity_id=row.id,
              after={"intent": intent})


def _month_start(dt: datetime) -> datetime:
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _flag_config(db: Session, org_id: str, key: str) -> dict:
    flag = (
        db.query(models.FeatureFlag)
        .filter(models.FeatureFlag.org_id == org_id,
                models.FeatureFlag.key == key,
                models.FeatureFlag.enabled.is_(True))
        .first()
    )
    return dict(flag.config or {}) if flag else {}


# ---------------------------------------------------------------------------
# POST /command
# ---------------------------------------------------------------------------

_CAPABILITIES = (
    "I can: show delayed or unassigned loads, check a load's status, "
    "match carriers to a load, optimize a route, scan for exceptions, "
    "review invoices, check carrier compliance, forecast volumes, "
    "analyze bottlenecks, and price a lane."
)


@router.post("/command", response_model=dict)
def ai_command(
    payload: CommandRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    provider = get_provider()
    parsed = provider.complete(
        f"PARSE_INTENT: {payload.message}", db=db, org_id=user.org_id,
        agent_name="command_router", task_type="intent")
    intent = parsed.get("intent", "help")
    entities = parsed.get("entities", {}) or {}

    answer, data, recommendations, actions = "", {}, [], []
    confidence, approval_required = 0.7, False

    if intent == "delayed_loads":
        now = utcnow()
        loads = (
            db.query(models.Load)
            .filter(models.Load.org_id == user.org_id,
                    models.Load.delivery_datetime < now,
                    models.Load.status.notin_(
                        ("delivered", "pod_received", "invoiced", "paid", "cancelled")),
                    models.Load.is_archived.is_(False))
            .order_by(models.Load.delivery_datetime.asc())
            .limit(50).all()
        )
        items = [{"load_number": l.load_number, "status": l.status,
                  "delivery_datetime": l.delivery_datetime.isoformat()
                  if l.delivery_datetime else None} for l in loads]
        answer = (f"{len(items)} delayed load(s) found."
                  if items else "No delayed loads right now.")
        data = {"delayed_loads": items, "count": len(items)}
        recommendations = [r["title"] for r in
                           _exception_agent.run(db, user.org_id)
                           ["recommendation"]["created"]]
        if items:
            actions.append({"label": "Run exception scan", "method": "POST",
                            "endpoint": "/api/v1/ai/exceptions/scan",
                            "payload": {}})

    elif intent == "unassigned_loads":
        rec = _dispatch_agent.run(db, user.org_id)
        body = rec["recommendation"]
        answer = (f"{body['unassigned_loads']} unassigned load(s), "
                  f"{body['available_drivers']} available driver(s); "
                  f"top recommendation covers {body['loads_covered']} load(s).")
        data = body
        recommendations = [
            f"Assign {c['driver_name']} to {c['load_number']} "
            f"(score {c['score']})" + (" — warnings: " + "; ".join(c["warnings"])
                                       if c["warnings"] else "")
            for c in body["assignments"][:5]
        ]
        approval_required = True

    elif intent == "load_status":
        load = _find_load(db, user.org_id, entities.get("load_number", ""))
        if load is None:
            answer = "I couldn't find that load number in your org."
            confidence = 0.3
        else:
            rec = _cs_agent.run(db, user.org_id, load_id=load.id)
            body = rec["recommendation"]
            answer = body["summary"] + (" " + body["delay_explanation"]
                                       if body["delay_explanation"] else "")
            data = body
            recommendations = ["Share the drafted customer update below."]

    elif intent == "match_carriers":
        load = _find_load(db, user.org_id, entities.get("load_number", ""))
        if load is None:
            answer = "Which load? Include a load number like LD-10001."
            confidence = 0.3
        else:
            rec = _carrier_agent.run(db, user.org_id, load_id=load.id,
                                     top_n=entities.get("top_n", 5))
            body = rec["recommendation"]
            top = body["rankings"][0] if body["rankings"] else None
            answer = (f"Top carrier for {body['load_number']}: "
                      f"{top['carrier_name']} ({top['score']}/100)."
                      if top else "No eligible carriers found.")
            data = body

    elif intent == "optimize_route":
        load = _find_load(db, user.org_id, entities.get("load_number", ""))
        if load is None:
            answer = "Which load? Include a load number like LD-10001."
            confidence = 0.3
        else:
            rec = _routing_agent.run(db, user.org_id, load_id=load.id)
            body = rec["recommendation"]
            s = body["savings"]
            answer = (f"Optimized route for {body['load_number']} saves "
                      f"{s['miles']} miles (${s['cost_usd']}).")
            data = body
            approval_required = True
            actions.append({"label": "Apply optimized route", "method": "POST",
                            "endpoint": "/api/v1/ai/optimize-route",
                            "payload": {"load_id": load.id}})

    elif intent == "exceptions":
        open_exc = (
            db.query(models.Exception)
            .filter(models.Exception.org_id == user.org_id,
                    models.Exception.status.in_(("open", "acknowledged")))
            .order_by(models.Exception.detected_at.desc()).limit(50).all()
        )
        items = [{"id": e.id, "type": e.exception_type, "severity": e.severity,
                  "title": e.title, "load_id": e.load_id} for e in open_exc]
        answer = (f"{len(items)} open exception(s)."
                  if items else "No open exceptions.")
        data = {"exceptions": items, "count": len(items)}
        actions.append({"label": "Run exception scan", "method": "POST",
                        "endpoint": "/api/v1/ai/exceptions/scan", "payload": {}})

    elif intent == "finance":
        rec = _finance_agent.run(db, user.org_id)
        body = rec["recommendation"]
        answer = (f"Reviewed {body['invoices_reviewed']} invoice(s); "
                  f"{body['findings_count']} issue(s) found.")
        data = body
        recommendations = body["suggestions"][:5]

    elif intent == "compliance":
        rec = _compliance_agent.run(db, user.org_id)
        body = rec["recommendation"]
        answer = (f"{body['blocked_count']} carrier(s) should be blocked from "
                  f"assignment; {len(body['expiring_soon'])} expiring soon.")
        data = body

    elif intent == "forecast":
        rec = _forecast(db, user.org_id,
                        entities.get("forecast_type", "volume"),
                        entities.get("periods", 3))
        answer = (f"{rec['forecast_type']} forecast: current "
                  f"{rec['current']}, next {len(rec['forecast'])} period(s) "
                  f"{[p['value'] for p in rec['forecast']]}.")
        data = rec

    elif intent == "pricing":
        answer = ("Tell me the lane (origin city/state and destination "
                  "city/state) and I'll price it from lane history.")
        confidence = 0.5
        actions.append({"label": "Price a lane", "method": "POST",
                        "endpoint": "/api/v1/ai/forecast",
                        "payload": {"type": "volume", "periods": 3}})

    elif intent == "analytics":
        result = execute_tool(db, user, "query_analytics", metric="overview")
        answer = (f"{result['active_loads']} active loads, "
                  f"${result['total_revenue']:,.0f} revenue, "
                  f"{result['open_exceptions']} open exceptions.")
        data = result
        recommendations = [
            b for b in _ops_agent.run(db, user.org_id)
            ["recommendation"]["bottlenecks"]
        ]

    else:  # help
        answer = _CAPABILITIES
        confidence = 0.9
        data = {"intents": ["delayed_loads", "unassigned_loads", "load_status",
                            "match_carriers", "optimize_route", "exceptions",
                            "finance", "compliance", "forecast", "pricing",
                            "analytics"]}

    output = {"intent": intent}
    _log_command(db, user, payload.message, intent, output)
    db.commit()
    return {
        "answer": answer,
        "data": data,
        "recommendations": recommendations,
        "actions": actions,
        "confidence": confidence,
        "approval_required": approval_required,
    }


# ---------------------------------------------------------------------------
# POST /match-carriers
# ---------------------------------------------------------------------------

@router.post("/match-carriers", response_model=dict)
def match_carriers(
    payload: MatchCarriersRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    rec = _carrier_agent.run(db, user.org_id, load_id=payload.load_id,
                             top_n=payload.top_n)
    db.commit()
    return {**rec["recommendation"], "approval_required": False}


# ---------------------------------------------------------------------------
# POST /optimize-route
# ---------------------------------------------------------------------------

@router.post("/optimize-route", response_model=dict)
def optimize_route(
    payload: OptimizeRouteRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    rec = _routing_agent.run(db, user.org_id, load_id=payload.load_id)
    body = rec["recommendation"]
    proposed = ai_approvals.propose_action(
        db, user,
        agent_name="routing_agent",
        action_type="optimize_route",
        entity_type="loads",
        entity_id=payload.load_id,
        payload={"load_id": payload.load_id},
        reason=f"Persist optimized route for {body['load_number']}: "
               f"saves {body['savings']['miles']} miles.",
    )
    return {
        "current": body["current"],
        "optimized": body["optimized"],
        "savings": body["savings"],
        "approval_required": proposed["decision"] == "approval_required",
        "decision": proposed["decision"],
        "approval_id": proposed.get("approval_id"),
        "execution_result": proposed.get("result"),
        "reason": proposed.get("reason"),
    }


# ---------------------------------------------------------------------------
# POST /exceptions/scan
# ---------------------------------------------------------------------------

@router.post("/exceptions/scan", response_model=dict)
def scan_exceptions(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    rec = _exception_agent.run(db, user.org_id)
    agent = ai_approvals.ensure_agent(db, user.org_id, "exception_agent")
    row = models.AIAction(
        org_id=user.org_id, agent_id=agent.id, agent_name="exception_agent",
        action_type="scan_exceptions",
        input={}, output=rec["recommendation"], decision="auto",
        result={"created": len(rec["recommendation"]["created"])},
    )
    db.add(row)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=agent.id,
              actor_name="exception_agent", action="ai.scan_exceptions",
              entity_type="ai_actions", entity_id=row.id,
              after={"created": len(rec["recommendation"]["created"])})
    db.commit()
    return {"created": rec["recommendation"]["created"],
            "created_count": rec["recommendation"]["created_count"],
            "loads_scanned": rec["recommendation"]["loads_scanned"]}


# ---------------------------------------------------------------------------
# POST /forecast
# ---------------------------------------------------------------------------

_FORECAST_TYPES = ("volume", "cost", "lane_pricing", "driver_demand")


def _month_label(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _forecast(db: Session, org_id: str, ftype: str, periods: int) -> dict:
    if ftype not in _FORECAST_TYPES:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported forecast type '{ftype}'. "
                   f"Supported: {', '.join(_FORECAST_TYPES)}.")
    now = utcnow()
    months: list[tuple[int, int]] = []
    y, m = now.year, now.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    months.reverse()

    loads = (
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.is_archived.is_(False))
        .all()
    )
    buckets: dict[tuple[int, int], list[models.Load]] = {k: [] for k in months}
    for load in loads:
        created = load.created_at or now
        key = (created.year, created.month)
        if key in buckets:
            buckets[key].append(load)

    historical = []
    for key in months:
        group = buckets[key]
        if ftype == "volume" or ftype == "driver_demand":
            value = float(len(group))
        elif ftype == "cost":
            value = round(sum(l.carrier_rate or 0 for l in group), 2)
        else:  # lane_pricing
            rates = [l.customer_rate for l in group if l.customer_rate]
            value = round(sum(rates) / len(rates), 2) if rates else 0.0
        historical.append({"period": _month_label(*key), "value": value})

    values = [h["value"] for h in historical]
    avg3 = sum(values[-3:]) / 3 if values else 0.0
    avg_first3 = sum(values[:3]) / 3 if len(values) >= 3 else avg3
    trend = (avg3 - avg_first3) / 3

    forecast = []
    fy, fm = now.year, now.month
    for i in range(periods):
        fm += 1
        if fm == 13:
            fm, fy = 1, fy + 1
        val = max(0.0, round(avg3 + trend * (i + 1), 2))
        forecast.append({"period": _month_label(fy, fm), "value": val})

    confidence = round(min(0.85, 0.5 + 0.05 * len(historical)), 2)
    return {
        "forecast_type": ftype,
        "historical": historical,
        "current": historical[-1]["value"] if historical else 0.0,
        "forecast": forecast,
        "confidence": confidence,
        "method": "moving_average_3_plus_trend",
    }


@router.post("/forecast", response_model=dict)
def forecast(
    payload: ForecastRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    result = _forecast(db, user.org_id, payload.type, payload.periods)
    db.commit()
    return result


# ---------------------------------------------------------------------------
# POST /actions/propose
# ---------------------------------------------------------------------------

@router.post("/actions/propose", response_model=dict)
def propose(
    payload: ProposeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    return ai_approvals.propose_action(
        db, user,
        agent_name=payload.agent,
        action_type=payload.action_type,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        payload=payload.payload,
        reason=payload.reason,
    )


# ---------------------------------------------------------------------------
# GET /usage
# ---------------------------------------------------------------------------

@router.get("/usage", response_model=dict)
def ai_usage(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*AI_ROLES)),
):
    now = utcnow()
    start = _month_start(now)
    rows = (
        db.query(models.AIUsage)
        .filter(models.AIUsage.org_id == user.org_id,
                models.AIUsage.created_at >= start)
        .all()
    )
    by_agent: dict[str, dict] = {}
    total_in = total_out = 0
    total_cost = 0.0
    for r in rows:
        total_in += r.tokens_in or 0
        total_out += r.tokens_out or 0
        total_cost += r.est_cost_usd or 0.0
        agg = by_agent.setdefault(r.agent_name, {"agent_name": r.agent_name,
                                                 "calls": 0, "tokens_in": 0,
                                                 "tokens_out": 0,
                                                 "est_cost_usd": 0.0})
        agg["calls"] += 1
        agg["tokens_in"] += r.tokens_in or 0
        agg["tokens_out"] += r.tokens_out or 0
        agg["est_cost_usd"] = round(agg["est_cost_usd"] + (r.est_cost_usd or 0.0), 6)

    cfg = _flag_config(db, user.org_id, "ai_monthly_budget_usd")
    budget = float(cfg.get("value", 500))
    used_pct = round(total_cost / budget * 100, 2) if budget else 0.0
    db.commit()
    return {
        "period": _month_label(now.year, now.month),
        "calls": len(rows),
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "est_cost_usd": round(total_cost, 6),
        "by_agent": sorted(by_agent.values(),
                           key=lambda a: a["est_cost_usd"], reverse=True),
        "budget_usd": budget,
        "budget_used_pct": used_pct,
        "budget_alert": used_pct >= 80.0,
    }


# Re-export for tests / external tracks.
__all__ = ["router", "AGENT_RUNNERS"]
