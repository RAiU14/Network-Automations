from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

JSONVariant = JSON().with_variant(JSONB(), "postgresql")


class PidCatalog(Base):
    __tablename__ = "pid_catalog"
    __table_args__ = (
        UniqueConstraint("normalized_pid", "technology", name="uq_pid_catalog_norm_technology"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    normalized_pid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    technology: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    category_name: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_eox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="seed", index=True)
    payload: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProductEox(Base):
    __tablename__ = "product_eox"
    __table_args__ = (
        UniqueConstraint("normalized_pid", name="uq_product_eox_normalized_pid"),
        Index("ix_product_eox_status_updated", "status", "updated_at"),
        Index("ix_product_eox_technology_status", "technology", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    pid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_pid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    technology: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    series: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown", index=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="cache", index=True)

    end_of_sale_date: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_date_of_support: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_of_sw_maintenance: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_of_security_support: Mapped[str | None] = mapped_column(String(128), nullable=True)
    end_of_routine_failure_analysis: Mapped[str | None] = mapped_column(String(128), nullable=True)

    eox_announcement_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_bulletin_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    payload: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    raw_response: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)

    lookup_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_lookup_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scraped_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    lookup_history: Mapped[list["LookupHistory"]] = relationship(back_populates="product")
    affected_rows: Mapped[list["EoxAffectedProduct"]] = relationship(back_populates="product")


class LookupHistory(Base):
    __tablename__ = "lookup_history"
    __table_args__ = (
        Index("ix_lookup_history_pid_created", "normalized_pid", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    query_pid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_pid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    technology: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("product_eox.id"), nullable=True)
    source_used: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_snapshot: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product: Mapped[ProductEox | None] = relationship(back_populates="lookup_history")


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SystemEvent(Base):
    __tablename__ = "system_events"
    __table_args__ = (
        Index("ix_system_events_type_created", "event_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    level: Mapped[str] = mapped_column(String(32), nullable=False, default="info", index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class SeedRun(Base):
    __tablename__ = "seed_runs"
    __table_args__ = (
        Index("ix_seed_runs_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    mode: Mapped[str] = mapped_column(String(64), nullable=False, default="seed", index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="running", index=True)
    stats: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)




class AutoPopCheckpoint(Base):
    __tablename__ = "auto_pop_checkpoints"
    __table_args__ = (
        UniqueConstraint("scope", "scope_key", name="uq_auto_pop_checkpoint_scope_key"),
        Index("ix_auto_pop_checkpoint_status_next", "status", "next_allowed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="never_run", index=True)
    last_started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_allowed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    catalog_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eox_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    announcements_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EoxAnnouncement(Base):
    __tablename__ = "eox_announcements"
    __table_args__ = (
        Index("ix_eox_ann_technology_updated", "technology", "updated_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    announcement_url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    announcement_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_bulletin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    technology: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    series: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    series_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="seed", index=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    raw_response: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tables: Mapped[list["EoxAnnouncementTable"]] = relationship(back_populates="announcement", cascade="all, delete-orphan")
    affected_products: Mapped[list["EoxAffectedProduct"]] = relationship(back_populates="announcement", cascade="all, delete-orphan")


class EoxAnnouncementTable(Base):
    __tablename__ = "eox_announcement_tables"
    __table_args__ = (
        UniqueConstraint("announcement_id", "table_index", name="uq_eox_announcement_table_index"),
        Index("ix_eox_table_announcement_index", "announcement_id", "table_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("eox_announcements.id"), nullable=False, index=True)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    headers: Mapped[list] = mapped_column(JSONVariant, nullable=False, default=list)
    rows: Mapped[list] = mapped_column(JSONVariant, nullable=False, default=list)
    raw_table: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    announcement: Mapped["EoxAnnouncement"] = relationship(back_populates="tables")


class EoxAffectedProduct(Base):
    __tablename__ = "eox_affected_products"
    __table_args__ = (
        UniqueConstraint("announcement_id", "normalized_pid", "table_index", "row_index", name="uq_eox_affected_pid_row"),
        Index("ix_eox_affected_norm_updated", "normalized_pid", "updated_at"),
        Index("ix_eox_affected_announcement_pid", "announcement_id", "normalized_pid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    announcement_id: Mapped[int] = mapped_column(ForeignKey("eox_announcements.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("product_eox.id"), nullable=True, index=True)
    pid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    normalized_pid: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    technology: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    product_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="seed", index=True)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    raw_response: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    announcement: Mapped["EoxAnnouncement"] = relationship(back_populates="affected_products")
    product: Mapped[ProductEox | None] = relationship(back_populates="affected_rows")


class AutoPopJob(Base):
    __tablename__ = "auto_pop_jobs"
    __table_args__ = (
        Index("ix_auto_pop_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="queued", index=True)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    command: Mapped[list] = mapped_column(JSONVariant, nullable=False, default=list)
    log_file: Mapped[str | None] = mapped_column(Text, nullable=True)
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    return_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stats: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ExportJob(Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_dataset_created", "dataset", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    format: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="completed", index=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONVariant, nullable=False, default=dict)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
