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


def test_runtime_auth_file_can_enable_without_env_true(tmp_path, monkeypatch):
    monkeypatch.delenv("EOX_AUTH_ENABLED", raising=False)
    monkeypatch.setenv("EOX_AUTH_CONFIG_FILE", str(tmp_path / ".eox_auth.env"))
    monkeypatch.delenv("EOX_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("EOX_ADMIN_TOKEN_HASH", raising=False)
    import importlib
    auth = importlib.import_module("app.core.auth")
    status = auth.save_admin_token("runtime-secret-token", enable_auth=True)
    assert status.enabled is True
    assert status.required is True
    assert auth.verify_token("runtime-secret-token") is True


def test_runtime_auth_can_be_disabled_when_env_not_forced(tmp_path, monkeypatch):
    monkeypatch.delenv("EOX_AUTH_ENABLED", raising=False)
    monkeypatch.setenv("EOX_AUTH_CONFIG_FILE", str(tmp_path / ".eox_auth.env"))
    import importlib
    auth = importlib.import_module("app.core.auth")
    auth.save_admin_token("runtime-secret-token", enable_auth=True)
    status = auth.set_runtime_auth_enabled(False)
    assert status.enabled is False
    assert status.required is False
