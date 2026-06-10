from __future__ import annotations

import pytest


def test_rows_to_csv_has_headers():
    pytest.importorskip("sqlalchemy")
    from app.services.export_service import rows_to_csv

    payload = rows_to_csv([{"pid": "C9300-24T", "status": "eox_available"}]).decode("utf-8-sig")
    assert "pid" in payload
    assert "C9300-24T" in payload
