"""Analytics: overview KPI bundle + financial / operational / carrier / customer.

Filters (where relevant): date_from, date_to (load created_at), customer_id,
carrier_id, driver_id, origin_city, origin_state, dest_city, dest_state.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import deps, models
from ..database import get_db
from .crud import _parse_date

router = APIRouter(prefix="/analytics", tags=["analytics"])

ANALYTICS_ROLES = ("admin", "finance", "ops_manager", "broker", "dispatcher")

ACTIVE_STATUSES = {
    "assigned", "confirmed", "dispatched", "at_pickup", "picked_up",
    "in_transit", "at_delivery",
}
IN_TRANSIT_STATUSES = {"dispatched", "at_pickup", "picked_up", "in_transit", "at_delivery"}
COMPLETED_STATUSES = {"delivered", "pod_received", "invoiced", "paid"}


def _filtered_loads(db: Session, user: models.User, *,
                    date_from=None, date_to=None, customer_id=None,
                    carrier_id=None, driver_id=None, origin_city=None,
                    origin_state=None, dest_city=None, dest_state=None,
                    exclude_cancelled=True):
    q = db.query(models.Load).filter(
        models.Load.org_id == user.org_id,
        models.Load.is_archived.is_(False),
    )
    q = deps.scope_loads(q, user)
    if exclude_cancelled:
        q = q.filter(models.Load.status != "cancelled")
    if date_from:
        q = q.filter(models.Load.created_at >= _parse_date(date_from))
    if date_to:
        q = q.filter(models.Load.created_at <= _parse_date(date_to, end_of_day=True))
    if customer_id:
        q = q.filter(models.Load.customer_id == customer_id)
    if carrier_id:
        q = q.filter(models.Load.carrier_id == carrier_id)
    if driver_id:
        q = q.filter(models.Load.driver_id == driver_id)
    loads = q.all()
    if origin_city:
        loads = [l for l in loads
                 if (l.origin or {}).get("city", "").lower() == origin_city.lower()]
    if origin_state:
        loads = [l for l in loads
                 if (l.origin or {}).get("state", "").lower() == origin_state.lower()]
    if dest_city:
        loads = [l for l in loads
                 if (l.destination or {}).get("city", "").lower() == dest_city.lower()]
    if dest_state:
        loads = [l for l in loads
                 if (l.destination or {}).get("state", "").lower() == dest_state.lower()]
    return loads


def _money(loads):
    revenue = round(sum(l.customer_rate or 0 for l in loads), 2)
    cost = round(sum(l.carrier_rate or 0 for l in loads), 2)
    margin = round(revenue - cost, 2)
    margin_pct = round(margin / revenue * 100, 2) if revenue else 0.0
    return revenue, cost, margin, margin_pct


def _on_time_pct(db: Session, user: models.User, loads) -> float | None:
    delivered = [l for l in loads if l.status in COMPLETED_STATUSES]
    if not delivered:
        return None
    late_ids = {
        row[0]
        for row in db.query(models.Exception.load_id).filter(
            models.Exception.org_id == user.org_id,
            models.Exception.exception_type == "late_delivery",
            models.Exception.load_id.isnot(None),
        ).all()
    }
    on_time = sum(1 for l in delivered if l.id not in late_ids)
    return round(on_time / len(delivered) * 100, 2)


@router.get("/overview", response_model=dict)
def overview(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*ANALYTICS_ROLES)),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    driver_id: str | None = Query(default=None),
):
    loads = _filtered_loads(
        db, user, date_from=date_from, date_to=date_to,
        customer_id=customer_id, carrier_id=carrier_id, driver_id=driver_id,
    )
    revenue, cost, margin, margin_pct = _money(loads)
    by_status: dict[str, int] = defaultdict(int)
    for l in loads:
        by_status[l.status] += 1

    open_exc = (
        db.query(models.Exception)
        .filter(models.Exception.org_id == user.org_id,
                models.Exception.status == "open")
        .count()
    )
    critical_exc = (
        db.query(models.Exception)
        .filter(models.Exception.org_id == user.org_id,
                models.Exception.status == "open",
                models.Exception.severity == "critical")
        .count()
    )
    invoices = (
        db.query(models.Invoice)
        .filter(models.Invoice.org_id == user.org_id,
                models.Invoice.status.in_(("issued", "overdue")))
        .all()
    )
    outstanding = round(sum((i.total or 0) - (i.amount_paid or 0) for i in invoices), 2)
    overdue = round(
        sum((i.total or 0) - (i.amount_paid or 0) for i in invoices
            if i.status == "overdue"), 2
    )

    # Month-to-date + 14-day revenue series (dashboard charts)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mtd_loads = [l for l in loads
                 if l.created_at and l.created_at >= month_start]
    revenue_mtd, _, margin_mtd, _ = _money(mtd_loads)
    revenue_by_day = []
    for i in range(13, -1, -1):
        day = (now - timedelta(days=i)).date()
        day_rev = round(sum(l.customer_rate or 0 for l in loads
                            if l.created_at and l.created_at.date() == day), 2)
        revenue_by_day.append({"date": day.isoformat(), "revenue": day_rev})

    return {
        "total_loads": len(loads),
        "active_loads": sum(1 for l in loads if l.status in ACTIVE_STATUSES),
        "in_transit": sum(1 for l in loads if l.status in IN_TRANSIT_STATUSES),
        "in_transit_loads": sum(1 for l in loads if l.status in IN_TRANSIT_STATUSES),
        "delivered_loads": sum(1 for l in loads if l.status in COMPLETED_STATUSES),
        "total_revenue": revenue,
        "total_cost": cost,
        "margin": margin,
        "margin_pct": margin_pct,
        "revenue_mtd": revenue_mtd,
        "margin_mtd": margin_mtd,
        "revenue_by_day": revenue_by_day,
        "avg_margin_per_load": round(margin / len(loads), 2) if loads else 0.0,
        "on_time_pct": _on_time_pct(db, user, loads),
        "open_exceptions": open_exc,
        "critical_exceptions": critical_exc,
        "outstanding_invoices": outstanding,
        "overdue_invoices": overdue,
        "loads_by_status": [{"status": s, "count": c}
                            for s, c in sorted(by_status.items())],
    }


@router.get("/financial", response_model=dict)
def financial(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*ANALYTICS_ROLES)),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
):
    loads = _filtered_loads(
        db, user, date_from=date_from, date_to=date_to,
        customer_id=customer_id, carrier_id=carrier_id,
    )
    revenue, cost, margin, margin_pct = _money(loads)

    invoices = (
        db.query(models.Invoice)
        .filter(models.Invoice.org_id == user.org_id)
        .all()
    )
    invoiced = round(sum(i.total or 0 for i in invoices if i.status != "void"), 2)
    paid = round(sum(i.amount_paid or 0 for i in invoices), 2)
    outstanding = round(
        sum((i.total or 0) - (i.amount_paid or 0) for i in invoices
            if i.status in ("issued", "overdue")), 2
    )
    overdue = round(
        sum((i.total or 0) - (i.amount_paid or 0) for i in invoices
            if i.status == "overdue"), 2
    )

    by_month: dict[str, dict] = defaultdict(
        lambda: {"revenue": 0.0, "cost": 0.0, "loads": 0}
    )
    for l in loads:
        key = l.created_at.strftime("%Y-%m") if l.created_at else "unknown"
        by_month[key]["revenue"] += l.customer_rate or 0
        by_month[key]["cost"] += l.carrier_rate or 0
        by_month[key]["loads"] += 1
    monthly = [
        {"month": k, "revenue": round(v["revenue"], 2),
         "cost": round(v["cost"], 2), "loads": v["loads"],
         "margin": round(v["revenue"] - v["cost"], 2)}
        for k, v in sorted(by_month.items())
    ]

    by_customer: dict[str, dict] = defaultdict(
        lambda: {"revenue": 0.0, "cost": 0.0, "loads": 0}
    )
    for l in loads:
        v = by_customer[l.customer_id]
        v["revenue"] += l.customer_rate or 0
        v["cost"] += l.carrier_rate or 0
        v["loads"] += 1
    customers = []
    for cid, v in sorted(by_customer.items(), key=lambda x: -x[1]["revenue"])[:20]:
        cust = db.query(models.Customer).filter(models.Customer.id == cid).first()
        customers.append({
            "customer_id": cid,
            "customer_name": cust.name if cust else cid,
            "loads": v["loads"],
            "revenue": round(v["revenue"], 2),
            "cost": round(v["cost"], 2),
            "margin": round(v["revenue"] - v["cost"], 2),
        })

    return {
        "revenue": revenue, "cost": cost, "margin": margin,
        "margin_pct": margin_pct, "load_count": len(loads),
        "invoiced_total": invoiced, "paid_total": paid,
        "outstanding": outstanding, "overdue_total": overdue,
        "by_month": monthly, "by_customer": customers,
    }


@router.get("/operational", response_model=dict)
def operational(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*ANALYTICS_ROLES)),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
    driver_id: str | None = Query(default=None),
):
    loads = _filtered_loads(
        db, user, date_from=date_from, date_to=date_to,
        carrier_id=carrier_id, driver_id=driver_id,
    )
    by_status: dict[str, int] = defaultdict(int)
    for l in loads:
        by_status[l.status] += 1

    exc_q = db.query(models.Exception).filter(
        models.Exception.org_id == user.org_id
    )
    exc_q = deps.scope_exceptions(exc_q, db, user)
    exceptions = exc_q.all()
    by_type: dict[str, int] = defaultdict(int)
    by_severity: dict[str, int] = defaultdict(int)
    for e in exceptions:
        by_type[e.exception_type] += 1
        by_severity[e.severity] += 1

    per_day: dict[str, int] = defaultdict(int)
    for l in loads:
        if l.created_at:
            per_day[l.created_at.strftime("%Y-%m-%d")] += 1
    trend = [{"date": k, "loads": v} for k, v in sorted(per_day.items())]

    return {
        "load_count": len(loads),
        "loads_by_status": dict(by_status),
        "on_time_pct": _on_time_pct(db, user, loads),
        "exceptions_total": len(exceptions),
        "exceptions_by_type": dict(by_type),
        "exceptions_by_severity": dict(by_severity),
        "loads_per_day": trend,
    }


@router.get("/carrier", response_model=dict)
def carrier_analytics(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*ANALYTICS_ROLES)),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    carrier_id: str | None = Query(default=None),
):
    from .carriers import compute_carrier_score, get_score_weights

    weights = get_score_weights(db, user.org_id)
    loads = _filtered_loads(
        db, user, date_from=date_from, date_to=date_to, carrier_id=carrier_id,
    )
    by_carrier: dict[str, list] = defaultdict(list)
    for l in loads:
        if l.carrier_id:
            by_carrier[l.carrier_id].append(l)

    carriers = (
        db.query(models.Carrier)
        .filter(models.Carrier.org_id == user.org_id)
        .all()
    )
    if carrier_id:
        carriers = [c for c in carriers if c.id == carrier_id]
    rows = []
    for c in carriers:
        cloads = by_carrier.get(c.id, [])
        revenue = round(sum(l.carrier_rate or 0 for l in cloads), 2)
        score = compute_carrier_score(c, weights)["score"]
        rows.append({
            "carrier_id": c.id,
            "legal_name": c.legal_name,
            "load_count": len(cloads),
            "total_carrier_cost": revenue,
            "on_time_pct": c.on_time_pct,
            "acceptance_rate": c.acceptance_rate,
            "claims_count": c.claims_count,
            "score": score,
            "compliance_status": c.compliance_status,
        })
    rows.sort(key=lambda r: -r["score"])
    return {"carriers": rows, "total": len(rows)}


@router.get("/customer", response_model=dict)
def customer_analytics(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*ANALYTICS_ROLES)),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
):
    loads = _filtered_loads(
        db, user, date_from=date_from, date_to=date_to,
        customer_id=customer_id,
    )
    by_customer: dict[str, list] = defaultdict(list)
    for l in loads:
        by_customer[l.customer_id].append(l)

    customers = deps.scope_customers(
        db.query(models.Customer).filter(models.Customer.org_id == user.org_id), user
    ).all()
    if customer_id:
        customers = [c for c in customers if c.id == customer_id]
    rows = []
    for c in customers:
        cloads = by_customer.get(c.id, [])
        revenue, cost, margin, margin_pct = _money(cloads)
        inv_outstanding = round(
            sum((i.total or 0) - (i.amount_paid or 0)
                for i in db.query(models.Invoice).filter(
                    models.Invoice.org_id == user.org_id,
                    models.Invoice.customer_id == c.id,
                    models.Invoice.status.in_(("issued", "overdue")),
                ).all()), 2
        )
        rows.append({
            "customer_id": c.id,
            "name": c.name,
            "load_count": len(cloads),
            "revenue": revenue,
            "cost": cost,
            "margin": margin,
            "margin_pct": margin_pct,
            "outstanding": inv_outstanding,
        })
    rows.sort(key=lambda r: -r["revenue"])
    return {"customers": rows, "total": len(rows)}
