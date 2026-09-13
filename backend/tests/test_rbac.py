"""RBAC: role matrix — 403s and scoped visibility."""

from .conftest import CUST_A, DRV_A, LOAD_A1, login


def test_driver_blocked_from_admin_endpoints(client):
    headers = login(client, "driver@acme.test")
    resp = client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 403
    resp = client.get("/api/v1/audit", headers=headers)
    assert resp.status_code == 403


def test_driver_blocked_from_carrier_write(client):
    headers = login(client, "driver@acme.test")
    resp = client.post("/api/v1/carriers", headers=headers,
                       json={"legal_name": "Nope"})
    assert resp.status_code == 403


def test_shipper_sees_only_own_customer(client):
    headers = login(client, "shipper@acme.test")
    resp = client.get("/api/v1/customers", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == CUST_A


def test_shipper_sees_only_own_loads(client):
    headers = login(client, "shipper@acme.test")
    resp = client.get("/api/v1/loads", headers=headers)
    assert resp.status_code == 200
    for item in resp.json()["items"]:
        assert item["customer_id"] == CUST_A


def test_driver_sees_only_own_loads(client):
    # Assign LD-10001 to the driver, then check the driver's scoped view.
    disp = login(client, "dispatcher@acme.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/assign", headers=disp,
                       json={"driver_id": DRV_A})
    assert resp.status_code == 200

    headers = login(client, "driver@acme.test")
    resp = client.get("/api/v1/loads", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    for item in items:
        assert item["driver_id"] == DRV_A


def test_finance_cannot_dispatch(client):
    headers = login(client, "finance@acme.test")
    resp = client.get("/api/v1/dispatch/board", headers=headers)
    assert resp.status_code == 403


def test_admin_passes_everything(client):
    headers = login(client, "admin@acme.test")
    assert client.get("/api/v1/users", headers=headers).status_code == 200
    assert client.get("/api/v1/audit", headers=headers).status_code == 200
    assert client.get("/api/v1/dispatch/board", headers=headers).status_code == 200
