from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import extract_token, get_auth_status, save_admin_token, verify_token

router = APIRouter(prefix="/auth", tags=["Auth"])


class AuthStatusResponse(BaseModel):
    enabled: bool
    token_configured: bool
    required: bool
    source: str
    bootstrap_open: bool
    updated_at: str | None = None


class BootstrapAuthRequest(BaseModel):
    admin_token: str = Field(..., min_length=12)
    current_token: str | None = None


class VerifyAuthRequest(BaseModel):
    admin_token: str | None = None


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
    )


@router.get("/status", response_model=AuthStatusResponse)
def auth_status() -> AuthStatusResponse:
    return _status_response()


@router.post("/bootstrap", response_model=AuthActionResponse)
def bootstrap_auth(request: BootstrapAuthRequest, http_request: Request) -> AuthActionResponse:
    status = get_auth_status()
    if status.required:
        supplied = request.current_token or extract_token(http_request)
        if not verify_token(supplied):
            raise HTTPException(status_code=401, detail="Current admin token is required to rotate the token")
    try:
        save_admin_token(request.admin_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuthActionResponse(ok=True, message="Admin token saved", status=_status_response())


@router.post("/verify", response_model=AuthActionResponse)
def verify_auth(request: VerifyAuthRequest, http_request: Request) -> AuthActionResponse:
    token = request.admin_token or extract_token(http_request)
    if not verify_token(token):
        raise HTTPException(status_code=401, detail="Invalid admin token")
    return AuthActionResponse(ok=True, message="Admin token accepted", status=_status_response())
