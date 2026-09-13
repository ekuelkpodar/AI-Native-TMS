"""Documents: multipart upload with size/type validation, list, download.

Files are stored under STORAGE_DIR/<org_id>/<uuid>_<filename> (outside any
web root). Uploading a POD also fires POD_UPLOADED.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import audit, deps, events, models, schemas
from ..config import settings
from ..database import get_db

router = APIRouter(prefix="/documents", tags=["documents"])

DOC_ROLES = (
    "admin", "broker", "dispatcher", "finance", "ops_manager",
    "carrier", "driver", "shipper",
)
DOC_WRITE_ROLES = ("admin", "broker", "dispatcher", "carrier", "driver")

ALLOWED_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "csv", "txt",
    "xls", "xlsx", "doc", "docx",
}

# Entities a document may be attached to. The referenced entity must exist in
# the caller's org and be visible under the caller's scoped role.
_ENTITY_MODELS = {
    "loads": models.Load,
    "shipments": models.Shipment,
    "carriers": models.Carrier,
    "drivers": models.Driver,
    "customers": models.Customer,
    "invoices": models.Invoice,
}
_ENTITY_SCOPES = {
    "loads": deps.scope_loads,
    "shipments": deps.scope_shipments,
    "carriers": deps.scope_carriers,
    "drivers": deps.scope_drivers,
    "customers": deps.scope_customers,
    "invoices": deps.scope_invoices,
}


def _safe_filename(filename: str) -> str:
    name = Path(filename or "upload").name
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)


@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
    entity_id: str = Form(...),
    doc_type: schemas.DocType = Form("other"),
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*DOC_WRITE_ROLES)),
):
    # Contract: multipart(file, entity_type, entity_id, doc_type). The filename
    # and content type come from the uploaded file itself.
    # Accept singular aliases too ("load" -> "loads") for frontend convenience;
    # the canonical stored value is always the plural table name.
    _ALIASES = {
        "load": "loads", "shipment": "shipments", "carrier": "carriers",
        "driver": "drivers", "customer": "customers", "invoice": "invoices",
    }
    entity_type = _ALIASES.get(entity_type, entity_type)
    if entity_type not in _ENTITY_MODELS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"entity_type must be one of: {sorted(_ENTITY_MODELS)}",
        )
    model = _ENTITY_MODELS[entity_type]
    scope_fn = _ENTITY_SCOPES[entity_type]
    q = scope_fn(
        db.query(model.id).filter(
            model.org_id == user.org_id, model.id == entity_id
        ),
        user,
    )
    if q.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Referenced entity not found or not visible to this user",
        )
    filename = file.filename or "upload"
    content_type = file.content_type or "application/octet-stream"
    content = await file.read()
    size = len(content)
    if size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({size} bytes > {settings.MAX_UPLOAD_BYTES})",
        )
    clean = _safe_filename(filename)
    ext = clean.rsplit(".", 1)[-1].lower() if "." in clean else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '.{ext}' not allowed. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )
    org_dir = settings.STORAGE_DIR / user.org_id
    org_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{clean}"
    storage_path = org_dir / stored_name
    storage_path.write_bytes(content)

    version = (
        db.query(models.Document)
        .filter(
            models.Document.org_id == user.org_id,
            models.Document.entity_type == entity_type,
            models.Document.entity_id == entity_id,
            models.Document.doc_type == doc_type,
        )
        .count()
        + 1
    )
    doc = models.Document(
        org_id=user.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        doc_type=doc_type,
        filename=clean,
        content_type=content_type,
        size_bytes=size,
        storage_path=str(storage_path),
        version=version,
        uploaded_by=user.id,
    )
    db.add(doc)
    db.flush()
    audit.log(
        db, org_id=user.org_id, actor_type="user", actor_id=user.id,
        actor_name=user.full_name, action="documents.upload",
        entity_type="documents", entity_id=doc.id,
        after=audit.model_to_dict(doc),
    )
    payload = {
        "document_id": doc.id, "entity_type": entity_type,
        "entity_id": entity_id, "doc_type": doc_type, "filename": clean,
    }
    events.emit(db, "DOCUMENT_UPLOADED", user.org_id, "documents", doc.id, payload)
    if doc_type == "pod":
        events.emit(db, "POD_UPLOADED", user.org_id, "documents", doc.id, payload)
    db.commit()
    db.refresh(doc)
    return schemas.DocumentOut.model_validate(doc).model_dump()


@router.get("", response_model=dict)
def list_documents(
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*DOC_ROLES)),
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    doc_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    q = db.query(models.Document).filter(models.Document.org_id == user.org_id)
    q = deps.scope_documents(q, db, user)
    if entity_type:
        q = q.filter(models.Document.entity_type == entity_type)
    if entity_id:
        q = q.filter(models.Document.entity_id == entity_id)
    if doc_type:
        q = q.filter(models.Document.doc_type == doc_type)
    total = q.count()
    items = (
        q.order_by(models.Document.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [schemas.DocumentOut.model_validate(d).model_dump() for d in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{doc_id}/download")
def download_document(
    doc_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(deps.require_roles(*DOC_ROLES)),
):
    q = db.query(models.Document).filter(
        models.Document.id == doc_id,
        models.Document.org_id == user.org_id,
    )
    doc = deps.scope_documents(q, db, user).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    path = Path(doc.storage_path)
    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File missing from storage"
        )
    return FileResponse(
        path,
        media_type=doc.content_type or "application/octet-stream",
        filename=doc.filename,
    )
