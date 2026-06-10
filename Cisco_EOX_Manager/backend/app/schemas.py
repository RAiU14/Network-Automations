from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "Cisco EOX Manager"
    database_ready: bool = False
    database_error: str | None = None


class SetupStatusResponse(BaseModel):
    database_ready: bool
    database_error: str | None = None
    database_url_hint: str = ""
    database_config_source: str = "environment"
    cisco_credentials_configured: bool
    client_id_hint: str | None = None
    api_base_url: str
    token_url: str
    has_cached_token: bool
    graphql_enabled: bool = True
    recommended_database_type: str = "sqlite"


class DatabaseSetupRequest(BaseModel):
    database_type: Literal["postgresql", "sqlite", "url"] = Field(
        "postgresql",
        description="Database mode selected from the setup UI",
    )
    database_url: str | None = Field(None, description="Full SQLAlchemy database URL for advanced mode")
    sqlite_path: str | None = Field(None, description="SQLite file path. Relative paths are stored in the product data directory.")
    host: str = "postgres"
    port: int = Field(5432, ge=1, le=65535)
    database: str = "eox_cache"
    username: str = "eox_user"
    password: str = "eox_password"
    initialize_after_save: bool = True
    write_env_file: bool = True
    test_only: bool = False


class DatabaseSetupResponse(BaseModel):
    ok: bool
    tested: bool
    saved: bool
    initialized: bool
    database_url_hint: str
    message: str
    env_file: str | None = None


class CiscoSetupRequest(BaseModel):
    client_id: str | None = Field(None, description="Cisco API client ID")
    client_secret: str | None = Field(None, description="Cisco API client secret")
    access_token: str | None = Field(None, description="Optional existing Cisco access token")
    token_expires_in_seconds: int | None = Field(None, ge=60)
    api_base_url: str | None = None
    token_url: str | None = None
    grant_type: str = "client_credentials"
    test_connection: bool = False


class CiscoSetupResponse(BaseModel):
    configured: bool
    tested: bool = False
    message: str
    token_cached: bool = False


class LookupRequest(BaseModel):
    pids: list[str] = Field(..., min_length=1)
    technology: str = "Routing and Switching"
    refresh: bool = False
    prefer_api: bool = False
    auto_learn: bool = True


class EoxProductOut(BaseModel):
    pid: str
    normalized_pid: str
    technology: str | None = None
    status: str
    source: str
    product_name: str | None = None
    series: str | None = None
    end_of_sale_date: str | None = None
    last_date_of_support: str | None = None
    end_of_sw_maintenance: str | None = None
    end_of_security_support: str | None = None
    end_of_routine_failure_analysis: str | None = None
    eox_announcement_url: str | None = None
    product_bulletin_url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    lookup_count: int = 0
    last_lookup_at: datetime | None = None
    last_scraped_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PidCatalogOut(BaseModel):
    pid: str
    normalized_pid: str
    technology: str | None = None
    category_name: str | None = None
    product_name: str | None = None
    product_url: str | None = None
    is_eox: bool = False
    source: str = "seed"
    payload: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class PidLookupResult(BaseModel):
    pid: str
    normalized_pid: str
    found: bool
    from_cache: bool
    source_used: Literal["cache", "api", "scraper", "seed", "none", "error"]
    status: str
    message: str | None = None
    product: EoxProductOut | None = None
    catalog_entry: PidCatalogOut | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class LookupResponse(BaseModel):
    results: list[PidLookupResult]
    summary: dict[str, int]


class AutoPopulateRequest(BaseModel):
    pids: list[str] = Field(..., min_length=1)
    technology: str = "Routing and Switching"
    refresh_existing: bool = False
    prefer_api: bool = False
    batch_note: str | None = None


class AutoPopulateResponse(BaseModel):
    inserted_or_updated: int
    cache_hits: int
    failed: int
    results: list[PidLookupResult]


class CacheSearchResponse(BaseModel):
    items: list[EoxProductOut]
    total: int
    limit: int
    offset: int


class PidCatalogSearchResponse(BaseModel):
    items: list[PidCatalogOut]
    total: int
    limit: int
    offset: int


class CacheStatsResponse(BaseModel):
    total_products: int
    total_pid_catalog: int
    by_status: dict[str, int]
    by_source: dict[str, int]
    by_catalog_source: dict[str, int]
    recent_lookups: int


class FrontendLogRequest(BaseModel):
    level: Literal["debug", "info", "warning", "error"] = "info"
    event_type: str = "frontend"
    message: str
    source: str = "front_end"
    payload: dict[str, Any] = Field(default_factory=dict)


class SystemEventOut(BaseModel):
    id: int
    level: str
    event_type: str
    source: str | None = None
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SystemEventResponse(BaseModel):
    ok: bool
    event: SystemEventOut | None = None
    message: str


class CatalogDiscoveryRequest(BaseModel):
    categories: list[str] = Field(default_factory=list, description="Optional Cisco category names. Empty means all categories.")
    limit_categories: int | None = Field(None, ge=1, le=100)
    include_eox_links: bool = True
    save_to_database: bool = True
    crawl_models: bool = False
    limit_series: int | None = Field(None, ge=1, le=10000)


class CatalogDiscoveryResponse(BaseModel):
    categories_seen: int
    catalog_inserted_or_updated: int
    catalog_skipped: int
    message: str


class AuthSetupRequest(BaseModel):
    admin_token: str = Field(..., min_length=12)
    current_token: str | None = None


class AutoPopJobRequest(BaseModel):
    categories: list[str] = Field(default_factory=list)
    category_urls: list[str] = Field(default_factory=list)
    limit_categories: int | None = Field(None, ge=1, le=100)
    limit_series_eox: int | None = Field(None, ge=1)
    limit_announcements: int | None = Field(None, ge=1)
    eox_candidates_only: bool = False
    parse_workers: int = Field(2, ge=1, le=8)
    delay: float = Field(1.0, ge=0, le=60)
    category_break: float = Field(10.0, ge=0, le=3600)
    force_refresh: bool = False
    overwrite: bool = False
    allow_empty: bool = False
    use_api: bool = False
    note: str | None = None


class AutoPopJobOut(BaseModel):
    id: int
    status: str
    requested_by: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    command: list[str] = Field(default_factory=list)
    log_file: str | None = None
    process_id: int | None = None
    return_code: int | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class AutoPopJobListResponse(BaseModel):
    items: list[AutoPopJobOut]
    total: int
    limit: int
    offset: int


class ExportRequest(BaseModel):
    dataset: Literal["products", "pid_catalog", "affected_products", "announcements", "checkpoints", "system_events"] = "products"
    format: Literal["csv", "xlsx"] = "csv"
    search: str | None = None
    limit: int = Field(10000, ge=1, le=100000)
