from __future__ import annotations

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


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
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="preset", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProductEox(Base):
    __tablename__ = "product_eox"
    __table_args__ = (
        UniqueConstraint("normalized_pid", name="uq_product_eox_normalized_pid"),
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

    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    raw_response: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    lookup_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_lookup_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_scraped_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    lookup_history: Mapped[list["LookupHistory"]] = relationship(back_populates="product")


class LookupHistory(Base):
    __tablename__ = "lookup_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    query_pid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    normalized_pid: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    technology: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("product_eox.id"), nullable=True)
    source_used: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
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
