from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import extract_token, get_auth_status, save_admin_token, set_runtime_auth_enabled, verify_token
from app.core.rate_limit import get_rate_limit_settings

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthStatusResponse(BaseModel):
    enabled: bool
    token_configured: bool
    required: bool
    source: str
    bootstrap_open: bool
    updated_at: str | None = None
    env_forced_enabled: bool = False


class RateLimitStatusResponse(BaseModel):
    enabled: bool
    read_per_minute: int
    write_per_minute: int
    autopop_jobs_per_hour: int
    exempt_paths: list[str]


class SecurityStatusResponse(BaseModel):
    auth: AuthStatusResponse
    rate_limit: RateLimitStatusResponse


class BootstrapAuthRequest(BaseModel):
    admin_token: str = Field(..., min_length=12)
    current_token: str | None = None
    enable_auth: bool = True


class VerifyAuthRequest(BaseModel):
    admin_token: str | None = None


class AuthEnableRequest(BaseModel):
    enabled: bool = True
    current_token: str | None = None


class AuthActionResponse(BaseModel):
    ok: bool
    message: str
    status: AuthStatusResponse


def _status_response() -> AuthStatusResponse:
    status = get_auth_status()
    return AuthStatusResponse(
        enabled=status.enabled,
        token_configured=status.token_configured,
        required=status.required,
        source=status.source,
        bootstrap_open=status.bootstrap_open,
        updated_at=status.updated_at,
        env_forced_enabled=status.env_forced_enabled,
    )


def _rate_limit_status_response() -> RateLimitStatusResponse:
    settings = get_rate_limit_settings()
    return RateLimitStatusResponse(
        enabled=settings.enabled,
        read_per_minute=settings.read_per_minute,
        write_per_minute=settings.write_per_minute,
        autopop_jobs_per_hour=settings.autopop_jobs_per_hour,
        exempt_paths=list(settings.exempt_paths),
    )


def _require_current_token(http_request: Request, supplied: str | None = None) -> None:
    status = get_auth_status()
    if status.required and not verify_token(supplied or extract_token(http_request)):
        raise HTTPException(status_code=401, detail="Current admin token is required")


@router.get("/status", response_model=AuthStatusResponse)
def auth_status() -> AuthStatusResponse:
    return _status_response()


@router.get("/security-status", response_model=SecurityStatusResponse)
def security_status() -> SecurityStatusResponse:
    return SecurityStatusResponse(auth=_status_response(), rate_limit=_rate_limit_status_response())


@router.post("/bootstrap", response_model=AuthActionResponse)
def bootstrap_auth(request: BootstrapAuthRequest, http_request: Request) -> AuthActionResponse:
    _require_current_token(http_request, request.current_token)
    try:
        save_admin_token(request.admin_token, enable_auth=request.enable_auth)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    message = "Admin token saved and API protection enabled" if request.enable_auth else "Admin token saved; API protection is disabled"
    return AuthActionResponse(ok=True, message=message, status=_status_response())


@router.post("/verify", response_model=AuthActionResponse)
def verify_auth(request: VerifyAuthRequest, http_request: Request) -> AuthActionResponse:
    token = request.admin_token or extract_token(http_request)
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return AuthActionResponse(ok=True, message="Admin token accepted", status=_status_response())


@router.post("/enabled", response_model=AuthActionResponse)
def set_auth_enabled(request: AuthEnableRequest, http_request: Request) -> AuthActionResponse:
    _require_current_token(http_request, request.current_token)
    status = get_auth_status()
    if request.enabled and not status.token_configured:
        raise HTTPException(status_code=400, detail="Create an admin token before enabling API protection")
    new_status = set_runtime_auth_enabled(request.enabled)
    if request.enabled:
        message = "API protection enabled"
    elif new_status.env_forced_enabled:
        message = "Runtime API protection disabled, but EOX_AUTH_ENABLED=true in the environment still forces protection on"
    else:
        message = "API protection disabled"
    return AuthActionResponse(ok=True, message=message, status=_status_response())
