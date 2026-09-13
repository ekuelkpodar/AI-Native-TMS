"""Rates: quote math — profit = revenue - cost; margin_pct."""

import pytest

from .conftest import login


def test_quote_from_rate_card(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post(
        "/api/v1/rates/quote", headers=headers,
        json={"origin": {"city": "Atlanta", "state": "GA"},
              "destination": {"city": "Dallas", "state": "TX"},
              "equipment_type": "dry_van"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["customer_rate"] == pytest.approx(2100.0)
    assert body["carrier_rate"] == pytest.approx(1750.0)
    assert body["basis"] == "rate_card"
    # profit = revenue - cost
    assert body["margin"] == pytest.approx(
        body["customer_rate"] - body["carrier_rate"])
    assert body["margin"] == pytest.approx(350.0)
    assert body["margin_pct"] == pytest.approx(350.0 / 2100.0 * 100, abs=0.01)


def test_quote_estimated_from_distance(client):
    headers = login(client, "broker@acme.test")
    resp = client.post(
        "/api/v1/rates/quote", headers=headers,
        json={"origin": {"city": "Nowhere", "state": "ZZ"},
              "destination": {"city": "Elsewhere", "state": "YY"},
              "equipment_type": "dry_van",
              "distance_miles": 1000})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["basis"] == "estimated"
    assert body["margin"] == pytest.approx(
        body["customer_rate"] - body["carrier_rate"])
    assert body["margin"] > 0


def test_quote_no_rate_no_distance_422(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post(
        "/api/v1/rates/quote", headers=headers,
        json={"origin": {"city": "Nowhere", "state": "ZZ"},
              "destination": {"city": "Elsewhere", "state": "YY"}})
    assert resp.status_code == 422
