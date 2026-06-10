from __future__ import annotations

from pathlib import Path

import pytest

try:
    from app.db.models import EoxAffectedProduct, EoxAnnouncement, ProductEox
    from app.db.session import init_db, make_session
    from app.services.export_service import dataset_field_options, dataset_rows, export_dataset
except Exception as exc:  # pragma: no cover
    pytestmark = pytest.mark.skip(reason=f"database dependencies unavailable: {exc}")


def test_eox_report_dynamic_fields_and_selected_export(tmp_path: Path):
    database_url = f"sqlite:///{tmp_path / 'export.db'}"
    init_db(database_url)
    db = make_session(database_url)
    try:
        product = ProductEox(
            pid="C9300-24T",
            normalized_pid="C930024T",
            technology="Switches",
            status="eox_available",
            source="scraper",
            product_name="Catalyst 9300 24-port data only",
            end_of_sale_date="2025-10-31",
            last_date_of_support="2030-10-31",
            payload={},
            raw_response={},
        )
        announcement = EoxAnnouncement(
            announcement_url="https://www.cisco.com/example/eox",
            announcement_name="EOX test",
            technology="Switches",
            source="scraper",
            payload={},
            raw_response={},
        )
        db.add_all([product, announcement])
        db.flush()
        affected = EoxAffectedProduct(
            announcement_id=announcement.id,
            product_id=product.id,
            pid=product.pid,
            normalized_pid=product.normalized_pid,
            technology="Switches",
            product_description="Catalyst 9300 24-port data only",
            source="scraper",
            table_index=2,
            row_index=1,
            row_hash="abc",
            payload={
                "affected_product_row": {
                    "columns": {
                        "End-of-Sale Product Part Number": "C9300-24T",
                        "Replacement Product Part Number": "C9300-24T-A",
                    }
                }
            },
            raw_response={},
        )
        db.add(affected)
        db.commit()

        fields = dataset_field_options(db, "eox_report")
        keys = {field["key"] for field in fields}
        assert "pid" in keys
        assert "cisco::Replacement Product Part Number" in keys

        rows = dataset_rows(db, "eox_report", fields=["pid", "replacement_product_id", "cisco::Replacement Product Part Number"])
        assert rows == [{"pid": "C9300-24T", "replacement_product_id": "C9300-24T-A", "cisco::Replacement Product Part Number": "C9300-24T-A"}]

        content, filename, media_type, row_count = export_dataset(
            db,
            dataset="eox_report",
            format="csv",
            search=None,
            limit=100,
            fields=["pid", "replacement_product_id"],
            requested_by="pytest",
        )
        assert filename.endswith(".csv")
        assert media_type.startswith("text/csv")
        assert row_count == 1
        assert "C9300-24T-A" in content.decode("utf-8-sig")
    finally:
        db.close()
