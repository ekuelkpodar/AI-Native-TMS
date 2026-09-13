"""Notification service helper."""

from . import models


def create_notification(
    db,
    *,
    org_id: str,
    ntype: str,
    title: str,
    body: str | None = None,
    user_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> models.Notification:
    """Add a notification row. Does not commit — the caller commits."""
    row = models.Notification(
        org_id=org_id,
        user_id=user_id,
        type=ntype,
        title=title,
        body=body,
        entity_type=entity_type,
        entity_id=entity_id,
    )
    db.add(row)
    db.flush()
    return row
