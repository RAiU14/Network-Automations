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
    ("ix_product_eox_payload_gin", "product_eox", "payload"),
    ("ix_eox_affected_payload_gin", "eox_affected_products", "payload"),
    ("ix_eox_table_rows_gin", "eox_announcement_tables", "rows"),
    ("ix_eox_ann_payload_gin", "eox_announcements", "payload"),
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
