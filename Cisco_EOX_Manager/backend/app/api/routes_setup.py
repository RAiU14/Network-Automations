from __future__ import annotations

import os
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.runtime_config import (
    build_postgres_url,
    build_sqlite_url,
    database_url_hint,
    effective_database_url,
    env_export_path,
    read_runtime_config,
    write_runtime_database_url,
)
from app.db.session import check_db_connection, get_db, init_db, make_session, reset_engine
from app.schemas import (
    CiscoSetupRequest,
    CiscoSetupResponse,
    DatabaseSetupRequest,
    DatabaseSetupResponse,
    PostgresBootstrapRequest,
    PostgresBootstrapResponse,
    PostgresDefaultsResponse,
    SetupStatusResponse,
)
from app.services.cisco_api_client import CiscoApiClient, CiscoApiError
from app.services.credential_store import CredentialStore

router = APIRouter(prefix="/setup", tags=["Setup"])


_POSTGRES_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_-]{0,62}$")


def _clean_postgres_identifier(value: str, *, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not _POSTGRES_IDENTIFIER_RE.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid PostgreSQL {field_name}. Use 1-63 letters, numbers, underscores, or hyphens; it must not start with a hyphen.",
        )
    return cleaned


def _quote_pg_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _docker_postgres_defaults() -> dict[str, str | int]:
    return {
        "host": "postgres",
        "port": 5432,
        "host_port": int(os.getenv("EOX_POSTGRES_HOST_PORT", "5433")),
        "database": os.getenv("EOX_POSTGRES_DB", "eox_cache"),
        "username": os.getenv("EOX_POSTGRES_USER", "eox_user"),
        "password": os.getenv("EOX_POSTGRES_PASSWORD", "eox_password"),
    }


def _create_postgres_database_if_needed(request: PostgresBootstrapRequest) -> tuple[bool, bool, str | None]:
    database = _clean_postgres_identifier(request.database, field_name="database name")
    maintenance_database = _clean_postgres_identifier(request.maintenance_database, field_name="maintenance database name")
    maintenance_url = build_postgres_url(
        host=request.host,
        port=request.port,
        database=maintenance_database,
        username=request.username,
        password=request.password,
    )
    engine = create_engine(maintenance_url, future=True, pool_pre_ping=True, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as connection:
            exists = bool(connection.execute(text("SELECT 1 FROM pg_database WHERE datname = :database"), {"database": database}).scalar())
            if exists:
                return False, True, None
            if request.test_only or not request.create_database:
                return False, False, None
            connection.execute(text(f"CREATE DATABASE {_quote_pg_identifier(database)}"))
            return True, False, None
    except Exception as exc:
        return False, False, str(exc)
    finally:
        engine.dispose()


def _sqlite_setup_response(*, test_only: bool = False) -> DatabaseSetupResponse:
    database_url = build_sqlite_url(path=None)
    ok, error = check_db_connection(database_url)
    if not ok:
        return DatabaseSetupResponse(
            ok=False,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(database_url),
            message=f"SQLite setup failed: {error}",
            env_file=None,
        )
    if test_only:
        return DatabaseSetupResponse(
            ok=True,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(database_url),
            message="SQLite connection test passed",
            env_file=None,
        )
    runtime = write_runtime_database_url(database_url, write_env_file=True)
    reset_engine(database_url)
    init_db(database_url)
    return DatabaseSetupResponse(
        ok=True,
        tested=True,
        saved=True,
        initialized=True,
        database_url_hint=database_url_hint(runtime.database_url),
        message="SQLite local database is ready",
        env_file=str(env_export_path()),
    )


@router.get("/status", response_model=SetupStatusResponse)
def setup_status() -> SetupStatusResponse:
    runtime = read_runtime_config()
    db_ready, db_error = check_db_connection()
    if not db_ready:
        return SetupStatusResponse(
            database_ready=False,
            database_error=db_error,
            database_url_hint=database_url_hint(),
            database_config_source=runtime.database_source,
            cisco_credentials_configured=False,
            api_base_url="",
            token_url="",
            has_cached_token=False,
        )

    with make_session() as db:
        try:
            store = CredentialStore(db)
            status = store.status()
        except Exception as exc:
            return SetupStatusResponse(
                database_ready=False,
                database_error=str(exc),
                database_url_hint=database_url_hint(),
                database_config_source=runtime.database_source,
                cisco_credentials_configured=False,
                api_base_url="",
                token_url="",
                has_cached_token=False,
            )
    return SetupStatusResponse(
        database_ready=db_ready,
        database_error=db_error,
        database_url_hint=database_url_hint(),
        database_config_source=runtime.database_source,
        cisco_credentials_configured=bool(status["configured"]),
        client_id_hint=status["client_id_hint"],
        api_base_url=str(status["api_base_url"]),
        token_url=str(status["token_url"]),
        has_cached_token=bool(status["has_cached_token"]),
    )


@router.post("/database/use-sqlite", response_model=DatabaseSetupResponse)
def configure_sqlite_default() -> DatabaseSetupResponse:
    return _sqlite_setup_response(test_only=False)




@router.get("/database/postgres-defaults", response_model=PostgresDefaultsResponse)
def postgres_defaults() -> PostgresDefaultsResponse:
    defaults = _docker_postgres_defaults()
    internal_url = build_postgres_url(
        host=str(defaults["host"]),
        port=int(defaults["port"]),
        database=str(defaults["database"]),
        username=str(defaults["username"]),
        password=str(defaults["password"]),
    )
    host_url = build_postgres_url(
        host="127.0.0.1",
        port=int(defaults["host_port"]),
        database=str(defaults["database"]),
        username=str(defaults["username"]),
        password=str(defaults["password"]),
    )
    return PostgresDefaultsResponse(
        host=str(defaults["host"]),
        port=int(defaults["port"]),
        host_port=int(defaults["host_port"]),
        database=str(defaults["database"]),
        username=str(defaults["username"]),
        password=str(defaults["password"]),
        internal_url_hint=database_url_hint(internal_url),
        host_url_hint=database_url_hint(host_url),
        notes=[
            "Use postgres:5432 from the API container and GUI setup.",
            "Use 127.0.0.1:5433 only from the server shell or external database tools.",
            "Click Save + Create Tables to initialize the app schema without running shell commands.",
        ],
    )


@router.post("/database/use-docker-postgres", response_model=PostgresBootstrapResponse)
def configure_docker_postgres_default() -> PostgresBootstrapResponse:
    defaults = _docker_postgres_defaults()
    request = PostgresBootstrapRequest(
        host=str(defaults["host"]),
        port=int(defaults["port"]),
        database=str(defaults["database"]),
        username=str(defaults["username"]),
        password=str(defaults["password"]),
        create_database=True,
        initialize_tables=True,
        save_as_active=True,
        write_env_file=True,
        test_only=False,
    )
    return bootstrap_postgres_database(request)


@router.post("/database/postgres/bootstrap", response_model=PostgresBootstrapResponse)
def bootstrap_postgres_database(request: PostgresBootstrapRequest) -> PostgresBootstrapResponse:
    database_name = _clean_postgres_identifier(request.database, field_name="database name")
    target_url = build_postgres_url(
        host=request.host,
        port=request.port,
        database=database_name,
        username=request.username,
        password=request.password,
    )
    created, existed, create_error = _create_postgres_database_if_needed(request)
    if create_error:
        return PostgresBootstrapResponse(
            ok=False,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(target_url),
            message=f"PostgreSQL server/database setup failed: {create_error}",
            env_file=None,
            database_created=False,
            database_existed=False,
            tables_initialized=False,
            active_database_saved=False,
            database_name=database_name,
        )

    if request.test_only and not existed and not created:
        return PostgresBootstrapResponse(
            ok=True,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(target_url),
            message="PostgreSQL server connection passed. Database does not exist yet; click Save + Create Tables to create it.",
            env_file=None,
            database_created=False,
            database_existed=False,
            tables_initialized=False,
            active_database_saved=False,
            database_name=database_name,
        )

    ok, error = check_db_connection(target_url)
    if not ok:
        return PostgresBootstrapResponse(
            ok=False,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(target_url),
            message=f"PostgreSQL database connection failed: {error}",
            env_file=None,
            database_created=created,
            database_existed=existed,
            tables_initialized=False,
            active_database_saved=False,
            database_name=database_name,
        )

    if request.test_only:
        return PostgresBootstrapResponse(
            ok=True,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(target_url),
            message="PostgreSQL database connection test passed",
            env_file=None,
            database_created=created,
            database_existed=existed or created,
            tables_initialized=False,
            active_database_saved=False,
            database_name=database_name,
        )

    tables_initialized = False
    if request.initialize_tables:
        init_db(target_url)
        tables_initialized = True

    runtime = None
    active_saved = False
    if request.save_as_active:
        runtime = write_runtime_database_url(target_url, write_env_file=request.write_env_file)
        reset_engine(target_url)
        active_saved = True

    message_parts = ["PostgreSQL ready"]
    if created:
        message_parts.append("database created")
    elif existed:
        message_parts.append("database already existed")
    if tables_initialized:
        message_parts.append("tables initialized")
    if active_saved:
        message_parts.append("saved as active app database")

    return PostgresBootstrapResponse(
        ok=True,
        tested=True,
        saved=active_saved,
        initialized=tables_initialized,
        database_url_hint=database_url_hint(runtime.database_url if runtime else target_url),
        message="; ".join(message_parts),
        env_file=str(env_export_path()) if active_saved and request.write_env_file else None,
        database_created=created,
        database_existed=existed or created,
        tables_initialized=tables_initialized,
        active_database_saved=active_saved,
        database_name=database_name,
    )


@router.post("/database/configure", response_model=DatabaseSetupResponse)
def configure_database(request: DatabaseSetupRequest) -> DatabaseSetupResponse:
    if request.database_type == "sqlite":
        database_url = build_sqlite_url(path=request.sqlite_path)
    elif request.database_type == "url" or request.database_url:
        if not request.database_url:
            raise HTTPException(status_code=400, detail="Database URL is required for Advanced URL mode")
        database_url = request.database_url
    else:
        database_url = build_postgres_url(
            host=request.host,
            port=request.port,
            database=request.database,
            username=request.username,
            password=request.password,
        )
    ok, error = check_db_connection(database_url)
    if not ok:
        return DatabaseSetupResponse(
            ok=False,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(database_url),
            message=f"Database connection failed: {error}",
            env_file=None,
        )
    if request.test_only:
        return DatabaseSetupResponse(
            ok=True,
            tested=True,
            saved=False,
            initialized=False,
            database_url_hint=database_url_hint(database_url),
            message="Database connection test passed",
            env_file=None,
        )

    runtime = write_runtime_database_url(database_url, write_env_file=request.write_env_file)
    reset_engine(database_url)
    initialized = False
    if request.initialize_after_save:
        init_db(database_url)
        initialized = True
    return DatabaseSetupResponse(
        ok=True,
        tested=True,
        saved=True,
        initialized=initialized,
        database_url_hint=database_url_hint(runtime.database_url),
        message="Database setup saved" + (" and tables initialized" if initialized else ""),
        env_file=str(env_export_path()) if request.write_env_file else None,
    )


@router.post("/database/initialize")
def initialize_database() -> dict[str, str]:
    try:
        init_db()
        return {"status": "ok", "message": "Database tables are ready", "database_url": database_url_hint(effective_database_url())}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database initialization failed: {exc}") from exc


@router.post("/cisco", response_model=CiscoSetupResponse)
def configure_cisco(request: CiscoSetupRequest, db: Session = Depends(get_db)) -> CiscoSetupResponse:
    if not any([request.client_id, request.client_secret, request.access_token, request.api_base_url, request.token_url]):
        raise HTTPException(status_code=400, detail="Provide at least one Cisco setup value to save")

    store = CredentialStore(db)
    store.setup_cisco_credentials(
        client_id=request.client_id,
        client_secret=request.client_secret,
        access_token=request.access_token,
        token_expires_in_seconds=request.token_expires_in_seconds,
        api_base_url=request.api_base_url,
        token_url=request.token_url,
        grant_type=request.grant_type,
    )

    token_cached = bool(store.get_valid_access_token())
    if request.test_connection:
        try:
            CiscoApiClient(db).test_connection()
            token_cached = True
            return CiscoSetupResponse(
                configured=True,
                tested=True,
                message="Cisco API credentials saved and token test passed",
                token_cached=token_cached,
            )
        except CiscoApiError as exc:
            raise HTTPException(status_code=400, detail=f"Saved credentials, but Cisco token test failed: {exc}") from exc

    return CiscoSetupResponse(
        configured=store.cisco_credentials_configured(),
        tested=False,
        message="Cisco API setup saved",
        token_cached=token_cached,
    )
