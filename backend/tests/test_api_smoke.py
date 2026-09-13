"""API smoke: analytics overview keys, dispatch board shape, lanes,
ai/command structured response, ai/usage budget check."""

from .conftest import login


def test_analytics_overview_keys(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.get("/api/v1/analytics/overview", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("total_loads", "active_loads", "total_revenue", "total_cost",
                "margin", "margin_pct", "open_exceptions", "loads_by_status"):
        assert key in body, f"missing key: {key}"
    assert body["total_loads"] >= 3


def test_dispatch_board_shape(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.get("/api/v1/dispatch/board", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("unassigned_loads", "available_drivers", "available_vehicles",
                "conflicts"):
        assert key in body, f"missing key: {key}"
    assert any(l["load_number"] == "LD-10001"
               for l in body["unassigned_loads"])
    assert any(d["full_name"] == "John Driver"
               for d in body["available_drivers"])


def test_lanes_endpoint(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.get("/api/v1/lanes", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    assert body[0]["load_count"] >= 1


def test_ai_command_delayed_loads_structured(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/command", headers=headers,
                       json={"message": "show me delayed loads"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("answer", "data", "recommendations", "actions",
                "confidence", "approval_required"):
        assert key in body, f"missing key: {key}"
    assert body["data"]["count"] >= 1
    assert any(l["load_number"] == "LD-10002"
               for l in body["data"]["delayed_loads"])
    assert isinstance(body["confidence"], float)


def test_ai_command_help_shape(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/command", headers=headers,
                       json={"message": "hello"})
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body and body["data"]["intents"]


def test_ai_usage_budget_check(client):
    headers = login(client, "dispatcher@acme.test")
    # Generate some usage first.
    client.post("/api/v1/ai/command", headers=headers,
                json={"message": "show me delayed loads"})
    resp = client.get("/api/v1/ai/usage", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("period", "calls", "total_tokens_in", "total_tokens_out",
                "est_cost_usd", "by_agent", "budget_usd",
                "budget_used_pct", "budget_alert"):
        assert key in body, f"missing key: {key}"
    assert body["budget_usd"] == 500
    assert body["calls"] >= 1
    assert body["budget_alert"] is False


def test_ai_forecast_shape(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/forecast", headers=headers,
                       json={"type": "volume", "periods": 3})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("historical", "current", "forecast", "confidence"):
        assert key in body, f"missing key: {key}"
    assert len(body["historical"]) == 6
    assert len(body["forecast"]) == 3
