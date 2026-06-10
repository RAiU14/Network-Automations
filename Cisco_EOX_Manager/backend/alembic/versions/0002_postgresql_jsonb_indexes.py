from __future__ import annotations

from alembic import op

revision = "0002_postgresql_jsonb_indexes"
down_revision = "0001_initial_db_first_schema"
branch_labels = None
depends_on = None

JSONB_COLUMNS = {
    "pid_catalog": ["payload"],
    "product_eox": ["payload", "raw_response"],
    "lookup_history": ["response_snapshot"],
    "system_events": ["payload"],
    "seed_runs": ["stats"],
    "auto_pop_checkpoints": ["stats"],
    "eox_announcements": ["payload", "raw_response"],
    "eox_announcement_tables": ["headers", "rows", "raw_table"],
    "eox_affected_products": ["payload", "raw_response"],
    "auto_pop_jobs": ["parameters", "stats"],
    "export_jobs": ["parameters"],
}

INDEXES = [
    ("ix_pid_catalog_payload_gin", "pid_catalog", "payload"),
    ("ix_product_eox_payload_gin", "product_eox", "payload"),
    ("ix_product_eox_raw_gin", "product_eox", "raw_response"),
    ("ix_lookup_history_snapshot_gin", "lookup_history", "response_snapshot"),
    ("ix_system_events_payload_gin", "system_events", "payload"),
    ("ix_seed_runs_stats_gin", "seed_runs", "stats"),
    ("ix_auto_pop_checkpoint_stats_gin", "auto_pop_checkpoints", "stats"),
    ("ix_eox_ann_payload_gin", "eox_announcements", "payload"),
    ("ix_eox_ann_raw_gin", "eox_announcements", "raw_response"),
    ("ix_eox_table_headers_gin", "eox_announcement_tables", "headers"),
    ("ix_eox_table_rows_gin", "eox_announcement_tables", "rows"),
    ("ix_eox_table_raw_gin", "eox_announcement_tables", "raw_table"),
    ("ix_eox_affected_payload_gin", "eox_affected_products", "payload"),
    ("ix_eox_affected_raw_gin", "eox_affected_products", "raw_response"),
    ("ix_auto_pop_jobs_params_gin", "auto_pop_jobs", "parameters"),
    ("ix_auto_pop_jobs_stats_gin", "auto_pop_jobs", "stats"),
    ("ix_export_jobs_params_gin", "export_jobs", "parameters"),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, columns in JSONB_COLUMNS.items():
        for column in columns:
            op.execute(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE jsonb USING {column}::jsonb')
    for name, table, column in INDEXES:
        op.execute(f'CREATE INDEX IF NOT EXISTS {name} ON {table} USING gin ({column})')


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for name, _table, _column in reversed(INDEXES):
        op.execute(f'DROP INDEX IF EXISTS {name}')
