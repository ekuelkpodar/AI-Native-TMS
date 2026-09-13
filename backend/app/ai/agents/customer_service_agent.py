"""Customer service agent: shipment status summary + delay explanation +
drafted customer email (text via the mock provider, deterministic).
"""

import json

from fastapi import HTTPException, status

from ..providers import get_provider, utcnow
from ... import models

NAME = "customer_service_agent"

_DELIVERED = {"delivered", "pod_received", "invoiced", "paid"}


def run(db, org_id: str, load_id: str) -> dict:
    load = (
        db.query(models.Load)
        .filter(models.Load.id == load_id, models.Load.org_id == org_id)
        .first()
    )
    if load is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Load not found")

    customer = (
        db.query(models.Customer)
        .filter(models.Customer.id == load.customer_id,
                models.Customer.org_id == org_id)
        .first()
    )
    origin = load.origin or {}
    dest = load.destination or {}
    now = utcnow()

    delay_explanation = ""
    if load.delivery_datetime and now > load.delivery_datetime \
            and load.status not in _DELIVERED:
        days = (now - load.delivery_datetime).days
        delay_explanation = (
            f"Delivery appointment was {load.delivery_datetime.isoformat()} "
            f"({days} day(s) ago); current status is '{load.status}'.")
    elif load.pickup_datetime and now > load.pickup_datetime \
            and load.status in ("tendered", "available", "assigned",
                                "confirmed", "dispatched", "at_pickup"):
        days = (now - load.pickup_datetime).days
        delay_explanation = (
            f"Pickup appointment was {load.pickup_datetime.isoformat()} "
            f"({days} day(s) ago); load has not been picked up "
            f"(status '{load.status}').")

    last_event = (
        db.query(models.TrackingEvent)
        .filter(models.TrackingEvent.org_id == org_id,
                models.TrackingEvent.load_id == load.id)
        .order_by(models.TrackingEvent.recorded_at.desc())
        .first()
    )

    summary = (
        f"Load {load.load_number}: {origin.get('city', '')}, "
        f"{origin.get('state', '')} -> {dest.get('city', '')}, "
        f"{dest.get('state', '')}. Status '{load.status}'."
    )
    if last_event and last_event.city:
        summary += f" Last reported near {last_event.city}."

    facts = {
        "load_number": load.load_number,
        "customer_name": customer.name if customer else "valued customer",
        "status": load.status,
        "origin": f"{origin.get('city', '')}, {origin.get('state', '')}".strip(", "),
        "destination": f"{dest.get('city', '')}, {dest.get('state', '')}".strip(", "),
        "eta": load.delivery_datetime.isoformat() if load.delivery_datetime else None,
        "delay_explanation": delay_explanation,
    }
    provider = get_provider()
    draft = provider.complete("DRAFT:" + json.dumps(facts), db=db,
                              org_id=org_id, agent_name=NAME,
                              task_type="email_draft")["text"]

    return {
        "recommendation": {
            "load_id": load.id,
            "load_number": load.load_number,
            "summary": summary,
            "delay_explanation": delay_explanation,
            "email_draft": draft,
        },
        "reason": "Summary assembled from load, appointment, and latest "
                  "tracking data; email drafted from the same facts.",
        "expected_impact": "Proactive, consistent customer communication; "
                           "reduces inbound status inquiries.",
        "confidence": 0.9,
        "alternatives": ["Phone the customer instead of emailing."],
        "risks": ["Draft must be reviewed before sending — it is not sent automatically."],
        "approval_required": False,
    }
