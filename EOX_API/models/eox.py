from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CategoryResponse(BaseModel):
    categories: dict[str, str]


class OpenCategoryRequest(BaseModel):
    link: str = Field(..., description="Cisco relative link like /c/en/us/support/...")


class OpenCategoryResponse(BaseModel):
    series: dict[str, str] = Field(default_factory=dict)
    eox: dict[str, str] | None = None


class FindSeriesLinkRequest(BaseModel):
    pid: str
    technology: str = Field("Routing and Switching", description="Example: Routing and Switching")


class FindSeriesLinkResponse(BaseModel):
    pid: str
    technology: str
    series_link: str | None = None
    matched: bool
    note: str | None = None


class EoxCheckRequest(BaseModel):
    product_link: str


class EoxCheckResponse(BaseModel):
    product_link: str
    has_eox_link: bool
    eol_data: dict[str, str] = Field(default_factory=dict)


class EoxDetailsRequest(BaseModel):
    redirect_link: str


class EoxDetailsResponse(BaseModel):
    redirect_link: str
    announcement_urls: dict[str, str]


class EoxScrapeRequest(BaseModel):
    announcement_link: str


class EoxScrapeResponse(BaseModel):
    announcement_link: str
    milestones: dict[str, str]
    affected_devices: list[str]


class PidLookupRequest(BaseModel):
    pids: list[str] = Field(..., min_length=1)
    technology: str = "Routing and Switching"
    use_cache: bool = True


class PidLookupResponse(BaseModel):
    results: dict[str, Any]


class HardwareEoxRequest(BaseModel):
    pids: list[str] = Field(..., min_length=1)


class HardwareEoxResponse(BaseModel):
    results: dict[str, dict[str, Any]]


class SoftwareMilestonesRequest(BaseModel):
    device_versions: dict[str, list[str] | str] = Field(
        ...,
        description="Mapping of PID to one or more software versions",
    )


class SoftwareMilestonesResponse(BaseModel):
    results: dict[str, Any]


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "Cisco EOX API"
