from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.core.runtime_config import effective_database_url
from app.db.session import get_engine
from app.schemas import (
    BackupCreateRequest,
    BackupCreateResponse,
    BackupListResponse,
    BackupRestoreRequest,
    DatabaseHealthResponse,
    MaintenanceResponse,
    SystemCapabilitiesResponse,
)
from app.services.backup_service import BACKUP_DIR, create_backup, list_backups, restore_backup
from app.services.system_info import get_database_health, get_system_capabilities

router = APIRouter(prefix="/system", tags=["System"])


@router.get("/capabilities", response_model=SystemCapabilitiesResponse)
def system_capabilities() -> SystemCapabilitiesResponse:
    return get_system_capabilities()


@router.get("/database-health", response_model=DatabaseHealthResponse)
def database_health() -> DatabaseHealthResponse:
    return get_database_health()


@router.post("/maintenance/analyze", response_model=MaintenanceResponse)
def analyze_database() -> MaintenanceResponse:
    url = effective_database_url()
    try:
        with get_engine(url).begin() as conn:
            if url.startswith("sqlite"):
                conn.execute(text("ANALYZE"))
                return MaintenanceResponse(ok=True, message="SQLite ANALYZE completed")
            if url.startswith("postgres"):
                conn.execute(text("ANALYZE"))
                return MaintenanceResponse(ok=True, message="PostgreSQL ANALYZE completed")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analyze failed: {exc}") from exc
    return MaintenanceResponse(ok=False, message="Unsupported database type")


@router.post("/maintenance/vacuum", response_model=MaintenanceResponse)
def vacuum_database() -> MaintenanceResponse:
    url = effective_database_url()
    try:
        engine = get_engine(url)
        if url.startswith("sqlite"):
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("VACUUM"))
            return MaintenanceResponse(ok=True, message="SQLite VACUUM completed. This may reduce file size after large deletes.")
        if url.startswith("postgres"):
            with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
                conn.execute(text("VACUUM ANALYZE"))
            return MaintenanceResponse(ok=True, message="PostgreSQL VACUUM ANALYZE completed")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vacuum failed: {exc}") from exc
    return MaintenanceResponse(ok=False, message="Unsupported database type")


@router.get("/backups", response_model=BackupListResponse)
def backups() -> BackupListResponse:
    return BackupListResponse(items=list_backups())


@router.post("/backups", response_model=BackupCreateResponse)
def create_database_backup(_request: BackupCreateRequest | None = None) -> BackupCreateResponse:
    backup = create_backup()
    return BackupCreateResponse(ok=True, message=f"Backup created: {backup.file_name}", backup=backup)


@router.post("/backups/restore", response_model=BackupCreateResponse)
def restore_database_backup(request: BackupRestoreRequest) -> BackupCreateResponse:
    backup = restore_backup(request.file_name, confirm=request.confirm)
    return BackupCreateResponse(ok=True, message=f"Backup restored: {backup.file_name}", backup=backup)


@router.get("/backups/{file_name}/download")
def download_backup(file_name: str):
    if "/" in file_name or ".." in file_name:
        raise HTTPException(status_code=400, detail="Invalid backup file name")
    path = BACKUP_DIR / file_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    return FileResponse(path, filename=file_name)
