"""Policy + approval round-trip: propose -> require_approval -> approve executes;
deny policy blocks; financial mutation at autonomy 4 still needs approval."""

from app import models

from .conftest import LOAD_A1, login


def _add_policy(db, name, rule, priority=10):
    db.add(models.Policy(org_id="org-a-fixture", name=name,
                         description="test policy", rule=rule,
                         priority=priority, is_active=True))
    db.commit()


def test_propose_creates_pending_approval(client, db):
    _add_policy(db, "route approval", {
        "conditions": [{"field": "action_type", "op": "==",
                        "value": "optimize_route"}],
        "effect": "require_approval",
        "required_role": "dispatcher",
    })
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/optimize-route", headers=headers,
                       json={"load_id": LOAD_A1})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["approval_required"] is True
    assert body["decision"] == "approval_required"
    assert body["approval_id"]

    resp = client.get("/api/v1/approvals", headers=headers,
                      params={"status": "pending"})
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()["items"]]
    assert body["approval_id"] in ids


def test_approve_executes_action(client, db):
    _add_policy(db, "route approval", {
        "conditions": [{"field": "action_type", "op": "==",
                        "value": "optimize_route"}],
        "effect": "require_approval",
        "required_role": "dispatcher",
    })
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/optimize-route", headers=headers,
                       json={"load_id": LOAD_A1})
    approval_id = resp.json()["approval_id"]

    resp = client.post(f"/api/v1/approvals/{approval_id}/approve",
                       headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["executed"] is True
    assert body["execution_result"]["route_id"]
    assert body["approval"]["status"] == "approved"

    # The optimized route was actually persisted.
    routes = (db.query(models.Route)
              .filter(models.Route.load_id == LOAD_A1).all())
    assert len(routes) == 1
    assert routes[0].optimized is True


def test_wrong_role_cannot_approve(client, db):
    _add_policy(db, "route approval", {
        "conditions": [{"field": "action_type", "op": "==",
                        "value": "optimize_route"}],
        "effect": "require_approval",
        "required_role": "dispatcher",
    })
    disp = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/optimize-route", headers=disp,
                       json={"load_id": LOAD_A1})
    approval_id = resp.json()["approval_id"]

    broker = login(client, "broker@acme.test")
    resp = client.post(f"/api/v1/approvals/{approval_id}/approve",
                       headers=broker)
    assert resp.status_code == 403


def test_deny_policy_blocks_action(client, db):
    _add_policy(db, "no invoice actions", {
        "conditions": [{"field": "entity_type", "op": "==",
                        "value": "invoices"}],
        "effect": "deny",
    }, priority=5)
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/actions/propose", headers=headers, json={
        "agent": "finance_agent",
        "action_type": "generate_invoice",
        "entity_type": "invoices",
        "entity_id": LOAD_A1,
        "payload": {"load_id": LOAD_A1},
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["decision"] == "denied"

    resp = client.get("/api/v1/approvals", headers=headers)
    assert resp.json()["total"] == 0

    # The denial was recorded as an ai_action + emitted as POLICY_VIOLATION.
    denied = (db.query(models.AIAction)
              .filter(models.AIAction.decision == "denied").all())
    assert len(denied) == 1
    events = (db.query(models.EventsLog)
              .filter(models.EventsLog.event_name == "POLICY_VIOLATION").all())
    assert len(events) == 1


def test_financial_mutation_at_autonomy_4_still_requires_approval(client, db):
    headers = login(client, "dispatcher@acme.test")
    # First propose registers the agent row (code default autonomy 2)...
    resp = client.post("/api/v1/ai/actions/propose", headers=headers, json={
        "agent": "finance_agent",
        "action_type": "generate_invoice",
        "entity_type": "invoices",
        "entity_id": LOAD_A1,
        "payload": {"load_id": LOAD_A1},
    })
    assert resp.json()["decision"] == "approval_required"

    # ...now raise the agent to full autonomy and propose again.
    agent = (db.query(models.AIAgent)
             .filter(models.AIAgent.org_id == "org-a-fixture",
                     models.AIAgent.name == "finance_agent").one())
    agent.autonomy_level = 4
    db.commit()

    resp = client.post("/api/v1/ai/actions/propose", headers=headers, json={
        "agent": "finance_agent",
        "action_type": "generate_invoice",
        "entity_type": "invoices",
        "entity_id": LOAD_A1,
        "payload": {"load_id": LOAD_A1},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "approval_required"
    assert "Hard-deny" in body["reason"]


def test_low_risk_autonomy_3_auto_executes(client, db):
    # routing_agent: autonomy 3, risk low -> optimize_route auto-executes
    # when no policy says otherwise.
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/actions/propose", headers=headers, json={
        "agent": "routing_agent",
        "action_type": "optimize_route",
        "entity_type": "loads",
        "entity_id": LOAD_A1,
        "payload": {"load_id": LOAD_A1},
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["decision"] == "auto"
    assert body["result"]["route_id"]

    auto = (db.query(models.AIAction)
            .filter(models.AIAction.decision == "auto").all())
    assert len(auto) == 1
    audit_rows = (db.query(models.AuditLog)
                  .filter(models.AuditLog.action == "ai.optimize_route").all())
    assert len(audit_rows) >= 1


def test_reject_approval_flow(client, db):
    _add_policy(db, "route approval", {
        "conditions": [{"field": "action_type", "op": "==",
                        "value": "optimize_route"}],
        "effect": "require_approval",
    })
    headers = login(client, "dispatcher@acme.test")
    resp = client.post("/api/v1/ai/optimize-route", headers=headers,
                       json={"load_id": LOAD_A1})
    approval_id = resp.json()["approval_id"]

    resp = client.post(f"/api/v1/approvals/{approval_id}/reject",
                       headers=headers, json={"reason": "not needed"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["approval"]["status"] == "rejected"
    assert resp.json()["executed"] is False

    # Nothing was persisted.
    assert db.query(models.Route).filter(
        models.Route.load_id == LOAD_A1).count() == 0
