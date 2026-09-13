"""Auth: login success/fail, /me, missing/invalid token -> 401."""

from .conftest import login


def test_login_success(client):
    resp = client.post("/api/v1/auth/login",
                       json={"email": "admin@acme.test", "password": "Demo1234!"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "admin@acme.test"
    assert body["user"]["role"] == "admin"


def test_login_wrong_password(client):
    resp = client.post("/api/v1/auth/login",
                       json={"email": "admin@acme.test", "password": "wrong"})
    assert resp.status_code == 401


def test_login_unknown_email(client):
    resp = client.post("/api/v1/auth/login",
                       json={"email": "nobody@acme.test", "password": "Demo1234!"})
    assert resp.status_code == 401


def test_me_with_token(client):
    headers = login(client, "dispatcher@acme.test")
    resp = client.get("/api/v1/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == "dispatcher@acme.test"
    assert body["user"]["role"] == "dispatcher"
    assert body["organization"]["slug"] == "acme-test"


def test_me_without_token(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_invalid_token(client):
    resp = client.get("/api/v1/auth/me",
                      headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401


def test_protected_route_without_token(client):
    resp = client.get("/api/v1/loads")
    assert resp.status_code == 401
