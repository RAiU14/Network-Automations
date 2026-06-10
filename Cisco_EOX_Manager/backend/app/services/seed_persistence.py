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
            run.status = "failed"
            run.finished_at = _now()
            run.stats = result.as_dict()
            if commit:
                self.db.commit()
            raise

    def save_catalog_entry(self, item: Mapping[str, Any], *, overwrite: bool = False) -> str:
        pid = _as_text(item.get("pid") or item.get("name") or item.get("product_name") or item.get("model"))
        if not pid:
            return "skipped"
        technology = _as_text(item.get("technology") or item.get("category_name") or "Imported") or "Imported"
        normalized = normalize_pid(pid)
        entry = (
            self.db.query(PidCatalog)
            .filter(PidCatalog.normalized_pid == normalized, PidCatalog.technology == technology)
            .one_or_none()
        )
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

        raw_response = _record_raw_response(record)
        existing_payload = product.payload or {}
        existing_raw = product.raw_response or {}
        merged_payload = _merge_dict(existing_payload, payload, overwrite=overwrite or _is_better_source(source, product.source))
        merged_raw = _merge_dict(existing_raw, raw_response, overwrite=overwrite)
        imports = list(merged_raw.get("seed_imports") or [])
        import_marker = {
            "source": source,
            "announcement_url": record.get("announcement_url") or _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]),
            "content_hash": content_hash(payload),
            "seen_at": _now().isoformat(),
        }
        if stable_json(import_marker) not in {stable_json(item) for item in imports}:
            imports.append(import_marker)
        merged_raw["seed_imports"] = imports[-20:]

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
        announcement_payload = {
            "announcement_name": record.get("announcement_name") or payload.get("AnnouncementName"),
            "announcement_title": payload.get("AnnouncementTitle"),
            "product_bulletin_url": record.get("product_bulletin_url") or _payload_value(payload, FIELD_ALIASES["product_bulletin_url"]),
            "technology": technology,
            "series": record.get("series") or payload.get("Series"),
            "series_url": record.get("series_url") or payload.get("SeriesURL"),
            "tables": payload.get("announcement_tables") or [],
        }
        announcement.announcement_name = _as_text(announcement_payload.get("announcement_name")) or announcement.announcement_name
        announcement.title = _as_text(announcement_payload.get("announcement_title")) or announcement.title
        announcement.product_bulletin_url = _as_text(announcement_payload.get("product_bulletin_url")) or announcement.product_bulletin_url
        announcement.technology = technology or announcement.technology
        announcement.series = _as_text(announcement_payload.get("series")) or announcement.series
        announcement.series_url = _as_text(announcement_payload.get("series_url")) or announcement.series_url
        announcement.source = source or announcement.source
        announcement.payload = _merge_dict(announcement.payload or {}, announcement_payload, overwrite=True)
        announcement.raw_response = _merge_dict(announcement.raw_response or {}, _record_raw_response(record), overwrite=True)
        new_hash = content_hash(announcement.payload)
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
            raw_table = dict(table)
            new_hash = content_hash(raw_table)
            changed = created or existing.content_hash != new_hash
            existing.heading = _as_text(table.get("heading")) or None
            existing.caption = _as_text(table.get("caption")) or None
            existing.headers = list(table.get("headers") or [])
            existing.rows = list(table.get("rows") or [])
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
        row_info = payload.get("affected_product_row") if isinstance(payload.get("affected_product_row"), Mapping) else None
        if not row_info:
            return counts
        pid = product.pid
        normalized = product.normalized_pid
        table_index = int(row_info.get("table_index") or 0)
        row_index = int(row_info.get("row_index") or 0)
        row_hash = content_hash(row_info)
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
        existing.payload = dict(payload)
        existing.raw_response = {"affected_product_row": dict(row_info)}
        existing.last_seen_at = _now()
        if created:
            counts["inserted"] += 1
        elif changed:
            counts["updated"] += 1
        return counts
