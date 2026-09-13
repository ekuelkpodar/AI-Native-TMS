"""Invoices CRUD + issue + pay.

Totals are (re)computed from line_items on create/update. Pay records a
payment row; a fully-paid invoice moves to 'paid' and fires PAYMENT_RECEIVED.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..database import get_db
from .crud import make_crud
from .loads import LOAD_TRANSITIONS

INVOICE_READ_ROLES = ("admin", "finance", "broker", "shipper", "ops_manager")
INVOICE_WRITE_ROLES = ("admin", "finance")


def _next_invoice_number(db: Session, org_id: str) -> str:
    max_n = 10000
    for (inv,) in (
        db.query(models.Invoice.invoice_number)
        .filter(models.Invoice.org_id == org_id)
        .all()
    ):
        try:
            n = int(str(inv).split("-")[-1])
            max_n = max(max_n, n)
        except ValueError:
            continue
    return f"INV-{max_n + 1}"


def _recompute_totals(data: dict) -> None:
    items = data.get("line_items") or []
    subtotal = round(
        sum(float(i.get("amount", 0) or 0) for i in items if isinstance(i, dict)), 2
    )
    data["subtotal"] = subtotal
    tax = round(float(data.get("tax", 0) or 0), 2)
    data["tax"] = tax
    data["total"] = round(subtotal + tax, 2)


def _on_create(db: Session, data: dict, user: models.User):
    data["invoice_number"] = _next_invoice_number(db, user.org_id)
    data.setdefault("status", "draft")
    _recompute_totals(data)


router = make_crud(
    model=models.Invoice,
    create_schema=schemas.InvoiceCreate,
    update_schema=schemas.InvoiceUpdate,
    out_schema=schemas.InvoiceOut,
    prefix="/invoices",
    tags=["invoices"],
    read_roles=INVOICE_READ_ROLES,
    write_roles=INVOICE_WRITE_ROLES,
    search_fields=("invoice_number",),
    scope_fn=deps.scope_invoices,
    create_event="INVOICE_CREATED",
    on_create=_on_create,
    entity_name="invoices",
    include=("list", "create", "get", "delete"),  # update is custom below (totals)
)


@router.put("/{obj_id}", response_model=dict)
def update_invoice(
    obj_id: str,
    payload: schemas.InvoiceUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*INVOICE_WRITE_ROLES)),
):
    invoice = router.get_one(db, user, obj_id)
    before = audit.model_to_dict(invoice)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(invoice, key, value)
    if "line_items" in data or "tax" in data:
        live = {"line_items": invoice.line_items, "tax": invoice.tax}
        _recompute_totals(live)
        invoice.subtotal, invoice.tax, invoice.total = (
            live["subtotal"], live["tax"], live["total"],
        )
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="invoices.update",
        entity_type="invoices", entity_id=invoice.id,
        before=before, after=audit.model_to_dict(invoice),
    )
    db.commit()
    db.refresh(invoice)
    return schemas.InvoiceOut.model_validate(invoice).model_dump()


@router.post("/{obj_id}/issue", response_model=dict)
def issue_invoice(
    obj_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*INVOICE_WRITE_ROLES)),
):
    invoice = router.get_one(db, user, obj_id)
    if invoice.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Only draft invoices can be issued (current: {invoice.status})",
        )
    before = audit.model_to_dict(invoice)
    invoice.status = "issued"
    invoice.issue_date = invoice.issue_date or date.today()
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="invoices.issue",
        entity_type="invoices", entity_id=invoice.id,
        before=before, after=audit.model_to_dict(invoice),
    )
    events.emit(
        db, "INVOICE_CREATED", user.org_id, "invoices", invoice.id,
        {"invoice_id": invoice.id, "invoice_number": invoice.invoice_number,
         "customer_id": invoice.customer_id, "total": invoice.total},
    )
    db.commit()
    db.refresh(invoice)
    return schemas.InvoiceOut.model_validate(invoice).model_dump()


@router.post("/{obj_id}/pay", response_model=dict)
def pay_invoice(
    obj_id: str,
    payload: schemas.InvoicePayRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*INVOICE_WRITE_ROLES)),
):
    invoice = router.get_one(db, user, obj_id)
    if invoice.status not in ("issued", "overdue"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invoice cannot be paid in status '{invoice.status}'",
        )
    before = audit.model_to_dict(invoice)
    payment = models.Payment(
        org_id=user.org_id, invoice_id=invoice.id,
        amount=payload.amount, method=payload.method,
        reference=payload.reference,
    )
    db.add(payment)
    db.flush()
    invoice.amount_paid = round((invoice.amount_paid or 0) + payload.amount, 2)
    if invoice.amount_paid >= (invoice.total or 0):
        invoice.status = "paid"
        # move linked load to paid when the transition is legal
        if invoice.load_id:
            load = (
                db.query(models.Load)
                .filter(models.Load.id == invoice.load_id,
                        models.Load.org_id == user.org_id)
                .first()
            )
            if load and "paid" in LOAD_TRANSITIONS.get(load.status, set()):
                load.status = "paid"
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="invoices.pay",
        entity_type="invoices", entity_id=invoice.id,
        before=before, after=audit.model_to_dict(invoice),
    )
    events.emit(
        db, "PAYMENT_RECEIVED", user.org_id, "invoices", invoice.id,
        {"invoice_id": invoice.id, "invoice_number": invoice.invoice_number,
         "amount": payload.amount, "method": payload.method,
         "amount_paid": invoice.amount_paid, "total": invoice.total,
         "status": invoice.status},
    )
    db.commit()
    db.refresh(invoice)
    return {
        "invoice": schemas.InvoiceOut.model_validate(invoice).model_dump(),
        "payment": schemas.PaymentOut.model_validate(payment).model_dump(),
    }
