from __future__ import annotations

from collections.abc import Generator
from threading import Lock

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.runtime_config import effective_database_url

_engine_lock = Lock()
_engine_cache: dict[str, Engine] = {}
_current_url: str | None = None

SQLITE_BAD_JSON_INDEXES = (
    "ix_product_eox_payload_gin",
    "ix_product_eox_raw_gin",
    "ix_eox_affected_payload_gin",
    "ix_eox_affected_raw_gin",
    "ix_eox_table_rows_gin",
    "ix_eox_table_raw_gin",
    "ix_eox_table_headers_gin",
    "ix_eox_ann_payload_gin",
    "ix_eox_ann_raw_gin",
    "ix_pid_catalog_payload_gin",
    "ix_lookup_history_snapshot_gin",
    "ix_system_events_payload_gin",
    "ix_seed_runs_stats_gin",
    "ix_auto_pop_checkpoint_stats_gin",
    "ix_auto_pop_jobs_params_gin",
    "ix_auto_pop_jobs_stats_gin",
    "ix_export_jobs_params_gin",
)

POSTGRES_JSONB_INDEXES = (
    ("ix_product_eox_payload_gin", "product_eox", "payload"),
    ("ix_product_eox_raw_gin", "product_eox", "raw_response"),
    ("ix_eox_affected_payload_gin", "eox_affected_products", "payload"),
    ("ix_eox_table_rows_gin", "eox_announcement_tables", "rows"),
    ("ix_eox_ann_payload_gin", "eox_announcements", "payload"),
)


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return effective_database_url()


def _is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def _is_postgres_url(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres")


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA cache_size=-32768")
        cursor.close()


def get_engine(database_url: str | None = None) -> Engine:
    global _current_url
    url = database_url or get_database_url()
    with _engine_lock:
        engine = _engine_cache.get(url)
        if engine is None:
            if _is_sqlite_url(url):
                connect_args = {"check_same_thread": False, "timeout": 60}
                engine = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
                _configure_sqlite(engine)
            else:
                engine = create_engine(url, future=True, pool_pre_ping=True, pool_size=5, max_overflow=5)
            _engine_cache[url] = engine
        _current_url = url
        return engine


def reset_engine(database_url: str | None = None) -> None:
    global _current_url
    url = database_url or get_database_url()
    with _engine_lock:
        engine = _engine_cache.pop(url, None)
        if engine is not None:
            engine.dispose()
        _current_url = None


def make_session(database_url: str | None = None) -> Session:
    SessionLocal = sessionmaker(bind=get_engine(database_url), autoflush=False, autocommit=False, future=True, expire_on_commit=False)
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    db = make_session()
    try:
        yield db
    finally:
        db.close()


def _cleanup_sqlite_legacy_indexes(engine: Engine) -> None:
    with engine.begin() as connection:
        for index_name in SQLITE_BAD_JSON_INDEXES:
            connection.execute(text(f'DROP INDEX IF EXISTS "{index_name}"'))


def _ensure_postgres_jsonb_indexes(engine: Engine) -> None:
    with engine.begin() as connection:
        for index_name, table_name, column_name in POSTGRES_JSONB_INDEXES:
            connection.execute(text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" USING gin ("{column_name}")'))


def init_db(database_url: str | None = None) -> None:
    from app.db import models  # noqa: F401

    url = database_url or get_database_url()
    engine = get_engine(url)
    Base.metadata.create_all(bind=engine)
    if _is_sqlite_url(url):
        _cleanup_sqlite_legacy_indexes(engine)
    elif _is_postgres_url(url):
        _ensure_postgres_jsonb_indexes(engine)


def check_db_connection(database_url: str | None = None) -> tuple[bool, str | None]:
    try:
        with get_engine(database_url).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)
