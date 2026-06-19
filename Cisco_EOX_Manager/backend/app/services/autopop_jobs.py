from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import AutoPopJob
from app.db.session import init_db, make_session
from app.schemas import AutoPopJobOut, JobLogResponse
from app.services.event_log import create_system_event

logger = get_logger("eox_manager.autopop_jobs")
PRODUCT_ROOT = Path(__file__).resolve().parents[3]
AUTOPop_SCRIPT = PRODUCT_ROOT / "tools" / "auto_pop_pid_database.py"
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("EOX_AUTOPOP_JOB_WORKERS", "1")))
_processes: dict[int, subprocess.Popen] = {}
_process_lock = threading.Lock()

RUNNING_STATUSES = {"queued", "running", "pause_requested", "paused", "resume_requested", "cancel_requested"}
FINAL_STATUSES = {"completed", "failed", "cancelled", "skipped", "unknown_after_restart"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _execution_mode() -> str:
    return os.getenv("EOX_AUTOPOP_EXECUTION_MODE", "local").strip().lower()


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
        stats={"execution_mode": _execution_mode()},
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
        payload={"job_id": job.id, "parameters": parameters, "execution_mode": _execution_mode()},
        commit=True,
    )
    if _execution_mode() in {"local", "api", "inline"}:
        _executor.submit(run_job, job.id)
    return job


def _signal_process(job_id: int, signum: int) -> bool:
    with _process_lock:
        process = _processes.get(job_id)
    if process and process.poll() is None:
        try:
            process.send_signal(signum)
            return True
        except Exception:
            return False
    return False


def run_job(job_id: int) -> None:
    init_db()
    settings = get_settings()
    log_dir = settings.log_dir / "jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"auto_pop_job_{job_id}.log"

    db = make_session()
    paused = False
    try:
        job = db.get(AutoPopJob, job_id)
        if not job or job.status not in {"queued", "resume_requested"}:
            return
        job.status = "running"
        job.started_at = job.started_at or _now()
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
            return_code: int | None = None
            while return_code is None:
                return_code = process.poll()
                if return_code is not None:
                    break
                db.expire_all()
                current = db.get(AutoPopJob, job_id)
                if not current:
                    process.terminate()
                    return_code = process.wait(timeout=30)
                    break
                if current.status == "cancel_requested":
                    process.terminate()
                    try:
                        return_code = process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        return_code = process.wait(timeout=10)
                    break
                if current.status == "pause_requested" and not paused:
                    if hasattr(signal, "SIGSTOP"):
                        process.send_signal(signal.SIGSTOP)
                        paused = True
                        current.status = "paused"
                        db.commit()
                elif current.status == "resume_requested" and paused:
                    if hasattr(signal, "SIGCONT"):
                        process.send_signal(signal.SIGCONT)
                    paused = False
                    current.status = "running"
                    db.commit()
                time.sleep(2)
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


def run_next_queued_job_once() -> bool:
    db = make_session()
    try:
        job = db.query(AutoPopJob).filter(AutoPopJob.status == "queued").order_by(AutoPopJob.created_at.asc()).first()
        if not job:
            return False
        job_id = job.id
        db.commit()
    finally:
        db.close()
    run_job(job_id)
    return True


def cancel_job(db: Session, job_id: int) -> AutoPopJob | None:
    job = db.get(AutoPopJob, job_id)
    if not job:
        return None
    if job.status not in RUNNING_STATUSES:
        return job
    job.status = "cancel_requested"
    db.commit()
    _signal_process(job_id, signal.SIGTERM)
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


def pause_job(db: Session, job_id: int) -> AutoPopJob | None:
    job = db.get(AutoPopJob, job_id)
    if not job:
        return None
    if job.status == "running":
        job.status = "pause_requested"
        db.commit()
        if hasattr(signal, "SIGSTOP") and _signal_process(job_id, signal.SIGSTOP):
            job.status = "paused"
            db.commit()
    db.refresh(job)
    return job


def resume_job(db: Session, job_id: int) -> AutoPopJob | None:
    job = db.get(AutoPopJob, job_id)
    if not job:
        return None
    if job.status in {"paused", "pause_requested"}:
        job.status = "resume_requested"
        db.commit()
        if hasattr(signal, "SIGCONT") and _signal_process(job_id, signal.SIGCONT):
            job.status = "running"
            db.commit()
    db.refresh(job)
    return job


def mark_stale_jobs() -> None:
    db = make_session()
    try:
        # Keep queued jobs queued so an external worker can pick them up after API restarts.
        jobs = db.query(AutoPopJob).filter(AutoPopJob.status.in_(["running", "pause_requested", "paused", "resume_requested", "cancel_requested"])).all()
        for job in jobs:
            job.status = "unknown_after_restart"
            job.finished_at = _now()
            job.last_error = "API/worker process restarted before this job reported completion"
        if jobs:
            db.commit()
    finally:
        db.close()


def _tail_lines(path: Path, lines: int) -> list[str]:
    if not path.exists() or not path.is_file():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        all_lines = handle.readlines()
    return [line.rstrip("\n") for line in all_lines[-max(1, min(lines, 1000)):]]


def _parse_progress(lines: list[str]) -> tuple[str | None, str | None, dict[str, Any]]:
    current_category = None
    current_series = None
    progress: dict[str, Any] = {}
    category_re = re.compile(r"\[(\d+)/(\d+)\]\s+Opening category:\s+(.+)$")
    series_re = re.compile(r"\[(\d+)/(\d+)\]\s+EOX check:\s+(.+)$")
    saved_re = re.compile(r"Saved category (.+?) to database:")
    for line in lines:
        if match := category_re.search(line):
            current_category = match.group(3)
            progress["category_index"] = int(match.group(1))
            progress["category_total"] = int(match.group(2))
        if match := series_re.search(line):
            current_series = match.group(3)
            progress["series_index"] = int(match.group(1))
            progress["series_total"] = int(match.group(2))
        if match := saved_re.search(line):
            progress["last_saved_category"] = match.group(1)
    return current_category, current_series, progress


def job_log_response(db: Session, job_id: int, *, lines: int = 200) -> JobLogResponse | None:
    job = db.get(AutoPopJob, job_id)
    if not job:
        return None
    log_lines = _tail_lines(Path(job.log_file), lines) if job.log_file else []
    current_category, current_series, progress = _parse_progress(log_lines)
    return JobLogResponse(
        job_id=job_id,
        status=job.status,
        log_file=job.log_file,
        lines=log_lines,
        current_category=current_category,
        current_series=current_series,
        progress=progress,
    )


def clear_old_jobs(db: Session, *, delete_logs: bool = False, statuses: list[str] | None = None) -> dict[str, Any]:
    safe_statuses = statuses or ["completed", "failed", "cancelled", "skipped", "unknown_after_restart"]
    jobs = db.query(AutoPopJob).filter(AutoPopJob.status.in_(safe_statuses)).all()
    deleted_logs = 0
    for job in jobs:
        if delete_logs and job.log_file:
            try:
                path = Path(job.log_file)
                if path.exists() and path.is_file():
                    path.unlink()
                    deleted_logs += 1
            except Exception:
                logger.warning("Could not delete Auto_Pop log file for job %s", job.id)
        db.delete(job)
    deleted_jobs = len(jobs)
    db.commit()
    create_system_event(
        db,
        level="info",
        event_type="autopop_jobs_cleared",
        source="backend",
        message=f"Cleared {deleted_jobs} old Auto_Pop job(s)",
        payload={"deleted_jobs": deleted_jobs, "deleted_logs": deleted_logs, "statuses": safe_statuses},
        commit=True,
    )
    running_count = db.query(AutoPopJob).filter(AutoPopJob.status.in_(list(RUNNING_STATUSES))).count()
    return {"deleted_jobs": deleted_jobs, "deleted_logs": deleted_logs, "statuses": safe_statuses, "skipped_running": running_count}
