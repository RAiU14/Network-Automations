from __future__ import annotations

import importlib


def test_auth_bootstrap_file_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("EOX_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EOX_AUTH_ENABLED", "true")
    monkeypatch.setenv("EOX_AUTH_CONFIG_FILE", str(tmp_path / ".eox_auth.env"))
    monkeypatch.delenv("EOX_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("EOX_ADMIN_TOKEN_HASH", raising=False)
    auth = importlib.import_module("app.core.auth")
    status = auth.save_admin_token("super-secret-token")
    assert status.token_configured is True
    assert status.required is True
    assert auth.verify_token("super-secret-token") is True
    assert auth.verify_token("wrong-token") is False


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("EOX_AUTH_ENABLED", raising=False)
    auth = importlib.import_module("app.core.auth")
    assert auth.auth_enabled() is False
    assert auth.verify_token(None) is True
