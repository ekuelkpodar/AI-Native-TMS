"""Communications CRUD + thread view. Scoped roles see only their own threads."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import deps, models, schemas
from ..database import get_db
from .crud import make_crud

COMM_ROLES = ("admin", "broker", "dispatcher", "carrier", "driver", "shipper")


def _stamp_sender(db: Session, data: dict, user: models.User):
    data.setdefault("sender", user.full_name or user.email)
    data.setdefault("created_by", user.id)
    data.setdefault("direction", "out")


router = make_crud(
    model=models.Communication,
    create_schema=schemas.CommunicationCreate,
    update_schema=schemas.CommunicationUpdate,
    out_schema=schemas.CommunicationOut,
    prefix="/communications",
    tags=["communications"],
    read_roles=COMM_ROLES,
    write_roles=COMM_ROLES,
    search_fields=("subject", "body", "sender", "recipient"),
    scope_fn=deps.scope_communications,
    on_create=_stamp_sender,
    entity_name="communications",
)


@router.get("/thread/{thread_type}/{thread_id}", response_model=list)
def thread_view(
    thread_type: str,
    thread_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*COMM_ROLES)),
):
    q = db.query(models.Communication).filter(
        models.Communication.org_id == user.org_id,
        models.Communication.thread_type == thread_type,
        models.Communication.thread_id == thread_id,
    )
    q = deps.scope_communications(q, user)
    items = q.order_by(models.Communication.created_at.asc()).all()
    return [schemas.CommunicationOut.model_validate(c).model_dump() for c in items]
