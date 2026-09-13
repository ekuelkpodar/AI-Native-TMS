"""Exceptions: AI scan creates exceptions (with dedupe); ack/resolve flow."""

from app import models

from .conftest import LOAD_A2, LOAD_A3, login


def test_scan_creates_expected_exceptions(client, db):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/exceptions/scan", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["created_count"] == 3

    created = {(c["load_id"], c["exception_type"]) for c in body["created"]}
    # LD-10002: in_transit, delivery appointment yesterday -> late_delivery
    assert (LOAD_A2, "late_delivery") in created
    # LD-10003: delivered 2 days ago, no POD/BOL docs -> pod_missing + document_missing
    assert (LOAD_A3, "pod_missing") in created
    assert (LOAD_A3, "document_missing") in created

    events = (db.query(models.EventsLog)
              .filter(models.EventsLog.event_name == "EXCEPTION_CREATED").all())
    assert len(events) == 3


def test_scan_dedupes_open_exceptions(client):
    headers = login(client, "dispatcher@acme.test")
    first = client.post("/api/v1/ai/exceptions/scan", headers=headers)
    assert first.json()["created_count"] == 3
    second = client.post("/api/v1/ai/exceptions/scan", headers=headers)
    assert second.json()["created_count"] == 0


def test_acknowledge_and_resolve_flow(client, db):
    headers = login(client, "dispatcher@acme.test")
    client.post("/api/v1/ai/exceptions/scan", headers=headers)

    resp = client.get("/api/v1/exceptions", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 3
    exc_id = items[0]["id"]
    assert items[0]["status"] == "open"

    resp = client.post(f"/api/v1/exceptions/{exc_id}/acknowledge",
                       headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "acknowledged"

    resp = client.post(f"/api/v1/exceptions/{exc_id}/resolve", headers=headers,
                       json={"resolution": "customer notified, rebooked"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "resolved"
    assert body["resolution"] == "customer notified, rebooked"
    assert body["resolved_at"] is not None


def test_scan_records_ai_action_and_audit(client, db):
    headers = login(client, "dispatcher@acme.test")
    client.post("/api/v1/ai/exceptions/scan", headers=headers)

    actions = (db.query(models.AIAction)
               .filter(models.AIAction.action_type == "scan_exceptions").all())
    assert len(actions) == 1
    assert actions[0].decision == "auto"

    audit_rows = (db.query(models.AuditLog)
                  .filter(models.AuditLog.action == "ai.scan_exceptions").all())
    assert len(audit_rows) == 1
