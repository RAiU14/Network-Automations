from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import (
    AutoPopulateRequest,
    AutoPopulateResponse,
    CacheSearchResponse,
    CacheStatsResponse,
    CatalogDiscoveryRequest,
    CatalogDiscoveryResponse,
    LegacyImportRequest,
    LegacyImportResponse,
    LookupRequest,
    LookupResponse,
    PidCatalogSearchResponse,
    PresetImportRequest,
    PresetStatusResponse,
)
from app.services.eox_orchestrator import EoxOrchestrator

router = APIRouter(prefix="/eox", tags=["EOX"])


@router.post("/lookup", response_model=LookupResponse)
def lookup_eox(request: LookupRequest, db: Session = Depends(get_db)) -> LookupResponse:
    return EoxOrchestrator(db).lookup_pids(
        request.pids,
        technology=request.technology,
        refresh=request.refresh,
        prefer_api=request.prefer_api,
        auto_learn=request.auto_learn,
    )


@router.post("/auto-populate", response_model=AutoPopulateResponse)
def auto_populate(request: AutoPopulateRequest, db: Session = Depends(get_db)) -> AutoPopulateResponse:
    return EoxOrchestrator(db).auto_populate(
        request.pids,
        technology=request.technology,
        refresh_existing=request.refresh_existing,
        prefer_api=request.prefer_api,
    )


@router.get("/cache", response_model=CacheSearchResponse)
def search_cache(
    q: str | None = Query(default=None, description="Search PID, normalized PID, technology, or status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> CacheSearchResponse:
    return EoxOrchestrator(db).search_cache(query=q, limit=limit, offset=offset)


@router.get("/pid-catalog", response_model=PidCatalogSearchResponse)
def search_pid_catalog(
    q: str | None = Query(default=None, description="Search the local PID/series catalog"),
    limit: int = Query(default=50, ge=1, le=300),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PidCatalogSearchResponse:
    return EoxOrchestrator(db).search_pid_catalog(query=q, limit=limit, offset=offset)


@router.get("/stats", response_model=CacheStatsResponse)
def cache_stats(db: Session = Depends(get_db)) -> CacheStatsResponse:
    return EoxOrchestrator(db).get_stats()


@router.get("/preset", response_model=PresetStatusResponse)
def preset_status(db: Session = Depends(get_db)) -> PresetStatusResponse:
    return EoxOrchestrator(db).preset_status()


@router.post("/import-preset", response_model=LegacyImportResponse)
def import_preset(request: PresetImportRequest, db: Session = Depends(get_db)) -> LegacyImportResponse:
    return EoxOrchestrator(db).import_preset_json(path=request.path, overwrite=request.overwrite)


@router.post("/import-legacy-json", response_model=LegacyImportResponse)
def import_legacy_json(request: LegacyImportRequest, db: Session = Depends(get_db)) -> LegacyImportResponse:
    return EoxOrchestrator(db).import_legacy_json(path=request.path, overwrite=request.overwrite)


@router.post("/discover-catalog", response_model=CatalogDiscoveryResponse)
def discover_catalog(request: CatalogDiscoveryRequest, db: Session = Depends(get_db)) -> CatalogDiscoveryResponse:
    return EoxOrchestrator(db).discover_catalog(
        categories=request.categories,
        limit_categories=request.limit_categories,
        include_eox_links=request.include_eox_links,
        save_to_database=request.save_to_database,
        crawl_models=request.crawl_models,
        limit_series=request.limit_series,
    )
