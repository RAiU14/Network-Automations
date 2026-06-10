from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from io import BytesIO, StringIO
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import (
    AutoPopCheckpoint,
    EoxAffectedProduct,
    EoxAnnouncement,
    ExportJob,
    PidCatalog,
    ProductEox,
    SystemEvent,
)

DATASETS = {"eox_report", "products", "affected_products", "announcements", "pid_catalog", "checkpoints", "system_events"}

BASE_FIELDS: dict[str, list[dict[str, Any]]] = {
    "eox_report": [
        {"key": "pid", "label": "PID", "group": "Core", "default": True},
        {"key": "product_name", "label": "Product Name", "group": "Core", "default": True},
        {"key": "technology", "label": "Technology", "group": "Core", "default": True},
        {"key": "status", "label": "EOX Status", "group": "Core", "default": True},
        {"key": "series", "label": "Series", "group": "Core", "default": True},
        {"key": "end_of_sale_date", "label": "End-of-Sale Date", "group": "Lifecycle", "default": True},
        {"key": "end_of_sw_maintenance", "label": "End of SW Maintenance", "group": "Lifecycle", "default": True},
        {"key": "end_of_security_support", "label": "End of Security Support", "group": "Lifecycle", "default": True},
        {"key": "end_of_routine_failure_analysis", "label": "End of Routine Failure Analysis", "group": "Lifecycle", "default": False},
        {"key": "last_date_of_support", "label": "Last Date of Support", "group": "Lifecycle", "default": True},
        {"key": "replacement_product_id", "label": "Replacement Product ID", "group": "Replacement", "default": True},
        {"key": "replacement_product_description", "label": "Replacement Product Description", "group": "Replacement", "default": False},
        {"key": "product_bulletin_url", "label": "Product Bulletin URL", "group": "Source", "default": False},
        {"key": "eox_announcement_url", "label": "EOX Announcement URL", "group": "Source", "default": True},
        {"key": "source", "label": "Source", "group": "Metadata", "default": False},
        {"key": "updated_at", "label": "Last Updated", "group": "Metadata", "default": False},
    ],
    "products": [
        {"key": "pid", "label": "PID", "group": "Core", "default": True},
        {"key": "normalized_pid", "label": "Normalized PID", "group": "Core", "default": False},
        {"key": "product_name", "label": "Product Name", "group": "Core", "default": True},
        {"key": "technology", "label": "Technology", "group": "Core", "default": True},
        {"key": "status", "label": "Status", "group": "Core", "default": True},
        {"key": "series", "label": "Series", "group": "Core", "default": True},
        {"key": "end_of_sale_date", "label": "End-of-Sale Date", "group": "Lifecycle", "default": True},
        {"key": "last_date_of_support", "label": "Last Date of Support", "group": "Lifecycle", "default": True},
        {"key": "end_of_sw_maintenance", "label": "End of SW Maintenance", "group": "Lifecycle", "default": True},
        {"key": "end_of_security_support", "label": "End of Security Support", "group": "Lifecycle", "default": True},
        {"key": "end_of_routine_failure_analysis", "label": "End of Routine Failure Analysis", "group": "Lifecycle", "default": False},
        {"key": "eox_announcement_url", "label": "EOX Announcement URL", "group": "Source", "default": True},
        {"key": "product_bulletin_url", "label": "Product Bulletin URL", "group": "Source", "default": False},
        {"key": "lookup_count", "label": "Lookup Count", "group": "Metadata", "default": False},
        {"key": "last_lookup_at", "label": "Last Lookup At", "group": "Metadata", "default": False},
        {"key": "last_scraped_at", "label": "Last Scraped At", "group": "Metadata", "default": False},
        {"key": "updated_at", "label": "Updated At", "group": "Metadata", "default": False},
    ],
    "affected_products": [
        {"key": "pid", "label": "PID", "group": "Core", "default": True},
        {"key": "product_description", "label": "Product Description", "group": "Core", "default": True},
        {"key": "technology", "label": "Technology", "group": "Core", "default": True},
        {"key": "announcement_id", "label": "Announcement ID", "group": "Source", "default": False},
        {"key": "table_index", "label": "Cisco Table Index", "group": "Source", "default": False},
        {"key": "row_index", "label": "Cisco Row Index", "group": "Source", "default": False},
        {"key": "source", "label": "Source", "group": "Metadata", "default": False},
        {"key": "updated_at", "label": "Updated At", "group": "Metadata", "default": False},
    ],
    "announcements": [
        {"key": "id", "label": "ID", "group": "Core", "default": True},
        {"key": "announcement_name", "label": "Announcement Name", "group": "Core", "default": True},
        {"key": "title", "label": "Title", "group": "Core", "default": True},
        {"key": "technology", "label": "Technology", "group": "Core", "default": True},
        {"key": "series", "label": "Series", "group": "Core", "default": True},
        {"key": "announcement_url", "label": "Announcement URL", "group": "Source", "default": True},
        {"key": "product_bulletin_url", "label": "Product Bulletin URL", "group": "Source", "default": False},
        {"key": "source", "label": "Source", "group": "Metadata", "default": False},
        {"key": "updated_at", "label": "Updated At", "group": "Metadata", "default": False},
    ],
    "pid_catalog": [
        {"key": "pid", "label": "PID", "group": "Core", "default": True},
        {"key": "product_name", "label": "Product Name", "group": "Core", "default": True},
        {"key": "technology", "label": "Technology", "group": "Core", "default": True},
        {"key": "category_name", "label": "Category", "group": "Core", "default": True},
        {"key": "product_url", "label": "Product URL", "group": "Source", "default": False},
        {"key": "is_eox", "label": "EOX Related", "group": "Metadata", "default": False},
        {"key": "source", "label": "Source", "group": "Metadata", "default": False},
        {"key": "updated_at", "label": "Updated At", "group": "Metadata", "default": False},
    ],
    "checkpoints": [
        {"key": "scope", "label": "Scope", "group": "Core", "default": True},
        {"key": "scope_key", "label": "Scope Key", "group": "Core", "default": True},
        {"key": "status", "label": "Status", "group": "Core", "default": True},
        {"key": "last_started_at", "label": "Last Started", "group": "Timing", "default": True},
        {"key": "last_success_at", "label": "Last Success", "group": "Timing", "default": True},
        {"key": "next_allowed_at", "label": "Next Allowed", "group": "Timing", "default": True},
        {"key": "catalog_records", "label": "Catalog Records", "group": "Stats", "default": True},
        {"key": "eox_records", "label": "EOX Records", "group": "Stats", "default": True},
        {"key": "announcements_seen", "label": "Announcements Seen", "group": "Stats", "default": True},
        {"key": "last_error", "label": "Last Error", "group": "Errors", "default": False},
    ],
    "system_events": [
        {"key": "id", "label": "ID", "group": "Core", "default": False},
        {"key": "level", "label": "Level", "group": "Core", "default": True},
        {"key": "event_type", "label": "Event Type", "group": "Core", "default": True},
        {"key": "source", "label": "Source", "group": "Core", "default": True},
        {"key": "message", "label": "Message", "group": "Core", "default": True},
        {"key": "created_at", "label": "Created At", "group": "Core", "default": True},
    ],
}

REPLACEMENT_ALIASES = (
    "Replacement Product Part Number",
    "Replacement Product ID",
    "Replacement PID",
    "Migration Product ID",
    "Suggested Replacement",
)
REPLACEMENT_DESCRIPTION_ALIASES = (
    "Replacement Product Description",
    "Migration Product Description",
    "Replacement Description",
)


def _text(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _first_value(mapping: dict[str, Any], aliases: Iterable[str]) -> Any:
    normalized = {_norm(key): key for key in mapping.keys()}
    for alias in aliases:
        key = normalized.get(_norm(alias))
        if key and mapping.get(key) not in (None, ""):
            return mapping[key]
    return None


def _row_columns_from_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    row = payload.get("affected_product_row")
    if isinstance(row, dict) and isinstance(row.get("columns"), dict):
        return dict(row["columns"])
    if isinstance(payload.get("columns"), dict):
        return dict(payload["columns"])
    return {}


def _dynamic_field_key(column: str) -> str:
    return f"cisco::{column}"


def _dynamic_field_label(key: str) -> str:
    return key.split("::", 1)[1] if key.startswith("cisco::") else key


def _apply_fields(rows: list[dict[str, Any]], fields: Sequence[str] | None) -> list[dict[str, Any]]:
    selected = [field for field in (fields or []) if field]
    if not selected:
        return rows
    return [{field: row.get(field) for field in selected} for row in rows]


def _fieldnames(rows: list[dict[str, Any]], fields: Sequence[str] | None = None) -> list[str]:
    selected = [field for field in (fields or []) if field]
    if selected:
        return selected
    names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row.keys():
            if key not in seen:
                names.append(key)
                seen.add(key)
    return names or ["message"]


def _products_query(db: Session, search: str | None):
    query = db.query(ProductEox)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(ProductEox.pid.ilike(like), ProductEox.normalized_pid.ilike(like), ProductEox.technology.ilike(like), ProductEox.status.ilike(like), ProductEox.product_name.ilike(like), ProductEox.series.ilike(like)))
    return query


def _affected_query(db: Session, search: str | None):
    query = db.query(EoxAffectedProduct)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(EoxAffectedProduct.pid.ilike(like), EoxAffectedProduct.normalized_pid.ilike(like), EoxAffectedProduct.technology.ilike(like), EoxAffectedProduct.product_description.ilike(like)))
    return query


def _base_product_row(item: ProductEox) -> dict[str, Any]:
    return {
        "pid": item.pid,
        "normalized_pid": item.normalized_pid,
        "technology": item.technology,
        "status": item.status,
        "source": item.source,
        "product_name": item.product_name,
        "series": item.series,
        "end_of_sale_date": item.end_of_sale_date,
        "last_date_of_support": item.last_date_of_support,
        "end_of_sw_maintenance": item.end_of_sw_maintenance,
        "end_of_security_support": item.end_of_security_support,
        "end_of_routine_failure_analysis": item.end_of_routine_failure_analysis,
        "eox_announcement_url": item.eox_announcement_url,
        "product_bulletin_url": item.product_bulletin_url,
        "lookup_count": item.lookup_count,
        "last_lookup_at": item.last_lookup_at,
        "last_scraped_at": item.last_scraped_at,
        "updated_at": item.updated_at,
    }


def _rows_eox_report(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    products = _products_query(db, search).order_by(ProductEox.updated_at.desc()).limit(limit).all()
    rows: list[dict[str, Any]] = []
    for product in products:
        affected_rows = (
            db.query(EoxAffectedProduct)
            .filter(or_(EoxAffectedProduct.product_id == product.id, EoxAffectedProduct.normalized_pid == product.normalized_pid))
            .order_by(EoxAffectedProduct.updated_at.desc())
            .limit(25)
            .all()
        )
        if not affected_rows:
            rows.append(_base_product_row(product))
            continue
        for affected in affected_rows:
            columns = _row_columns_from_payload(affected.payload)
            row = _base_product_row(product)
            row.update(
                {
                    "affected_product_description": affected.product_description,
                    "announcement_id": affected.announcement_id,
                    "cisco_table_index": affected.table_index,
                    "cisco_row_index": affected.row_index,
                }
            )
            replacement_id = _first_value(columns, REPLACEMENT_ALIASES)
            replacement_description = _first_value(columns, REPLACEMENT_DESCRIPTION_ALIASES)
            if replacement_id is not None:
                row["replacement_product_id"] = replacement_id
            if replacement_description is not None:
                row["replacement_product_description"] = replacement_description
            for key, value in columns.items():
                row[_dynamic_field_key(str(key))] = value
            rows.append(row)
    return rows[:limit]


def _rows_products(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    items = _products_query(db, search).order_by(ProductEox.updated_at.desc()).limit(limit).all()
    rows = []
    for item in items:
        row = _base_product_row(item)
        for key, value in _row_columns_from_payload(item.payload).items():
            row[_dynamic_field_key(str(key))] = value
        rows.append(row)
    return rows


def _rows_catalog(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(PidCatalog)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(PidCatalog.pid.ilike(like), PidCatalog.normalized_pid.ilike(like), PidCatalog.technology.ilike(like), PidCatalog.category_name.ilike(like), PidCatalog.product_name.ilike(like)))
    items = query.order_by(PidCatalog.updated_at.desc()).limit(limit).all()
    return [
        {
            "pid": item.pid,
            "normalized_pid": item.normalized_pid,
            "technology": item.technology,
            "category_name": item.category_name,
            "product_name": item.product_name,
            "product_url": item.product_url,
            "is_eox": item.is_eox,
            "source": item.source,
            "updated_at": item.updated_at,
        }
        for item in items
    ]


def _rows_affected(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    items = _affected_query(db, search).order_by(EoxAffectedProduct.updated_at.desc()).limit(limit).all()
    rows = []
    for item in items:
        row = {
            "pid": item.pid,
            "normalized_pid": item.normalized_pid,
            "technology": item.technology,
            "product_description": item.product_description,
            "announcement_id": item.announcement_id,
            "product_id": item.product_id,
            "table_index": item.table_index,
            "row_index": item.row_index,
            "source": item.source,
            "updated_at": item.updated_at,
        }
        for key, value in _row_columns_from_payload(item.payload).items():
            row[_dynamic_field_key(str(key))] = value
        rows.append(row)
    return rows


def _rows_announcements(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(EoxAnnouncement)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(EoxAnnouncement.announcement_name.ilike(like), EoxAnnouncement.title.ilike(like), EoxAnnouncement.technology.ilike(like), EoxAnnouncement.series.ilike(like), EoxAnnouncement.announcement_url.ilike(like)))
    items = query.order_by(EoxAnnouncement.updated_at.desc()).limit(limit).all()
    return [
        {
            "id": item.id,
            "announcement_name": item.announcement_name,
            "title": item.title,
            "technology": item.technology,
            "series": item.series,
            "announcement_url": item.announcement_url,
            "product_bulletin_url": item.product_bulletin_url,
            "source": item.source,
            "updated_at": item.updated_at,
        }
        for item in items
    ]


def _rows_checkpoints(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(AutoPopCheckpoint)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(AutoPopCheckpoint.scope.ilike(like), AutoPopCheckpoint.scope_key.ilike(like), AutoPopCheckpoint.status.ilike(like)))
    items = query.order_by(AutoPopCheckpoint.updated_at.desc()).limit(limit).all()
    return [
        {
            "scope": item.scope,
            "scope_key": item.scope_key,
            "status": item.status,
            "last_started_at": item.last_started_at,
            "last_completed_at": item.last_completed_at,
            "last_success_at": item.last_success_at,
            "next_allowed_at": item.next_allowed_at,
            "run_count": item.run_count,
            "skip_count": item.skip_count,
            "catalog_records": item.catalog_records,
            "eox_records": item.eox_records,
            "announcements_seen": item.announcements_seen,
            "last_error": item.last_error,
        }
        for item in items
    ]


def _rows_events(db: Session, search: str | None, limit: int) -> list[dict[str, Any]]:
    query = db.query(SystemEvent)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(SystemEvent.level.ilike(like), SystemEvent.event_type.ilike(like), SystemEvent.source.ilike(like), SystemEvent.message.ilike(like)))
    items = query.order_by(SystemEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": item.id,
            "level": item.level,
            "event_type": item.event_type,
            "source": item.source,
            "message": item.message,
            "created_at": item.created_at,
        }
        for item in items
    ]


def dataset_rows(db: Session, dataset: str, *, search: str | None = None, limit: int = 10000, fields: Sequence[str] | None = None) -> list[dict[str, Any]]:
    if dataset == "eox_report":
        rows = _rows_eox_report(db, search, limit)
    elif dataset == "products":
        rows = _rows_products(db, search, limit)
    elif dataset == "pid_catalog":
        rows = _rows_catalog(db, search, limit)
    elif dataset == "affected_products":
        rows = _rows_affected(db, search, limit)
    elif dataset == "announcements":
        rows = _rows_announcements(db, search, limit)
    elif dataset == "checkpoints":
        rows = _rows_checkpoints(db, search, limit)
    elif dataset == "system_events":
        rows = _rows_events(db, search, limit)
    else:
        raise ValueError(f"Unsupported dataset: {dataset}")
    return _apply_fields(rows, fields)


def _discover_dynamic_columns(db: Session, dataset: str, search: str | None, limit: int) -> list[str]:
    rows: list[Any]
    if dataset in {"eox_report", "affected_products"}:
        rows = _affected_query(db, search).order_by(EoxAffectedProduct.updated_at.desc()).limit(limit).all()
        columns: set[str] = set()
        for item in rows:
            columns.update(str(key) for key in _row_columns_from_payload(item.payload).keys() if key)
        return sorted(columns, key=lambda item: item.lower())
    if dataset == "products":
        rows = _products_query(db, search).order_by(ProductEox.updated_at.desc()).limit(limit).all()
        columns = set()
        for item in rows:
            columns.update(str(key) for key in _row_columns_from_payload(item.payload).keys() if key)
        return sorted(columns, key=lambda item: item.lower())
    return []


def dataset_field_options(db: Session, dataset: str, *, search: str | None = None, limit: int = 5000) -> list[dict[str, Any]]:
    if dataset not in DATASETS:
        raise ValueError(f"Unsupported dataset: {dataset}")
    options = [dict(item) for item in BASE_FIELDS.get(dataset, [])]
    existing = {item["key"] for item in options}
    for column in _discover_dynamic_columns(db, dataset, search, limit):
        key = _dynamic_field_key(column)
        if key in existing:
            continue
        options.append({"key": key, "label": column, "group": "Cisco table columns", "default": False, "dynamic": True})
        existing.add(key)
    return options


def default_fields(db: Session, dataset: str, *, search: str | None = None) -> list[str]:
    return [item["key"] for item in dataset_field_options(db, dataset, search=search, limit=1000) if item.get("default")]


def rows_to_csv(rows: list[dict[str, Any]], fieldnames: Sequence[str] | None = None) -> bytes:
    buffer = StringIO()
    names = _fieldnames(rows, fieldnames)
    writer = csv.DictWriter(buffer, fieldnames=names, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: _text(row.get(key)) for key in names})
    return buffer.getvalue().encode("utf-8-sig")


def rows_to_xlsx(rows: list[dict[str, Any]], fieldnames: Sequence[str] | None = None) -> bytes:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "export"
    names = _fieldnames(rows, fieldnames)
    labels = [_dynamic_field_label(name) for name in names]
    sheet.append(labels)
    for row in rows:
        sheet.append([_text(row.get(key)) for key in names])
    for column_cells in sheet.columns:
        width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 70)
        sheet.column_dimensions[column_cells[0].column_letter].width = width
    sheet.freeze_panes = "A2"
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def export_dataset(
    db: Session,
    *,
    dataset: str,
    format: str,
    search: str | None,
    limit: int,
    fields: Sequence[str] | None = None,
    include_all: bool = False,
    requested_by: str | None = None,
) -> tuple[bytes, str, str, int]:
    selected_fields = None if include_all else list(fields or default_fields(db, dataset, search=search))
    rows = dataset_rows(db, dataset, search=search, limit=limit, fields=selected_fields)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_dataset = dataset.replace("/", "_")
    if format == "xlsx":
        content = rows_to_xlsx(rows, selected_fields)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"cisco_eox_{safe_dataset}_{timestamp}.xlsx"
    elif format == "csv":
        content = rows_to_csv(rows, selected_fields)
        media_type = "text/csv; charset=utf-8"
        filename = f"cisco_eox_{safe_dataset}_{timestamp}.csv"
    else:
        raise ValueError("Unsupported export format")
    job = ExportJob(
        dataset=dataset,
        format=format,
        status="completed",
        row_count=len(rows),
        requested_by=requested_by,
        parameters={"search": search, "limit": limit, "fields": selected_fields or "all"},
        file_name=filename,
    )
    db.add(job)
    db.commit()
    return content, filename, media_type, len(rows)
