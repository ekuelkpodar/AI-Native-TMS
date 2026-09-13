"""Carrier matching: deterministic score math + feature-flag weight override."""

import pytest

from .conftest import CAR_A, CAR_B, LOAD_A1, login

# Hand-computed from the fixture stats and the spec formula
# 0.30*rate_competitiveness + 0.25*on_time + 0.15*acceptance
#   + 0.15*lane_history + 0.10*compliance + 0.05*equipment_match
#
# Fast Freight LLC: 0.30*100 + 0.25*95 + 0.15*90 + 0.15*88 + 0.10*100 + 0.05*100
EXPECTED_A = 30.0 + 23.75 + 13.5 + 13.2 + 10.0 + 5.0  # = 95.45
# Slow Haul Inc: rate_competitiveness = 100 - 3*8 - 2*4 = 68
#   0.30*68 + 0.25*70 + 0.15*60 + 0.15*60 + 0.10*60 + 0.05*100
EXPECTED_B = 20.4 + 17.5 + 9.0 + 9.0 + 6.0 + 5.0  # = 66.9


def test_carrier_score_deterministic_math(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.get(f"/api/v1/carriers/{CAR_A}/score", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["score"] == pytest.approx(EXPECTED_A, abs=0.01)
    factors = {f["name"]: f for f in body["factors"]}
    assert factors["on_time"]["value"] == pytest.approx(95.0)
    assert factors["on_time"]["weight"] == pytest.approx(0.25)
    assert factors["on_time"]["contribution"] == pytest.approx(23.75)
    assert "explanation" in body


def test_carrier_score_weights_override_via_flag(client, db):
    from app import models

    db.add(models.FeatureFlag(
        org_id="org-a-fixture", key="carrier_score_weights", enabled=True,
        config={"weights": {"rate_competitiveness": 0.0, "on_time": 1.0,
                            "acceptance": 0.0, "lane_history": 0.0,
                            "compliance": 0.0, "equipment_match": 0.0}}))
    db.commit()

    headers = login(client, "dispatcher@acme.test")
    resp = client.get(f"/api/v1/carriers/{CAR_A}/score", headers=headers)
    assert resp.status_code == 200
    # weights normalize to on_time=1.0 -> score == on_time value
    assert resp.json()["score"] == pytest.approx(95.0, abs=0.01)


def test_ai_match_carriers_ranking(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/match-carriers",
                       headers=headers,
                       json={"load_id": LOAD_A1, "top_n": 5})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    rankings = body["rankings"]
    assert len(rankings) == 2
    assert rankings[0]["carrier_name"] == "Fast Freight LLC"
    assert rankings[0]["score"] == pytest.approx(EXPECTED_A, abs=0.01)
    assert rankings[1]["carrier_name"] == "Slow Haul Inc"
    assert rankings[1]["score"] == pytest.approx(EXPECTED_B, abs=0.01)
    # per-factor explanations present
    assert all("explanation" in f for f in rankings[0]["factors"])
    assert body["approval_required"] is False


def test_match_carriers_unknown_load_404(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/match-carriers",
                       headers=headers, json={"load_id": "nope"})
    assert resp.status_code == 404
