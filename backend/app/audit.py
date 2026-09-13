"""Audit log helper. Every mutation writes an audit_logs row with before/after."""

from datetime import date, datetime
from typing import Any

from . import models

_EXCLUDED_KEYS = {"password_hash"}


def model_to_dict(obj: Any) -> dict:
    data: dict[str, Any] = {}
    mapper = getattr(obj, "__mapper__", None)
    if mapper is None:
        return data
    for col in mapper.columns:
        if col.key in _EXCLUDED_KEYS:
            continue
        value = getattr(obj, col.key)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, date):
            value = value.isoformat()
        data[col.key] = value
    return data


def log(
    db,
    *,
    org_id: str,
    actor_type: str = "user",
    actor_id: str | None = None,
    actor_name: str = "",
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    before: dict | None = None,
    after: dict | None = None,
    ip_address: str | None = None,
) -> models.AuditLog:
    """Add an audit_logs row. Does not commit — the caller commits."""
    row = models.AuditLog(
        org_id=org_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_name=actor_name,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=after,
        ip_address=ip_address,
    )
    db.add(row)
    db.flush()
    return row
