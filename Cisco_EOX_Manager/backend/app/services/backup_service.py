from __future__ import annotations

import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy.engine import make_url

from app.core.runtime_config import effective_database_url
from app.schemas import BackupInfo

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
BACKUP_DIR = PRODUCT_ROOT / "data" / "backups"


def _database_type(url: str) -> str:
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgres"):
        return "postgresql"
    return "unknown"


def _sqlite_path(url: str) -> Path:
    raw = url.replace("sqlite:///", "", 1)
    return Path(raw)


def _backup_info(path: Path, database_type: str) -> BackupInfo:
    created = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) if path.exists() else None
    return BackupInfo(
        file_name=path.name,
        path=str(path),
        database_type=database_type,
        size_mb=round(path.stat().st_size / 1024 / 1024, 2) if path.exists() else 0,
        created_at=created,
    )


def list_backups() -> list[BackupInfo]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    items: list[BackupInfo] = []
    for path in sorted(BACKUP_DIR.glob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        if path.suffix in {".db", ".sqlite", ".dump", ".sql"}:
            db_type = "postgresql" if path.suffix in {".dump", ".sql"} else "sqlite"
            items.append(_backup_info(path, db_type))
    return items



def _libpq_url(url: str) -> str:
    parsed = make_url(url)
    driver = "postgresql" if parsed.drivername.startswith("postgres") else parsed.drivername
    if "+" in driver:
        driver = driver.split("+", 1)[0]
    return str(parsed.set(drivername=driver))

def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def create_backup() -> BackupInfo:
    url = effective_database_url()
    db_type = _database_type(url)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    if db_type == "sqlite":
        src = _sqlite_path(url)
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"SQLite DB file not found: {src}")
        dest = BACKUP_DIR / f"eox_sqlite_{_timestamp()}.db"
        src_conn = sqlite3.connect(src)
        try:
            dst_conn = sqlite3.connect(dest)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
        finally:
            src_conn.close()
        return _backup_info(dest, db_type)

    if db_type == "postgresql":
        dest = BACKUP_DIR / f"eox_postgres_{_timestamp()}.dump"
        command = ["pg_dump", "-Fc", "--no-owner", "--no-acl", "-f", str(dest), _libpq_url(url)]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=3600, check=False)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="pg_dump is not installed in the API container. Rebuild with the updated Dockerfile.") from exc
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"pg_dump failed: {result.stderr or result.stdout}")
        return _backup_info(dest, db_type)

    raise HTTPException(status_code=400, detail=f"Unsupported database type for backup: {db_type}")


def restore_backup(file_name: str, *, confirm: bool = False) -> BackupInfo:
    if not confirm:
        raise HTTPException(status_code=400, detail="Set confirm=true to restore a backup. This replaces current data.")
    if "/" in file_name or ".." in file_name:
        raise HTTPException(status_code=400, detail="Invalid backup file name")
    path = BACKUP_DIR / file_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")
    url = effective_database_url()
    db_type = _database_type(url)
    if db_type == "sqlite":
        dest = _sqlite_path(url)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        return _backup_info(path, "sqlite")
    if db_type == "postgresql":
        command = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-acl", "-d", _libpq_url(url), str(path)]
        try:
            result = subprocess.run(command, text=True, capture_output=True, timeout=3600, check=False)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=500, detail="pg_restore is not installed in the API container. Rebuild with the updated Dockerfile.") from exc
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"pg_restore failed: {result.stderr or result.stdout}")
        return _backup_info(path, "postgresql")
    raise HTTPException(status_code=400, detail=f"Unsupported database type for restore: {db_type}")
