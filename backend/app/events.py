"""In-process synchronous event bus.

Every emission is persisted to the events_log table. Subscribers receive
(db, event) where event is a plain dict. A recursion-depth guard prevents
automation-triggered events from looping forever.
"""

from contextvars import ContextVar
from typing import Any, Callable

from . import models

_MAX_DEPTH = 3
_depth: ContextVar[int] = ContextVar("event_depth", default=0)

Subscriber = Callable[..., None]
_subscribers: list[Subscriber] = []


def subscribe(fn: Subscriber) -> Subscriber:
    _subscribers.append(fn)
    return fn


def emit(
    db,
    event_name: str,
    org_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    payload: dict | None = None,
) -> models.EventsLog:
    """Persist the event and notify subscribers. Does not commit — the caller
    commits the surrounding transaction."""
    payload = dict(payload or {})
    row = models.EventsLog(
        org_id=org_id,
        event_name=event_name,
        entity_type=entity_type,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(row)
    db.flush()

    depth = _depth.get()
    if depth < _MAX_DEPTH:
        token = _depth.set(depth + 1)
        try:
            event: dict[str, Any] = {
                "event_name": event_name,
                "org_id": org_id,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "payload": payload,
            }
            for fn in list(_subscribers):
                fn(db, event)
        finally:
            _depth.reset(token)
    return row
