"""Automation rules engine (WHEN event / IF conditions / THEN actions).

Evaluates active automation_rules on each emitted event:
- conditions: JSON — a single {field, op, value}, {"all": [...]}, or {"any": [...]}.
  `field` is a dot-path into the event payload (e.g. "delay_minutes",
  "load.status"). Supported ops: eq, ne, gt, gte, lt, lte, in, not_in,
  contains, startswith.
- actions: list of {type, params}. Supported types: create_exception,
  create_notification, update_load_status, send_communication.
  Param values may reference the event payload with a "$payload.<dot.path>"
  prefix, e.g. {"load_id": "$payload.load_id"}.

Registered as an event-bus subscriber on import.
"""

from datetime import datetime, timezone

from . import audit, events, models, notifications

LOAD_TRANSITIONS = {
    "draft": {"quoted", "cancelled"},
    "quoted": {"tendered", "cancelled"},
    "tendered": {"available", "cancelled"},
    "available": {"assigned", "cancelled"},
    "assigned": {"confirmed", "dispatched", "cancelled"},
    "confirmed": {"dispatched"},
    "dispatched": {"at_pickup"},
    "at_pickup": {"picked_up"},
    "picked_up": {"in_transit"},
    "in_transit": {"at_delivery"},
    "at_delivery": {"delivered"},
    "delivered": {"pod_received"},
    "pod_received": {"invoiced"},
    "invoiced": {"paid"},
    "cancelled": set(),
    "paid": set(),
}

STATUS_EVENTS = {
    "assigned": "LOAD_ASSIGNED",
    "dispatched": "DRIVER_DISPATCHED",
    "picked_up": "PICKUP_COMPLETED",
    "in_transit": "SHIPMENT_IN_TRANSIT",
    "delivered": "DELIVERY_COMPLETED",
}


def _get_path(payload: dict, path: str):
    current = payload
    for part in str(path).split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _compare(op: str, actual, expected) -> bool:
    try:
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if op == "gt":
            return actual is not None and actual > expected
        if op == "gte":
            return actual is not None and actual >= expected
        if op == "lt":
            return actual is not None and actual < expected
        if op == "lte":
            return actual is not None and actual <= expected
        if op == "in":
            return actual in (expected or [])
        if op == "not_in":
            return actual not in (expected or [])
        if op == "contains":
            return expected in (actual or "")
        if op == "startswith":
            return str(actual or "").startswith(str(expected))
    except TypeError:
        return False
    raise ValueError(f"Unsupported condition op: {op}")


def conditions_match(conditions: dict | None, payload: dict) -> bool:
    if not conditions:
        return True
    if "all" in conditions:
        return all(conditions_match(c, payload) for c in conditions["all"])
    if "any" in conditions:
        return any(conditions_match(c, payload) for c in conditions["any"])
    actual = _get_path(payload, conditions.get("field", ""))
    return _compare(conditions.get("op", "eq"), actual, conditions.get("value"))


def _resolve(value, payload: dict):
    if isinstance(value, str) and value.startswith("$payload."):
        return _get_path(payload, value[len("$payload."):])
    if isinstance(value, dict):
        return {k: _resolve(v, payload) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, payload) for v in value]
    return value


def _resolve_params(params: dict, payload: dict) -> dict:
    return {k: _resolve(v, payload) for k, v in (params or {}).items()}


def run_action(db, action: dict, event: dict) -> None:
    """Execute one automation action. Runs inside the caller's transaction."""
    atype = action.get("type")
    params = _resolve_params(action.get("params", {}), event["payload"])
    org_id = event["org_id"]

    if atype == "create_exception":
        exc = models.Exception(
            org_id=org_id,
            load_id=params.get("load_id"),
            exception_type=params.get("exception_type", "other"),
            severity=params.get("severity", "medium"),
            title=params.get("title", "Automated exception"),
            description=params.get("description"),
            recommended_action=params.get("recommended_action"),
        )
        db.add(exc)
        db.flush()
        exc.history = (exc.history or []) + [
            {"at": datetime.now(timezone.utc).isoformat(),
             "event": "created by automation rule"}
        ]
        audit.log(
            db, org_id=org_id, actor_type="system", actor_name="automation",
            action="exceptions.create", entity_type="exceptions", entity_id=exc.id,
            after=audit.model_to_dict(exc),
        )
        events.emit(
            db, "EXCEPTION_CREATED", org_id, "exceptions", exc.id,
            {"exception_id": exc.id, "load_id": exc.load_id,
             "exception_type": exc.exception_type, "severity": exc.severity},
        )

    elif atype == "create_notification":
        notifications.create_notification(
            db, org_id=org_id,
            ntype=params.get("notification_type", params.get("type", "info")),
            title=params.get("title", "Automation notification"),
            body=params.get("body"),
            user_id=params.get("user_id"),
            entity_type=params.get("entity_type"),
            entity_id=params.get("entity_id") or event.get("entity_id"),
        )

    elif atype == "update_load_status":
        load_id = params.get("load_id") or event["payload"].get("load_id")
        new_status = params.get("status")
        if not load_id or not new_status:
            return
        load = (
            db.query(models.Load)
            .filter(models.Load.id == load_id, models.Load.org_id == org_id)
            .first()
        )
        if not load:
            return
        allowed = LOAD_TRANSITIONS.get(load.status, set())
        if new_status not in allowed:
            return  # invalid transition — skip rather than fail the event
        before = audit.model_to_dict(load)
        old_status = load.status
        load.status = new_status
        db.flush()
        audit.log(
            db, org_id=org_id, actor_type="system", actor_name="automation",
            action="loads.status", entity_type="loads", entity_id=load.id,
            before=before, after=audit.model_to_dict(load),
        )
        mapped = STATUS_EVENTS.get(new_status)
        if mapped:
            events.emit(
                db, mapped, org_id, "loads", load.id,
                {"load_id": load.id, "load_number": load.load_number,
                 "old_status": old_status, "new_status": new_status},
            )

    elif atype == "send_communication":
        comm = models.Communication(
            org_id=org_id,
            thread_type=params.get("thread_type", "load"),
            thread_id=params.get("thread_id") or event["payload"].get("load_id"),
            channel=params.get("channel", "in_app"),
            direction="out",
            sender=params.get("sender", "automation"),
            recipient=params.get("recipient"),
            subject=params.get("subject"),
            body=params.get("body", ""),
        )
        db.add(comm)
        db.flush()
        audit.log(
            db, org_id=org_id, actor_type="system", actor_name="automation",
            action="communications.create", entity_type="communications",
            entity_id=comm.id, after=audit.model_to_dict(comm),
        )

    else:
        raise ValueError(f"Unsupported automation action type: {atype}")


def handle_event(db, event: dict) -> None:
    rules = (
        db.query(models.AutomationRule)
        .filter(
            models.AutomationRule.org_id == event["org_id"],
            models.AutomationRule.event_name == event["event_name"],
            models.AutomationRule.is_active.is_(True),
        )
        .all()
    )
    for rule in rules:
        try:
            if not conditions_match(rule.conditions, event["payload"]):
                continue
            for action in rule.actions or []:
                run_action(db, action, event)
        except Exception:
            # A broken rule must never break the originating transaction's event.
            continue


# Register with the in-process bus on import.
events.subscribe(handle_event)
