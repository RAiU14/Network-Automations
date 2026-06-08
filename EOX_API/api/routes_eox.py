from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from EOX_API.models.eox import (
    CategoryResponse,
    EoxCheckRequest,
    EoxCheckResponse,
    EoxDetailsRequest,
    EoxDetailsResponse,
    EoxScrapeRequest,
    EoxScrapeResponse,
    FindSeriesLinkRequest,
    FindSeriesLinkResponse,
    HardwareEoxRequest,
    HardwareEoxResponse,
    OpenCategoryRequest,
    OpenCategoryResponse,
    PidLookupRequest,
    PidLookupResponse,
    SoftwareMilestonesRequest,
    SoftwareMilestonesResponse,
)
from EOX_API.services.cisco_api_client import CiscoApiClient, CiscoApiError
from EOX_API.services.cisco_eox_scraper import CiscoEoxScraperService

router = APIRouter(prefix="/eox", tags=["Cisco EOX"])


def get_scraper_service() -> CiscoEoxScraperService:
    return CiscoEoxScraperService()


def get_api_client() -> CiscoApiClient:
    return CiscoApiClient()


@router.get("/categories", response_model=CategoryResponse)
def get_categories(service: CiscoEoxScraperService = Depends(get_scraper_service)) -> CategoryResponse:
    return CategoryResponse(categories=service.category())


@router.post("/open-category", response_model=OpenCategoryResponse)
def open_category(
    request: OpenCategoryRequest,
    service: CiscoEoxScraperService = Depends(get_scraper_service),
) -> OpenCategoryResponse:
    output = service.open_cat(request.link)
    if output is None:
        raise HTTPException(status_code=502, detail="Failed to open Cisco category page")
    series, eox = output
    return OpenCategoryResponse(series=series, eox=eox)


@router.post("/find-series-link", response_model=FindSeriesLinkResponse)
def find_series_link(
    request: FindSeriesLinkRequest,
    service: CiscoEoxScraperService = Depends(get_scraper_service),
) -> FindSeriesLinkResponse:
    link = service.find_device_series_link(request.pid, request.technology)
    return FindSeriesLinkResponse(
        pid=request.pid,
        technology=request.technology,
        series_link=link,
        matched=bool(link),
        note=None if link else "No matching Cisco series page found",
    )


@router.post("/check-product", response_model=EoxCheckResponse)
def check_product(
    request: EoxCheckRequest,
    service: CiscoEoxScraperService = Depends(get_scraper_service),
) -> EoxCheckResponse:
    output = service.eox_check(request.product_link)
    if output is None:
        raise HTTPException(status_code=404, detail="No EOX information found on Cisco product page")
    has_link, eol_data = output
    return EoxCheckResponse(product_link=request.product_link, has_eox_link=has_link, eol_data=eol_data)


@router.post("/details", response_model=EoxDetailsResponse)
def details(
    request: EoxDetailsRequest,
    service: CiscoEoxScraperService = Depends(get_scraper_service),
) -> EoxDetailsResponse:
    urls = service.eox_details(request.redirect_link)
    if urls is None:
        raise HTTPException(status_code=502, detail="Failed to fetch Cisco EOX details page")
    return EoxDetailsResponse(redirect_link=request.redirect_link, announcement_urls=urls)


@router.post("/scrape", response_model=EoxScrapeResponse)
def scrape(
    request: EoxScrapeRequest,
    service: CiscoEoxScraperService = Depends(get_scraper_service),
) -> EoxScrapeResponse:
    output = service.eox_scraping(request.announcement_link)
    if output is None:
        raise HTTPException(status_code=502, detail="Failed to scrape Cisco EOX announcement page")
    milestones, affected_devices = output
    return EoxScrapeResponse(
        announcement_link=request.announcement_link,
        milestones=milestones,
        affected_devices=affected_devices,
    )


@router.post("/lookup-pids", response_model=PidLookupResponse)
def lookup_pids(
    request: PidLookupRequest,
    service: CiscoEoxScraperService = Depends(get_scraper_service),
) -> PidLookupResponse:
    if request.use_cache:
        results = service.request_eox_data_from_local_db(request.pids, request.technology)
    else:
        results = service.request_eox_data_from_online(request.pids, request.technology)
    return PidLookupResponse(results=results)


@router.post("/hardware-milestones", response_model=HardwareEoxResponse)
def hardware_milestones(
    request: HardwareEoxRequest,
    client: CiscoApiClient = Depends(get_api_client),
) -> HardwareEoxResponse:
    try:
        return HardwareEoxResponse(results=client.get_hardware_eox_by_product_id(request.pids))
    except CiscoApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/software-milestones", response_model=SoftwareMilestonesResponse)
def software_milestones(
    request: SoftwareMilestonesRequest,
    client: CiscoApiClient = Depends(get_api_client),
) -> SoftwareMilestonesResponse:
    try:
        return SoftwareMilestonesResponse(results=client.software_milestones(request.device_versions))
    except CiscoApiError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
