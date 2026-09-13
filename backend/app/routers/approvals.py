"""Approvals: list pending approvals, approve, reject.

Approve/reject updates the approval row and fires AI_ACTION_APPROVED /
AI_ACTION_REJECTED. Actually *executing* the approved action belongs to the
AI track — see execute_approved_action() below.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db

router = APIRouter(prefix="/approvals", tags=["approvals"])

APPROVAL_ROLES = ("admin", "dispatcher", "ops_manager", "broker")


def execute_approved_action(db: Session, approval: models.Approval) -> dict:
    """Execute the action described by an approved approval.

    Delegates to the AI control plane (backend/app/ai/approvals.py), which
    executes the action via the tool registry with the deciding user's
    scopes, updates the pending ai_actions row, and emits AI_ACTION_EXECUTED.

    Contract: return a JSON-serializable result dict describing what was
    executed. The approve endpoint records it on an ai_actions row.
    The import is local to avoid a circular import (app.ai imports routers).
    """
    from ..ai.approvals import execute_approved_action as _ai_execute

    return _ai_execute(db, approval)


def _get_approval(db: Session, user: models.User, approval_id: str) -> models.Approval:
    approval = (
        db.query(models.Approval)
        .filter(
            models.Approval.id == approval_id,
            models.Approval.org_id == user.org_id,
        )
        .first()
    )
    if not approval:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found"
        )
    return approval


@router.get("", response_model=dict)
def list_approvals(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*APPROVAL_ROLES)),
    status: str | None = Query(default=None),
    agent_name: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    q = db.query(models.Approval).filter(models.Approval.org_id == user.org_id)
    if status is not None:
        q = q.filter(models.Approval.status == status)
    if agent_name:
        q = q.filter(models.Approval.agent_name == agent_name)
    total = q.count()
    items = (
        q.order_by(models.Approval.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [schemas.ApprovalOut.model_validate(a).model_dump() for a in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/{approval_id}/approve", response_model=dict)
def approve_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*APPROVAL_ROLES)),
):
    approval = _get_approval(db, user, approval_id)
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Approval is already '{approval.status}'",
        )
    # required_role gates who may approve; admins may always approve.
    if user.role != "admin" and user.role != approval.required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This approval requires role '{approval.required_role}'",
        )
    before = audit.model_to_dict(approval)
    approval.status = "approved"
    approval.decided_by = user.id
    approval.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.flush()

    executed = False
    execution_result = None
    execution_error = None
    try:
        execution_result = execute_approved_action(db, approval)
        executed = True
    except NotImplementedError as exc:
        execution_error = str(exc)

    action_row = models.AIAction(
        org_id=user.org_id,
        agent_name=approval.agent_name,
        action_type=approval.action_type,
        entity_type=approval.entity_type,
        entity_id=approval.entity_id,
        input=approval.payload or {},
        decision="approved",
        approval_id=approval.id,
        result={"executed": executed, "result": execution_result}
        if executed
        else {"executed": False, "error": execution_error},
    )
    db.add(action_row)
    db.flush()

    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="approvals.approve",
        entity_type="approvals", entity_id=approval.id,
        before=before, after=audit.model_to_dict(approval),
    )
    events.emit(
        db, "AI_ACTION_APPROVED", user.org_id, "approvals", approval.id,
        {"approval_id": approval.id, "agent_name": approval.agent_name,
         "action_type": approval.action_type, "executed": executed},
    )
    db.commit()
    db.refresh(approval)
    return {
        "approval": schemas.ApprovalOut.model_validate(approval).model_dump(),
        "executed": executed,
        "execution_result": execution_result,
        "execution_error": execution_error,
    }


@router.post("/{approval_id}/reject", response_model=dict)
def reject_approval(
    approval_id: str,
    payload: schemas.ApprovalRejectRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*APPROVAL_ROLES)),
):
    approval = _get_approval(db, user, approval_id)
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Approval is already '{approval.status}'",
        )
    # required_role gates who may reject; admins may always reject.
    if user.role != "admin" and user.role != approval.required_role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"This approval requires role '{approval.required_role}'",
        )
    before = audit.model_to_dict(approval)
    approval.status = "rejected"
    approval.decided_by = user.id
    approval.decided_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if payload.reason:
        approval.reason = payload.reason
    db.flush()

    action_row = models.AIAction(
        org_id=user.org_id,
        agent_name=approval.agent_name,
        action_type=approval.action_type,
        entity_type=approval.entity_type,
        entity_id=approval.entity_id,
        input=approval.payload or {},
        decision="rejected",
        approval_id=approval.id,
        result={"executed": False, "reason": payload.reason},
    )
    db.add(action_row)
    db.flush()

    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="approvals.reject",
        entity_type="approvals", entity_id=approval.id,
        before=before, after=audit.model_to_dict(approval),
    )
    events.emit(
        db, "AI_ACTION_REJECTED", user.org_id, "approvals", approval.id,
        {"approval_id": approval.id, "agent_name": approval.agent_name,
         "action_type": approval.action_type, "reason": payload.reason},
    )
    db.commit()
    db.refresh(approval)
    return {
        "approval": schemas.ApprovalOut.model_validate(approval).model_dump(),
        "executed": False,
        "execution_result": None,
        "execution_error": None,
    }
