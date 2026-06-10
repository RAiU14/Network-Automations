from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import SystemEvent
from app.db.session import get_db
from app.schemas import FrontendLogRequest, SystemEventOut, SystemEventResponse
from app.services.event_log import create_system_event, system_event_to_out

router = APIRouter(prefix="/logs", tags=["Logs"])


@router.post("/frontend", response_model=SystemEventResponse)
def capture_frontend_log(request: FrontendLogRequest, db: Session = Depends(get_db)) -> SystemEventResponse:
    event = create_system_event(
        db,
        level=request.level,
        event_type=request.event_type,
        source=request.source,
        message=request.message,
        payload=request.payload,
        commit=True,
    )
    return SystemEventResponse(ok=True, event=system_event_to_out(event), message="Frontend event captured")


@router.get("/events", response_model=list[SystemEventOut])
def list_system_events(
    level: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[SystemEventOut]:
    query = db.query(SystemEvent)
    if level:
        query = query.filter(SystemEvent.level == level.lower())
    if event_type:
        query = query.filter(SystemEvent.event_type == event_type)
    if source:
        query = query.filter(SystemEvent.source == source)
    items = query.order_by(SystemEvent.created_at.desc()).offset(offset).limit(limit).all()
    return [system_event_to_out(item) for item in items]
