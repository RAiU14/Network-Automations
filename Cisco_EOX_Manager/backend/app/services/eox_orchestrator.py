from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.models import LookupHistory, PidCatalog, ProductEox
from app.schemas import (
    AutoPopulateResponse,
    CacheSearchResponse,
    CacheStatsResponse,
    CatalogDiscoveryResponse,
    EoxProductOut,
    LegacyImportResponse,
    LookupResponse,
    PidCatalogOut,
    PidCatalogSearchResponse,
    PidLookupResult,
    PresetStatusResponse,
)
from app.services.cisco_api_client import CiscoApiClient, CiscoApiError
from app.services.cisco_scraper import CiscoEoxScraperService
from app.services.credential_store import CredentialStore
from app.services.normalization import clean_pid_list, normalize_pid

logger = get_logger("eox_manager.orchestrator")


FIELD_ALIASES = {
    "end_of_sale_date": [
        "End-of-Sale Date",
        "End-of-Sale Date: HW",
        "End of Sale Date",
        "EndOfSaleDate",
    ],
    "last_date_of_support": [
        "Last Date of Support",
        "Last Date of Support: HW",
        "LastDateOfSupport",
    ],
    "end_of_sw_maintenance": [
        "End of SW Maintenance Releases Date",
        "End of SW Maintenance Releases Date: HW",
        "EndOfSWMaintenanceReleases",
    ],
    "end_of_security_support": [
        "End of Vulnerability/Security Support",
        "End of Vulnerability/Security Support: HW",
        "EndOfSecurityVulSupportDate",
    ],
    "end_of_routine_failure_analysis": [
        "End of Routine Failure Analysis Date",
        "End of Routine Failure Analysis Date:  HW",
        "EndOfRoutineFailureAnalysisDate",
    ],
    "product_bulletin_url": [
        "ProductBulletinURL",
        "Product Bulletin URL",
        "LinkToProductBulletinURL",
    ],
    "eox_announcement_url": ["url", "AnnouncementURL", "EOXAnnouncementURL"],
    "product_name": ["ProductIDDescription", "Product Name", "ProductDescription", "product_name"],
    "pid": ["EOLProductID", "ProductID", "PID", "pid"],
}


def _payload_value(payload: Mapping[str, Any], aliases: Iterable[str]) -> Any:
    if not isinstance(payload, Mapping):
        return None
    normalized_lookup = {str(key).lower().replace(" ", "").replace("-", "").replace(":", ""): key for key in payload}
    for alias in aliases:
        direct = payload.get(alias)
        if direct is not None:
            return direct.get("value") if isinstance(direct, Mapping) else direct
        key = normalized_lookup.get(alias.lower().replace(" ", "").replace("-", "").replace(":", ""))
        if key is not None:
            value = payload.get(key)
            return value.get("value") if isinstance(value, Mapping) else value
    return None


def _status_from_payload(payload: Any, source: str) -> str:
    if isinstance(payload, Mapping):
        if any(_payload_value(payload, aliases) for aliases in FIELD_ALIASES.values()):
            return "eox_available"
        return "known"
    if isinstance(payload, str):
        text = payload.lower()
        if "series not found" in text:
            return "series_not_found"
        if "not announced" in text or "check online" in text:
            return "not_announced"
        if "error" in text:
            return "error"
    return "unknown" if source in {"cache", "preset"} else "not_found"


def product_to_out(product: ProductEox) -> EoxProductOut:
    return EoxProductOut(
        pid=product.pid,
        normalized_pid=product.normalized_pid,
        technology=product.technology,
        status=product.status,
        source=product.source,
        product_name=product.product_name,
        series=product.series,
        end_of_sale_date=product.end_of_sale_date,
        last_date_of_support=product.last_date_of_support,
        end_of_sw_maintenance=product.end_of_sw_maintenance,
        end_of_security_support=product.end_of_security_support,
        end_of_routine_failure_analysis=product.end_of_routine_failure_analysis,
        eox_announcement_url=product.eox_announcement_url,
        product_bulletin_url=product.product_bulletin_url,
        payload=product.payload or {},
        lookup_count=product.lookup_count or 0,
        last_lookup_at=product.last_lookup_at,
        last_scraped_at=product.last_scraped_at,
        updated_at=product.updated_at,
    )


def catalog_to_out(entry: PidCatalog) -> PidCatalogOut:
    return PidCatalogOut(
        pid=entry.pid,
        normalized_pid=entry.normalized_pid,
        technology=entry.technology,
        category_name=entry.category_name,
        product_name=entry.product_name,
        product_url=entry.product_url,
        is_eox=entry.is_eox,
        source=entry.source,
        payload=entry.payload or {},
        updated_at=entry.updated_at,
    )


class EoxOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()

    def _get_product(self, pid: str) -> ProductEox | None:
        return self.db.query(ProductEox).filter(ProductEox.normalized_pid == normalize_pid(pid)).one_or_none()

    def _get_catalog(self, pid: str, technology: str | None = None) -> PidCatalog | None:
        q = self.db.query(PidCatalog).filter(PidCatalog.normalized_pid == normalize_pid(pid))
        if technology:
            direct = q.filter(PidCatalog.technology == technology).one_or_none()
            if direct:
                return direct
        return q.order_by(PidCatalog.updated_at.desc()).first()

    def _save_catalog_entry(
        self,
        *,
        pid: str,
        technology: str | None = None,
        category_name: str | None = None,
        product_name: str | None = None,
        product_url: str | None = None,
        is_eox: bool = False,
        source: str = "preset",
        payload: Mapping[str, Any] | None = None,
        overwrite: bool = True,
    ) -> tuple[PidCatalog, bool]:
        normalized = normalize_pid(pid)
        tech_key = technology or "Unknown"
        entry = (
            self.db.query(PidCatalog)
            .filter(PidCatalog.normalized_pid == normalized, PidCatalog.technology == tech_key)
            .one_or_none()
        )
        created = False
        if entry is None:
            entry = PidCatalog(pid=pid.strip(), normalized_pid=normalized, technology=tech_key)
            self.db.add(entry)
            created = True
        elif not overwrite:
            return entry, False

        entry.pid = pid.strip()
        entry.normalized_pid = normalized
        entry.technology = tech_key
        entry.category_name = category_name
        entry.product_name = product_name or pid.strip()
        entry.product_url = product_url
        entry.is_eox = bool(is_eox)
        entry.source = source
        entry.payload = dict(payload or {})
        entry.last_seen_at = datetime.now(timezone.utc)
        return entry, created

    def _save_product(
        self,
        *,
        pid: str,
        technology: str,
        payload: Any,
        source: str,
        raw_response: Any | None = None,
        status: str | None = None,
    ) -> ProductEox:
        normalized = normalize_pid(pid)
        payload_dict = payload if isinstance(payload, Mapping) else {"message": payload}
        raw_dict = raw_response if isinstance(raw_response, Mapping) else {"raw": raw_response if raw_response is not None else payload}
        status = status or _status_from_payload(payload, source)

        product = self._get_product(pid)
        if product is None:
            product = ProductEox(pid=pid.strip(), normalized_pid=normalized)
            self.db.add(product)

        product.pid = pid.strip()
        product.normalized_pid = normalized
        product.technology = technology
        product.status = status
        product.source = source
        product.payload = dict(payload_dict)
        product.raw_response = dict(raw_dict)
        product.product_name = _payload_value(payload_dict, FIELD_ALIASES["product_name"])
        product.end_of_sale_date = _payload_value(payload_dict, FIELD_ALIASES["end_of_sale_date"])
        product.last_date_of_support = _payload_value(payload_dict, FIELD_ALIASES["last_date_of_support"])
        product.end_of_sw_maintenance = _payload_value(payload_dict, FIELD_ALIASES["end_of_sw_maintenance"])
        product.end_of_security_support = _payload_value(payload_dict, FIELD_ALIASES["end_of_security_support"])
        product.end_of_routine_failure_analysis = _payload_value(
            payload_dict,
            FIELD_ALIASES["end_of_routine_failure_analysis"],
        )
        product.eox_announcement_url = _payload_value(payload_dict, FIELD_ALIASES["eox_announcement_url"])
        product.product_bulletin_url = _payload_value(payload_dict, FIELD_ALIASES["product_bulletin_url"])
        product.last_seen_at = datetime.now(timezone.utc)
        product.last_scraped_at = datetime.now(timezone.utc) if source in {"api", "scraper", "legacy-json", "preset"} else product.last_scraped_at
        return product

    def _record_history(
        self,
        *,
        query_pid: str,
        technology: str,
        product: ProductEox | None,
        source_used: str,
        status: str,
        message: str | None,
        snapshot: Mapping[str, Any] | None = None,
    ) -> None:
        if product is not None and product.id is None:
            self.db.flush()
        self.db.add(
            LookupHistory(
                query_pid=query_pid,
                normalized_pid=normalize_pid(query_pid),
                technology=technology,
                product_id=product.id if product and product.id else None,
                source_used=source_used,
                status=status,
                message=message,
                response_snapshot=dict(snapshot or {}),
            )
        )

    def _cache_result(self, query_pid: str, technology: str, product: ProductEox) -> PidLookupResult:
        product.lookup_count = (product.lookup_count or 0) + 1
        product.last_lookup_at = datetime.now(timezone.utc)
        catalog_entry = self._get_catalog(query_pid, technology)
        self._record_history(
            query_pid=query_pid,
            technology=technology,
            product=product,
            source_used="cache",
            status=product.status,
            message="Served from PostgreSQL cache",
            snapshot=product.payload,
        )
        return PidLookupResult(
            pid=query_pid,
            normalized_pid=normalize_pid(query_pid),
            found=True,
            from_cache=True,
            source_used="cache",
            status=product.status,
            message="Served from PostgreSQL cache",
            product=product_to_out(product),
            catalog_entry=catalog_to_out(catalog_entry) if catalog_entry else None,
            data=product.payload or {},
        )

    def _catalog_only_result(self, pid: str, technology: str, catalog: PidCatalog) -> PidLookupResult:
        return PidLookupResult(
            pid=pid,
            normalized_pid=normalize_pid(pid),
            found=True,
            from_cache=True,
            source_used="preset",
            status="catalog_only",
            message="PID/series found in local PID catalog, but no EOX milestone payload is cached yet",
            product=None,
            catalog_entry=catalog_to_out(catalog),
            data=catalog.payload or {},
        )

    def lookup_pids(
        self,
        pids: Iterable[str],
        *,
        technology: str,
        refresh: bool = False,
        prefer_api: bool = False,
        auto_learn: bool = True,
    ) -> LookupResponse:
        clean_pids = clean_pid_list(pids)
        results_by_norm: dict[str, PidLookupResult] = {}
        missing: list[str] = []

        for pid in clean_pids:
            cached = self._get_product(pid)
            if cached and not refresh:
                results_by_norm[normalize_pid(pid)] = self._cache_result(pid, technology, cached)
            else:
                # Keep local catalog lookup visible, but continue online lookup unless auto_learn is disabled.
                catalog_entry = self._get_catalog(pid, technology)
                if catalog_entry and not refresh and not auto_learn:
                    results_by_norm[normalize_pid(pid)] = self._catalog_only_result(pid, technology, catalog_entry)
                else:
                    missing.append(pid)

        if missing and prefer_api:
            api_results, unresolved = self._lookup_with_api(missing, technology, auto_learn=auto_learn)
            results_by_norm.update({normalize_pid(item.pid): item for item in api_results})
            missing = unresolved

        if missing:
            scraper_results = self._lookup_with_scraper(missing, technology, auto_learn=auto_learn)
            results_by_norm.update({normalize_pid(item.pid): item for item in scraper_results})

        ordered = [results_by_norm.get(normalize_pid(pid)) for pid in clean_pids]
        final_results = [item for item in ordered if item is not None]
        self.db.commit()
        summary = {
            "total": len(final_results),
            "cache_hits": sum(1 for item in final_results if item.source_used == "cache"),
            "catalog_hits": sum(1 for item in final_results if item.source_used == "preset"),
            "api_hits": sum(1 for item in final_results if item.source_used == "api"),
            "scraper_hits": sum(1 for item in final_results if item.source_used == "scraper"),
            "not_found": sum(1 for item in final_results if not item.found),
        }
        return LookupResponse(results=final_results, summary=summary)

    def _lookup_with_api(self, pids: list[str], technology: str, *, auto_learn: bool) -> tuple[list[PidLookupResult], list[str]]:
        store = CredentialStore(self.db)
        if not store.cisco_credentials_configured():
            return [], pids

        try:
            api_data = CiscoApiClient(self.db).get_hardware_eox_by_product_id(pids)
        except CiscoApiError as exc:
            logger.warning("Cisco API lookup failed, falling back to scraper: %s", exc)
            return [], pids

        results: list[PidLookupResult] = []
        request_by_norm = {normalize_pid(pid): pid for pid in pids}
        resolved_norms: set[str] = set()
        for returned_pid, payload in api_data.items():
            norm = normalize_pid(returned_pid)
            query_pid = request_by_norm.get(norm, returned_pid)
            resolved_norms.add(norm)
            product = self._save_product(pid=query_pid, technology=technology, payload=payload, source="api") if auto_learn else None
            catalog_entry = self._get_catalog(query_pid, technology)
            if product:
                product.lookup_count = (product.lookup_count or 0) + 1
                product.last_lookup_at = datetime.now(timezone.utc)
                if not catalog_entry:
                    catalog_entry, _ = self._save_catalog_entry(
                        pid=query_pid,
                        technology=technology,
                        category_name=technology,
                        product_name=product.product_name or query_pid,
                        is_eox=True,
                        source="api",
                        payload={"learned_from": "api"},
                    )
            self._record_history(
                query_pid=query_pid,
                technology=technology,
                product=product,
                source_used="api",
                status="eox_available",
                message="Fetched from Cisco API and cached" if auto_learn else "Fetched from Cisco API",
                snapshot=payload,
            )
            results.append(
                PidLookupResult(
                    pid=query_pid,
                    normalized_pid=normalize_pid(query_pid),
                    found=True,
                    from_cache=False,
                    source_used="api",
                    status=product.status if product else _status_from_payload(payload, "api"),
                    message="Fetched from Cisco API and cached" if auto_learn else "Fetched from Cisco API",
                    product=product_to_out(product) if product else None,
                    catalog_entry=catalog_to_out(catalog_entry) if catalog_entry else None,
                    data=dict(payload),
                )
            )
        unresolved = [pid for pid in pids if normalize_pid(pid) not in resolved_norms]
        return results, unresolved

    def _lookup_with_scraper(self, pids: list[str], technology: str, *, auto_learn: bool) -> list[PidLookupResult]:
        scraper = CiscoEoxScraperService()
        results: list[PidLookupResult] = []
        scraped = scraper.request_eox_data_from_online(pids, technology)
        for pid in pids:
            value = scraped.get(pid, [False, "No result returned"])
            found = False
            payload: Any = value
            message = None
            if isinstance(value, list) and len(value) >= 2:
                found = bool(value[0]) and isinstance(value[1], Mapping)
                payload = value[1]
                message = "Fetched through Cisco web scraping" if found else str(value[1])
            else:
                message = str(value)

            product = None
            catalog_entry = self._get_catalog(pid, technology)
            status = _status_from_payload(payload, "scraper")
            if auto_learn:
                product = self._save_product(
                    pid=pid,
                    technology=technology,
                    payload=payload,
                    source="scraper",
                    raw_response={"scraper_response": value},
                    status=status,
                )
                product.lookup_count = (product.lookup_count or 0) + 1
                product.last_lookup_at = datetime.now(timezone.utc)
                if not catalog_entry:
                    catalog_entry, _ = self._save_catalog_entry(
                        pid=pid,
                        technology=technology,
                        category_name=technology,
                        product_name=pid,
                        is_eox=bool(found),
                        source="scraper",
                        payload={"learned_from": "scraper", "status": status},
                    )

            self._record_history(
                query_pid=pid,
                technology=technology,
                product=product,
                source_used="scraper",
                status=status,
                message=message,
                snapshot={"scraper_response": value},
            )
            results.append(
                PidLookupResult(
                    pid=pid,
                    normalized_pid=normalize_pid(pid),
                    found=bool(found),
                    from_cache=False,
                    source_used="scraper",
                    status=status,
                    message=message,
                    product=product_to_out(product) if product else None,
                    catalog_entry=catalog_to_out(catalog_entry) if catalog_entry else None,
                    data=product.payload if product else (payload if isinstance(payload, Mapping) else {"message": str(payload)}),
                )
            )
        return results

    def auto_populate(
        self,
        pids: Iterable[str],
        *,
        technology: str,
        refresh_existing: bool = False,
        prefer_api: bool = False,
    ) -> AutoPopulateResponse:
        response = self.lookup_pids(
            pids,
            technology=technology,
            refresh=refresh_existing,
            prefer_api=prefer_api,
            auto_learn=True,
        )
        inserted_or_updated = sum(1 for item in response.results if item.source_used in {"api", "scraper"})
        cache_hits = sum(1 for item in response.results if item.from_cache)
        failed = sum(1 for item in response.results if not item.found and item.status in {"error", "series_not_found", "not_found"})
        return AutoPopulateResponse(
            inserted_or_updated=inserted_or_updated,
            cache_hits=cache_hits,
            failed=failed,
            results=response.results,
        )

    def search_cache(self, *, query: str | None = None, limit: int = 50, offset: int = 0) -> CacheSearchResponse:
        q = self.db.query(ProductEox)
        if query:
            like = f"%{query.strip()}%"
            q = q.filter((ProductEox.pid.ilike(like)) | (ProductEox.normalized_pid.ilike(like)) | (ProductEox.technology.ilike(like)) | (ProductEox.status.ilike(like)))
        total = q.count()
        products = q.order_by(ProductEox.updated_at.desc()).offset(offset).limit(limit).all()
        return CacheSearchResponse(
            items=[product_to_out(product) for product in products],
            total=total,
            limit=limit,
            offset=offset,
        )

    def search_pid_catalog(self, *, query: str | None = None, limit: int = 50, offset: int = 0) -> PidCatalogSearchResponse:
        q = self.db.query(PidCatalog)
        if query:
            like = f"%{query.strip()}%"
            q = q.filter(
                (PidCatalog.pid.ilike(like))
                | (PidCatalog.normalized_pid.ilike(like))
                | (PidCatalog.technology.ilike(like))
                | (PidCatalog.category_name.ilike(like))
                | (PidCatalog.product_name.ilike(like))
            )
        total = q.count()
        entries = q.order_by(PidCatalog.updated_at.desc()).offset(offset).limit(limit).all()
        return PidCatalogSearchResponse(items=[catalog_to_out(entry) for entry in entries], total=total, limit=limit, offset=offset)

    def get_stats(self) -> CacheStatsResponse:
        total = self.db.query(func.count(ProductEox.id)).scalar() or 0
        total_catalog = self.db.query(func.count(PidCatalog.id)).scalar() or 0
        by_status = dict(self.db.query(ProductEox.status, func.count(ProductEox.id)).group_by(ProductEox.status).all())
        by_source = dict(self.db.query(ProductEox.source, func.count(ProductEox.id)).group_by(ProductEox.source).all())
        by_catalog_source = dict(self.db.query(PidCatalog.source, func.count(PidCatalog.id)).group_by(PidCatalog.source).all())
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = self.db.query(func.count(LookupHistory.id)).filter(LookupHistory.created_at >= since).scalar() or 0
        return CacheStatsResponse(
            total_products=int(total),
            total_pid_catalog=int(total_catalog),
            by_status={str(key): int(value) for key, value in by_status.items()},
            by_source={str(key): int(value) for key, value in by_source.items()},
            by_catalog_source={str(key): int(value) for key, value in by_catalog_source.items()},
            recent_lookups=int(recent),
        )

    def import_legacy_json(self, *, path: str | None = None, overwrite: bool = False) -> LegacyImportResponse:
        default_path = self.settings.default_eox_db_path
        source_path = Path(path).expanduser().resolve() if path else default_path
        return self.import_preset_json(path=str(source_path), overwrite=overwrite)

    def preset_status(self) -> PresetStatusResponse:
        path = self.settings.preset_seed_path
        if not path.exists():
            return PresetStatusResponse(
                preset_available=False,
                preset_path=str(path),
                approximate_records=None,
                message="Preset file is not present yet. Generate it with tools/auto_pop_pid_database.py or copy your JSON to this path.",
            )
        approximate = None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            approximate = self._count_preset_records(data)
        except Exception:
            pass
        return PresetStatusResponse(
            preset_available=True,
            preset_path=str(path),
            approximate_records=approximate,
            message="Bundled preset file is available",
        )

    def import_preset_json(self, *, path: str | None = None, overwrite: bool = False) -> LegacyImportResponse:
        source_path = Path(path).expanduser().resolve() if path else self.settings.preset_seed_path
        if not source_path.exists():
            return LegacyImportResponse(
                imported=0,
                skipped=0,
                catalog_imported=0,
                catalog_skipped=0,
                message=f"Preset JSON file not found: {source_path}",
            )
        data = json.loads(source_path.read_text(encoding="utf-8"))
        imported = skipped = catalog_imported = catalog_skipped = 0

        for item in self._iter_catalog_entries(data):
            pid = str(item.get("pid") or item.get("name") or item.get("product_name") or "").strip()
            if not pid:
                continue
            _, created_or_changed = self._save_catalog_entry(
                pid=pid,
                technology=item.get("technology") or item.get("category_name") or "Imported",
                category_name=item.get("category_name") or item.get("technology") or "Imported",
                product_name=item.get("product_name") or item.get("name") or pid,
                product_url=item.get("product_url") or item.get("url"),
                is_eox=bool(item.get("is_eox", False)),
                source=item.get("source") or "preset",
                payload=item,
                overwrite=overwrite,
            )
            if created_or_changed or overwrite:
                catalog_imported += 1
            else:
                catalog_skipped += 1

        for pid, payload, technology, source in self._iter_eox_records(data):
            if not pid:
                continue
            if not overwrite and self._get_product(pid):
                skipped += 1
                continue
            self._save_product(
                pid=str(pid),
                technology=technology or "Imported",
                payload=payload,
                source=source or "preset",
                raw_response={"preset": payload},
            )
            self._save_catalog_entry(
                pid=str(pid),
                technology=technology or "Imported",
                category_name=technology or "Imported",
                product_name=str(_payload_value(payload if isinstance(payload, Mapping) else {}, FIELD_ALIASES["product_name"]) or pid),
                product_url=str(_payload_value(payload if isinstance(payload, Mapping) else {}, FIELD_ALIASES["product_bulletin_url"]) or "") or None,
                is_eox=True,
                source=source or "preset",
                payload=payload if isinstance(payload, Mapping) else {"value": payload},
                overwrite=True,
            )
            imported += 1

        self.db.commit()
        return LegacyImportResponse(
            imported=imported,
            skipped=skipped,
            catalog_imported=catalog_imported,
            catalog_skipped=catalog_skipped,
            message=f"Imported preset from {source_path}",
        )

    def discover_catalog(
        self,
        *,
        categories: list[str] | None = None,
        limit_categories: int | None = None,
        include_eox_links: bool = True,
        save_to_database: bool = True,
        crawl_models: bool = False,
        limit_series: int | None = None,
    ) -> CatalogDiscoveryResponse:
        scraper = CiscoEoxScraperService()
        available = scraper.category()
        selected_names = categories or list(available.keys())
        selected_names = [name for name in selected_names if name in available]
        if limit_categories:
            selected_names = selected_names[:limit_categories]

        inserted = skipped = 0
        series_pages_opened = 0
        for category_name in selected_names:
            opened = scraper.open_cat(available[category_name])
            if not opened:
                continue
            series, eox = opened
            if save_to_database:
                for name, url in series.items():
                    is_eox = bool(eox and name in eox)
                    _entry, changed = self._save_catalog_entry(
                        pid=name,
                        technology=category_name,
                        category_name=category_name,
                        product_name=name,
                        product_url=url,
                        is_eox=is_eox,
                        source="online-discovery",
                        payload={"source_url": url, "category": category_name, "kind": "series"},
                        overwrite=True,
                    )
                    inserted += int(changed)
                    skipped += int(not changed)
                    if crawl_models and url and (limit_series is None or series_pages_opened < limit_series):
                        series_pages_opened += 1
                        for model_name in scraper.extract_models_from_series_page(url):
                            _model_entry, model_changed = self._save_catalog_entry(
                                pid=model_name,
                                technology=category_name,
                                category_name=category_name,
                                product_name=model_name,
                                product_url=url,
                                is_eox=is_eox,
                                source="online-discovery",
                                payload={"source_url": url, "category": category_name, "kind": "model", "parent_series": name},
                                overwrite=True,
                            )
                            inserted += int(model_changed)
                            skipped += int(not model_changed)
                if include_eox_links and eox:
                    for name, url in eox.items():
                        _entry, changed = self._save_catalog_entry(
                            pid=name,
                            technology=category_name,
                            category_name=category_name,
                            product_name=name,
                            product_url=url,
                            is_eox=True,
                            source="online-discovery",
                            payload={"source_url": url, "category": category_name},
                            overwrite=True,
                        )
                        inserted += int(changed)
                        skipped += int(not changed)
        if save_to_database:
            self.db.commit()
        return CatalogDiscoveryResponse(
            categories_seen=len(selected_names),
            catalog_inserted_or_updated=inserted,
            catalog_skipped=skipped,
            message=f"Catalog discovery completed. Series pages opened for models: {series_pages_opened}",
        )

    @staticmethod
    def _count_preset_records(data: Any) -> int:
        if isinstance(data, Mapping):
            count = 0
            count += len(data.get("pid_catalog") or []) if isinstance(data.get("pid_catalog"), list) else 0
            count += len(data.get("eox_records") or []) if isinstance(data.get("eox_records"), list) else 0
            count += len(data.get("EOXRecord") or []) if isinstance(data.get("EOXRecord"), list) else 0
            if not count and all(isinstance(value, Mapping) for value in data.values()):
                count = len(data)
            return count
        if isinstance(data, list):
            return len(data)
        return 0

    @staticmethod
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
                if isinstance(entry, Mapping) and not any(key in entry for key in ("EndOfSaleDate", "EOLProductID")):
                    yield entry

    @staticmethod
    def _iter_eox_records(data: Any) -> Iterable[tuple[str, Any, str, str]]:
        if isinstance(data, Mapping):
            if isinstance(data.get("EOXRecord"), list):
                for record in data["EOXRecord"]:
                    if isinstance(record, Mapping):
                        pid = str(record.get("EOLProductID") or record.get("ProductID") or record.get("EOXInputValue") or "").strip()
                        yield pid, record, "Imported", "preset"
            if isinstance(data.get("eox_records"), list):
                for record in data["eox_records"]:
                    if not isinstance(record, Mapping):
                        continue
                    pid = str(record.get("pid") or record.get("EOLProductID") or "").strip()
                    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else record
                    yield pid, payload, str(record.get("technology") or "Imported"), str(record.get("source") or "preset")
            # Legacy flat {pid: payload} JSON.
            structural_keys = {"schema_version", "generated_at", "source", "pid_catalog", "eox_records", "EOXRecord", "metadata"}
            if not any(key in data for key in structural_keys):
                for pid, payload in data.items():
                    yield str(pid), payload, "Imported", "legacy-json"
        elif isinstance(data, list):
            for record in data:
                if isinstance(record, Mapping):
                    pid = str(record.get("pid") or record.get("EOLProductID") or record.get("ProductID") or "").strip()
                    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else record
                    yield pid, payload, str(record.get("technology") or "Imported"), str(record.get("source") or "preset")
