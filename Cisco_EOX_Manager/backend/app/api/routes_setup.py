from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
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
    SetupStatusResponse,
)
from app.services.cisco_api_client import CiscoApiClient, CiscoApiError
from app.services.credential_store import CredentialStore

router = APIRouter(prefix="/setup", tags=["Setup"])


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
