from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import AutoPopJob
from app.db.session import get_db
from app.schemas import AutoPopJobListResponse, AutoPopJobOut, AutoPopJobRequest
from app.services.autopop_jobs import cancel_job, create_job, job_to_out

router = APIRouter(prefix="/autopop", tags=["Auto_Pop Jobs"])


@router.post("/jobs", response_model=AutoPopJobOut)
def start_autopop_job(request: AutoPopJobRequest, db: Session = Depends(get_db)) -> AutoPopJobOut:
    job = create_job(db, request.model_dump(), requested_by="gui")
    return job_to_out(job)


@router.get("/jobs", response_model=AutoPopJobListResponse)
def list_autopop_jobs(
    status: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> AutoPopJobListResponse:
    query = db.query(AutoPopJob)
    if status:
        query = query.filter(AutoPopJob.status == status)
    total = query.count()
    items = query.order_by(AutoPopJob.created_at.desc()).offset(offset).limit(limit).all()
    return AutoPopJobListResponse(items=[job_to_out(item) for item in items], total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}", response_model=AutoPopJobOut)
def get_autopop_job(job_id: int, db: Session = Depends(get_db)) -> AutoPopJobOut:
    job = db.get(AutoPopJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return job_to_out(job)


@router.post("/jobs/{job_id}/cancel", response_model=AutoPopJobOut)
def cancel_autopop_job(job_id: int, db: Session = Depends(get_db)) -> AutoPopJobOut:
    job = cancel_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return job_to_out(job)
