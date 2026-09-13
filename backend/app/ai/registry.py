"""Agent Registry + Tool Registry.

The Agent Registry is code-defined (source of truth); ai.approvals syncs it
into the ai_agents table per org. The Tool Registry maps tool names to
handlers; every tool execution verifies the invoking user's scopes first.
"""

from fastapi import HTTPException, status

from .. import audit, deps, events, models
from . import geo
from .providers import utcnow

# ---------------------------------------------------------------------------
# Role -> scopes (ARCHITECTURE.md section 3.2; "admin" implies everything)
# ---------------------------------------------------------------------------

ROLE_SCOPES: dict[str, set[str]] = {
    "broker": {
        "loads:*", "shipments:*", "customers:*", "carriers:*", "rates:*",
        "dispatch:write", "documents:*", "communications:*",
        "exceptions:read", "ai:use", "invoices:read",
    },
    "dispatcher": {
        "loads:*", "shipments:*", "drivers:*", "fleet:*", "dispatch:write",
        "tracking:*", "exceptions:*", "communications:*", "ai:use",
    },
    "carrier": {"loads:read", "loads:write", "documents:write", "communications:*"},
    "driver": {"assignments:read", "loads:write", "documents:write"},
    "shipper": {"shipments:*", "loads:read", "invoices:read", "documents:read"},
    "finance": {"invoices:*", "payments:*", "rates:read", "analytics:read"},
    "ops_manager": {"analytics:read", "exceptions:*", "policies:read",
                    "lanes:read", "ai:use"},
}


def user_scopes(user: models.User) -> set[str]:
    if user.role == "admin":
        return {"*"}
    return set(ROLE_SCOPES.get(user.role, set()))


def scope_allows(have: set[str], required: str) -> bool:
    if "*" in have or required in have:
        return True
    prefix = required.split(":")[0] + ":"
    return any(s == prefix + "*" and required.startswith(prefix) for s in have)


def check_scopes(user: models.User, required_scopes: list[str]) -> None:
    have = user_scopes(user)
    missing = [s for s in required_scopes if not scope_allows(have, s)]
    if missing:
        raise ToolPermissionDenied(
            f"User '{user.email}' (role {user.role}) lacks scopes: "
            f"{', '.join(missing)}"
        )


# ---------------------------------------------------------------------------
# Agent Registry (code-defined)
# ---------------------------------------------------------------------------

AGENTS: dict[str, dict] = {
    "dispatch_agent": {
        "name": "dispatch_agent", "version": "1.0", "model": "mock-1",
        "tools": ["search_loads", "get_load", "assign_driver",
                  "assign_carrier", "send_notification"],
        "permissions": ["loads:read", "loads:write", "dispatch:write",
                        "communications:write"],
        "status": "active", "owner": "operations",
        "risk_level": "medium", "autonomy_level": 2,
        "config": {"max_assignments_per_run": 25},
        "description": "Matches unassigned loads to available drivers.",
    },
    "routing_agent": {
        "name": "routing_agent", "version": "1.0", "model": "mock-1",
        "tools": ["get_load", "optimize_route", "query_analytics"],
        "permissions": ["loads:read", "loads:write", "analytics:read"],
        "status": "active", "owner": "operations",
        "risk_level": "low", "autonomy_level": 3,
        "config": {},
        "description": "Reorders stops to minimize miles and cost.",
    },
    "carrier_agent": {
        "name": "carrier_agent", "version": "1.0", "model": "mock-1",
        "tools": ["search_carriers", "match_carriers", "get_load",
                  "assign_carrier"],
        "permissions": ["carriers:read", "loads:read", "dispatch:write"],
        "status": "active", "owner": "operations",
        "risk_level": "medium", "autonomy_level": 2,
        "config": {},
        "description": "Ranks carriers for a load with explanations.",
    },
    "customer_service_agent": {
        "name": "customer_service_agent", "version": "1.0", "model": "mock-1",
        "tools": ["get_load", "search_loads", "draft_communication",
                  "query_analytics"],
        "permissions": ["loads:read", "communications:write", "analytics:read"],
        "status": "active", "owner": "customer-success",
        "risk_level": "low", "autonomy_level": 1,
        "config": {},
        "description": "Shipment status summaries and customer drafts.",
    },
    "exception_agent": {
        "name": "exception_agent", "version": "1.0", "model": "mock-1",
        "tools": ["search_loads", "get_load", "create_exception",
                  "send_notification"],
        "permissions": ["loads:read", "exceptions:write", "communications:write"],
        "status": "active", "owner": "operations",
        "risk_level": "low", "autonomy_level": 3,
        "config": {"pod_missing_hours": 24, "margin_floor_pct": 10.0},
        "description": "Detects late pickups/deliveries, missing docs, margin anomalies.",
    },
    "pricing_agent": {
        "name": "pricing_agent", "version": "1.0", "model": "mock-1",
        "tools": ["query_analytics", "draft_communication"],
        "permissions": ["analytics:read", "rates:read", "communications:write"],
        "status": "active", "owner": "finance",
        "risk_level": "low", "autonomy_level": 1,
        "config": {"target_margin_pct": 15.0},
        "description": "Recommends customer rates from lane history.",
    },
    "finance_agent": {
        "name": "finance_agent", "version": "1.0", "model": "mock-1",
        "tools": ["generate_invoice", "query_analytics", "get_load"],
        "permissions": ["invoices:write", "analytics:read", "loads:read"],
        "status": "active", "owner": "finance",
        "risk_level": "medium", "autonomy_level": 2,
        "config": {},
        "description": "Invoice hygiene checks and reconciliation suggestions.",
    },
    "compliance_agent": {
        "name": "compliance_agent", "version": "1.0", "model": "mock-1",
        "tools": ["search_carriers", "get_load", "query_analytics"],
        "permissions": ["carriers:read", "loads:read", "analytics:read"],
        "status": "active", "owner": "compliance",
        "risk_level": "medium", "autonomy_level": 2,
        "config": {"expiring_within_days": 30},
        "description": "Flags expired/expiring carrier insurance and authority.",
    },
    "ops_analyst_agent": {
        "name": "ops_analyst_agent", "version": "1.0", "model": "mock-1",
        "tools": ["query_analytics", "search_loads"],
        "permissions": ["analytics:read", "loads:read"],
        "status": "active", "owner": "operations",
        "risk_level": "low", "autonomy_level": 1,
        "config": {},
        "description": "KPI bottleneck analysis across exceptions, lanes, carriers.",
    },
}


# ---------------------------------------------------------------------------
# Tool errors
# ---------------------------------------------------------------------------

class ToolNotFound(Exception):
    pass


class ToolPermissionDenied(Exception):
    pass


# ---------------------------------------------------------------------------
# Internal helpers shared by tool handlers
# ---------------------------------------------------------------------------

def _org_load(db, user: models.User, load_id: str) -> models.Load:
    load = (
        db.query(models.Load)
        .filter(models.Load.id == load_id,
                models.Load.org_id == user.org_id)
        .first()
    )
    if not load:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Load not found")
    return load


def _next_load_number(db, org_id: str) -> str:
    max_n = 10000
    for (ln,) in db.query(models.Load.load_number).filter(
            models.Load.org_id == org_id).all():
        try:
            max_n = max(max_n, int(str(ln).split("-")[-1]))
        except ValueError:
            continue
    return f"LD-{max_n + 1}"


def _next_invoice_number(db, org_id: str) -> str:
    max_n = 10000
    for (num,) in db.query(models.Invoice.invoice_number).filter(
            models.Invoice.org_id == org_id).all():
        try:
            max_n = max(max_n, int(str(num).split("-")[-1]))
        except ValueError:
            continue
    return f"INV-{max_n + 1}"


def _load_summary(load: models.Load) -> dict:
    origin = load.origin or {}
    dest = load.destination or {}
    return {
        "load_id": load.id,
        "load_number": load.load_number,
        "status": load.status,
        "customer_id": load.customer_id,
        "carrier_id": load.carrier_id,
        "driver_id": load.driver_id,
        "origin": f"{origin.get('city', '')}, {origin.get('state', '')}".strip(", "),
        "destination": f"{dest.get('city', '')}, {dest.get('state', '')}".strip(", "),
        "pickup_datetime": load.pickup_datetime.isoformat() if load.pickup_datetime else None,
        "delivery_datetime": load.delivery_datetime.isoformat() if load.delivery_datetime else None,
        "customer_rate": load.customer_rate,
        "carrier_rate": load.carrier_rate,
        "margin": load.margin,
        "margin_pct": round(load.margin_pct, 2) if load.margin_pct is not None else None,
    }


# ---------------------------------------------------------------------------
# Tool handlers: handler(db, user, **params) -> dict. All org-scoped.
# ---------------------------------------------------------------------------

def _t_search_loads(db, user, status: str | None = None,
                     unassigned: bool = False, limit: int = 50, **kw) -> dict:
    q = db.query(models.Load).filter(models.Load.org_id == user.org_id)
    q = deps.scope_loads(q, user)
    if status:
        q = q.filter(models.Load.status == status)
    if unassigned:
        q = q.filter(models.Load.driver_id.is_(None))
    q = q.filter(models.Load.is_archived.is_(False))
    loads = q.order_by(models.Load.created_at.desc()).limit(min(limit, 200)).all()
    return {"loads": [_load_summary(l) for l in loads], "count": len(loads)}


def _t_get_load(db, user, load_id: str, **kw) -> dict:
    return {"load": _load_summary(_org_load(db, user, load_id))}


def _t_create_load(db, user, customer_id: str, origin: dict | None = None,
                   destination: dict | None = None,
                   equipment_type: str = "dry_van", **kw) -> dict:
    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == customer_id,
                models.Customer.org_id == user.org_id)
        .first()
    )
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Customer not found")
    load = models.Load(
        org_id=user.org_id,
        load_number=_next_load_number(db, user.org_id),
        customer_id=customer_id,
        origin=origin or {},
        destination=destination or {},
        equipment_type=equipment_type,
        status="draft",
    )
    # allowlist of extra creatable fields
    for field in ("reference_number", "pickup_datetime", "delivery_datetime",
                  "commodity", "weight_lbs", "pallets", "pieces",
                  "customer_rate", "carrier_rate", "distance_miles",
                  "hazmat", "notes"):
        if field in kw and kw[field] is not None:
            setattr(load, field, kw[field])
    db.add(load)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="user", actor_id=user.id,
              actor_name=user.full_name, action="loads.create",
              entity_type="loads", entity_id=load.id,
              after=audit.model_to_dict(load))
    events.emit(db, "LOAD_CREATED", user.org_id, "loads", load.id,
                {"load_id": load.id, "load_number": load.load_number})
    return {"load_id": load.id, "load_number": load.load_number}


def _t_update_load_status(db, user, load_id: str, status: str, **kw) -> dict:
    from ..routers.loads import _set_status  # local import: router layer

    load = _org_load(db, user, load_id)
    return _set_status(db, load, status, user, actor_type="agent")


def _t_search_carriers(db, user, equipment_type: str | None = None,
                       state: str | None = None, limit: int = 50, **kw) -> dict:
    q = db.query(models.Carrier).filter(
        models.Carrier.org_id == user.org_id,
        models.Carrier.is_active.is_(True),
    )
    q = deps.scope_carriers(q, user)
    carriers = q.order_by(models.Carrier.legal_name).limit(min(limit, 200)).all()
    out = []
    for c in carriers:
        if equipment_type and c.equipment_types and \
                equipment_type not in c.equipment_types:
            continue
        if state and c.service_areas and state not in c.service_areas:
            continue
        out.append({
            "carrier_id": c.id, "legal_name": c.legal_name,
            "mc_number": c.mc_number,
            "compliance_status": c.compliance_status,
            "on_time_pct": c.on_time_pct,
        })
    return {"carriers": out, "count": len(out)}


def _t_match_carriers(db, user, load_id: str, top_n: int = 5, **kw) -> dict:
    from .agents import carrier_agent  # local import: avoid cycle

    return carrier_agent.run(db, user.org_id, load_id=load_id, top_n=top_n)


def _t_assign_carrier(db, user, load_id: str, carrier_id: str, **kw) -> dict:
    from ..routers.loads import _do_assign, _set_status

    load = _org_load(db, user, load_id)
    before = audit.model_to_dict(load)
    warnings = _do_assign(db, load, carrier_id, None, None, user)
    if load.status != "assigned":
        _set_status(db, load, "assigned", user, emit_event=False)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=user.id,
              actor_name=user.full_name, action="loads.assign_carrier",
              entity_type="loads", entity_id=load.id,
              before=before, after=audit.model_to_dict(load))
    events.emit(db, "LOAD_ASSIGNED", user.org_id, "loads", load.id,
                {"load_id": load.id, "carrier_id": carrier_id,
                 "warnings": warnings})
    return {"load_id": load.id, "carrier_id": carrier_id, "warnings": warnings}


def _t_assign_driver(db, user, load_id: str, driver_id: str,
                     vehicle_id: str | None = None, **kw) -> dict:
    from ..routers.loads import _do_assign, _set_status

    load = _org_load(db, user, load_id)
    before = audit.model_to_dict(load)
    warnings = _do_assign(db, load, None, driver_id, vehicle_id, user)
    if load.status != "assigned":
        _set_status(db, load, "assigned", user, emit_event=False)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=user.id,
              actor_name=user.full_name, action="loads.assign_driver",
              entity_type="loads", entity_id=load.id,
              before=before, after=audit.model_to_dict(load))
    events.emit(db, "DRIVER_DISPATCHED", user.org_id, "loads", load.id,
                {"load_id": load.id, "driver_id": driver_id,
                 "vehicle_id": vehicle_id, "warnings": warnings})
    return {"load_id": load.id, "driver_id": driver_id,
            "vehicle_id": vehicle_id, "warnings": warnings}


def _t_optimize_route(db, user, load_id: str, **kw) -> dict:
    from .agents import routing_agent  # local import: avoid cycle

    load = _org_load(db, user, load_id)
    rec = routing_agent.run(db, user.org_id, load_id=load_id)
    body = rec["recommendation"]
    route = models.Route(
        load_id=load.id,
        waypoints=body["optimized"]["waypoints"],
        total_miles=body["optimized"]["miles"],
        total_minutes=body["optimized"]["minutes"],
        optimized=True,
    )
    db.add(route)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=user.id,
              actor_name=user.full_name, action="routes.optimize",
              entity_type="loads", entity_id=load.id,
              after={"route_id": route.id,
                     "optimized_miles": body["optimized"]["miles"]})
    return {"route_id": route.id, "load_id": load.id,
            "current": body["current"], "optimized": body["optimized"],
            "savings": body["savings"]}


def _t_create_exception(db, user, load_id: str, exception_type: str,
                        title: str, description: str | None = None,
                        severity: str = "medium", **kw) -> dict:
    load = _org_load(db, user, load_id)
    existing = (
        db.query(models.Exception)
        .filter(models.Exception.org_id == user.org_id,
                models.Exception.load_id == load.id,
                models.Exception.exception_type == exception_type,
                models.Exception.status.in_(("open", "acknowledged")))
        .first()
    )
    if existing:
        return {"exception_id": existing.id, "deduplicated": True,
                "load_number": load.load_number}
    exc = models.Exception(
        org_id=user.org_id, load_id=load.id, exception_type=exception_type,
        severity=severity, title=title, description=description,
        detected_at=utcnow(),
        history=[{"at": utcnow().isoformat(), "by": "exception_agent",
                  "note": "auto-detected"}],
    )
    db.add(exc)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=user.id,
              actor_name=user.full_name, action="exceptions.create",
              entity_type="exceptions", entity_id=exc.id,
              after=audit.model_to_dict(exc))
    events.emit(db, "EXCEPTION_CREATED", user.org_id, "exceptions", exc.id,
                {"exception_id": exc.id, "load_id": load.id,
                 "exception_type": exception_type, "severity": severity})
    return {"exception_id": exc.id, "deduplicated": False,
            "load_number": load.load_number}


def _t_send_notification(db, user, title: str, body: str | None = None,
                         type: str = "info", user_id: str | None = None,
                         **kw) -> dict:
    note = models.Notification(
        org_id=user.org_id, user_id=user_id, type=type, title=title, body=body,
    )
    db.add(note)
    db.flush()
    return {"notification_id": note.id}


def _t_generate_invoice(db, user, load_id: str, **kw) -> dict:
    load = _org_load(db, user, load_id)
    if load.customer_rate is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Load has no customer_rate; cannot invoice.",
        )
    amount = round(float(load.customer_rate), 2)
    invoice = models.Invoice(
        org_id=user.org_id,
        invoice_number=_next_invoice_number(db, user.org_id),
        customer_id=load.customer_id,
        load_id=load.id,
        line_items=[{"description": f"Freight charges - load "
                                     f"{load.load_number}",
                     "quantity": 1, "unit_price": amount, "amount": amount}],
        subtotal=amount, tax=0.0, total=amount, status="draft",
    )
    db.add(invoice)
    db.flush()
    audit.log(db, org_id=user.org_id, actor_type="agent", actor_id=user.id,
              actor_name=user.full_name, action="invoices.create",
              entity_type="invoices", entity_id=invoice.id,
              after=audit.model_to_dict(invoice))
    events.emit(db, "INVOICE_CREATED", user.org_id, "invoices", invoice.id,
                {"invoice_id": invoice.id, "load_id": load.id, "total": amount})
    return {"invoice_id": invoice.id, "invoice_number": invoice.invoice_number,
            "total": amount}


def _t_query_analytics(db, user, metric: str = "overview", **kw) -> dict:
    loads = (
        db.query(models.Load)
        .filter(models.Load.org_id == user.org_id,
                models.Load.is_archived.is_(False))
        .all()
    )
    active_statuses = {"tendered", "available", "assigned", "confirmed",
                       "dispatched", "at_pickup", "picked_up", "in_transit",
                       "at_delivery"}
    revenue = sum(l.customer_rate or 0 for l in loads)
    cost = sum(l.carrier_rate or 0 for l in loads)
    margins = [l.margin_pct for l in loads if l.margin_pct is not None]
    open_exc = (
        db.query(models.Exception)
        .filter(models.Exception.org_id == user.org_id,
                models.Exception.status.in_(("open", "acknowledged")))
        .count()
    )
    return {
        "metric": metric,
        "total_loads": len(loads),
        "active_loads": sum(1 for l in loads if l.status in active_statuses),
        "total_revenue": round(revenue, 2),
        "total_cost": round(cost, 2),
        "total_margin": round(revenue - cost, 2),
        "avg_margin_pct": round(sum(margins) / len(margins), 2) if margins else None,
        "open_exceptions": open_exc,
    }


def _t_draft_communication(db, user, thread_type: str, thread_id: str,
                           body: str, channel: str = "email",
                           subject: str | None = None, recipient: str | None = None,
                           **kw) -> dict:
    comm = models.Communication(
        org_id=user.org_id, thread_type=thread_type, thread_id=thread_id,
        channel=channel, direction="out", sender=user.email,
        recipient=recipient, subject=subject, body=body, created_by=user.id,
    )
    db.add(comm)
    db.flush()
    return {"communication_id": comm.id, "channel": channel}


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, dict] = {
    "search_loads": {
        "name": "search_loads",
        "description": "Search loads in the org (optionally by status / unassigned).",
        "required_scopes": ["loads:read"],
        "handler": _t_search_loads,
    },
    "get_load": {
        "name": "get_load",
        "description": "Get a single load summary by id.",
        "required_scopes": ["loads:read"],
        "handler": _t_get_load,
    },
    "create_load": {
        "name": "create_load",
        "description": "Create a draft load for a customer.",
        "required_scopes": ["loads:write"],
        "handler": _t_create_load,
    },
    "update_load_status": {
        "name": "update_load_status",
        "description": "Transition a load's status (transition map enforced).",
        "required_scopes": ["loads:write"],
        "handler": _t_update_load_status,
    },
    "search_carriers": {
        "name": "search_carriers",
        "description": "Search active carriers, filterable by equipment/state.",
        "required_scopes": ["carriers:read"],
        "handler": _t_search_carriers,
    },
    "match_carriers": {
        "name": "match_carriers",
        "description": "Rank carriers for a load (read-only scoring).",
        "required_scopes": ["carriers:read"],
        "handler": _t_match_carriers,
    },
    "assign_carrier": {
        "name": "assign_carrier",
        "description": "Assign a carrier to a load.",
        "required_scopes": ["dispatch:write"],
        "handler": _t_assign_carrier,
    },
    "assign_driver": {
        "name": "assign_driver",
        "description": "Assign a driver (and optional vehicle) to a load.",
        "required_scopes": ["dispatch:write"],
        "handler": _t_assign_driver,
    },
    "optimize_route": {
        "name": "optimize_route",
        "description": "Reorder a load's stops (nearest-neighbor) and persist the route.",
        "required_scopes": ["loads:write"],
        "handler": _t_optimize_route,
    },
    "create_exception": {
        "name": "create_exception",
        "description": "Create an exception for a load (deduped).",
        "required_scopes": ["exceptions:write"],
        "handler": _t_create_exception,
    },
    "send_notification": {
        "name": "send_notification",
        "description": "Create an in-app notification.",
        "required_scopes": ["communications:write"],
        "handler": _t_send_notification,
    },
    "generate_invoice": {
        "name": "generate_invoice",
        "description": "Generate a draft invoice from a load's customer rate.",
        "required_scopes": ["invoices:write"],
        "handler": _t_generate_invoice,
    },
    "query_analytics": {
        "name": "query_analytics",
        "description": "Read-only KPI aggregates (revenue, margin, exceptions).",
        "required_scopes": ["analytics:read"],
        "handler": _t_query_analytics,
    },
    "draft_communication": {
        "name": "draft_communication",
        "description": "Draft an outbound communication (stored, not sent).",
        "required_scopes": ["communications:write"],
        "handler": _t_draft_communication,
    },
}

#: Action types that do not mutate state (used by the policy engine).
READ_ACTIONS = {"search_loads", "get_load", "search_carriers",
                "match_carriers", "query_analytics"}


def execute_tool(db, user: models.User, tool_name: str, **params) -> dict:
    """Execute a registered tool after verifying the user's scopes.

    Raises ToolNotFound / ToolPermissionDenied; handler errors propagate.
    """
    tool = TOOLS.get(tool_name)
    if tool is None:
        raise ToolNotFound(f"Unknown tool: {tool_name}")
    check_scopes(user, tool["required_scopes"])
    return tool["handler"](db, user, **params)


def get_agent_def(agent_name: str) -> dict | None:
    return AGENTS.get(agent_name)
