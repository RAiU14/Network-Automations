from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from sqlalchemy import func, or_
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import AutoPopJob, EoxAffectedProduct, EoxAnnouncement, EoxAnnouncementTable, LookupHistory, PidCatalog, ProductEox
from app.schemas import (
    AutoPopulateResponse,
    CacheSearchResponse,
    CacheStatsResponse,
    CatalogDiscoveryResponse,
    EoxEvidenceResponse,
    EoxProductOut,
    LookupResponse,
    PidCatalogOut,
    PidCatalogSearchResponse,
    PidLookupResult,
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
    return "unknown" if source in {"cache", "seed"} else "not_found"


def _slim_lookup_payload(pid: str, technology: str, payload: Any, source: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"PID": pid, "technology": technology, "source": source, "message": str(payload)}
    output: dict[str, Any] = {"PID": pid, "ProductID": pid, "EOLProductID": pid, "technology": technology, "source": source}
    for key in (
        "ProductIDDescription",
        "ProductDescription",
        "Product Name",
        "Series",
        "End-of-Sale Date",
        "End-of-Sale Date: HW",
        "Last Date of Support",
        "Last Date of Support: HW",
        "End of SW Maintenance Releases Date",
        "End of SW Maintenance Releases Date: HW",
        "End of Vulnerability/Security Support",
        "End of Vulnerability/Security Support: HW",
        "End of Routine Failure Analysis Date",
        "End of Routine Failure Analysis Date:  HW",
        "EOXAnnouncementURL",
        "AnnouncementURL",
        "url",
        "ProductBulletinURL",
        "LinkToProductBulletinURL",
    ):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            output[key] = value.get("value") if isinstance(value, Mapping) else value
    return output


def _slim_raw_payload(payload: Any, source: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {"source": source, "message": str(payload)[:4000]}
    return {
        "source": source,
        "keys": sorted(str(key) for key in payload.keys())[:100],
        "eox_announcement_url": _payload_value(payload, FIELD_ALIASES["eox_announcement_url"]),
        "product_bulletin_url": _payload_value(payload, FIELD_ALIASES["product_bulletin_url"]),
    }


def _row_columns(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    if isinstance(payload.get("columns"), Mapping):
        return dict(payload["columns"])
    row = payload.get("affected_product_row")
    if isinstance(row, Mapping) and isinstance(row.get("columns"), Mapping):
        return dict(row["columns"])
    return {}


def _product_dict(product: ProductEox | None) -> dict[str, Any] | None:
    if product is None:
        return None
    return {
        "pid": product.pid,
        "normalized_pid": product.normalized_pid,
        "technology": product.technology,
        "status": product.status,
        "source": product.source,
        "product_name": product.product_name,
        "series": product.series,
        "end_of_sale_date": product.end_of_sale_date,
        "last_date_of_support": product.last_date_of_support,
        "end_of_sw_maintenance": product.end_of_sw_maintenance,
        "end_of_security_support": product.end_of_security_support,
        "end_of_routine_failure_analysis": product.end_of_routine_failure_analysis,
        "eox_announcement_url": product.eox_announcement_url,
        "product_bulletin_url": product.product_bulletin_url,
        "lookup_count": product.lookup_count or 0,
        "last_lookup_at": product.last_lookup_at.isoformat() if hasattr(product.last_lookup_at, "isoformat") else None,
        "last_scraped_at": product.last_scraped_at.isoformat() if hasattr(product.last_scraped_at, "isoformat") else None,
        "updated_at": product.updated_at.isoformat() if hasattr(product.updated_at, "isoformat") else None,
        "payload": product.payload or {},
    }

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
        source: str = "seed",
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
        payload_dict = _slim_lookup_payload(pid, technology, payload, source)
        raw_dict = _slim_raw_payload(raw_response if raw_response is not None else payload, source)
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
        product.last_scraped_at = datetime.now(timezone.utc) if source in {"api", "scraper", "seed"} else product.last_scraped_at
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
            message="Served from local database cache",
            snapshot=product.payload,
        )
        return PidLookupResult(
            pid=query_pid,
            normalized_pid=normalize_pid(query_pid),
            found=True,
            from_cache=True,
            source_used="cache",
            status=product.status,
            message="Served from local database cache",
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
            source_used="seed",
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
                catalog_entry = self._get_catalog(pid, technology)
                if catalog_entry and not refresh and not auto_learn:
                    results_by_norm[normalize_pid(pid)] = self._catalog_only_result(pid, technology, catalog_entry)
                else:
                    missing.append(pid)

        api_available = CredentialStore(self.db).cisco_credentials_configured()
        if missing and (prefer_api or api_available):
            api_results, unresolved = self._lookup_with_api(missing, technology, auto_learn=auto_learn)
            results_by_norm.update({normalize_pid(item.pid): item for item in api_results})
            missing = unresolved

        if missing:
            scraper_results = self._lookup_with_scraper(missing, technology, auto_learn=auto_learn)
            results_by_norm.update({normalize_pid(item.pid): item for item in scraper_results})

        ordered = [results_by_norm.get(normalize_pid(pid)) for pid in clean_pids]
        final_results = [item for item in ordered if item is not None]
        try:
            self.db.commit()
        except OperationalError as exc:
            logger.warning("Lookup result returned without saving lookup metadata because the database was busy: %s", exc)
            self.db.rollback()
        except SQLAlchemyError as exc:
            logger.warning("Lookup result returned without saving lookup metadata: %s", exc)
            self.db.rollback()
        summary = {
            "total": len(final_results),
            "cache_hits": sum(1 for item in final_results if item.source_used == "cache"),
            "catalog_hits": sum(1 for item in final_results if item.source_used == "seed"),
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
        total_announcements = self.db.query(func.count(EoxAnnouncement.id)).scalar() or 0
        total_tables = self.db.query(func.count(EoxAnnouncementTable.id)).scalar() or 0
        total_affected = self.db.query(func.count(EoxAffectedProduct.id)).scalar() or 0
        total_jobs = self.db.query(func.count(AutoPopJob.id)).scalar() or 0
        by_status = dict(self.db.query(ProductEox.status, func.count(ProductEox.id)).group_by(ProductEox.status).all())
        by_source = dict(self.db.query(ProductEox.source, func.count(ProductEox.id)).group_by(ProductEox.source).all())
        by_catalog_source = dict(self.db.query(PidCatalog.source, func.count(PidCatalog.id)).group_by(PidCatalog.source).all())
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = self.db.query(func.count(LookupHistory.id)).filter(LookupHistory.created_at >= since).scalar() or 0
        return CacheStatsResponse(
            total_products=int(total),
            total_pid_catalog=int(total_catalog),
            total_announcements=int(total_announcements),
            total_announcement_tables=int(total_tables),
            total_affected_products=int(total_affected),
            total_autopop_jobs=int(total_jobs),
            by_status={str(key): int(value) for key, value in by_status.items()},
            by_source={str(key): int(value) for key, value in by_source.items()},
            by_catalog_source={str(key): int(value) for key, value in by_catalog_source.items()},
            recent_lookups=int(recent),
        )

    def get_product_evidence(self, pid: str, *, table_limit: int = 20, row_limit: int = 500) -> EoxEvidenceResponse:
        normalized = normalize_pid(pid)
        product = self.db.query(ProductEox).filter(ProductEox.normalized_pid == normalized).one_or_none()
        affected = (
            self.db.query(EoxAffectedProduct)
            .filter(EoxAffectedProduct.normalized_pid == normalized)
            .order_by(EoxAffectedProduct.updated_at.desc())
            .limit(200)
            .all()
        )
        if product and product.id:
            seen_ids = {item.id for item in affected}
            extra = (
                self.db.query(EoxAffectedProduct)
                .filter(EoxAffectedProduct.product_id == product.id)
                .order_by(EoxAffectedProduct.updated_at.desc())
                .limit(200)
                .all()
            )
            affected.extend(item for item in extra if item.id not in seen_ids)
        announcement_ids = sorted({item.announcement_id for item in affected if item.announcement_id})
        if not announcement_ids and product and product.eox_announcement_url:
            announcement = self.db.query(EoxAnnouncement).filter(EoxAnnouncement.announcement_url == product.eox_announcement_url).one_or_none()
            if announcement:
                announcement_ids = [announcement.id]
        announcements = (
            self.db.query(EoxAnnouncement)
            .filter(EoxAnnouncement.id.in_(announcement_ids))
            .order_by(EoxAnnouncement.updated_at.desc())
            .all()
            if announcement_ids
            else []
        )
        tables = (
            self.db.query(EoxAnnouncementTable)
            .filter(EoxAnnouncementTable.announcement_id.in_(announcement_ids))
            .order_by(EoxAnnouncementTable.announcement_id.asc(), EoxAnnouncementTable.table_index.asc())
            .limit(max(1, min(table_limit, 100)))
            .all()
            if announcement_ids
            else []
        )
        affected_payload = []
        for item in affected:
            affected_payload.append(
                {
                    "id": item.id,
                    "announcement_id": item.announcement_id,
                    "product_id": item.product_id,
                    "pid": item.pid,
                    "normalized_pid": item.normalized_pid,
                    "technology": item.technology,
                    "product_description": item.product_description,
                    "source": item.source,
                    "table_index": item.table_index,
                    "row_index": item.row_index,
                    "columns": _row_columns(item.payload or {}),
                    "milestones": (item.payload or {}).get("milestones", {}),
                    "updated_at": item.updated_at.isoformat() if hasattr(item.updated_at, "isoformat") else None,
                }
            )
        announcement_payload = []
        for item in announcements:
            announcement_payload.append(
                {
                    "id": item.id,
                    "announcement_url": item.announcement_url,
                    "announcement_name": item.announcement_name,
                    "title": item.title,
                    "product_bulletin_url": item.product_bulletin_url,
                    "technology": item.technology,
                    "series": item.series,
                    "series_url": item.series_url,
                    "source": item.source,
                    "updated_at": item.updated_at.isoformat() if hasattr(item.updated_at, "isoformat") else None,
                }
            )
        table_payload = []
        bounded_row_limit = max(1, min(row_limit, 5000))
        for item in tables:
            rows = item.rows or []
            table_payload.append(
                {
                    "id": item.id,
                    "announcement_id": item.announcement_id,
                    "table_index": item.table_index,
                    "heading": item.heading,
                    "caption": item.caption,
                    "headers": item.headers or [],
                    "rows": rows[:bounded_row_limit],
                    "row_count": len(rows),
                    "truncated": len(rows) > bounded_row_limit,
                    "updated_at": item.updated_at.isoformat() if hasattr(item.updated_at, "isoformat") else None,
                }
            )
        return EoxEvidenceResponse(
            product=_product_dict(product),
            affected_products=affected_payload,
            announcements=announcement_payload,
            tables=table_payload,
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
