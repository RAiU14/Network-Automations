from fastapi import APIRouter, HTTPException, Depends

from EOX_API.models.eox import (
    CategoryResponse, OpenCategoryRequest, OpenCategoryResponse,
    FindSeriesLinkRequest, FindSeriesLinkResponse,
    EoxCheckRequest, EoxCheckResponse,
    EoxDetailsRequest, EoxDetailsResponse,
    EoxScrapeRequest, EoxScrapeResponse,
)
from EOX_API.services.cisco_eox_scrapper import CiscoEoxScraperService

router = APIRouter(prefix="/eox", tags=["Cisco EOX"])

def get_service() -> CiscoEoxScraperService:
    return CiscoEoxScraperService()

@router.get("/categories", response_model=CategoryResponse)
def get_categories(svc: CiscoEoxScraperService = Depends(get_service)):
    return CategoryResponse(categories=svc.category())

@router.post("/open-category", response_model=OpenCategoryResponse)
def open_category(req: OpenCategoryRequest, svc: CiscoEoxScraperService = Depends(get_service)):
    out = svc.open_cat(req.link)
    if out is None:
        raise HTTPException(status_code=500, detail="Failed to open category")
    series, eox = out
    return OpenCategoryResponse(series=series, eox=eox)

@router.post("/find-series-link", response_model=FindSeriesLinkResponse)
def find_series_link(req: FindSeriesLinkRequest, svc: CiscoEoxScraperService = Depends(get_service)):
    link = svc.find_device_series_link(req.pid, req.technology)
    return FindSeriesLinkResponse(
        pid=req.pid,
        technology=req.technology,
        series_link=link,
        matched=bool(link),
        note=None if link else "No match found",
    )

@router.post("/check-product", response_model=EoxCheckResponse)
def check_product(req: EoxCheckRequest, svc: CiscoEoxScraperService = Depends(get_service)):
    out = svc.eox_check(req.product_link)
    if out is None:
        raise HTTPException(status_code=404, detail="No EOX info found on product page")
    has_link, eol = out
    return EoxCheckResponse(product_link=req.product_link, has_eox_link=has_link, eol_data=eol)

@router.post("/details", response_model=EoxDetailsResponse)
def details(req: EoxDetailsRequest, svc: CiscoEoxScraperService = Depends(get_service)):
    urls = svc.eox_details(req.redirect_link)
    if urls is None:
        raise HTTPException(status_code=500, detail="Failed to fetch EOX details page")
    return EoxDetailsResponse(redirect_link=req.redirect_link, announcement_urls=urls)

@router.post("/scrape", response_model=EoxScrapeResponse)
def scrape(req: EoxScrapeRequest, svc: CiscoEoxScraperService = Depends(get_service)):
    out = svc.eox_scrapping(req.announcement_link)
    if out is None:
        raise HTTPException(status_code=500, detail="Failed to scrape announcement page")
    milestones, devices = out
    return EoxScrapeResponse(announcement_link=req.announcement_link, milestones=milestones, affected_devices=devices)
