"""AI action proposal / approval / rejection.

propose_action() runs the policy engine; allowed actions execute immediately
via the tool registry, gated actions create an approvals row for a human,
denied actions are recorded and blocked.

approve_approval() / reject_approval() are the programmatic counterparts of
the /approvals HTTP endpoints. execute_approved_action(db, approval) is the
hook target wired into backend/app/routers/approvals.py.

Every path writes an ai_actions row and an audit_logs row, and emits the
matching domain event (AI_ACTION_PROPOSED / AI_ACTION_EXECUTED /
AI_ACTION_APPROVED / AI_ACTION_REJECTED / POLICY_VIOLATION).
"""

from fastapi import HTTPException, status

from .. import audit, events, models
from .policy import PolicyEngine
from .providers import utcnow
from .registry import (
    AGENTS, TOOLS, ToolNotFound, ToolPermissionDenied, execute_tool,
)
import inspect


def _tool_params(action_type: str, entity_type: str | None,
                 entity_id: str | None, payload: dict) -> dict:
    """Merge payload with entity context for tool execution.

    Callers usually put the target in entity_type/entity_id (e.g.
    entity_type="load", entity_id=<id>) while the tool handler expects a
    named kwarg (e.g. load_id). Inject the conventional `<entity>_id` kwarg
    when the handler's signature accepts it and the payload doesn't already
    provide it. Never inject kwargs the handler doesn't declare.
    """
    params = dict(payload or {})
    if entity_id and entity_type:
        tool = TOOLS.get(action_type)
        if tool is not None:
            names = set(inspect.signature(tool["handler"]).parameters)
            et = entity_type.strip().lower()
            singular = et[:-1] if et.endswith("s") and len(et) > 1 else et
            for cand in (f"{et}_id", f"{singular}_id"):
                if cand in names and cand not in params:
                    params[cand] = entity_id
                    break
    return params


def _canonical_agent_name(agent_name: str) -> str | None:
    """Normalize a caller-supplied agent name to a registry key.

    Accepts "Dispatch Agent", "dispatch-agent", "DISPATCH_AGENT", etc.
    """
    if not agent_name:
        return None
    norm = agent_name.strip().lower().replace("-", "_").replace(" ", "_")
    norm = "_".join(p for p in norm.split("_") if p)
    for key in AGENTS:
        if key == norm:
            return key
    return None


def ensure_agent(db, org_id: str, agent_name: str) -> models.AIAgent:
    """Sync the code-defined agent definition into ai_agents (upsert)."""
    canonical = _canonical_agent_name(agent_name)
    if canonical is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown agent: {agent_name}",
        )
    agent_name = canonical
    definition = AGENTS[agent_name]
    row = (
        db.query(models.AIAgent)
        .filter(models.AIAgent.org_id == org_id,
                models.AIAgent.name == agent_name)
        .first()
    )
    if row is None:
        row = models.AIAgent(org_id=org_id, name=agent_name)
        db.add(row)
    row.version = definition.get("version", "1.0")
    row.model = definition.get("model")
    row.tools = list(definition.get("tools", []))
    row.permissions = list(definition.get("permissions", []))
    row.status = definition.get("status", "active")
    row.owner = definition.get("owner")
    row.risk_level = definition.get("risk_level", "medium")
    # Preserve a human-tuned autonomy_level if one was set on the row and the
    # code definition did not change it: the DB row is authoritative here.
    if row.autonomy_level is None:
        row.autonomy_level = definition.get("autonomy_level", 1)
    row.config = dict(definition.get("config", {}))
    db.flush()
    return row


def _write_ai_action(db, *, org_id: str, agent: models.AIAgent,
                     action_type: str, entity_type: str | None,
                     entity_id: str | None, payload: dict, decision: str,
                     policy: dict | None, approval_id: str | None = None,
                     output: dict | None = None,
                     result: dict | None = None) -> models.AIAction:
    row = models.AIAction(
        org_id=org_id,
        agent_id=agent.id,
        agent_name=agent.name,
        action_type=action_type,
        entity_type=entity_type,
        entity_id=entity_id,
        input=dict(payload or {}),
        output=output,
        policy_id=(policy or {}).get("id"),
        decision=decision,
        approval_id=approval_id,
        result=result,
    )
    db.add(row)
    db.flush()
    audit.log(
        db, org_id=org_id, actor_type="agent", actor_id=agent.id,
        actor_name=agent.name, action=f"ai.{action_type}",
        entity_type=entity_type or "ai_actions", entity_id=row.id,
        after={
            "decision": decision,
            "policy": (policy or {}).get("name"),
            "approval_id": approval_id,
            "result": result,
        },
    )
    return row


# ---------------------------------------------------------------------------
# Propose
# ---------------------------------------------------------------------------

def propose_action(db, user: models.User, agent_name: str, action_type: str,
                   entity_type: str | None = None,
                   entity_id: str | None = None,
                   payload: dict | None = None,
                   reason: str | None = None) -> dict:
    """Evaluate policy for an AI-proposed action and act on the decision."""
    payload = dict(payload or {})
    agent = ensure_agent(db, user.org_id, agent_name)

    if agent.status != "active":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Agent '{agent_name}' is {agent.status}; cannot propose actions.",
        )

    action = {
        "agent": agent_name,
        "action_type": action_type,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "payload": payload,
    }
    context = {
        "user": user,
        "autonomy_level": agent.autonomy_level or 1,
        "risk_level": agent.risk_level or "medium",
    }
    evaluation = PolicyEngine.evaluate(db, user.org_id, action, context)
    decision = evaluation["decision"]
    policy = evaluation.get("policy")

    if decision in ("allow", "notify"):
        try:
            result = execute_tool(
                db, user, action_type,
                **_tool_params(action_type, entity_type, entity_id, payload))
        except ToolNotFound as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        except ToolPermissionDenied as exc:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail=str(exc))
        notified = False
        if decision == "notify":
            db.add(models.Notification(
                org_id=user.org_id, user_id=None, type="ai_recommendation",
                title=f"AI action auto-executed: {agent_name}.{action_type}",
                body=evaluation.get("reason", ""),
                entity_type=entity_type, entity_id=entity_id,
            ))
            notified = True
        _write_ai_action(
            db, org_id=user.org_id, agent=agent, action_type=action_type,
            entity_type=entity_type, entity_id=entity_id, payload=payload,
            decision="auto", policy=policy, output=result, result=result,
        )
        events.emit(
            db, "AI_ACTION_EXECUTED", user.org_id, entity_type, entity_id,
            {"agent_name": agent_name, "action_type": action_type,
             "decision": "auto", "notified": notified, "result": result},
        )
        db.commit()
        return {"decision": "auto", "result": result, "approval_id": None,
                "policy": policy, "reason": evaluation.get("reason"),
                "notified": notified}

    if decision == "require_approval":
        required_role = evaluation.get("required_role", "dispatcher")
        approval = models.Approval(
            org_id=user.org_id,
            agent_name=agent_name,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            reason=reason or evaluation.get("reason"),
            risk_level=agent.risk_level,
            required_role=required_role,
            status="pending",
            requested_by=user.id,
        )
        db.add(approval)
        db.flush()
        _write_ai_action(
            db, org_id=user.org_id, agent=agent, action_type=action_type,
            entity_type=entity_type, entity_id=entity_id, payload=payload,
            decision="pending", policy=policy, approval_id=approval.id,
            result={"status": "pending"},
        )
        events.emit(
            db, "AI_ACTION_PROPOSED", user.org_id, entity_type, entity_id,
            {"agent_name": agent_name, "action_type": action_type,
             "approval_id": approval.id, "required_role": required_role,
             "reason": evaluation.get("reason")},
        )
        db.commit()
        return {"decision": "approval_required", "approval_id": approval.id,
                "required_role": required_role, "policy": policy,
                "reason": evaluation.get("reason")}

    # decision == "deny"
    _write_ai_action(
        db, org_id=user.org_id, agent=agent, action_type=action_type,
        entity_type=entity_type, entity_id=entity_id, payload=payload,
        decision="denied", policy=policy,
        result={"reason": evaluation.get("reason")},
    )
    events.emit(
        db, "POLICY_VIOLATION", user.org_id, entity_type, entity_id,
        {"agent_name": agent_name, "action_type": action_type,
         "reason": evaluation.get("reason")},
    )
    db.commit()
    return {"decision": "denied", "approval_id": None, "policy": policy,
            "reason": evaluation.get("reason")}


# ---------------------------------------------------------------------------
# Execution (hook target for routers/approvals.py)
# ---------------------------------------------------------------------------

def _deciding_user(db, approval: models.Approval) -> models.User:
    user_id = approval.decided_by or approval.requested_by
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise RuntimeError(
            "Cannot execute approved action: deciding user not found."
        )
    return user


def execute_approved_action(db, approval: models.Approval,
                           user: models.User | None = None) -> dict:
    """Execute an approved approval's action via the tool registry.

    Contract for routers/approvals.py: return a JSON-serializable result dict.
    Flushes but does not commit — the caller owns the transaction.
    """
    user = user or _deciding_user(db, approval)
    try:
        result = execute_tool(db, user, approval.action_type,
                              **_tool_params(approval.action_type,
                                             approval.entity_type,
                                             approval.entity_id,
                                             approval.payload))
    except ToolNotFound as exc:
        raise RuntimeError(f"Approved action references {exc}")
    except ToolPermissionDenied as exc:
        raise RuntimeError(f"Approved action blocked: {exc}")

    pending = (
        db.query(models.AIAction)
        .filter(models.AIAction.approval_id == approval.id,
                models.AIAction.decision == "pending")
        .order_by(models.AIAction.created_at.desc())
        .first()
    )
    if pending is not None:
        pending.decision = "approved"
        pending.output = result
        pending.result = result

    agent = ensure_agent(db, approval.org_id, approval.agent_name)
    audit.log(
        db, org_id=approval.org_id, actor_type="agent", actor_id=agent.id,
        actor_name=approval.agent_name, action=f"ai.{approval.action_type}",
        entity_type=approval.entity_type or "approvals", entity_id=approval.id,
        after={"decision": "approved", "approval_id": approval.id,
               "result": result},
    )
    events.emit(
        db, "AI_ACTION_EXECUTED", approval.org_id, approval.entity_type,
        approval.entity_id,
        {"agent_name": approval.agent_name,
         "action_type": approval.action_type, "decision": "approved",
         "approval_id": approval.id, "result": result},
    )
    db.flush()
    return result


# ---------------------------------------------------------------------------
# Programmatic approve / reject (mirror the /approvals HTTP endpoints)
# ---------------------------------------------------------------------------

def _get_pending(db, org_id: str, approval_id: str) -> models.Approval:
    approval = (
        db.query(models.Approval)
        .filter(models.Approval.id == approval_id,
                models.Approval.org_id == org_id)
        .first()
    )
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"Approval is already '{approval.status}'")
    return approval


def _check_decider(user: models.User, approval: models.Approval) -> None:
    if user.role != "admin" and user.role != approval.required_role:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail=f"This approval requires role '{approval.required_role}'",
        )


def approve_approval(db, user: models.User, approval_id: str) -> dict:
    """Approve a pending approval and execute its action."""
    approval = _get_pending(user.org_id, approval_id)
    _check_decider(user, approval)
    before = audit.model_to_dict(approval)
    approval.status = "approved"
    approval.decided_by = user.id
    approval.decided_at = utcnow()
    db.flush()

    result = execute_approved_action(db, approval, user=user)

    agent = ensure_agent(db, user.org_id, approval.agent_name)
    _write_ai_action(
        db, org_id=user.org_id, agent=agent, action_type=approval.action_type,
        entity_type=approval.entity_type, entity_id=approval.entity_id,
        payload=approval.payload or {}, decision="approved", policy=None,
        approval_id=approval.id, output=result, result=result,
    )
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="approvals.approve",
        entity_type="approvals", entity_id=approval.id,
        before=before, after=audit.model_to_dict(approval),
    )
    events.emit(
        db, "AI_ACTION_APPROVED", user.org_id, "approvals", approval.id,
        {"approval_id": approval.id, "agent_name": approval.agent_name,
         "action_type": approval.action_type},
    )
    db.commit()
    return {"approval_id": approval.id, "status": "approved",
            "executed": True, "result": result}


def reject_approval(db, user: models.User, approval_id: str,
                    reason: str | None = None) -> dict:
    """Reject a pending approval without executing its action."""
    approval = _get_pending(user.org_id, approval_id)
    _check_decider(user, approval)
    before = audit.model_to_dict(approval)
    approval.status = "rejected"
    approval.decided_by = user.id
    approval.decided_at = utcnow()
    if reason:
        approval.reason = reason
    db.flush()

    agent = ensure_agent(db, user.org_id, approval.agent_name)
    _write_ai_action(
        db, org_id=user.org_id, agent=agent, action_type=approval.action_type,
        entity_type=approval.entity_type, entity_id=approval.entity_id,
        payload=approval.payload or {}, decision="rejected", policy=None,
        approval_id=approval.id,
        result={"executed": False, "reason": reason},
    )
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="approvals.reject",
        entity_type="approvals", entity_id=approval.id,
        before=before, after=audit.model_to_dict(approval),
    )
    events.emit(
        db, "AI_ACTION_REJECTED", user.org_id, "approvals", approval.id,
        {"approval_id": approval.id, "agent_name": approval.agent_name,
         "action_type": approval.action_type, "reason": reason},
    )
    db.commit()
    return {"approval_id": approval.id, "status": "rejected",
            "executed": False}
