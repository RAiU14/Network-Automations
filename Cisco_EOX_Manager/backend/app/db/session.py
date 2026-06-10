from __future__ import annotations

from collections.abc import Generator
from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.runtime_config import effective_database_url

_engine_lock = Lock()
_engine_cache: dict[str, Engine] = {}
_current_url: str | None = None


class Base(DeclarativeBase):
    pass


def get_database_url() -> str:
    return effective_database_url()


def get_engine(database_url: str | None = None) -> Engine:
    global _current_url
    url = database_url or get_database_url()
    with _engine_lock:
        engine = _engine_cache.get(url)
        if engine is None:
            connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
            engine = create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
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
    SessionLocal = sessionmaker(bind=get_engine(database_url), autoflush=False, autocommit=False, future=True)
    return SessionLocal()


def get_db() -> Generator[Session, None, None]:
    db = make_session()
    try:
        yield db
    finally:
        db.close()


def init_db(database_url: str | None = None) -> None:
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine(database_url))


def check_db_connection(database_url: str | None = None) -> tuple[bool, str | None]:
    try:
        with get_engine(database_url).connect() as connection:
            connection.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)
