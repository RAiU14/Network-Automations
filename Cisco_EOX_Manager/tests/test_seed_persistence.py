from __future__ import annotations

import pytest

pytest.importorskip("sqlalchemy")

from app.db.models import EoxAffectedProduct, EoxAnnouncement, EoxAnnouncementTable, ProductEox
from app.db.session import init_db, make_session
from app.services.seed_persistence import SeedPersistenceService


def test_seed_persistence_saves_product_announcement_tables_and_affected_rows(tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'eox_test.db'}"
    init_db(database_url)
    db = make_session(database_url)
    try:
        seed = {
            "source": "pytest",
            "pid_catalog": [
                {
                    "pid": "C9300-24T",
                    "normalized_pid": "C9300-24T",
                    "technology": "Switches",
                    "category_name": "Switches",
                    "product_name": "C9300-24T",
                    "product_url": "https://example.test/product",
                    "source": "test",
                    "payload": {"kind": "model"},
                }
            ],
            "eox_records": [
                {
                    "pid": "C9300-24T",
                    "technology": "Switches",
                    "source": "scraper",
                    "announcement_name": "Sample Announcement",
                    "announcement_url": "https://example.test/eox",
                    "payload": {
                        "PID": "C9300-24T",
                        "ProductIDDescription": "Catalyst 9300 24-port data only",
                        "End-of-Sale Date": "January 31, 2027",
                        "Last Date of Support": "January 31, 2032",
                        "EOXAnnouncementURL": "https://example.test/eox",
                        "affected_product_row": {
                            "table_index": 2,
                            "row_index": 1,
                            "columns": {"End-of-Sale Product Part Number": "C9300-24T"},
                        },
                        "announcement_tables": [
                            {"table_index": 1, "headers": ["Milestone", "Date"], "rows": [{"columns": {"Milestone": "End-of-Sale Date", "Date": "January 31, 2027"}}]},
                            {"table_index": 2, "headers": ["End-of-Sale Product Part Number"], "rows": [{"columns": {"End-of-Sale Product Part Number": "C9300-24T"}}]},
                        ],
                    },
                    "raw_response": {"source": "pytest"},
                }
            ],
        }
        result = SeedPersistenceService(db).save_seed(seed, source_path="pytest", mode="test", commit=True)
        assert result.products_inserted == 1
        assert result.announcements_inserted == 1
        assert result.announcement_tables_inserted == 2
        assert result.affected_rows_inserted == 1
        assert db.query(ProductEox).filter(ProductEox.pid == "C9300-24T").count() == 1
        assert db.query(EoxAnnouncement).count() == 1
        assert db.query(EoxAnnouncementTable).count() == 2
        assert db.query(EoxAffectedProduct).count() == 1
    finally:
        db.close()
