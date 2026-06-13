from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")
from sqlalchemy import text

from app.db.models import EoxAffectedProduct, EoxAnnouncementTable, ProductEox
from app.db.session import init_db, make_session
from app.services.seed_persistence import SeedPersistenceService


def _seed_with_large_table(pid_count: int = 20):
    rows = []
    for index in range(pid_count):
        rows.append(
            {
                "row_index": index,
                "columns": {
                    "End-of-Sale Product Part Number": f"PID-{index}",
                    "Product Description": "Large row description " + ("x" * 200),
                    "Replacement Product Part Number": f"PID-{index}-R",
                },
                "cells": [f"PID-{index}", "Large row description " + ("x" * 200), f"PID-{index}-R"],
            }
        )
    table = {
        "table_index": 2,
        "heading": "Affected products",
        "headers": ["End-of-Sale Product Part Number", "Product Description", "Replacement Product Part Number"],
        "rows": rows,
    }
    records = []
    for index in range(pid_count):
        row = rows[index]
        records.append(
            {
                "pid": f"PID-{index}",
                "technology": "Test",
                "source": "scraper",
                "announcement_name": "Large test announcement",
                "announcement_url": "https://example.test/eox-large",
                "product_name": row["columns"]["Product Description"],
                "payload": {
                    "PID": f"PID-{index}",
                    "ProductIDDescription": row["columns"]["Product Description"],
                    "End-of-Sale Date": "January 1, 2030",
                    "Last Date of Support": "January 1, 2035",
                    "EOXAnnouncementURL": "https://example.test/eox-large",
                    "affected_product_row": {"table_index": 2, "row_index": index, "columns": row["columns"], "cells": row["cells"], "pid_headers": ["End-of-Sale Product Part Number"]},
                    "announcement_tables": [table] if index == 0 else [],
                },
                "raw_response": {"announcement": {"title": "Large test announcement", "tables": [table]}, "affected_product_row": row},
            }
        )
    return {"source": "pytest", "pid_catalog": [], "eox_records": records}


def test_product_snapshot_does_not_duplicate_raw_tables(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'efficient.db'}"
    init_db(database_url)
    db = make_session(database_url)
    try:
        result = SeedPersistenceService(db).save_seed(_seed_with_large_table(), source_path="pytest", mode="test", commit=True)
        assert result.products_inserted == 20
        assert db.query(EoxAnnouncementTable).count() == 1
        assert db.query(EoxAffectedProduct).count() == 20
        largest_product_payload = max(len(str(item.payload)) for item in db.query(ProductEox).all())
        assert largest_product_payload < 5000
        for product in db.query(ProductEox).all():
            assert "announcement_tables" not in product.payload
            assert "affected_product_row" not in product.payload
    finally:
        db.close()


def test_sqlite_does_not_create_legacy_json_payload_indexes(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'indexes.db'}"
    init_db(database_url)
    db = make_session(database_url)
    try:
        rows = db.execute(text("select name from sqlite_master where type='index'")).fetchall()
        names = {row[0] for row in rows}
        assert "ix_product_eox_payload_gin" not in names
        assert "ix_eox_affected_payload_gin" not in names
        assert "ix_eox_table_rows_gin" not in names
    finally:
        db.close()
