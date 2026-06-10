from __future__ import annotations

import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import AutoPopJob
from app.db.session import init_db, make_session
from app.schemas import AutoPopJobOut
from app.services.event_log import create_system_event

logger = get_logger("eox_manager.autopop_jobs")
PRODUCT_ROOT = Path(__file__).resolve().parents[3]
AUTOPop_SCRIPT = PRODUCT_ROOT / "tools" / "auto_pop_pid_database.py"
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("EOX_AUTOPOP_JOB_WORKERS", "1")))
_processes: dict[int, subprocess.Popen] = {}
_process_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def job_to_out(job: AutoPopJob) -> AutoPopJobOut:
    return AutoPopJobOut.model_validate(job)


def _append_flag(command: list[str], flag: str, value: Any | None = None) -> None:
    if value is None or value is False or value == "":
        return
    command.append(flag)
    if value is not True:
        command.append(str(value))


def build_autopop_command(parameters: dict[str, Any]) -> list[str]:
    command = [sys.executable, str(AUTOPop_SCRIPT)]
    for category in parameters.get("categories") or []:
        _append_flag(command, "--category", category)
    for category_url in parameters.get("category_urls") or []:
        _append_flag(command, "--category-url", category_url)
    _append_flag(command, "--limit-categories", parameters.get("limit_categories"))
    _append_flag(command, "--limit-series-eox", parameters.get("limit_series_eox"))
    _append_flag(command, "--limit-announcements", parameters.get("limit_announcements"))
    _append_flag(command, "--parse-workers", parameters.get("parse_workers"))
    _append_flag(command, "--delay", parameters.get("delay"))
    _append_flag(command, "--category-break", parameters.get("category_break"))
    _append_flag(command, "--eox-candidates-only", bool(parameters.get("eox_candidates_only")))
    _append_flag(command, "--force-refresh", bool(parameters.get("force_refresh")))
    _append_flag(command, "--overwrite", bool(parameters.get("overwrite")))
    _append_flag(command, "--allow-empty", bool(parameters.get("allow_empty")))
    _append_flag(command, "--use-api", bool(parameters.get("use_api")))
    return command


def create_job(db: Session, parameters: dict[str, Any], *, requested_by: str | None = None) -> AutoPopJob:
    command = build_autopop_command(parameters)
    job = AutoPopJob(
        status="queued",
        requested_by=requested_by,
        parameters=parameters,
        command=command,
        stats={},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    create_system_event(
        db,
        level="info",
        event_type="autopop_job_queued",
        source="backend",
        message=f"Auto_Pop job {job.id} queued",
        payload={"job_id": job.id, "parameters": parameters},
        commit=True,
    )
    _executor.submit(_run_job, job.id)
    return job


def _run_job(job_id: int) -> None:
    init_db()
    settings = get_settings()
    log_dir = settings.log_dir / "jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"auto_pop_job_{job_id}.log"

    db = make_session()
    try:
        job = db.get(AutoPopJob, job_id)
        if not job:
            return
        job.status = "running"
        job.started_at = _now()
        job.log_file = str(log_file)
        db.commit()
        command = list(job.command or build_autopop_command(job.parameters or {}))
        logger.info("Starting Auto_Pop job %s", job_id)
        create_system_event(
            db,
            level="info",
            event_type="autopop_job_started",
            source="backend",
            message=f"Auto_Pop job {job_id} started",
            payload={"job_id": job_id, "command": command},
            commit=True,
        )
        env = os.environ.copy()
        env.setdefault("EOX_DATA_DIR", str(settings.data_dir))
        env.setdefault("EOX_LOG_DIR", str(settings.log_dir))
        with log_file.open("w", encoding="utf-8") as handle:
            process = subprocess.Popen(command, cwd=str(PRODUCT_ROOT), stdout=handle, stderr=subprocess.STDOUT, env=env)
            with _process_lock:
                _processes[job_id] = process
            job.process_id = process.pid
            db.commit()
            return_code = process.wait()
            with _process_lock:
                _processes.pop(job_id, None)
        job = db.get(AutoPopJob, job_id)
        if not job:
            return
        job.return_code = return_code
        job.finished_at = _now()
        if job.status == "cancel_requested":
            job.status = "cancelled"
        elif return_code == 0:
            job.status = "completed"
        else:
            job.status = "failed"
            job.last_error = f"Auto_Pop process exited with return code {return_code}"
        job.stats = {**dict(job.stats or {}), "return_code": return_code, "log_file": str(log_file)}
        db.commit()
        create_system_event(
            db,
            level="info" if return_code == 0 else "error",
            event_type="autopop_job_finished",
            source="backend",
            message=f"Auto_Pop job {job_id} finished with status {job.status}",
            payload={"job_id": job_id, "return_code": return_code, "log_file": str(log_file)},
            commit=True,
        )
    except Exception as exc:
        logger.exception("Auto_Pop job %s failed", job_id)
        job = db.get(AutoPopJob, job_id)
        if job:
            job.status = "failed"
            job.finished_at = _now()
            job.last_error = str(exc)
            db.commit()
    finally:
        db.close()


def cancel_job(db: Session, job_id: int) -> AutoPopJob | None:
    job = db.get(AutoPopJob, job_id)
    if not job:
        return None
    if job.status not in {"queued", "running"}:
        return job
    job.status = "cancel_requested"
    db.commit()
    with _process_lock:
        process = _processes.get(job_id)
    if process and process.poll() is None:
        process.terminate()
    create_system_event(
        db,
        level="warning",
        event_type="autopop_job_cancel_requested",
        source="backend",
        message=f"Auto_Pop job {job_id} cancellation requested",
        payload={"job_id": job_id},
        commit=True,
    )
    db.refresh(job)
    return job


def mark_stale_jobs() -> None:
    db = make_session()
    try:
        jobs = db.query(AutoPopJob).filter(AutoPopJob.status.in_(["queued", "running", "cancel_requested"])).all()
        for job in jobs:
            job.status = "unknown_after_restart"
            job.finished_at = _now()
            job.last_error = "API process restarted before this job reported completion"
        if jobs:
            db.commit()
    finally:
        db.close()
