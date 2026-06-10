from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy.orm import Session

from app.db.models import SystemEvent
from app.schemas import SystemEventOut


def create_system_event(
    db: Session,
    *,
    level: str,
    event_type: str,
    message: str,
    source: str | None = None,
    payload: Mapping[str, Any] | None = None,
    commit: bool = False,
) -> SystemEvent:
    event = SystemEvent(
        level=(level or "info").lower(),
        event_type=event_type or "system",
        source=source,
        message=message,
        payload=dict(payload or {}),
    )
    db.add(event)
    db.flush()
    if commit:
        db.commit()
        db.refresh(event)
    return event


def system_event_to_out(event: SystemEvent) -> SystemEventOut:
    return SystemEventOut(
        id=event.id,
        level=event.level,
        event_type=event.event_type,
        source=event.source,
        message=event.message,
        payload=event.payload or {},
        created_at=event.created_at,
    )
