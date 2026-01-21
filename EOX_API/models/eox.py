from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class CategoryResponse(BaseModel):
    categories: Dict[str, str]

class OpenCategoryRequest(BaseModel):
    link: str = Field(..., description="Cisco relative link like /c/en/us/support/...")

class OpenCategoryResponse(BaseModel):
    series: Dict[str, str] = Field(default_factory=dict)
    eox: Optional[Dict[str, str]] = None

class FindSeriesLinkRequest(BaseModel):
    pid: str
    technology: str = Field(..., description="e.g. 'Routing and Switching'")

class FindSeriesLinkResponse(BaseModel):
    pid: str
    technology: str
    series_link: Optional[str] = None
    matched: bool
    note: Optional[str] = None

class EoxCheckRequest(BaseModel):
    product_link: str

class EoxCheckResponse(BaseModel):
    product_link: str
    has_eox_link: bool
    eol_data: Optional[Dict[str, str]] = None

class EoxDetailsRequest(BaseModel):
    redirect_link: str

class EoxDetailsResponse(BaseModel):
    redirect_link: str
    announcement_urls: Dict[str, str]

class EoxScrapeRequest(BaseModel):
    announcement_link: str

class EoxScrapeResponse(BaseModel):
    announcement_link: str
    milestones: Dict[str, str]
    affected_devices: List[str]

class ErrorResponse(BaseModel):
    detail: str
    meta: Optional[Dict[str, Any]] = None
