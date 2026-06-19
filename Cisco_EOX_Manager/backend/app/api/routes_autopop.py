from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.models import AutoPopJob
from app.db.session import get_db
from app.schemas import AutoPopJobListResponse, AutoPopJobOut, AutoPopJobRequest, JobActionResponse, JobLogResponse
from app.services.autopop_jobs import (
    cancel_job,
    clear_old_jobs,
    create_job,
    job_log_response,
    job_to_out,
    pause_job,
    resume_job,
)

router = APIRouter(prefix="/autopop", tags=["Auto_Pop Jobs"])


def _sanitize_job_parameters(parameters: dict) -> dict:
    output = dict(parameters)
    notes: list[str] = []

    limit_categories = output.get("limit_categories")
    if limit_categories and limit_categories > 100:
        output["limit_categories"] = 100
        notes.append("Categories capped at 100, which is effectively all discovered top-level Cisco categories.")

    parse_workers = output.get("parse_workers") or 2
    if parse_workers > 8:
        output["parse_workers"] = 8
        notes.append("Parser workers capped at 8 to protect small servers.")

    if output.get("delay") is not None and output["delay"] < 0:
        output["delay"] = 0
    if output.get("category_break") is not None and output["category_break"] < 0:
        output["category_break"] = 0

    if notes:
        existing_note = output.get("note")
        output["note"] = (existing_note + " | " if existing_note else "") + " ".join(notes)
    return output


@router.post("/jobs", response_model=AutoPopJobOut)
def start_autopop_job(request: AutoPopJobRequest, db: Session = Depends(get_db)) -> AutoPopJobOut:
    job = create_job(db, _sanitize_job_parameters(request.model_dump()), requested_by="gui")
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


@router.delete("/jobs/clear")
def clear_autopop_jobs(
    delete_logs: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> dict:
    return clear_old_jobs(db, delete_logs=delete_logs)


@router.get("/jobs/{job_id}", response_model=AutoPopJobOut)
def get_autopop_job(job_id: int, db: Session = Depends(get_db)) -> AutoPopJobOut:
    job = db.get(AutoPopJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return job_to_out(job)


@router.get("/jobs/{job_id}/log", response_model=JobLogResponse)
def get_autopop_job_log(
    job_id: int,
    lines: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> JobLogResponse:
    response = job_log_response(db, job_id, lines=lines)
    if not response:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return response


@router.post("/jobs/{job_id}/cancel", response_model=AutoPopJobOut)
def cancel_autopop_job(job_id: int, db: Session = Depends(get_db)) -> AutoPopJobOut:
    job = cancel_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return job_to_out(job)


@router.post("/jobs/{job_id}/pause", response_model=JobActionResponse)
def pause_autopop_job(job_id: int, db: Session = Depends(get_db)) -> JobActionResponse:
    job = pause_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return JobActionResponse(ok=True, message=f"Auto_Pop job {job_id} pause requested", job=job_to_out(job))


@router.post("/jobs/{job_id}/resume", response_model=JobActionResponse)
def resume_autopop_job(job_id: int, db: Session = Depends(get_db)) -> JobActionResponse:
    job = resume_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Auto_Pop job not found")
    return JobActionResponse(ok=True, message=f"Auto_Pop job {job_id} resume requested", job=job_to_out(job))
