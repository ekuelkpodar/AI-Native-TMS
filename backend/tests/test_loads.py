"""Loads: CRUD, duplicate, cancel, assign, invalid transition -> 422."""

import pytest

from .conftest import CAR_A, CUST_A, DRV_A, LOAD_A1, VEH_A, login


def _create_payload():
    return {
        "customer_id": CUST_A,
        "origin": {"city": "Atlanta", "state": "GA"},
        "destination": {"city": "Miami", "state": "FL"},
        "equipment_type": "dry_van",
        "customer_rate": 1800.0,
        "carrier_rate": 1500.0,
    }


def test_create_load(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/loads", headers=headers, json=_create_payload())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["load_number"].startswith("LD-")
    assert body["status"] == "draft"
    assert body["margin"] == 300.0
    assert body["margin_pct"] == pytest.approx(16.67, abs=0.01)


def test_duplicate_load(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/duplicate", headers=headers)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["load_number"] != "LD-10001"
    assert body["customer_id"] == CUST_A


def test_cancel_load(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/cancel", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["new_status"] == "cancelled"
    assert resp.json()["load"]["status"] == "cancelled"


def test_assign_carrier_and_driver(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/assign", headers=headers,
                       json={"carrier_id": CAR_A, "driver_id": DRV_A,
                             "vehicle_id": VEH_A})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "warnings" in body

    resp = client.get(f"/api/v1/loads/{LOAD_A1}", headers=headers)
    assert resp.json()["carrier_id"] == CAR_A
    assert resp.json()["driver_id"] == DRV_A


def test_invalid_status_transition_422(client):
    headers = login(client, "dispatcher@acme.test")
    # draft -> delivered is not a legal transition.
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/status", headers=headers,
                       json={"status": "delivered"})
    assert resp.status_code == 422
    assert "Invalid status transition" in resp.json()["detail"]


def test_valid_status_transition(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/status", headers=headers,
                       json={"status": "assigned"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["new_status"] == "assigned"


def test_update_and_delete_load(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/loads", headers=headers, json=_create_payload())
    load_id = resp.json()["id"]

    resp = client.put(f"/api/v1/loads/{load_id}", headers=headers,
                      json={"commodity": "produce"})
    assert resp.status_code == 200
    assert resp.json()["commodity"] == "produce"

    resp = client.delete(f"/api/v1/loads/{load_id}", headers=headers)
    assert resp.status_code == 200
