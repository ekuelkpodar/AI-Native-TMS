"""Exception agent: scan active loads for late pickup/delivery, missing POD,
missing documents, and margin anomalies. Creates exceptions with dedupe
(no recreation of an already-open same-type exception for the same load).
"""

from datetime import timedelta

from ..providers import utcnow
from ... import events, models

NAME = "exception_agent"

_ACTIVE = {"tendered", "available", "assigned", "confirmed", "dispatched",
           "at_pickup", "picked_up", "in_transit", "at_delivery"}
_PRE_PICKUP = {"tendered", "available", "assigned", "confirmed",
               "dispatched", "at_pickup"}
_POD_MISSING_HOURS = 24
_MARGIN_FLOOR_PCT = 10.0


def _open_exists(db, org_id: str, load_id: str, exception_type: str) -> bool:
    return (
        db.query(models.Exception)
        .filter(models.Exception.org_id == org_id,
                models.Exception.load_id == load_id,
                models.Exception.exception_type == exception_type,
                models.Exception.status.in_(("open", "acknowledged")))
        .first()
    ) is not None


def _create(db, org_id: str, load: models.Load, exception_type: str,
            severity: str, title: str, description: str,
            recommended_action: str | None = None) -> dict | None:
    if _open_exists(db, org_id, load.id, exception_type):
        return None
    exc = models.Exception(
        org_id=org_id, load_id=load.id, exception_type=exception_type,
        severity=severity, title=title, description=description,
        detected_at=utcnow(), recommended_action=recommended_action,
        history=[{"at": utcnow().isoformat(), "by": NAME,
                  "note": "auto-detected by exception scan"}],
    )
    db.add(exc)
    db.flush()
    events.emit(db, "EXCEPTION_CREATED", org_id, "exceptions", exc.id,
                {"exception_id": exc.id, "load_id": load.id,
                 "exception_type": exception_type, "severity": severity})
    return {"exception_id": exc.id, "load_id": load.id,
            "load_number": load.load_number, "exception_type": exception_type,
            "severity": severity, "title": title}


def _has_doc(db, org_id: str, load_id: str, doc_type: str) -> bool:
    return (
        db.query(models.Document)
        .filter(models.Document.org_id == org_id,
                models.Document.entity_type == "loads",
                models.Document.entity_id == load_id,
                models.Document.doc_type == doc_type)
        .first()
    ) is not None


def run(db, org_id: str) -> dict:
    now = utcnow()
    created: list[dict] = []

    active = (
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.status.in_(_ACTIVE),
                models.Load.is_archived.is_(False))
        .all()
    )
    for load in active:
        if load.pickup_datetime and now > load.pickup_datetime \
                and load.status in _PRE_PICKUP:
            row = _create(db, org_id, load, "late_pickup", "high",
                          f"Late pickup on {load.load_number}",
                          f"Pickup appointment {load.pickup_datetime.isoformat()} "
                          f"passed; status is '{load.status}'.",
                          "Contact the driver/carrier for an updated pickup ETA.")
            if row:
                created.append(row)
        if load.delivery_datetime and now > load.delivery_datetime:
            row = _create(db, org_id, load, "late_delivery", "high",
                          f"Late delivery on {load.load_number}",
                          f"Delivery appointment {load.delivery_datetime.isoformat()} "
                          f"passed; status is '{load.status}'.",
                          "Notify the customer and re-plan the delivery appointment.")
            if row:
                created.append(row)
        if load.margin_pct is not None and load.margin_pct < _MARGIN_FLOOR_PCT:
            row = _create(db, org_id, load, "margin_anomaly", "medium",
                          f"Low margin on {load.load_number}",
                          f"Margin {load.margin_pct:.1f}% is below the "
                          f"{_MARGIN_FLOOR_PCT:.0f}% floor.",
                          "Review carrier rate vs customer rate.")
            if row:
                created.append(row)

    delivered = (
        db.query(models.Load)
        .filter(models.Load.org_id == org_id,
                models.Load.status.in_(("delivered", "pod_received")),
                models.Load.is_archived.is_(False))
        .all()
    )
    for load in delivered:
        if not _has_doc(db, org_id, load.id, "bol"):
            row = _create(db, org_id, load, "document_missing", "medium",
                          f"Missing BOL on {load.load_number}",
                          "Load is delivered but no bill-of-lading document is on file.",
                          "Request the BOL from the driver/carrier.")
            if row:
                created.append(row)
        updated = load.updated_at or load.created_at
        if load.status == "delivered" and updated \
                and now - updated > timedelta(hours=_POD_MISSING_HOURS) \
                and not _has_doc(db, org_id, load.id, "pod"):
            row = _create(db, org_id, load, "pod_missing", "medium",
                          f"Missing POD on {load.load_number}",
                          f"Delivered over {_POD_MISSING_HOURS}h ago with no "
                          f"proof-of-delivery document.",
                          "Request the POD from the driver; invoicing is blocked until then.")
            if row:
                created.append(row)

    db.flush()
    return {
        "recommendation": {
            "created": created,
            "created_count": len(created),
            "loads_scanned": len(active) + len(delivered),
        },
        "reason": "Scanned active and recently-delivered loads against "
                  "appointment times, document presence, and margin floor; "
                  "existing open exceptions were not recreated.",
        "expected_impact": f"{len(created)} new exception(s) surfaced for "
                           "dispatcher follow-up.",
        "confidence": 0.9,
        "alternatives": [],
        "risks": [
            "Detection is only as good as appointment and document data quality.",
        ],
        "approval_required": False,
    }
