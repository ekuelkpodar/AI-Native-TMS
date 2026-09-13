"""Tenant isolation: org B cannot read/mutate org A records."""

from .conftest import LOAD_A1, LOAD_B1, ORG_A, ORG_B, login


def test_org_b_cannot_read_org_a_load(client):
    headers = login(client, "admin@globex.test")
    resp = client.get(f"/api/v1/loads/{LOAD_A1}", headers=headers)
    assert resp.status_code == 404


def test_org_b_load_list_excludes_org_a(client):
    headers = login(client, "admin@globex.test")
    resp = client.get("/api/v1/loads", headers=headers)
    assert resp.status_code == 200
    numbers = [i["load_number"] for i in resp.json()["items"]]
    assert "LD-20001" in numbers
    assert "LD-10001" not in numbers


def test_org_b_cannot_list_org_a_customers(client):
    headers = login(client, "admin@globex.test")
    resp = client.get("/api/v1/customers", headers=headers)
    assert resp.status_code == 200
    names = [i["name"] for i in resp.json()["items"]]
    assert "Globex Goods" in names
    assert "Acme Foods" not in names


def test_org_b_cannot_mutate_org_a_load(client):
    headers = login(client, "admin@globex.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/cancel", headers=headers)
    assert resp.status_code == 404


def test_audit_log_is_tenant_scoped(client, db):
    # Create an audit row in org A via an API mutation.
    headers_a = login(client, "dispatcher@acme.test")
    resp = client.post(f"/api/v1/loads/{LOAD_A1}/cancel", headers=headers_a)
    assert resp.status_code == 200

    headers_b = login(client, "admin@globex.test")
    resp = client.get("/api/v1/audit", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    headers_a = login(client, "admin@acme.test")
    resp = client.get("/api/v1/audit", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


def test_exceptions_are_tenant_scoped(client):
    headers_b = login(client, "admin@globex.test")
    resp = client.get("/api/v1/exceptions", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
