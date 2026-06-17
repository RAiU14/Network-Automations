from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("fastapi")

from fastapi import HTTPException

from app.api.routes_setup import _clean_postgres_identifier, postgres_defaults
from app.schemas import PostgresBootstrapRequest


def test_postgres_defaults_use_docker_internal_port_and_safe_host_port() -> None:
    defaults = postgres_defaults()
    assert defaults.host == "postgres"
    assert defaults.port == 5432
    assert defaults.host_port == 5433
    assert "postgres:5432" in defaults.internal_url_hint
    assert "127.0.0.1:5433" in defaults.host_url_hint


def test_postgres_bootstrap_request_defaults_are_beginner_safe() -> None:
    request = PostgresBootstrapRequest()
    assert request.host == "postgres"
    assert request.port == 5432
    assert request.database == "eox_cache"
    assert request.create_database is True
    assert request.initialize_tables is True
    assert request.save_as_active is True


def test_postgres_database_identifier_rejects_sql_injection() -> None:
    with pytest.raises(HTTPException):
        _clean_postgres_identifier('eox_cache; drop database postgres;', field_name="database name")
