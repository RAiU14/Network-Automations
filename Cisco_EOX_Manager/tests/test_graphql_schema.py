from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("strawberry")

from app.graphql.schema import schema


def test_graphql_schema_exposes_database_retrieval_fields() -> None:
    schema_text = schema.as_str()
    assert "productJson" in schema_text
    assert "productEvidence" in schema_text
    assert "announcementTables" in schema_text
    assert "affectedProducts" in schema_text
    assert "autoPopCheckpoints" in schema_text
    assert "systemEvents" in schema_text
