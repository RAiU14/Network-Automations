from __future__ import annotations

import os
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.core.runtime_config import database_url_hint, effective_database_url
from app.db.models import (
    AutoPopJob,
    EoxAffectedProduct,
    EoxAnnouncement,
    EoxAnnouncementTable,
    PidCatalog,
    ProductEox,
    SystemEvent,
)
from app.db.session import check_db_connection, get_engine, make_session
from app.schemas import DatabaseHealthResponse, SystemCapabilitiesResponse, TableStorageInfo, WorkerRecommendation

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PRODUCT_ROOT / "data"
CORE_TABLES = {
    "product_eox": ProductEox,
    "pid_catalog": PidCatalog,
    "eox_announcements": EoxAnnouncement,
    "eox_announcement_tables": EoxAnnouncementTable,
    "eox_affected_products": EoxAffectedProduct,
    "auto_pop_jobs": AutoPopJob,
    "system_events": SystemEvent,
}


def _database_type(url: str) -> str:
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgres"):
        return "postgresql"
    return "unknown"


def _sqlite_path(url: str) -> Path | None:
    if not url.startswith("sqlite"):
        return None
    raw = url.replace("sqlite:///", "", 1)
    return Path(raw)


def _meminfo() -> tuple[float | None, float | None]:
    path = Path("/proc/meminfo")
    if not path.exists():
        return None, None
    values: dict[str, int] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            values[parts[0].rstrip(":")] = int(parts[1])
    total = values.get("MemTotal")
    available = values.get("MemAvailable", values.get("MemFree"))
    return (round(total / 1024 / 1024, 2) if total else None, round(available / 1024 / 1024, 2) if available else None)


def get_system_capabilities() -> SystemCapabilitiesResponse:
    url = effective_database_url()
    db_type = _database_type(url)
    cpu = os.cpu_count() or 1
    mem_total, mem_available = _meminfo()
    disk = shutil.disk_usage(DATA_DIR if DATA_DIR.exists() else PRODUCT_ROOT)
    disk_total = round(disk.total / 1024 / 1024 / 1024, 2)
    disk_free = round(disk.free / 1024 / 1024 / 1024, 2)
    notes: list[str] = []

    if db_type == "sqlite":
        low = 1
        optimal = max(1, min(2, cpu))
        aggressive = max(optimal, min(4, cpu * 2))
        max_allowed = 4
        delay = 5.0
        category_break = 60.0
        notes.append("SQLite detected: DB writes are serialized, so worker recommendations stay conservative.")
    else:
        low = max(1, min(2, cpu))
        optimal = max(low, min(4, cpu * 2))
        aggressive = max(optimal, min(8, cpu * 4))
        max_allowed = 8
        delay = 3.0 if cpu >= 4 else 5.0
        category_break = 30.0 if cpu >= 4 else 60.0
        notes.append("PostgreSQL detected: more concurrent parser work is safer than SQLite, but Cisco request delay still matters.")

    if cpu <= 2:
        notes.append("Low-core server detected. Use recommended workers unless you are intentionally stress testing.")
    if mem_available is not None and mem_available < 2:
        notes.append("Low available memory detected. Avoid aggressive workers and large exports.")
    if disk_free < 10:
        notes.append("Less than 10 GB free disk space. Back up and monitor DB growth before full crawls.")

    return SystemCapabilitiesResponse(
        cpu_logical=cpu,
        memory_total_gb=mem_total,
        memory_available_gb=mem_available,
        disk_total_gb=disk_total,
        disk_free_gb=disk_free,
        database_type=db_type,
        api_workers_configured=int(os.getenv("EOX_API_WORKERS", "1")),
        autopop_execution_mode=os.getenv("EOX_AUTOPOP_EXECUTION_MODE", "local"),
        recommended_workers=WorkerRecommendation(low=low, optimal=optimal, aggressive=aggressive, max_allowed=max_allowed),
        recommended_delay=delay,
        recommended_category_break=category_break,
        risk_notes=notes,
    )


def _counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    with make_session() as db:
        for name, model in CORE_TABLES.items():
            try:
                counts[name] = db.query(model).count()
            except Exception:
                counts[name] = -1
    return counts


def _last_updated() -> datetime | None:
    latest: datetime | None = None
    with get_engine().connect() as conn:
        for table, column in [
            ("product_eox", "updated_at"),
            ("pid_catalog", "updated_at"),
            ("eox_announcements", "updated_at"),
            ("eox_announcement_tables", "updated_at"),
            ("eox_affected_products", "updated_at"),
            ("auto_pop_jobs", "updated_at"),
            ("system_events", "created_at"),
        ]:
            try:
                value = conn.execute(text(f'SELECT MAX({column}) FROM "{table}"')).scalar()
            except Exception:
                value = None
            if isinstance(value, str):
                try:
                    value = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    value = None
            if isinstance(value, datetime):
                if latest is None or value > latest:
                    latest = value
    return latest


def _sqlite_storage(url: str, counts: dict[str, int]) -> tuple[float | None, dict[str, float], list[TableStorageInfo], list[str]]:
    path = _sqlite_path(url)
    files: dict[str, float] = {}
    warnings: list[str] = []
    db_size = None
    if path:
        for suffix in ["", "-wal", "-shm", "-journal"]:
            file_path = Path(str(path) + suffix)
            if file_path.exists():
                files[file_path.name] = round(file_path.stat().st_size / 1024 / 1024, 2)
        if path.exists():
            db_size = round(path.stat().st_size / 1024 / 1024, 2)
            if db_size > 5120:
                warnings.append("SQLite database is larger than 5 GB. PostgreSQL is recommended for full production data.")
    storage: list[TableStorageInfo] = []
    try:
        sqlite_path = path or Path("")
        conn = sqlite3.connect(sqlite_path)
        rows = conn.execute("select name, sum(pgsize) as bytes from dbstat group by name order by bytes desc limit 30").fetchall()
        for name, size_bytes in rows:
            storage.append(TableStorageInfo(name=name, row_count=counts.get(name), total_size_mb=round((size_bytes or 0) / 1024 / 1024, 2)))
        conn.close()
    except Exception:
        pass
    return db_size, files, storage, warnings


def _postgres_storage(counts: dict[str, int]) -> tuple[float | None, list[TableStorageInfo], list[str]]:
    warnings: list[str] = []
    storage: list[TableStorageInfo] = []
    db_size = None
    with get_engine().connect() as conn:
        try:
            db_size = round((conn.execute(text("select pg_database_size(current_database())")).scalar() or 0) / 1024 / 1024, 2)
        except Exception:
            db_size = None
        try:
            rows = conn.execute(text("""
                select relname,
                       pg_relation_size(c.oid) as table_bytes,
                       pg_indexes_size(c.oid) as index_bytes,
                       pg_total_relation_size(c.oid) as total_bytes
                from pg_class c
                join pg_namespace n on n.oid = c.relnamespace
                where n.nspname = 'public' and c.relkind = 'r'
                order by pg_total_relation_size(c.oid) desc
                limit 30
            """)).all()
            for name, table_bytes, index_bytes, total_bytes in rows:
                storage.append(TableStorageInfo(
                    name=name,
                    row_count=counts.get(name),
                    table_size_mb=round((table_bytes or 0) / 1024 / 1024, 2),
                    index_size_mb=round((index_bytes or 0) / 1024 / 1024, 2),
                    total_size_mb=round((total_bytes or 0) / 1024 / 1024, 2),
                ))
        except Exception:
            pass
    return db_size, storage, warnings


def get_database_health() -> DatabaseHealthResponse:
    url = effective_database_url()
    db_type = _database_type(url)
    ok, error = check_db_connection(url)
    disk = shutil.disk_usage(DATA_DIR if DATA_DIR.exists() else PRODUCT_ROOT)
    disk_free = round(disk.free / 1024 / 1024 / 1024, 2)
    if not ok:
        return DatabaseHealthResponse(
            database_type=db_type,
            database_url_hint=database_url_hint(url),
            connection_ok=False,
            connection_error=error,
            disk_free_gb=disk_free,
            warnings=["Database connection failed."],
        )

    counts = _counts()
    last_updated = _last_updated()
    warnings: list[str] = []
    sqlite_files: dict[str, float] = {}
    storage: list[TableStorageInfo] = []
    db_size = None
    if db_type == "sqlite":
        db_size, sqlite_files, storage, extra = _sqlite_storage(url, counts)
        warnings.extend(extra)
    elif db_type == "postgresql":
        db_size, storage, extra = _postgres_storage(counts)
        warnings.extend(extra)
    if disk_free < 10:
        warnings.append("Low disk space: less than 10 GB free.")
    if counts.get("product_eox", 0) and db_size and db_size / max(counts.get("product_eox", 1), 1) > 1:
        warnings.append("Average storage per product looks high. Check raw payloads and indexes if growth seems unusual.")

    return DatabaseHealthResponse(
        database_type=db_type,
        database_url_hint=database_url_hint(url),
        connection_ok=True,
        connection_error=None,
        database_size_mb=db_size,
        last_updated_at=last_updated,
        table_counts=counts,
        table_storage=storage,
        sqlite_files=sqlite_files,
        disk_free_gb=disk_free,
        warnings=warnings,
    )
