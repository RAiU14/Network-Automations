from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import (
    EoxAffectedProduct,
    EoxAnnouncement,
    EoxAnnouncementTable,
    PidCatalog,
    ProductEox,
    SeedRun,
)
from app.services.normalization import normalize_pid

logger = get_logger("eox_manager.seed_persistence")


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "pid": (
        "pid",
        "PID",
        "ProductID",
        "Product ID",
        "EOLProductID",
        "EOXInputValue",
        "End-of-Sale Product Part Number",
        "End of Sale Product Part Number",
        "End-of-Sale Product ID",
    ),
    "product_name": (
        "product_name",
        "ProductIDDescription",
        "ProductDescription",
        "Product Description",
        "Product Name",
        "Description",
    ),
    "series": ("series", "Series", "Product Series", "SeriesName"),
    "end_of_sale_date": (
        "end_of_sale_date",
        "End-of-Sale Date",
        "End-of-Sale Date: HW",
        "End of Sale Date",
        "EndOfSaleDate",
    ),
    "last_date_of_support": (
        "last_date_of_support",
        "Last Date of Support",
        "Last Date of Support: HW",
        "LastDateOfSupport",
    ),
    "end_of_sw_maintenance": (
        "end_of_sw_maintenance",
        "End of SW Maintenance Releases Date",
        "End of SW Maintenance Releases Date: HW",
        "EndOfSWMaintenanceReleases",
    ),
    "end_of_security_support": (
        "end_of_security_support",
        "End of Vulnerability/Security Support",
        "End of Vulnerability/Security Support: HW",
        "EndOfSecurityVulSupportDate",
    ),
    "end_of_routine_failure_analysis": (
        "end_of_routine_failure_analysis",
        "End of Routine Failure Analysis Date",
        "End of Routine Failure Analysis Date:  HW",
        "EndOfRoutineFailureAnalysisDate",
    ),
    "eox_announcement_url": (
        "announcement_url",
        "EOXAnnouncementURL",
        "AnnouncementURL",
        "url",
    ),
    "product_bulletin_url": (
        "product_bulletin_url",
        "ProductBulletinURL",
        "Product Bulletin URL",
        "LinkToProductBulletinURL",
    ),
}

SOURCE_PRIORITY = {
    "api": 100,
    "cisco-api": 100,
    "scraper": 80,
    "auto_pop": 75,
        "seed": 70,
    "online-discovery": 50,
    "input": 30,
    "cache": 10,
}

POSITIVE_STATUSES = {"eox_available", "known", "active", "not_announced", "catalog_only"}


@dataclass(slots=True)
class SeedSaveResult:
    catalog_inserted: int = 0
    catalog_updated: int = 0
    catalog_skipped: int = 0
    products_inserted: int = 0
    products_updated: int = 0
    products_skipped: int = 0
    announcements_inserted: int = 0
    announcements_updated: int = 0
    announcement_tables_inserted: int = 0
    announcement_tables_updated: int = 0
    affected_rows_inserted: int = 0
    affected_rows_updated: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def product_changed(self) -> int:
        return self.products_inserted + self.products_updated

    @property
    def catalog_changed(self) -> int:
        return self.catalog_inserted + self.catalog_updated

    def as_dict(self) -> dict[str, Any]:
        return {
            "catalog_inserted": self.catalog_inserted,
            "catalog_updated": self.catalog_updated,
            "catalog_skipped": self.catalog_skipped,
            "products_inserted": self.products_inserted,
            "products_updated": self.products_updated,
            "products_skipped": self.products_skipped,
            "announcements_inserted": self.announcements_inserted,
            "announcements_updated": self.announcements_updated,
            "announcement_tables_inserted": self.announcement_tables_inserted,
            "announcement_tables_updated": self.announcement_tables_updated,
            "affected_rows_inserted": self.affected_rows_inserted,
            "affected_rows_updated": self.affected_rows_updated,
            "errors": list(self.errors),
        }


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _norm_key(value: Any) -> str:
    return "".join(char for char in str(value or "").lower() if char.isalnum())


def _payload_value(payload: Mapping[str, Any] | None, aliases: Iterable[str]) -> Any:
    if not isinstance(payload, Mapping):
        return None
    normalized = {_norm_key(key): key for key in payload.keys()}
    for alias in aliases:
        if alias in payload and payload.get(alias) not in (None, ""):
            value = payload[alias]
            return value.get("value") if isinstance(value, Mapping) else value
        key = normalized.get(_norm_key(alias))
        if key is not None and payload.get(key) not in (None, ""):
            value = payload[key]
            return value.get("value") if isinstance(value, Mapping) else value
    return None


def _merge_dict(existing: Mapping[str, Any] | None, incoming: Mapping[str, Any] | None, *, overwrite: bool) -> dict[str, Any]:
    merged = dict(existing or {})
    for key, value in dict(incoming or {}).items():
        if value in (None, "", [], {}):
            continue
        if key not in merged or merged.get(key) in (None, "", [], {}) or overwrite:
            merged[key] = value
        elif isinstance(merged.get(key), Mapping) and isinstance(value, Mapping):
            merged[key] = _merge_dict(merged[key], value, overwrite=overwrite)
        elif isinstance(merged.get(key), list) and isinstance(value, list):
            seen = {stable_json(item) for item in merged[key]}
            for item in value:
                marker = stable_json(item)
                if marker not in seen:
                    merged[key].append(item)
                    seen.add(marker)
    return merged


def _status_from_payload(payload: Mapping[str, Any], explicit_status: str | None = None) -> str:
    if explicit_status:
        return explicit_status
    if any(_payload_value(payload, FIELD_ALIASES[field]) for field in (
        "end_of_sale_date",
        "last_date_of_support",
        "end_of_sw_maintenance",
        "end_of_security_support",
        "end_of_routine_failure_analysis",
    )):
        return "eox_available"
    text = stable_json(payload).lower()
    if "not announced" in text:
        return "not_announced"
    if "error" in text:
        return "error"
    return "known" if payload else "unknown"


def _source_priority(source: str | None) -> int:
    return SOURCE_PRIORITY.get(str(source or "").lower(), 60)


def _is_better_source(new_source: str | None, current_source: str | None) -> bool:
    return _source_priority(new_source) >= _source_priority(current_source)


def _record_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else record
    return dict(payload or {})


def _record_raw_response(record: Mapping[str, Any]) -> dict[str, Any]:
    raw_response = record.get("raw_response") if isinstance(record.get("raw_response"), Mapping) else {}
    if raw_response:
        return dict(raw_response)
    payload = _record_payload(record)
    return {"record": dict(record), "payload": payload}


def _strip_heavy_keys(value: Any) -> Any:
    heavy = {"announcement_tables", "affected_product_row", "additional_announcements", "raw_milestones"}
    if isinstance(value, Mapping):
        return {str(key): _strip_heavy_keys(val) for key, val in value.items() if key not in heavy}
    if isinstance(value, list):
        return [_strip_heavy_keys(item) for item in value]
    return value


def _compact_text(value: Any, limit: int = 4000) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    text = _as_text(value)
    return text if len(text) <= limit else f"{text[:limit]}... [trimmed {len(text) - limit} chars]"


def _row_info_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = payload.get("affected_product_row")
    return dict(row) if isinstance(row, Mapping) else {}


def _row_columns(row_info: Mapping[str, Any]) -> dict[str, Any]:
    columns = row_info.get("columns")
    return dict(columns) if isinstance(columns, Mapping) else {}


def _milestone_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for field, aliases in FIELD_ALIASES.items():
        if field == "pid":
            continue
        value = _payload_value(payload, aliases)
        if value not in (None, "", [], {}):
            output[aliases[0] if aliases else field] = _compact_text(value)
    for key in ("PID", "ProductID", "EOLProductID", "ProductIDDescription", "Series", "EOXStatus", "AnnouncementName", "AnnouncementTitle", "source", "scrape_mode"):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            output[key] = _compact_text(value)
    return output


def _compact_product_payload(*, pid: str, technology: str, payload: Mapping[str, Any], record: Mapping[str, Any], source: str) -> dict[str, Any]:
    row_info = _row_info_from_payload(payload)
    output = _milestone_payload(payload)
    output.update(
        {
            "PID": pid,
            "ProductID": pid,
            "EOLProductID": pid,
            "technology": technology,
            "source": source,
            "scrape_mode": _as_text(payload.get("scrape_mode")) or None,
            "announcement_url": _as_text(record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"])) or None,
            "announcement_name": _as_text(record.get("announcement_name") or payload.get("AnnouncementName")) or None,
            "table_index": row_info.get("table_index"),
            "row_index": row_info.get("row_index"),
        }
    )
    return {key: value for key, value in output.items() if value not in (None, "", [], {})}


def _compact_product_raw_response(record: Mapping[str, Any], payload: Mapping[str, Any], source: str) -> dict[str, Any]:
    raw_response = record.get("raw_response") if isinstance(record.get("raw_response"), Mapping) else {}
    birth_certificate = raw_response.get("birth_certificate") if isinstance(raw_response.get("birth_certificate"), Mapping) else {}
    series_record = raw_response.get("series_record") if isinstance(raw_response.get("series_record"), Mapping) else {}
    output = {
        "source": source,
        "scrape_mode": _as_text(payload.get("scrape_mode")) or None,
        "announcement_url": _as_text(record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"])) or None,
        "series_url": _as_text(record.get("series_url") or payload.get("SeriesURL")) or None,
        "birth_certificate": _strip_heavy_keys(birth_certificate),
        "series_record": _strip_heavy_keys(series_record),
        "record_hash": content_hash(_strip_heavy_keys(_milestone_payload(payload))),
    }
    return {key: value for key, value in output.items() if value not in (None, "", [], {})}


def _compact_announcement_payload(record: Mapping[str, Any], payload: Mapping[str, Any], technology: str) -> dict[str, Any]:
    tables = payload.get("announcement_tables") if isinstance(payload.get("announcement_tables"), list) else []
    output = {
        "announcement_name": record.get("announcement_name") or payload.get("AnnouncementName"),
        "announcement_title": payload.get("AnnouncementTitle"),
        "product_bulletin_url": record.get("product_bulletin_url") or _payload_value(payload, FIELD_ALIASES["product_bulletin_url"]),
        "technology": technology,
        "series": record.get("series") or payload.get("Series"),
        "series_url": record.get("series_url") or payload.get("SeriesURL"),
        "table_count": len(tables),
        "scrape_mode": payload.get("scrape_mode"),
    }
    return {key: _compact_text(value) for key, value in output.items() if value not in (None, "", [], {})}


def _compact_announcement_raw_response(record: Mapping[str, Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    raw_response = record.get("raw_response") if isinstance(record.get("raw_response"), Mapping) else {}
    announcement = raw_response.get("announcement") if isinstance(raw_response.get("announcement"), Mapping) else {}
    output = {
        "title": announcement.get("title") or payload.get("AnnouncementTitle"),
        "announcement_url": record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]),
        "table_count": len(payload.get("announcement_tables") or []) if isinstance(payload.get("announcement_tables"), list) else 0,
        "source_hash": content_hash(_strip_heavy_keys(announcement or payload)),
    }
    return {key: _compact_text(value) for key, value in output.items() if value not in (None, "", [], {})}


def _compact_table_raw(table: Mapping[str, Any], row_count: int, header_count: int) -> dict[str, Any]:
    output = {
        "table_index": table.get("table_index"),
        "heading": table.get("heading"),
        "caption": table.get("caption"),
        "row_count": row_count,
        "header_count": header_count,
        "content_hash": content_hash({"headers": table.get("headers") or [], "rows": table.get("rows") or []}),
    }
    for key in ("source_url", "announcement_url"):
        if table.get(key):
            output[key] = table.get(key)
    return {str(key): _compact_text(value) for key, value in output.items() if value not in (None, "", [], {})}


def _compact_table_rows(table: Mapping[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in enumerate(table.get("rows") or []):
        if not isinstance(row, Mapping):
            continue
        clean = {
            "row_index": row.get("row_index", index),
            "columns": dict(row.get("columns") or {}) if isinstance(row.get("columns"), Mapping) else {},
        }
        cells = row.get("cells")
        if isinstance(cells, list):
            clean["cells"] = [_compact_text(item, limit=2000) for item in cells]
        links = row.get("links")
        if isinstance(links, list) and links:
            clean["links"] = links
        output.append(clean)
    return output


def _compact_affected_payload(record: Mapping[str, Any], payload: Mapping[str, Any], row_info: Mapping[str, Any]) -> dict[str, Any]:
    milestones = _milestone_payload(payload)
    columns = _row_columns(row_info)
    return {
        "columns": columns,
        "affected_product_row": {
            "table_index": row_info.get("table_index"),
            "row_index": row_info.get("row_index"),
            "table_caption": row_info.get("table_caption"),
            "table_heading": row_info.get("table_heading"),
            "columns": columns,
            "pid_headers": list(row_info.get("pid_headers") or []),
        },
        "milestones": milestones,
        "announcement_url": record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]),
        "announcement_name": record.get("announcement_name") or payload.get("AnnouncementName"),
        "product_bulletin_url": record.get("product_bulletin_url") or _payload_value(payload, FIELD_ALIASES["product_bulletin_url"]),
    }

def _iter_catalog_entries(data: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(data, Mapping):
        entries = data.get("pid_catalog")
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, Mapping):
                    yield entry
            return
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, Mapping) and not _record_payload(entry):
                yield entry


def _iter_eox_records(data: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(data, Mapping):
        if isinstance(data.get("EOXRecord"), list):
            for record in data["EOXRecord"]:
                if isinstance(record, Mapping):
                    yield record
        if isinstance(data.get("eox_records"), list):
            for record in data["eox_records"]:
                if isinstance(record, Mapping):
                    yield record
        structural_keys = {"schema_version", "generated_at", "source", "pid_catalog", "eox_records", "EOXRecord", "metadata", "categories"}
        if not any(key in data for key in structural_keys):
            for pid, payload in data.items():
                if isinstance(payload, Mapping):
                    record = dict(payload)
                    record.setdefault("pid", pid)
                    yield record
    elif isinstance(data, list):
        for record in data:
            if isinstance(record, Mapping):
                yield record


class SeedPersistenceService:
    """Smart database saver for Auto_Pop seed data.

    This service treats the database as the source of truth. JSON is only one
    supported transport/backup format. It preserves full Cisco announcement
    tables in normalized side tables and also updates product_eox as the fast
    cache/snapshot used by lookup flows.
    """

    def __init__(self, db: Session):
        self.db = db

    def _pending_catalog_entry(self, normalized: str, technology: str) -> PidCatalog | None:
        collections = [list(self.db.new), list(self.db.dirty), list(self.db.identity_map.values())]
        for collection in collections:
            for obj in collection:
                if (
                    isinstance(obj, PidCatalog)
                    and obj.normalized_pid == normalized
                    and obj.technology == technology
                ):
                    return obj
        return None

    def _catalog_entry(self, normalized: str, technology: str) -> PidCatalog | None:
        pending = self._pending_catalog_entry(normalized, technology)
        if pending is not None:
            return pending
        with self.db.no_autoflush:
            return (
                self.db.query(PidCatalog)
                .filter(PidCatalog.normalized_pid == normalized, PidCatalog.technology == technology)
                .one_or_none()
            )

    def save_seed(
        self,
        data: Mapping[str, Any] | list[Any],
        *,
        source_path: str | None = None,
        mode: str = "seed",
        overwrite: bool = False,
        commit: bool = False,
    ) -> SeedSaveResult:
        result = SeedSaveResult()
        run = SeedRun(
            source=str(data.get("source") if isinstance(data, Mapping) else "seed"),
            source_path=source_path,
            mode=mode,
            status="running",
            started_at=_now(),
            stats={},
        )
        self.db.add(run)
        self.db.flush()
        try:
            for item in _iter_catalog_entries(data):
                try:
                    with self.db.begin_nested():
                        changed = self.save_catalog_entry(item, overwrite=overwrite)
                    if changed == "inserted":
                        result.catalog_inserted += 1
                    elif changed == "updated":
                        result.catalog_updated += 1
                    else:
                        result.catalog_skipped += 1
                except Exception as exc:  # pragma: no cover - defensive bulk import logging
                    message = f"Catalog record failed: {exc}"
                    logger.warning(message)
                    result.errors.append(message)

            for record in _iter_eox_records(data):
                try:
                    self._last_announcement_change = "skipped"
                    self._last_table_result = {"inserted": 0, "updated": 0}
                    self._last_affected_result = {"inserted": 0, "updated": 0}
                    with self.db.begin_nested():
                        changed = self.save_eox_record(record, overwrite=overwrite)
                    announcement_change = getattr(self, "_last_announcement_change", "skipped")
                    table_result = getattr(self, "_last_table_result", {"inserted": 0, "updated": 0})
                    affected_result = getattr(self, "_last_affected_result", {"inserted": 0, "updated": 0})
                    if announcement_change == "inserted":
                        result.announcements_inserted += 1
                    elif announcement_change == "updated":
                        result.announcements_updated += 1
                    result.announcement_tables_inserted += int(table_result.get("inserted", 0))
                    result.announcement_tables_updated += int(table_result.get("updated", 0))
                    result.affected_rows_inserted += int(affected_result.get("inserted", 0))
                    result.affected_rows_updated += int(affected_result.get("updated", 0))
                    if changed == "inserted":
                        result.products_inserted += 1
                    elif changed == "updated":
                        result.products_updated += 1
                    else:
                        result.products_skipped += 1
                except Exception as exc:  # pragma: no cover - defensive bulk import logging
                    message = f"EOX record failed: {exc}"
                    logger.warning(message)
                    result.errors.append(message)

            run.status = "completed" if not result.errors else "completed_with_errors"
            run.finished_at = _now()
            run.stats = result.as_dict()
            if commit:
                self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            run.status = "failed"
            run.finished_at = _now()
            run.stats = result.as_dict()
            if commit:
                self.db.add(run)
                self.db.commit()
            raise

    def save_catalog_entry(self, item: Mapping[str, Any], *, overwrite: bool = False) -> str:
        pid = _as_text(item.get("pid") or item.get("name") or item.get("product_name") or item.get("model"))
        if not pid:
            return "skipped"
        technology = _as_text(item.get("technology") or item.get("category_name") or "Imported") or "Imported"
        normalized = normalize_pid(pid)
        entry = self._catalog_entry(normalized, technology)
        created = False
        if entry is None:
            entry = PidCatalog(pid=pid, normalized_pid=normalized, technology=technology)
            self.db.add(entry)
            created = True

        incoming_payload = dict(item.get("payload") or {}) if isinstance(item.get("payload"), Mapping) else dict(item)
        incoming_source = _as_text(item.get("source") or "seed") or "seed"
        changed = created

        def set_if(value: Any, attr: str) -> None:
            nonlocal changed
            if value in (None, ""):
                return
            if getattr(entry, attr) in (None, "") or overwrite or _is_better_source(incoming_source, entry.source):
                if getattr(entry, attr) != value:
                    setattr(entry, attr, value)
                    changed = True

        set_if(pid, "pid")
        set_if(normalized, "normalized_pid")
        set_if(technology, "technology")
        set_if(item.get("category_name") or technology, "category_name")
        set_if(item.get("product_name") or item.get("name") or pid, "product_name")
        set_if(item.get("product_url") or item.get("url"), "product_url")

        if overwrite or _is_better_source(incoming_source, entry.source):
            if entry.source != incoming_source:
                entry.source = incoming_source
                changed = True
        if bool(item.get("is_eox", False)) and not entry.is_eox:
            entry.is_eox = True
            changed = True

        merged_payload = _merge_dict(entry.payload or {}, incoming_payload, overwrite=overwrite)
        if merged_payload != (entry.payload or {}):
            entry.payload = merged_payload
            changed = True
        entry.last_seen_at = _now()
        return "inserted" if created else "updated" if changed else "skipped"

    def save_eox_record(self, record: Mapping[str, Any], *, overwrite: bool = False) -> str:
        payload = _record_payload(record)
        pid = _as_text(
            record.get("pid")
            or _payload_value(payload, FIELD_ALIASES["pid"])
            or record.get("EOLProductID")
            or record.get("ProductID")
        )
        if not pid:
            return "skipped"
        technology = _as_text(record.get("technology") or payload.get("technology") or "Imported") or "Imported"
        source = _as_text(record.get("source") or payload.get("source") or "seed") or "seed"

        # Ensure a catalog row exists before creating the product snapshot.
        self.save_catalog_entry(
            {
                "pid": pid,
                "technology": technology,
                "category_name": record.get("category_name") or technology,
                "product_name": record.get("product_name") or _payload_value(payload, FIELD_ALIASES["product_name"]) or pid,
                "product_url": record.get("series_url") or payload.get("SeriesURL"),
                "is_eox": True,
                "source": source,
                "payload": {
                    "learned_from": "seed_eox_record",
                    "announcement_url": record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]),
                },
            },
            overwrite=overwrite,
        )

        product, product_change = self._save_product_snapshot(pid=pid, technology=technology, payload=payload, record=record, source=source, overwrite=overwrite)
        announcement = self._save_announcement(record=record, payload=payload, source=source, technology=technology)
        if announcement is not None:
            table_result = self._save_announcement_tables(announcement, payload)
            affected_result = self._save_affected_row(announcement, product, record, payload, source, technology)
            # Stash counts on the instance for save_seed to add after each record.
            # This avoids returning a larger object from save_eox_record and keeps
            # legacy callers simple.
            self._last_table_result = table_result
            self._last_affected_result = affected_result
        else:
            self._last_announcement_change = "skipped"
            self._last_table_result = {"inserted": 0, "updated": 0}
            self._last_affected_result = {"inserted": 0, "updated": 0}
        return product_change

    def _save_product_snapshot(
        self,
        *,
        pid: str,
        technology: str,
        payload: Mapping[str, Any],
        record: Mapping[str, Any],
        source: str,
        overwrite: bool,
    ) -> tuple[ProductEox, str]:
        normalized = normalize_pid(pid)
        product = self.db.query(ProductEox).filter(ProductEox.normalized_pid == normalized).one_or_none()
        created = False
        if product is None:
            product = ProductEox(pid=pid, normalized_pid=normalized)
            self.db.add(product)
            created = True

        compact_payload = _compact_product_payload(pid=pid, technology=technology, payload=payload, record=record, source=source)
        compact_raw = _compact_product_raw_response(record, payload, source)
        existing_payload = product.payload or {}
        existing_raw = product.raw_response or {}
        merged_payload = _merge_dict(existing_payload, compact_payload, overwrite=overwrite or _is_better_source(source, product.source))
        merged_raw = _merge_dict(existing_raw, compact_raw, overwrite=overwrite)
        imports = list(merged_raw.get("seed_imports") or [])
        import_marker = {
            "source": source,
            "announcement_url": record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]),
            "content_hash": content_hash(compact_payload),
            "seen_at": _now().isoformat(),
        }
        import_marker_key = stable_json({k: v for k, v in import_marker.items() if k != "seen_at"})
        existing_markers = {stable_json({k: v for k, v in item.items() if k != "seen_at"}) for item in imports if isinstance(item, Mapping)}
        if import_marker_key not in existing_markers:
            imports.append(import_marker)
        merged_raw["seed_imports"] = imports[-10:]

        changed = created

        def set_scalar(attr: str, value: Any, *, prefer_source: bool = True) -> None:
            nonlocal changed
            if value in (None, ""):
                return
            current = getattr(product, attr)
            if current in (None, "") or overwrite or (prefer_source and _is_better_source(source, product.source)):
                if current != value:
                    setattr(product, attr, value)
                    changed = True

        set_scalar("pid", pid)
        set_scalar("normalized_pid", normalized)
        set_scalar("technology", technology)
        set_scalar("product_name", record.get("product_name") or _payload_value(payload, FIELD_ALIASES["product_name"]) or pid)
        set_scalar("series", record.get("series") or _payload_value(payload, FIELD_ALIASES["series"]))
        set_scalar("end_of_sale_date", _payload_value(payload, FIELD_ALIASES["end_of_sale_date"]))
        set_scalar("last_date_of_support", _payload_value(payload, FIELD_ALIASES["last_date_of_support"]))
        set_scalar("end_of_sw_maintenance", _payload_value(payload, FIELD_ALIASES["end_of_sw_maintenance"]))
        set_scalar("end_of_security_support", _payload_value(payload, FIELD_ALIASES["end_of_security_support"]))
        set_scalar("end_of_routine_failure_analysis", _payload_value(payload, FIELD_ALIASES["end_of_routine_failure_analysis"]))
        set_scalar("eox_announcement_url", record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]))
        set_scalar("product_bulletin_url", record.get("product_bulletin_url") or _payload_value(payload, FIELD_ALIASES["product_bulletin_url"]))

        incoming_status = _status_from_payload(payload, str(record.get("status") or "") or None)
        if product.status in (None, "", "unknown") or incoming_status in POSITIVE_STATUSES or overwrite:
            if product.status != incoming_status:
                product.status = incoming_status
                changed = True
        if overwrite or _is_better_source(source, product.source):
            if product.source != source:
                product.source = source
                changed = True
        if product.payload != merged_payload:
            product.payload = merged_payload
            changed = True
        if product.raw_response != merged_raw:
            product.raw_response = merged_raw
            changed = True
        product.last_seen_at = _now()
        product.last_scraped_at = _now()
        return product, "inserted" if created else "updated" if changed else "skipped"

    def _save_announcement(
        self,
        *,
        record: Mapping[str, Any],
        payload: Mapping[str, Any],
        source: str,
        technology: str,
    ) -> EoxAnnouncement | None:
        announcement_url = _as_text(record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]))
        if not announcement_url:
            return None
        announcement = self.db.query(EoxAnnouncement).filter(EoxAnnouncement.announcement_url == announcement_url).one_or_none()
        created = False
        if announcement is None:
            announcement = EoxAnnouncement(announcement_url=announcement_url)
            self.db.add(announcement)
            created = True
        previous_hash = announcement.content_hash
        announcement_payload = _compact_announcement_payload(record, payload, technology)
        announcement.announcement_name = _as_text(announcement_payload.get("announcement_name")) or announcement.announcement_name
        announcement.title = _as_text(announcement_payload.get("announcement_title")) or announcement.title
        announcement.product_bulletin_url = _as_text(announcement_payload.get("product_bulletin_url")) or announcement.product_bulletin_url
        announcement.technology = technology or announcement.technology
        announcement.series = _as_text(announcement_payload.get("series")) or announcement.series
        announcement.series_url = _as_text(announcement_payload.get("series_url")) or announcement.series_url
        announcement.source = source or announcement.source
        announcement.payload = _merge_dict(announcement.payload or {}, announcement_payload, overwrite=True)
        announcement.raw_response = _merge_dict(announcement.raw_response or {}, _compact_announcement_raw_response(record, payload), overwrite=True)
        new_hash = content_hash({"payload": announcement.payload, "raw": announcement.raw_response})
        announcement.content_hash = new_hash
        announcement.last_seen_at = _now()
        self._last_announcement_change = "inserted" if created else "updated" if previous_hash != new_hash else "skipped"
        self.db.flush()
        return announcement

    def _save_announcement_tables(self, announcement: EoxAnnouncement, payload: Mapping[str, Any]) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0}
        tables = payload.get("announcement_tables") if isinstance(payload.get("announcement_tables"), list) else []
        for table in tables:
            if not isinstance(table, Mapping):
                continue
            table_index = int(table.get("table_index") or 0)
            existing = (
                self.db.query(EoxAnnouncementTable)
                .filter(EoxAnnouncementTable.announcement_id == announcement.id, EoxAnnouncementTable.table_index == table_index)
                .one_or_none()
            )
            created = False
            if existing is None:
                existing = EoxAnnouncementTable(announcement_id=announcement.id, table_index=table_index)
                self.db.add(existing)
                created = True
            headers = list(table.get("headers") or [])
            rows = _compact_table_rows(table)
            raw_table = _compact_table_raw(table, row_count=len(rows), header_count=len(headers))
            new_hash = content_hash({"headers": headers, "rows": rows, "raw_table": raw_table})
            changed = created or existing.content_hash != new_hash
            existing.heading = _as_text(table.get("heading")) or None
            existing.caption = _as_text(table.get("caption")) or None
            existing.headers = headers
            existing.rows = rows
            existing.raw_table = raw_table
            existing.content_hash = new_hash
            existing.last_seen_at = _now()
            if created:
                counts["inserted"] += 1
            elif changed:
                counts["updated"] += 1
        return counts

    def _save_affected_row(
        self,
        announcement: EoxAnnouncement,
        product: ProductEox,
        record: Mapping[str, Any],
        payload: Mapping[str, Any],
        source: str,
        technology: str,
    ) -> dict[str, int]:
        counts = {"inserted": 0, "updated": 0}
        row_info = _row_info_from_payload(payload)
        if not row_info:
            return counts
        pid = product.pid
        normalized = product.normalized_pid
        table_index = int(row_info.get("table_index") or 0)
        row_index = int(row_info.get("row_index") or 0)
        compact_payload = _compact_affected_payload(record, payload, row_info)
        row_hash = content_hash(compact_payload)
        existing = (
            self.db.query(EoxAffectedProduct)
            .filter(
                EoxAffectedProduct.announcement_id == announcement.id,
                EoxAffectedProduct.normalized_pid == normalized,
                EoxAffectedProduct.table_index == table_index,
                EoxAffectedProduct.row_index == row_index,
            )
            .one_or_none()
        )
        created = False
        if existing is None:
            existing = EoxAffectedProduct(
                announcement_id=announcement.id,
                product_id=product.id,
                pid=pid,
                normalized_pid=normalized,
                table_index=table_index,
                row_index=row_index,
            )
            self.db.add(existing)
            created = True
        changed = created or existing.row_hash != row_hash
        existing.product_id = product.id
        existing.pid = pid
        existing.normalized_pid = normalized
        existing.technology = technology
        existing.product_description = _as_text(record.get("product_name") or _payload_value(payload, FIELD_ALIASES["product_name"])) or None
        existing.source = source
        existing.row_hash = row_hash
        existing.payload = compact_payload
        existing.raw_response = {
            "table_index": table_index,
            "row_index": row_index,
            "cells": list(row_info.get("cells") or []),
            "pid_headers": list(row_info.get("pid_headers") or []),
            "table_headers": list(row_info.get("table_headers") or []),
        }
        existing.last_seen_at = _now()
        if created:
            counts["inserted"] += 1
        elif changed:
            counts["updated"] += 1
        return counts
