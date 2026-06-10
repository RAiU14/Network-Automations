"""initial db first schema

Revision ID: 0001_initial_db_first_schema
Revises:
Create Date: 2026-06-09
"""
from __future__ import annotations

from alembic import op

revision = "0001_initial_db_first_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.db.session import Base
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    from app.db.session import Base
    from app.db import models  # noqa: F401

    Base.metadata.drop_all(bind=op.get_bind())
