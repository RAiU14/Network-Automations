#!/usr/bin/env python3
"""Populate the Cisco EOX Manager database directly.

Auto_Pop crawls Cisco EOX announcement pages, preserves every scraped table,
maps affected PIDs to lifecycle data, and saves the result into PostgreSQL or
SQLite. JSON seed/export files are intentionally not part of this workflow.
JSON-shaped retrieval is exposed later through GraphQL from database records.
"""
from __future__ import annotations

import argparse
import csv
import logging
import os
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
import bs4
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PRODUCT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PRODUCT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.cisco_scraper import CiscoEoxScraperService  # noqa: E402
from app.services.normalization import clean_pid_list, normalize_pid  # noqa: E402

LOG_DIR = PRODUCT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / "auto_pop_pid_database.log", encoding="utf-8"),
    ],
)
LOGGER = logging.getLogger("auto_pop_pid_database")

# Importer field aliases in app.services.eox_orchestrator already understand
# these names match the database persistence layer.
CANONICAL_FIELDS = {
    "end_of_sale_date": "End-of-Sale Date",
    "last_date_of_support": "Last Date of Support",
    "end_of_sw_maintenance": "End of SW Maintenance Releases Date",
    "end_of_security_support": "End of Vulnerability/Security Support",
    "end_of_routine_failure_analysis": "End of Routine Failure Analysis Date",
    "product_bulletin_url": "ProductBulletinURL",
    "eox_announcement_url": "EOXAnnouncementURL",
}

FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "End-of-Sale Date": (
        r"end\s*[- ]?of\s*[- ]?sale\s*date",
        r"end\s*[- ]?of\s*[- ]?sale",
        r"endofsale",
    ),
    "Last Date of Support": (
        r"last\s*date\s*of\s*support",
        r"lastdateofsupport",
        r"last\s*support\s*date",
    ),
    "End of SW Maintenance Releases Date": (
        r"end\s*of\s*(sw|software)\s*maintenance\s*releases?\s*date",
        r"end\s*of\s*(sw|software)\s*maintenance",
        r"endofswmaintenance",
        r"endofsoftwaremaintenance",
    ),
    "End of Vulnerability/Security Support": (
        r"end\s*of\s*vulnerability\s*/?\s*security\s*support",
        r"end\s*of\s*security\s*support",
        r"endofsecurityvulsupport",
        r"endofvulnerabilitysecuritysupport",
    ),
    "End of Routine Failure Analysis Date": (
        r"end\s*of\s*routine\s*failure\s*analysis\s*date",
        r"end\s*of\s*routine\s*failure\s*analysis",
        r"endofroutinefailureanalysis",
    ),
}

DATE_WORDS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
EOX_WORDS = ("eox", "eol", "end-of-sale", "end of sale", "end-of-life", "end of life", "last date of support")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def _looks_like_date_or_marker(value: Any) -> bool:
    text = _as_text(value).lower()
    if not text:
        return False
    if any(month in text for month in DATE_WORDS):
        return True
    if re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text):
        return True
    if re.search(r"\b\d{4}-\d{1,2}-\d{1,2}\b", text):
        return True
    if text in {"tbd", "not announced", "na", "n/a", "not applicable"}:
        return True
    return False


def _empty_seed() -> dict[str, Any]:
    return {
        "schema_version": 3,
        "generated_at": _now(),
        "source": "auto_pop_pid_database.py",
        "metadata": {
            "purpose": "full_pid_to_eox_seed",
            "categories_seen": 0,
            "catalog_records": 0,
            "eox_records": 0,
            "include_eox_links": True,
            "full_eox_crawl": True,
            "table_scrape_mode": "all_announcement_tables",
            "crawl_models": False,
            "api_enabled": False,
            "fallback_used": False,
            "series_pages_checked_for_eox": 0,
            "announcement_pages_scraped": 0,
            "not_announced_series": 0,
            "failed_series": 0,
            "notes": [],
        },
        "categories": {},
        "pid_catalog": [],
        "eox_records": [],
    }


def _catalog_record(
    kind: str,
    name: str,
    url: str | None,
    technology: str,
    is_eox: bool,
    *,
    source: str = "auto_pop",
    product_name: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    pid = _as_text(name)
    tech = _as_text(technology) or "Imported"
    merged_payload: dict[str, Any] = {"kind": kind}
    if url:
        merged_payload["source_url"] = url
    if payload:
        merged_payload.update(dict(payload))
    return {
        "pid": pid,
        "normalized_pid": normalize_pid(pid),
        "product_name": _as_text(product_name) or pid,
        "technology": tech,
        "category_name": tech,
        "product_url": url,
        "is_eox": bool(is_eox),
        "source": source,
        "payload": merged_payload,
    }


def _dedupe_catalog(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        pid = _as_text(record.get("pid") or record.get("name") or record.get("product_name"))
        if not pid:
            continue
        technology = _as_text(record.get("technology") or record.get("category_name")) or "Imported"
        kind = _as_text((record.get("payload") or {}).get("kind") if isinstance(record.get("payload"), Mapping) else record.get("kind")) or "catalog"
        key = (normalize_pid(pid), technology.lower(), kind.lower())
        if key in seen:
            continue
        seen.add(key)
        clean = dict(record)
        clean["pid"] = pid
        clean["normalized_pid"] = normalize_pid(pid)
        clean.setdefault("product_name", pid)
        clean.setdefault("technology", technology)
        clean.setdefault("category_name", technology)
        clean.setdefault("product_url", record.get("url"))
        clean.setdefault("source", "auto_pop")
        clean.setdefault("payload", {"kind": kind})
        clean["is_eox"] = bool(clean.get("is_eox", False))
        output.append(clean)
    return output


def _payload_get(payload: Mapping[str, Any], names: Sequence[str]) -> Any:
    if not isinstance(payload, Mapping):
        return None
    lookup = {_normalize_key(key): key for key in payload.keys()}
    for name in names:
        if name in payload and payload[name] not in (None, ""):
            value = payload[name]
            return value.get("value") if isinstance(value, Mapping) else value
        key = lookup.get(_normalize_key(name))
        if key and payload.get(key) not in (None, ""):
            value = payload[key]
            return value.get("value") if isinstance(value, Mapping) else value
    return None


def _canonicalize_milestones(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(raw or {})
    canonical: dict[str, Any] = {}

    # First preserve any known exact values.
    for key, value in raw.items():
        if value in (None, ""):
            continue
        key_text = _as_text(key)
        value_text = _as_text(value)
        if not key_text or not value_text:
            continue
        canonical[key_text] = value_text

    normalized_items = [(_normalize_key(key), _as_text(key), _as_text(value)) for key, value in raw.items() if _as_text(value)]
    for canonical_field, patterns in FIELD_PATTERNS.items():
        if canonical.get(canonical_field):
            continue
        for normalized_key, original_key, value in normalized_items:
            haystack = f"{normalized_key} {_as_text(original_key).lower()}"
            if any(re.search(pattern, haystack, flags=re.I) for pattern in patterns):
                canonical[canonical_field] = value
                break

    return canonical


def _record_has_lifecycle_dates(record: Mapping[str, Any]) -> bool:
    payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else record
    if not isinstance(payload, Mapping):
        return False
    for field in FIELD_PATTERNS:
        value = _payload_get(payload, [field])
        if _looks_like_date_or_marker(value):
            return True
    return False


def _eox_record(
    *,
    pid: str,
    technology: str,
    source: str,
    milestones: Mapping[str, Any] | None,
    announcement_name: str | None = None,
    announcement_url: str | None = None,
    product_bulletin_url: str | None = None,
    product_name: str | None = None,
    series: str | None = None,
    series_url: str | None = None,
    raw_response: Mapping[str, Any] | None = None,
    status: str = "eox_available",
) -> dict[str, Any]:
    clean_pid = _as_text(pid)
    clean_technology = _as_text(technology) or "Imported"
    clean_announcement_url = _as_text(announcement_url) or None
    clean_product_bulletin_url = _as_text(product_bulletin_url) or clean_announcement_url
    canonical = _canonicalize_milestones(milestones or {})

    payload: dict[str, Any] = {
        "PID": clean_pid,
        "ProductID": clean_pid,
        "EOLProductID": clean_pid,
        "ProductIDDescription": _as_text(product_name) or clean_pid,
        "Series": _as_text(series) or None,
        "EOXStatus": status,
        "source": source,
    }
    payload.update(canonical)
    if clean_announcement_url:
        payload["EOXAnnouncementURL"] = clean_announcement_url
        payload["url"] = clean_announcement_url
    if clean_product_bulletin_url:
        payload["ProductBulletinURL"] = clean_product_bulletin_url
        payload["LinkToProductBulletinURL"] = clean_product_bulletin_url
    if announcement_name:
        payload["AnnouncementName"] = announcement_name
    if series_url:
        payload["SeriesURL"] = series_url
    payload["raw_milestones"] = dict(milestones or {})

    return {
        "pid": clean_pid,
        "normalized_pid": normalize_pid(clean_pid),
        "technology": clean_technology,
        "source": source,
        "status": status,
        "product_name": _as_text(product_name) or clean_pid,
        "series": _as_text(series) or None,
        "announcement_name": announcement_name,
        "announcement_url": clean_announcement_url,
        "product_bulletin_url": clean_product_bulletin_url,
        "payload": payload,
        "raw_response": dict(raw_response or {}),
    }


def _merge_duplicate_eox_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Keep one importable record per normalized PID and retain alternatives.

    ProductEox has a unique normalized_pid constraint. Multiple Cisco bulletins
    can mention the same PID, so the database seed should not contain duplicate rows
    that fight each other during import. The best record is the one with the
    most lifecycle fields; other announcement references are kept in payload.
    """
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        pid = _as_text(record.get("pid") or record.get("ProductID") or record.get("EOLProductID"))
        if not pid:
            continue
        clean = dict(record)
        clean["pid"] = pid
        clean["normalized_pid"] = normalize_pid(pid)
        grouped[clean["normalized_pid"]].append(clean)

    output: list[dict[str, Any]] = []
    lifecycle_fields = set(FIELD_PATTERNS.keys())
    for _norm, items in grouped.items():
        def score(item: Mapping[str, Any]) -> tuple[int, int, int]:
            payload = item.get("payload") if isinstance(item.get("payload"), Mapping) else item
            date_count = 0
            if isinstance(payload, Mapping):
                date_count = sum(1 for field in lifecycle_fields if _payload_get(payload, [field]))
            has_url = int(bool(item.get("announcement_url") or (isinstance(payload, Mapping) and _payload_get(payload, ["EOXAnnouncementURL", "url"]))))
            source_score = 2 if item.get("source") == "api" else 1
            return (date_count, has_url, source_score)

        items = sorted(items, key=score, reverse=True)
        primary = dict(items[0])
        payload = dict(primary.get("payload") or {})
        alternatives: list[dict[str, Any]] = []
        for duplicate in items[1:]:
            alternatives.append(
                {
                    "announcement_name": duplicate.get("announcement_name"),
                    "announcement_url": duplicate.get("announcement_url"),
                    "source": duplicate.get("source"),
                    "status": duplicate.get("status"),
                    "payload": duplicate.get("payload"),
                }
            )
        if alternatives:
            payload["additional_announcements"] = alternatives
        primary["payload"] = payload
        output.append(primary)
    return sorted(output, key=lambda item: item.get("pid", ""))


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _seed_from_csv(path: Path, *, source: str, default_technology: str = "Imported") -> dict[str, Any]:
    seed = _empty_seed()
    seed["source"] = source
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lower = {str(key).strip().lower(): value for key, value in row.items() if key is not None}
            pid = lower.get("pid") or lower.get("productid") or lower.get("product_id") or lower.get("model") or lower.get("product_name") or lower.get("name")
            if not pid:
                continue
            technology = lower.get("technology") or lower.get("category_name") or default_technology
            if _record_has_lifecycle_dates(row):
                seed["eox_records"].append(
                    _eox_record(
                        pid=str(pid),
                        technology=str(technology),
                        source=source,
                        milestones=row,
                        announcement_name=lower.get("announcement_name"),
                        announcement_url=lower.get("announcement_url") or lower.get("eoxannouncementurl") or lower.get("url"),
                        product_bulletin_url=lower.get("productbulletinurl") or lower.get("product_bulletin_url"),
                        product_name=lower.get("product_name") or lower.get("name") or pid,
                        raw_response={"csv_row": row},
                    )
                )
            else:
                is_eox_value = str(lower.get("is_eox") or lower.get("eox") or "").strip().lower()
                seed["pid_catalog"].append(
                    _catalog_record(
                        "csv",
                        str(pid),
                        lower.get("product_url") or lower.get("url") or lower.get("source_url"),
                        str(technology),
                        is_eox_value in {"true", "1", "yes", "y", "eox", "eol"},
                        source=source,
                        product_name=lower.get("product_name") or lower.get("name") or pid,
                        payload={"csv_row": row},
                    )
                )
    return seed


def _seed_from_txt(path: Path, *, source: str, default_technology: str = "Imported") -> dict[str, Any]:
    seed = _empty_seed()
    seed["source"] = source
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        pid = line.strip()
        if not pid or pid.startswith("#"):
            continue
        seed["pid_catalog"].append(_catalog_record("txt", pid, None, default_technology, False, source=source))
    return seed


def load_input_file(path_value: str, *, default_technology: str = "Imported") -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    suffix = path.suffix.lower()
    source = f"input:{path.name}"
    if suffix == ".json":
        raise ValueError("JSON input files are not supported. Use CSV/TXT input or database records exposed through GraphQL.")
    if suffix == ".csv":
        return _seed_from_csv(path, source=source, default_technology=default_technology)
    return _seed_from_txt(path, source=source, default_technology=default_technology)


def _merge_seed(base: dict[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(incoming.get("categories"), Mapping):
        base["categories"].update(dict(incoming["categories"]))
    if isinstance(incoming.get("pid_catalog"), list):
        base["pid_catalog"].extend([item for item in incoming["pid_catalog"] if isinstance(item, Mapping)])
    if isinstance(incoming.get("eox_records"), list):
        base["eox_records"].extend([item for item in incoming["eox_records"] if isinstance(item, Mapping)])
    return base


# ---------------------------------------------------------------------------
# Optional standalone Cisco API support
# ---------------------------------------------------------------------------

class StandaloneCiscoEoxApi:
    """Small Cisco EOX API client for this exporter.

    The main backend client stores credentials in PostgreSQL. Auto_Pop needs to
    run before/without the database too, so this local client reads credentials
    from CLI args or environment variables.
    """

    def __init__(
        self,
        *,
        access_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        token_url: str = "https://id.cisco.com/oauth2/default/v1/token",
        api_base_url: str = "https://apix.cisco.com",
        timeout: int = 30,
        retries: int = 2,
        user_agent: str = "Cisco-EOX-Manager-AutoPop/1.0",
    ) -> None:
        self.access_token = access_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})

    @property
    def configured(self) -> bool:
        return bool(self.access_token or (self.client_id and self.client_secret))

    def _token(self) -> str:
        if self.access_token:
            return self.access_token
        if not self.client_id or not self.client_secret:
            raise RuntimeError("Cisco API credentials are not configured")
        response = self.session.post(
            self.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Cisco token request failed: HTTP {response.status_code} - {response.text[:200]}")
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Cisco token response did not include access_token")
        self.access_token = str(token)
        return self.access_token

    def get_by_product_id(self, pids: Sequence[str], *, batch_size: int = 20) -> dict[str, dict[str, Any]]:
        clean = clean_pid_list(pids)
        if not clean:
            return {}
        token = self._token()
        output: dict[str, dict[str, Any]] = {}
        base_url = f"{self.api_base_url}/supporttools/eox/rest/5/EOXByProductID/1"
        for index in range(0, len(clean), batch_size):
            batch = clean[index:index + batch_size]
            pid_path = quote(",".join(batch), safe=",-")
            response = self.session.get(
                f"{base_url}/{pid_path}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=self.timeout,
            )
            if response.status_code >= 400:
                raise RuntimeError(f"Cisco EOX API request failed: HTTP {response.status_code} - {response.text[:240]}")
            data = response.json()
            records = data.get("EOXRecord")
            if records is None:
                records = []
            if isinstance(records, Mapping):
                records = [records]
            for record in records:
                if not isinstance(record, Mapping):
                    continue
                returned_pid = _api_pid_from_record(record)
                if not returned_pid:
                    continue
                output[returned_pid] = dict(record)
        return output


def _api_pid_from_record(record: Mapping[str, Any]) -> str | None:
    for key in ("EOLProductID", "ProductID", "EOXInputValue"):
        value = record.get(key)
        if isinstance(value, Mapping):
            value = value.get("value")
        if value:
            return str(value)
    return None


def _api_record_to_eox(record: Mapping[str, Any], *, query_pid: str, technology: str) -> dict[str, Any]:
    pid = _api_pid_from_record(record) or query_pid
    flattened: dict[str, Any] = {}
    for key, value in record.items():
        flattened[key] = value.get("value") if isinstance(value, Mapping) else value
    return _eox_record(
        pid=pid,
        technology=technology,
        source="api",
        milestones=flattened,
        announcement_name=flattened.get("ProductBulletinNumber") or flattened.get("EOXExternalAnnouncementID"),
        announcement_url=flattened.get("LinkToProductBulletinURL") or flattened.get("ProductBulletinURL"),
        product_bulletin_url=flattened.get("LinkToProductBulletinURL") or flattened.get("ProductBulletinURL"),
        product_name=flattened.get("ProductIDDescription") or flattened.get("ProductDescription"),
        raw_response={"api_record": dict(record)},
    )


def _api_client_from_args(args: argparse.Namespace) -> StandaloneCiscoEoxApi:
    return StandaloneCiscoEoxApi(
        access_token=args.api_access_token or os.getenv("CISCO_ACCESS_TOKEN"),
        client_id=args.api_client_id or os.getenv("CISCO_CLIENT_ID"),
        client_secret=args.api_client_secret or os.getenv("CISCO_CLIENT_SECRET"),
        token_url=args.api_token_url or os.getenv("CISCO_TOKEN_URL", "https://id.cisco.com/oauth2/default/v1/token"),
        api_base_url=args.api_base_url or os.getenv("CISCO_API_BASE_URL", "https://apix.cisco.com"),
        timeout=args.timeout,
        retries=args.retries,
    )


# ---------------------------------------------------------------------------
# Cisco web crawling
# ---------------------------------------------------------------------------

def _parse_category_url(values: Sequence[str]) -> dict[str, str]:
    output: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--category-url must use NAME=URL format")
        name, url = value.split("=", 1)
        name = name.strip()
        url = url.strip()
        if not name or not url:
            raise ValueError("--category-url requires a non-empty name and URL")
        output[name] = url
    return output


def _select_categories(available: Mapping[str, str], requested: Sequence[str], limit: int | None) -> list[str]:
    if requested:
        selected: list[str] = []
        available_lower = {name.lower(): name for name in available}
        for item in requested:
            if item in available:
                selected.append(item)
                continue
            lowered = item.lower()
            if lowered in available_lower:
                selected.append(available_lower[lowered])
                continue
            matches = [name for name in available if lowered in name.lower()]
            selected.extend(matches)
    else:
        selected = list(available.keys())

    deduped: list[str] = []
    seen: set[str] = set()
    for name in selected:
        if name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped[:limit] if limit else deduped



def _html_node_text(node: Any) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True) if node else "").strip()


def _nearest_heading(table: Any) -> str | None:
    """Best-effort section heading immediately before a Cisco HTML table."""
    for sibling in table.find_previous_siblings():
        name = getattr(sibling, "name", None)
        if name in {"h1", "h2", "h3", "h4", "h5"}:
            text = _html_node_text(sibling)
            if text:
                return text
        if name == "table":
            break
    heading = table.find_previous(["h1", "h2", "h3", "h4", "h5"])
    text = _html_node_text(heading)
    return text or None


def _unique_headers(headers: Sequence[str], width: int) -> list[str]:
    output: list[str] = []
    counts: dict[str, int] = defaultdict(int)
    for index in range(width):
        value = _as_text(headers[index] if index < len(headers) else "") or f"Column {index + 1}"
        counts[value] += 1
        output.append(value if counts[value] == 1 else f"{value} {counts[value]}")
    return output


def _table_rows(table: Any) -> list[dict[str, Any]]:
    """Return raw rows while preserving every visible table cell.

    This intentionally does not discard columns. It keeps a cell list, a header
    flag, and row/cell indexes so the database record can be audited back to the Cisco
    table that produced it.
    """
    rows: list[dict[str, Any]] = []
    for row_index, row in enumerate(table.find_all("tr"), start=1):
        cells: list[dict[str, Any]] = []
        for cell_index, cell in enumerate(row.find_all(["th", "td"]), start=1):
            text = _html_node_text(cell)
            links = []
            for anchor in cell.find_all("a"):
                href = anchor.get("href")
                label = _html_node_text(anchor)
                if href:
                    links.append({"text": label, "href": href})
            cells.append(
                {
                    "index": cell_index,
                    "text": text,
                    "tag": getattr(cell, "name", "td"),
                    "colspan": int(cell.get("colspan", 1) or 1),
                    "rowspan": int(cell.get("rowspan", 1) or 1),
                    "links": links,
                }
            )
        if not cells:
            continue
        rows.append(
            {
                "index": row_index,
                "is_header": any(cell["tag"] == "th" for cell in cells),
                "cells": cells,
                "cell_text": [cell["text"] for cell in cells],
            }
        )
    return rows


def _table_to_dict(table: Any, index: int) -> dict[str, Any]:
    raw_rows = _table_rows(table)
    caption = _html_node_text(table.find("caption")) or None
    heading = _nearest_heading(table)
    width = max((len(row["cell_text"]) for row in raw_rows), default=0)
    header_index = None
    for pos, row in enumerate(raw_rows):
        if row["is_header"]:
            header_index = pos
            break
    if header_index is None and raw_rows:
        header_index = 0

    headers = _unique_headers(raw_rows[header_index]["cell_text"] if header_index is not None else [], width)
    mapped_rows: list[dict[str, Any]] = []
    for pos, row in enumerate(raw_rows):
        # Keep the selected header row in raw_rows but do not repeat it in rows.
        if pos == header_index:
            continue
        values = row["cell_text"]
        if not any(values):
            continue
        mapped = {headers[i]: values[i] if i < len(values) else "" for i in range(width)}
        mapped_rows.append(
            {
                "row_index": row["index"],
                "columns": mapped,
                "cells": values,
                "raw_cells": row["cells"],
            }
        )

    return {
        "table_index": index,
        "caption": caption,
        "heading": heading,
        "headers": headers,
        "rows": mapped_rows,
        "raw_rows": raw_rows,
        "row_count": len(mapped_rows),
    }


def _fetch_announcement_html(scraper: CiscoEoxScraperService, announcement_url: str) -> str | None:
    try:
        return scraper._get(scraper._abs(announcement_url))
    except Exception:
        LOGGER.exception("Failed to fetch Cisco EOX announcement: %s", announcement_url)
        return None


def _parse_announcement_tables_from_html(announcement_url: str, html: str) -> dict[str, Any]:
    soup = bs4.BeautifulSoup(html, "lxml")
    title_node = soup.find("h1") or soup.find("title")
    title = _html_node_text(title_node) or None
    tables = [_table_to_dict(table, index) for index, table in enumerate(soup.find_all("table"), start=1)]
    return {
        "title": title,
        "url": announcement_url,
        "tables": tables,
        "table_count": len(tables),
    }


def _scrape_all_announcement_tables(scraper: CiscoEoxScraperService, announcement_url: str) -> dict[str, Any] | None:
    html = _fetch_announcement_html(scraper, announcement_url)
    if not html:
        return None
    return _parse_announcement_tables_from_html(announcement_url, html)


def _table_text(table_info: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("caption", "heading"):
        if table_info.get(key):
            parts.append(str(table_info[key]))
    parts.extend(str(item) for item in table_info.get("headers") or [])
    for row in table_info.get("rows") or []:
        if isinstance(row, Mapping):
            parts.extend(str(value) for value in (row.get("columns") or {}).values())
    return " ".join(parts).lower()


def _is_milestone_table(table_info: Mapping[str, Any]) -> bool:
    text = _table_text(table_info)
    return "milestone" in text and ("date" in text or "last date" in text or "support" in text)


def _is_affected_product_table(table_info: Mapping[str, Any]) -> bool:
    text = _table_text(table_info)
    if _is_milestone_table(table_info):
        return False
    positive = (
        "end-of-sale product", "end of sale product", "affected product",
        "product id", "product part number", "part number", "product number",
        "model number", "product identifier", "pid",
    )
    return any(marker in text for marker in positive)


def _milestone_fields_from_all_tables(tables: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for table in tables:
        if not _is_milestone_table(table):
            continue
        for row in table.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            columns = row.get("columns") if isinstance(row.get("columns"), Mapping) else {}
            cells = [str(cell).strip() for cell in row.get("cells") or [] if str(cell).strip()]
            if not cells:
                continue
            key = _as_text(cells[0])
            value = ""
            # Cisco milestone tables normally look like Milestone | Definition | Date.
            for header, cell_value in columns.items():
                if re.search(r"\bdate\b", str(header), flags=re.I) and _as_text(cell_value):
                    value = _as_text(cell_value)
                    break
            if not value and len(cells) >= 3:
                value = _as_text(cells[2])
            elif not value and len(cells) >= 2:
                value = _as_text(cells[-1])
            if key and value and not key.lower().startswith("milestone"):
                fields[key] = value
    return fields


def _affected_pid_headers(columns: Mapping[str, Any]) -> list[str]:
    preferred: list[str] = []
    fallback: list[str] = []
    for header in columns.keys():
        normalized = _normalize_key(header)
        header_text = str(header).lower()
        if any(bad in header_text for bad in ("replacement", "migration", "alternate", "new product", "recommended")):
            continue
        if any(marker in normalized for marker in ("endofsaleproductpartnumber", "eolproductid", "affectedproduct", "productid", "pid")):
            preferred.append(str(header))
            continue
        if "partnumber" in normalized or "modelnumber" in normalized or normalized == "product":
            fallback.append(str(header))
    return preferred or fallback


def _split_pid_cell(value: Any) -> list[str]:
    text = _as_text(value)
    if not text:
        return []
    # Cisco sometimes puts multiple PIDs in one cell separated by commas,
    # semicolons, slashes, or line breaks. Keep words with Cisco PID-like shape.
    rough_parts = re.split(r"[,;\n\r]+|\s{2,}", text)
    candidates: list[str] = []
    for part in rough_parts:
        cleaned = part.strip(" .")
        if not cleaned:
            continue
        # If the cell is a prose description, try extracting embedded PID tokens.
        embedded = re.findall(r"\b[A-Z0-9][A-Z0-9._/-]{2,}\b", cleaned, flags=re.I)
        if len(embedded) > 1 or (embedded and embedded[0] != cleaned):
            candidates.extend(embedded)
        else:
            candidates.append(cleaned)
    output: list[str] = []
    for item in candidates:
        pid = item.strip().strip("()[]{}")
        if not pid:
            continue
        lowered = pid.lower()
        if lowered in {"na", "n/a", "none", "all", "product", "products"}:
            continue
        if len(pid) > 120:
            continue
        output.append(pid)
    return clean_pid_list(output)


def _affected_rows_from_tables(tables: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    affected: list[dict[str, Any]] = []
    for table in tables:
        if not _is_affected_product_table(table):
            continue
        for row in table.get("rows") or []:
            if not isinstance(row, Mapping):
                continue
            columns = row.get("columns") if isinstance(row.get("columns"), Mapping) else {}
            if not columns:
                continue
            pid_headers = _affected_pid_headers(columns)
            pids: list[str] = []
            for header in pid_headers:
                pids.extend(_split_pid_cell(columns.get(header)))
            if not pids and row.get("cells"):
                pids = _split_pid_cell(row["cells"][0])
            if not pids:
                continue
            affected.append(
                {
                    "table_index": table.get("table_index"),
                    "table_caption": table.get("caption"),
                    "table_heading": table.get("heading"),
                    "table_headers": table.get("headers") or [],
                    "row_index": row.get("row_index"),
                    "columns": dict(columns),
                    "cells": list(row.get("cells") or []),
                    "pid_headers": pid_headers,
                    "pids": clean_pid_list(pids),
                }
            )
    return affected


def _row_product_description(row_info: Mapping[str, Any], fallback: str) -> str:
    columns = row_info.get("columns") if isinstance(row_info.get("columns"), Mapping) else {}
    for header, value in columns.items():
        key = _normalize_key(header)
        if "description" in key and not any(bad in key for bad in ("replacement", "migration")):
            text = _as_text(value)
            if text:
                return text
    return fallback


def _records_from_full_announcement(
    *,
    announcement_data: Mapping[str, Any],
    announcement_name: str | None,
    announcement_url: str,
    technology: str,
    series_name: str,
    series_url: str,
    birth_certificate: Mapping[str, Any] | None,
    series_record: Mapping[str, Any],
) -> list[dict[str, Any]]:
    tables = [table for table in announcement_data.get("tables") or [] if isinstance(table, Mapping)]
    milestone_fields = _milestone_fields_from_all_tables(tables)
    affected_rows = _affected_rows_from_tables(tables)
    output: list[dict[str, Any]] = []

    for row_info in affected_rows:
        for pid in row_info.get("pids") or []:
            product_description = _row_product_description(row_info, pid)
            full_payload: dict[str, Any] = {
                **milestone_fields,
                "PID": pid,
                "ProductID": pid,
                "EOLProductID": pid,
                "ProductIDDescription": product_description,
                "Series": series_name,
                "AnnouncementName": announcement_name,
                "AnnouncementTitle": announcement_data.get("title"),
                "EOXAnnouncementURL": announcement_url,
                "ProductBulletinURL": announcement_url,
                "LinkToProductBulletinURL": announcement_url,
                "scrape_mode": "full_table",
                # The exact row from the affected-products table. This is the
                # important change requested by the original Auto_Pop workflow.
                "affected_product_row": row_info,
                # Every table from the Cisco announcement page, not only the
                # milestone/product tables. This keeps the raw evidence intact.
                "announcement_tables": tables,
                "milestone_fields": milestone_fields,
            }
            record = _eox_record(
                pid=pid,
                technology=technology,
                source="scraper",
                milestones=full_payload,
                announcement_name=announcement_name,
                announcement_url=announcement_url,
                product_bulletin_url=announcement_url,
                product_name=product_description,
                series=series_name,
                series_url=series_url,
                raw_response={
                    "birth_certificate": dict(birth_certificate or {}),
                    "announcement": dict(announcement_data),
                    "affected_product_row": row_info,
                    "series_record": dict(series_record),
                },
            )
            # _eox_record keeps scalar milestone fields import-friendly. Make
            # sure the nested full-table evidence is also stored in payload so
            # current database persistence code stores it without requiring backend
            # changes.
            record["payload"].update(
                {
                    "scrape_mode": "full_table",
                    "affected_product_row": row_info,
                    "announcement_tables": tables,
                    "milestone_fields": milestone_fields,
                    "AnnouncementTitle": announcement_data.get("title"),
                }
            )
            output.append(record)

    return output


def _candidate_series(records: Sequence[Mapping[str, Any]], *, eox_only: bool, limit: int | None) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for record in records:
        payload = record.get("payload") if isinstance(record.get("payload"), Mapping) else {}
        kind = str(payload.get("kind") or "").lower()
        if kind not in {"series", "eox_series"}:
            continue
        if eox_only and not bool(record.get("is_eox")):
            continue
        if not record.get("product_url"):
            continue
        output.append(dict(record))
        if limit and len(output) >= limit:
            break
    return output


def _scrape_series_eox(
    *,
    scraper: CiscoEoxScraperService,
    series_record: Mapping[str, Any],
    limit_announcements: int | None,
    delay_seconds: float,
    parse_workers: int = 2,
) -> tuple[list[dict[str, Any]], str]:
    series_name = _as_text(series_record.get("pid") or series_record.get("product_name"))
    series_url = _as_text(series_record.get("product_url"))
    technology = _as_text(series_record.get("technology") or series_record.get("category_name")) or "Imported"
    if not series_url:
        return [], "missing_url"

    checked = scraper.eox_check(series_url)
    if delay_seconds:
        time.sleep(delay_seconds)
    if not checked:
        return [], "not_announced"

    has_link, eol_data = checked
    if not has_link:
        # Cisco birth certificate may expose release/EOS dates without a detail
        # link. Keep it only when lifecycle-looking values exist.
        if isinstance(eol_data, Mapping) and _record_has_lifecycle_dates(eol_data):
            record = _eox_record(
                pid=series_name,
                technology=technology,
                source="scraper",
                milestones=eol_data,
                announcement_url=eol_data.get("url"),
                product_name=series_name,
                series=series_name,
                series_url=series_url,
                raw_response={"birth_certificate": dict(eol_data), "series_record": dict(series_record)},
            )
            record["payload"].setdefault("scrape_mode", "birth_certificate_only")
            return [record], "eox_birth_certificate_only"
        return [], "not_announced"

    redirect_url = eol_data.get("url") if isinstance(eol_data, Mapping) else None
    if not redirect_url:
        return [], "eox_link_missing"

    announcements = scraper.eox_details(str(redirect_url)) or {}
    if delay_seconds:
        time.sleep(delay_seconds)

    if not announcements:
        # Some Cisco pages link straight to enough summary data but do not have
        # a listing page. Store the series-level dates as a fallback record.
        record = _eox_record(
            pid=series_name,
            technology=technology,
            source="scraper",
            milestones=eol_data,
            announcement_url=str(redirect_url),
            product_bulletin_url=str(redirect_url),
            product_name=series_name,
            series=series_name,
            series_url=series_url,
            raw_response={"birth_certificate": dict(eol_data), "series_record": dict(series_record)},
        )
        record["payload"].setdefault("scrape_mode", "eox_summary_only")
        return [record], "eox_summary_only"

    output: list[dict[str, Any]] = []
    announcement_items = list(announcements.items())
    if limit_announcements:
        announcement_items = announcement_items[:limit_announcements]

    full_table_pages = 0
    fallback_pages = 0
    fetched_pages: list[tuple[str, str, str]] = []
    for announcement_name, announcement_url in announcement_items:
        LOGGER.info("        Fetching announcement page: %s", announcement_name)
        html = _fetch_announcement_html(scraper, announcement_url)
        if html:
            fetched_pages.append((announcement_name, announcement_url, html))
        if delay_seconds:
            time.sleep(delay_seconds)

    parsed_pages: list[tuple[str, str, dict[str, Any] | None]] = []
    worker_count = max(1, min(int(parse_workers or 1), len(fetched_pages) or 1))
    if worker_count > 1 and len(fetched_pages) > 1:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(_parse_announcement_tables_from_html, announcement_url, html): (announcement_name, announcement_url)
                for announcement_name, announcement_url, html in fetched_pages
            }
            for future in as_completed(future_map):
                announcement_name, announcement_url = future_map[future]
                try:
                    parsed_pages.append((announcement_name, announcement_url, future.result()))
                except Exception:
                    LOGGER.exception("Failed to parse fetched announcement page: %s", announcement_url)
                    parsed_pages.append((announcement_name, announcement_url, None))
    else:
        for announcement_name, announcement_url, html in fetched_pages:
            try:
                parsed_pages.append((announcement_name, announcement_url, _parse_announcement_tables_from_html(announcement_url, html)))
            except Exception:
                LOGGER.exception("Failed to parse fetched announcement page: %s", announcement_url)
                parsed_pages.append((announcement_name, announcement_url, None))

    parsed_lookup = {(name, url): data for name, url, data in parsed_pages}
    for announcement_name, announcement_url in announcement_items:
        announcement_data = parsed_lookup.get((announcement_name, announcement_url))
        if announcement_data:
            full_records = _records_from_full_announcement(
                announcement_data=announcement_data,
                announcement_name=announcement_name,
                announcement_url=announcement_url,
                technology=technology,
                series_name=series_name,
                series_url=series_url,
                birth_certificate=eol_data if isinstance(eol_data, Mapping) else {},
                series_record=series_record,
            )
            if full_records:
                full_table_pages += 1
                output.extend(full_records)
                continue

        scraped = scraper.eox_scraping(announcement_url)
        if delay_seconds:
            time.sleep(delay_seconds)
        if not scraped:
            continue
        fallback_pages += 1
        milestones, affected_pids = scraped
        canonical = _canonicalize_milestones(milestones)
        if not canonical:
            canonical = dict(eol_data or {})
        clean_pids = clean_pid_list(affected_pids)
        if not clean_pids:
            clean_pids = [series_name]
        for pid in clean_pids:
            payload = {
                **canonical,
                "scrape_mode": "reduced_parser_fallback",
                "raw_milestones": dict(milestones or {}),
                "affected_pids": list(affected_pids or []),
            }
            record = _eox_record(
                pid=pid,
                technology=technology,
                source="scraper",
                milestones=payload,
                announcement_name=announcement_name,
                announcement_url=announcement_url,
                product_bulletin_url=announcement_url,
                product_name=pid,
                series=series_name,
                series_url=series_url,
                raw_response={
                    "birth_certificate": dict(eol_data or {}),
                    "milestones": dict(milestones or {}),
                    "affected_pids": list(affected_pids or []),
                    "series_record": dict(series_record),
                },
            )
            record["payload"].update(payload)
            output.append(record)

    if output:
        status = "eox_available_full_table" if full_table_pages else "eox_available_reduced_fallback"
        if full_table_pages and fallback_pages:
            status = "eox_available_mixed_table_and_fallback"
        return output, status
    return output, "announcement_not_parseable"



# ---------------------------------------------------------------------------
# DB checkpoint helpers
# ---------------------------------------------------------------------------

def _utcnow_dt() -> datetime:
    return datetime.now(timezone.utc)


def _aware_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _checkpoint_scope_key(value: Any) -> str:
    text = _as_text(value)
    return text[:512] if len(text) > 512 else text


def _with_checkpoint_db(database_url: str | None):
    from app.db.session import init_db, make_session

    init_db(database_url)
    return make_session(database_url)


def _get_or_create_checkpoint(db: Any, *, scope: str, scope_key: str):
    from app.db.models import AutoPopCheckpoint

    scope_key = _checkpoint_scope_key(scope_key)
    checkpoint = (
        db.query(AutoPopCheckpoint)
        .filter(AutoPopCheckpoint.scope == scope, AutoPopCheckpoint.scope_key == scope_key)
        .one_or_none()
    )
    if checkpoint is None:
        checkpoint = AutoPopCheckpoint(scope=scope, scope_key=scope_key, status="never_run", stats={})
        db.add(checkpoint)
        db.flush()
    return checkpoint


def _checkpoint_is_blocked(
    *,
    database_url: str | None,
    scope: str,
    scope_key: str,
    cooldown_hours: float,
    force_refresh: bool,
) -> tuple[bool, str]:
    """Return whether a crawler scope is still inside its cooldown window."""
    if force_refresh or cooldown_hours <= 0:
        return False, ""
    db = _with_checkpoint_db(database_url)
    try:
        checkpoint = _get_or_create_checkpoint(db, scope=scope, scope_key=scope_key)
        now = _utcnow_dt()
        next_allowed = _aware_datetime(checkpoint.next_allowed_at)
        if next_allowed and next_allowed > now:
            checkpoint.skip_count = int(checkpoint.skip_count or 0) + 1
            checkpoint.status = "skipped_cooldown"
            checkpoint.stats = {
                **dict(checkpoint.stats or {}),
                "last_skip_reason": f"cooldown active until {next_allowed.isoformat()}",
                "last_skip_at": now.isoformat(),
            }
            db.commit()
            return True, f"cooldown active until {next_allowed.isoformat()}"
        return False, ""
    finally:
        db.close()


def _mark_checkpoint_started(
    *,
    database_url: str | None,
    scope: str,
    scope_key: str,
    stats: Mapping[str, Any] | None = None,
) -> None:
    db = _with_checkpoint_db(database_url)
    try:
        checkpoint = _get_or_create_checkpoint(db, scope=scope, scope_key=scope_key)
        now = _utcnow_dt()
        checkpoint.status = "running"
        checkpoint.last_started_at = now
        checkpoint.run_count = int(checkpoint.run_count or 0) + 1
        checkpoint.last_error = None
        checkpoint.stats = {
            **dict(checkpoint.stats or {}),
            **dict(stats or {}),
            "last_started_at": now.isoformat(),
        }
        db.commit()
    finally:
        db.close()


def _mark_checkpoint_completed(
    *,
    database_url: str | None,
    scope: str,
    scope_key: str,
    cooldown_hours: float,
    stats: Mapping[str, Any] | None = None,
) -> None:
    db = _with_checkpoint_db(database_url)
    try:
        checkpoint = _get_or_create_checkpoint(db, scope=scope, scope_key=scope_key)
        now = _utcnow_dt()
        next_allowed = now + timedelta(hours=max(0.0, float(cooldown_hours or 0.0)))
        checkpoint.status = "completed"
        checkpoint.last_completed_at = now
        checkpoint.last_success_at = now
        checkpoint.next_allowed_at = next_allowed
        checkpoint.last_error = None
        normalized_stats = dict(stats or {})
        checkpoint.catalog_records = int(normalized_stats.get("catalog_records") or checkpoint.catalog_records or 0)
        checkpoint.eox_records = int(normalized_stats.get("eox_records") or checkpoint.eox_records or 0)
        checkpoint.announcements_seen = int(normalized_stats.get("announcements_seen") or checkpoint.announcements_seen or 0)
        checkpoint.stats = {
            **dict(checkpoint.stats or {}),
            **normalized_stats,
            "last_completed_at": now.isoformat(),
            "next_allowed_at": next_allowed.isoformat(),
        }
        db.commit()
    finally:
        db.close()


def _mark_checkpoint_failed(
    *,
    database_url: str | None,
    scope: str,
    scope_key: str,
    error: Exception,
    cooldown_hours: float,
    stats: Mapping[str, Any] | None = None,
) -> None:
    db = _with_checkpoint_db(database_url)
    try:
        checkpoint = _get_or_create_checkpoint(db, scope=scope, scope_key=scope_key)
        now = _utcnow_dt()
        # Even failures get a short cooldown so repeated 403/page-layout issues
        # do not hammer Cisco in a tight loop.
        next_allowed = now + timedelta(hours=max(1.0, float(cooldown_hours or 1.0)))
        checkpoint.status = "failed"
        checkpoint.last_completed_at = now
        checkpoint.next_allowed_at = next_allowed
        checkpoint.last_error = str(error)
        checkpoint.stats = {
            **dict(checkpoint.stats or {}),
            **dict(stats or {}),
            "last_failed_at": now.isoformat(),
            "next_allowed_at": next_allowed.isoformat(),
        }
        db.commit()
    finally:
        db.close()


def _category_seed(
    *,
    category_name: str,
    category_url: str,
    catalog_records: Sequence[Mapping[str, Any]],
    eox_records: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    seed = _empty_seed()
    seed["source"] = "auto_pop_category"
    seed["categories"] = {category_name: category_url}
    seed["pid_catalog"] = _dedupe_catalog(list(catalog_records))
    seed["eox_records"] = _merge_duplicate_eox_records(list(eox_records))
    seed["metadata"].update(dict(metadata))
    seed["metadata"].update(
        {
            "category_name": category_name,
            "category_url": category_url,
            "catalog_records": len(seed["pid_catalog"]),
            "eox_records": len(seed["eox_records"]),
            "announcements_seen": len({item.get("announcement_url") for item in seed["eox_records"] if item.get("announcement_url")}),
            "saved_incrementally": True,
        }
    )
    seed["generated_at"] = _now()
    return seed


def _build_from_cisco(
    *,
    categories: Sequence[str],
    category_urls: Mapping[str, str],
    limit_categories: int | None,
    include_eox_links: bool,
    crawl_models: bool,
    limit_model_series: int | None,
    full_eox_crawl: bool,
    eox_candidates_only: bool,
    limit_series_eox: int | None,
    limit_announcements: int | None,
    delay_seconds: float,
    parse_workers: int = 2,
    save_category_to_db: bool = False,
    database_url: str | None = None,
    overwrite: bool = False,
    category_break_seconds: float = 10.0,
    min_category_interval_hours: float = 168.0,
    force_refresh: bool = False,
) -> dict[str, Any]:
    scraper = CiscoEoxScraperService()
    category_links = dict(category_urls)
    if not category_links:
        category_links = scraper.category()
    if not category_links:
        return _empty_seed()

    selected = _select_categories(category_links, categories, limit_categories)
    if not selected:
        return _empty_seed()

    catalog_records: list[dict[str, Any]] = []
    eox_records: list[dict[str, Any]] = []
    categories_seen: dict[str, str] = {}
    series_pages_opened_for_models = 0
    series_pages_checked_for_eox = 0
    status_counts: dict[str, int] = defaultdict(int)
    skipped_categories: dict[str, str] = {}
    failed_categories: dict[str, str] = {}
    category_save_results: dict[str, dict[str, Any]] = {}

    for category_index, category_name in enumerate(selected, start=1):
        category_url = category_links[category_name]
        category_had_network_work = False
        checkpoint_scope = "category"
        checkpoint_key = category_name

        if save_category_to_db:
            blocked, reason = _checkpoint_is_blocked(
                database_url=database_url,
                scope=checkpoint_scope,
                scope_key=checkpoint_key,
                cooldown_hours=min_category_interval_hours,
                force_refresh=force_refresh,
            )
            if blocked:
                LOGGER.warning(
                    "[%s/%s] Skipping category %s: %s. Use --force-refresh to override.",
                    category_index,
                    len(selected),
                    category_name,
                    reason,
                )
                skipped_categories[category_name] = reason
                continue
            _mark_checkpoint_started(
                database_url=database_url,
                scope=checkpoint_scope,
                scope_key=checkpoint_key,
                stats={"category_url": category_url, "category_index": category_index, "total_categories": len(selected)},
            )

        category_catalog_records: list[dict[str, Any]] = []
        category_eox_records: list[dict[str, Any]] = []
        category_status_counts: dict[str, int] = defaultdict(int)

        try:
            LOGGER.info("[%s/%s] Opening category: %s", category_index, len(selected), category_name)
            opened = scraper.open_cat(category_url)
            category_had_network_work = True
            if delay_seconds:
                time.sleep(delay_seconds)
            if not opened:
                LOGGER.warning("No data found for category: %s", category_name)
                category_status_counts["category_empty"] += 1
            else:
                categories_seen[category_name] = category_url
                series, eox = opened
                eox = eox or {}

                for name, url in series.items():
                    is_eox = bool(name in eox)
                    category_catalog_records.append(
                        _catalog_record(
                            "series",
                            name,
                            url,
                            category_name,
                            is_eox,
                            source="online-discovery",
                            payload={"status_hint": "eox" if is_eox else "active_or_unknown"},
                        )
                    )
                    if crawl_models and url and (limit_model_series is None or series_pages_opened_for_models < limit_model_series):
                        series_pages_opened_for_models += 1
                        LOGGER.info("    Extracting models from series page: %s", name)
                        for model_name in scraper.extract_models_from_series_page(url):
                            category_catalog_records.append(
                                _catalog_record(
                                    "model",
                                    model_name,
                                    url,
                                    category_name,
                                    is_eox,
                                    source="online-discovery",
                                    payload={"parent_series": name, "parent_series_url": url},
                                )
                            )
                        if delay_seconds:
                            time.sleep(delay_seconds)

                if include_eox_links:
                    for name, url in eox.items():
                        category_catalog_records.append(
                            _catalog_record(
                                "eox_series",
                                name,
                                url,
                                category_name,
                                True,
                                source="online-discovery",
                                payload={"status_hint": "eox"},
                            )
                        )

                category_catalog_records = _dedupe_catalog(category_catalog_records)

                if full_eox_crawl:
                    remaining_series = None
                    if limit_series_eox is not None:
                        remaining_series = max(0, int(limit_series_eox) - series_pages_checked_for_eox)
                    candidates = [] if remaining_series == 0 else _candidate_series(
                        category_catalog_records,
                        eox_only=eox_candidates_only,
                        limit=remaining_series,
                    )
                    LOGGER.info("    Checking %s series pages for full EOX mappings in %s", len(candidates), category_name)
                    for series_index, series_record in enumerate(candidates, start=1):
                        LOGGER.info(
                            "        [%s/%s] EOX check: %s",
                            series_index,
                            len(candidates),
                            series_record.get("pid") or series_record.get("product_name"),
                        )
                        records, status = _scrape_series_eox(
                            scraper=scraper,
                            series_record=series_record,
                            limit_announcements=limit_announcements,
                            delay_seconds=delay_seconds,
                            parse_workers=parse_workers,
                        )
                        series_pages_checked_for_eox += 1
                        category_status_counts[status] += 1
                        status_counts[status] += 1
                        category_eox_records.extend(records)

                category_eox_records = _merge_duplicate_eox_records(category_eox_records)
                catalog_records.extend(category_catalog_records)
                eox_records.extend(category_eox_records)

            announcements_seen = len({item.get("announcement_url") for item in category_eox_records if item.get("announcement_url")})
            category_stats = {
                "category_name": category_name,
                "category_url": category_url,
                "catalog_records": len(category_catalog_records),
                "eox_records": len(category_eox_records),
                "announcements_seen": announcements_seen,
                "series_pages_checked_for_eox": sum(category_status_counts.values()),
                "eox_status_counts": dict(category_status_counts),
            }

            if save_category_to_db:
                category_seed_payload = _category_seed(
                    category_name=category_name,
                    category_url=category_url,
                    catalog_records=category_catalog_records,
                    eox_records=category_eox_records,
                    metadata={**category_stats, "full_eox_crawl": full_eox_crawl},
                )
                if category_catalog_records or category_eox_records:
                    db_result = save_seed_to_database(
                        category_seed_payload,
                        database_url=database_url,
                        source_path=f"auto_pop:category:{category_name}",
                        overwrite=overwrite,
                    )
                    category_stats["db_save_result"] = db_result
                    category_save_results[category_name] = db_result
                    LOGGER.info("    Saved category %s to database: %s", category_name, db_result)
                else:
                    category_stats["db_save_result"] = {"message": "No records discovered for category."}
                _mark_checkpoint_completed(
                    database_url=database_url,
                    scope=checkpoint_scope,
                    scope_key=checkpoint_key,
                    cooldown_hours=min_category_interval_hours,
                    stats=category_stats,
                )

        except Exception as exc:  # pragma: no cover - defensive online crawl isolation
            LOGGER.exception("Category failed: %s", category_name)
            failed_categories[category_name] = str(exc)
            status_counts["category_failed"] += 1
            if save_category_to_db:
                _mark_checkpoint_failed(
                    database_url=database_url,
                    scope=checkpoint_scope,
                    scope_key=checkpoint_key,
                    error=exc,
                    cooldown_hours=min_category_interval_hours,
                    stats={"category_name": category_name, "category_url": category_url},
                )
            continue
        finally:
            if category_had_network_work and category_break_seconds > 0 and category_index < len(selected):
                LOGGER.info(
                    "    Category complete. Sleeping %.1f seconds before next category to reduce Cisco request pressure.",
                    category_break_seconds,
                )
                time.sleep(category_break_seconds)

    catalog_records = _dedupe_catalog(catalog_records)
    seed = _empty_seed()
    seed["categories"] = categories_seen
    seed["pid_catalog"] = catalog_records
    seed["eox_records"] = _merge_duplicate_eox_records(eox_records)

    seed["metadata"].update(
        {
            "categories_seen": len(categories_seen),
            "catalog_records": len(seed["pid_catalog"]),
            "eox_records": len(seed.get("eox_records") or []),
            "include_eox_links": include_eox_links,
            "crawl_models": crawl_models,
            "full_eox_crawl": full_eox_crawl,
            "eox_candidates_only": eox_candidates_only,
            "series_pages_opened_for_models": series_pages_opened_for_models,
            "series_pages_checked_for_eox": series_pages_checked_for_eox,
            "not_announced_series": int(status_counts.get("not_announced", 0)),
            "failed_series": int(
                status_counts.get("missing_url", 0)
                + status_counts.get("eox_link_missing", 0)
                + status_counts.get("announcement_not_parseable", 0)
            ),
            "failed_categories": failed_categories,
            "skipped_categories": skipped_categories,
            "category_save_results": category_save_results,
            "announcement_pages_scraped": len({item.get("announcement_url") for item in eox_records if item.get("announcement_url")}),
            "eox_status_counts": dict(status_counts),
            "progressive_db_save": save_category_to_db,
            "category_break_seconds": category_break_seconds,
            "min_category_interval_hours": min_category_interval_hours,
        }
    )
    return seed

def _input_pids_for_online_lookup(seed: Mapping[str, Any], *, include_models: bool, limit: int | None) -> list[tuple[str, str]]:
    output: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in seed.get("pid_catalog") or []:
        if not isinstance(item, Mapping):
            continue
        payload = item.get("payload") if isinstance(item.get("payload"), Mapping) else {}
        kind = str(payload.get("kind") or "").lower()
        if kind == "series" and not include_models:
            continue
        pid = _as_text(item.get("pid"))
        if not pid:
            continue
        norm = normalize_pid(pid)
        if norm in seen:
            continue
        seen.add(norm)
        output.append((pid, _as_text(item.get("technology") or item.get("category_name")) or "Imported"))
        if limit and len(output) >= limit:
            break
    return output


def _enrich_input_pids_with_scraper(
    seed: dict[str, Any],
    *,
    technology: str,
    limit_pids: int | None,
    delay_seconds: float,
) -> dict[str, Any]:
    scraper = CiscoEoxScraperService()
    pid_pairs = _input_pids_for_online_lookup(seed, include_models=True, limit=limit_pids)
    if not pid_pairs:
        return seed

    LOGGER.info("Looking up %s imported/model PIDs through scraper", len(pid_pairs))
    additional: list[dict[str, Any]] = []
    for index, (pid, item_technology) in enumerate(pid_pairs, start=1):
        tech = technology if technology != "Imported" else item_technology
        LOGGER.info("    [%s/%s] Scraper PID lookup: %s", index, len(pid_pairs), pid)
        result = scraper.request_eox_data_from_online([pid], tech)
        if delay_seconds:
            time.sleep(delay_seconds)
        value = result.get(pid)
        if isinstance(value, list) and len(value) >= 2 and value[0] is True and isinstance(value[1], Mapping):
            additional.append(
                _eox_record(
                    pid=pid,
                    technology=tech,
                    source="scraper",
                    milestones=value[1],
                    product_name=pid,
                    raw_response={"scraper_response": value},
                )
            )
    seed["eox_records"].extend(additional)
    return seed


def _enrich_with_api(
    seed: dict[str, Any],
    *,
    api_client: StandaloneCiscoEoxApi,
    technology: str,
    limit_pids: int | None,
    batch_size: int,
) -> dict[str, Any]:
    pid_pairs = _input_pids_for_online_lookup(seed, include_models=True, limit=limit_pids)
    pids = [pid for pid, _tech in pid_pairs]
    if not pids:
        return seed
    LOGGER.info("Looking up %s PIDs through Cisco EOX API", len(pids))
    api_data = api_client.get_by_product_id(pids, batch_size=batch_size)
    request_technology = {normalize_pid(pid): tech for pid, tech in pid_pairs}
    additional: list[dict[str, Any]] = []
    for returned_pid, record in api_data.items():
        tech = technology if technology != "Imported" else request_technology.get(normalize_pid(returned_pid), "Imported")
        additional.append(_api_record_to_eox(record, query_pid=returned_pid, technology=tech))
    seed["eox_records"].extend(additional)
    seed["metadata"]["api_enabled"] = True
    seed["metadata"]["api_records"] = len(additional)
    return seed


# ---------------------------------------------------------------------------
# Build/write entry points
# ---------------------------------------------------------------------------

def build_catalog(
    *,
    categories: Sequence[str],
    category_urls: Mapping[str, str],
    limit_categories: int | None,
    include_eox_links: bool,
    input_files: Sequence[str],
    crawl_cisco: bool,
    crawl_models: bool,
    limit_model_series: int | None,
    full_eox_crawl: bool,
    eox_candidates_only: bool,
    limit_series_eox: int | None,
    limit_announcements: int | None,
    allow_empty: bool,
    default_technology: str,
    delay_seconds: float,
    parse_workers: int = 2,
    save_category_to_db: bool = False,
    database_url: str | None = None,
    overwrite: bool = False,
    category_break_seconds: float = 10.0,
    min_category_interval_hours: float = 168.0,
    force_refresh: bool = False,
) -> dict[str, Any]:
    seed = _empty_seed()
    seed["metadata"]["include_eox_links"] = include_eox_links
    seed["metadata"]["crawl_models"] = crawl_models
    seed["metadata"]["full_eox_crawl"] = full_eox_crawl

    for input_file in input_files:
        LOGGER.info("Loading input file: %s", input_file)
        _merge_seed(seed, load_input_file(input_file, default_technology=default_technology))

    if crawl_cisco:
        online_seed = _build_from_cisco(
            categories=categories,
            category_urls=category_urls,
            limit_categories=limit_categories,
            include_eox_links=include_eox_links,
            crawl_models=crawl_models,
            limit_model_series=limit_model_series,
            full_eox_crawl=full_eox_crawl,
            eox_candidates_only=eox_candidates_only,
            limit_series_eox=limit_series_eox,
            limit_announcements=limit_announcements,
            delay_seconds=delay_seconds,
            parse_workers=parse_workers,
            save_category_to_db=save_category_to_db,
            database_url=database_url,
            overwrite=overwrite,
            category_break_seconds=category_break_seconds,
            min_category_interval_hours=min_category_interval_hours,
            force_refresh=force_refresh,
        )
        _merge_seed(seed, online_seed)
    else:
        seed["metadata"].setdefault("notes", []).append("Cisco online category crawl was skipped by --no-cisco-crawl.")

    seed["pid_catalog"] = _dedupe_catalog(seed.get("pid_catalog", []))
    seed["eox_records"] = _merge_duplicate_eox_records(seed.get("eox_records", []))
    seed["metadata"]["categories_seen"] = len(seed.get("categories") or {})
    seed["metadata"]["catalog_records"] = len(seed.get("pid_catalog") or [])
    seed["metadata"]["eox_records"] = len(seed.get("eox_records") or [])

    if not seed["pid_catalog"] and not seed["eox_records"] and not allow_empty:
        raise RuntimeError(
            "No PID/EOX data was discovered. Cisco may have blocked the request or the page layout may have changed. "
            "Try: --input-file pids.txt, --category-url Switches=https://www.cisco.com/c/en/us/support/switches/category.html, "
            "or --allow-empty if you only want to test the exporter."
        )

    return seed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Populate the Cisco EOX Manager database with PID-to-lifecycle mappings",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--category", action="append", default=[], help="Cisco category name to include. Can be used more than once.")
    parser.add_argument("--category-url", action="append", default=[], help="Manual category in NAME=URL format. Useful when all-products.html is blocked.")
    parser.add_argument("--limit-categories", type=int, default=None, help="Limit categories for testing")
    parser.add_argument("--default-technology", default="Imported", help="Technology value for local input files without a technology column")

    parser.add_argument("--input-file", action="append", default=[], help="TXT/CSV file to merge into the database seed. Can be used more than once.")
    parser.add_argument("--no-cisco-crawl", action="store_true", help="Skip Cisco online category discovery. Use with --input-file for offline/API generation.")
    parser.add_argument("--allow-empty", action="store_true", help="Allow an empty run instead of failing when nothing is discovered")

    # Backward-compatible options, but the default now performs the complete
    # EOX crawl. Use --catalog-only to get the old catalog-only behavior.
    parser.add_argument("--crawl-eox", action="store_true", help="Compatibility flag. Full EOX crawl is now the default unless --catalog-only is used.")
    parser.add_argument("--catalog-only", action="store_true", help="Only build pid_catalog. Do not scrape EOX announcements.")
    parser.add_argument("--no-eox-links", action="store_true", help="Do not add EOX-marked series links to pid_catalog")
    parser.add_argument("--eox-candidates-only", action="store_true", help="Only check series already marked as EOX on category pages. Faster, but less complete.")
    parser.add_argument("--limit-series-eox", type=int, default=None, help="Limit number of series pages checked for EOX")
    parser.add_argument("--limit-eox", type=int, default=None, help="Compatibility alias for --limit-announcements")
    parser.add_argument("--limit-announcements", type=int, default=None, help="Limit announcements scraped per EOX listing page")
    parser.add_argument("--crawl-models", action="store_true", help="Open series pages and collect model names from the Select Model section")
    parser.add_argument("--limit-series", type=int, default=None, help="Limit series pages opened when --crawl-models is used")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between Cisco requests in seconds")
    parser.add_argument("--timeout", type=int, default=30, help="HTTP timeout for optional API calls")
    parser.add_argument("--retries", type=int, default=2, help="HTTP retry count for optional API calls")
    parser.add_argument("--parse-workers", type=int, default=2, help="Worker threads for CPU/local parsing after Cisco pages are fetched sequentially")
    parser.add_argument("--category-break", type=float, default=10.0, help="Seconds to pause after each category finishes before opening the next category")
    parser.add_argument("--min-run-interval-hours", type=float, default=168.0, help="Minimum hours before another full Cisco crawl is allowed when no explicit category/category-url is provided")
    parser.add_argument("--min-category-interval-hours", type=float, default=168.0, help="Minimum hours before the same category is crawled again")
    parser.add_argument("--force-refresh", action="store_true", help="Ignore Auto_Pop cooldown metadata and crawl anyway")

    parser.add_argument("--lookup-input-pids", action="store_true", help="After loading input/model PIDs, try to resolve each PID through the scraper")
    parser.add_argument("--limit-pids", type=int, default=None, help="Limit PID lookups for --lookup-input-pids or --use-api")

    parser.add_argument("--use-api", action="store_true", help="Use Cisco EOX API for input/model PIDs when credentials are supplied")
    parser.add_argument("--api-access-token", default=None, help="Cisco API bearer token. Or set CISCO_ACCESS_TOKEN.")
    parser.add_argument("--api-client-id", default=None, help="Cisco API client id. Or set CISCO_CLIENT_ID.")
    parser.add_argument("--api-client-secret", default=None, help="Cisco API client secret. Or set CISCO_CLIENT_SECRET.")
    parser.add_argument("--api-token-url", default=None, help="Cisco OAuth token URL. Or set CISCO_TOKEN_URL.")
    parser.add_argument("--api-base-url", default=None, help="Cisco API base URL. Or set CISCO_API_BASE_URL.")
    parser.add_argument("--api-batch-size", type=int, default=20, help="Product IDs per Cisco API request")

    parser.add_argument("--database-url", default=None, help="Optional SQLAlchemy database URL. Defaults to GUI/runtime config or EOX_DATABASE_URL.")
    parser.add_argument("--sqlite", action="store_true", help="Use a local SQLite database instead of the configured/default database")
    parser.add_argument("--sqlite-path", default=None, help="SQLite file path for --sqlite. Relative paths are stored under Cisco_EOX_Manager/data.")
    parser.add_argument("--overwrite", action="store_true", help="When saving to DB, allow stronger incoming values to replace existing cached values")
    return parser.parse_args()


def resolve_database_url(args: argparse.Namespace) -> str | None:
    if args.database_url:
        return args.database_url
    if args.sqlite:
        from app.core.runtime_config import build_sqlite_url

        return build_sqlite_url(path=args.sqlite_path)
    return None


def save_seed_to_database(seed: Mapping[str, Any], *, database_url: str | None, source_path: str | None, overwrite: bool) -> dict[str, Any]:
    """Persist generated seed data directly to SQLAlchemy database.

    This keeps Auto_Pop compatible with the DB-first workflow. JSON can still be
    written as a backup/export, but PostgreSQL/SQLite becomes the source of truth.
    """
    from app.db.session import init_db, make_session
    from app.services.seed_persistence import SeedPersistenceService

    init_db(database_url)
    db = make_session(database_url)
    try:
        result = SeedPersistenceService(db).save_seed(
            seed,
            source_path=source_path,
            mode="auto_pop",
            overwrite=overwrite,
            commit=True,
        )
        return result.as_dict()
    finally:
        db.close()


def main() -> int:
    args = parse_args()
    global_checkpoint_started = False
    database_url: str | None = None
    try:
        limit_announcements = args.limit_announcements if args.limit_announcements is not None else args.limit_eox
        full_eox_crawl = not args.catalog_only
        if args.crawl_eox:
            full_eox_crawl = True

        database_url = resolve_database_url(args)
        full_unbounded_cisco_crawl = (
            not args.no_cisco_crawl
            and full_eox_crawl
            and not args.category
            and not args.category_url
            and args.limit_categories is None
            and args.limit_series_eox is None
            and limit_announcements is None
        )
        if full_unbounded_cisco_crawl:
            blocked, reason = _checkpoint_is_blocked(
                database_url=database_url,
                scope="global",
                scope_key="auto_pop_full_crawl",
                cooldown_hours=max(0.0, float(args.min_run_interval_hours or 0.0)),
                force_refresh=args.force_refresh,
            )
            if blocked:
                LOGGER.warning("Skipping full Auto_Pop crawl: %s. Use --force-refresh to override.", reason)
                return 0
            _mark_checkpoint_started(
                database_url=database_url,
                scope="global",
                scope_key="auto_pop_full_crawl",
                stats={
                    "mode": "full_unbounded_cisco_crawl",
                    "min_run_interval_hours": args.min_run_interval_hours,
                    "min_category_interval_hours": args.min_category_interval_hours,
                },
            )
            global_checkpoint_started = True

        seed = build_catalog(
            categories=args.category,
            category_urls=_parse_category_url(args.category_url),
            limit_categories=args.limit_categories,
            include_eox_links=not args.no_eox_links,
            input_files=args.input_file,
            crawl_cisco=not args.no_cisco_crawl,
            crawl_models=args.crawl_models,
            limit_model_series=args.limit_series,
            full_eox_crawl=full_eox_crawl,
            eox_candidates_only=args.eox_candidates_only,
            limit_series_eox=args.limit_series_eox,
            limit_announcements=limit_announcements,
            allow_empty=args.allow_empty,
            default_technology=args.default_technology,
            delay_seconds=max(0.0, float(args.delay or 0.0)),
            parse_workers=max(1, int(args.parse_workers or 1)),
            save_category_to_db=not args.no_cisco_crawl,
            database_url=database_url,
            overwrite=args.overwrite,
            category_break_seconds=max(0.0, float(args.category_break or 0.0)),
            min_category_interval_hours=max(0.0, float(args.min_category_interval_hours or 0.0)),
            force_refresh=args.force_refresh,
        )

        if args.use_api:
            api_client = _api_client_from_args(args)
            if not api_client.configured:
                LOGGER.warning("--use-api was set but no API credentials/token were provided. Skipping API enrichment.")
                seed["metadata"].setdefault("notes", []).append("API enrichment skipped because credentials/token were not provided.")
            else:
                seed = _enrich_with_api(
                    seed,
                    api_client=api_client,
                    technology=args.default_technology,
                    limit_pids=args.limit_pids,
                    batch_size=args.api_batch_size,
                )

        if args.lookup_input_pids:
            seed = _enrich_input_pids_with_scraper(
                seed,
                technology=args.default_technology,
                limit_pids=args.limit_pids,
                delay_seconds=max(0.0, float(args.delay or 0.0)),
            )

        seed["pid_catalog"] = _dedupe_catalog(seed.get("pid_catalog", []))
        seed["eox_records"] = _merge_duplicate_eox_records(seed.get("eox_records", []))
        seed.setdefault("metadata", {})["catalog_records"] = len(seed.get("pid_catalog", []))
        seed.setdefault("metadata", {})["eox_records"] = len(seed.get("eox_records", []))
        seed.setdefault("metadata", {})["full_eox_crawl"] = full_eox_crawl
        seed["generated_at"] = _now()

        if full_eox_crawl and seed["metadata"]["eox_records"] == 0:
            seed["metadata"].setdefault("notes", []).append(
                "No full EOX records were produced. This usually means Cisco blocked pages, no EOX candidates were found, "
                "or the selected products have no public EOX announcement. Try --category-url, --input-file with --use-api, "
                "or --lookup-input-pids."
            )
            LOGGER.warning("No full EOX records were produced. The generated data may contain catalog records only.")

        progressive_saved = bool(seed.get("metadata", {}).get("progressive_db_save"))
        final_save_needed = not (
            progressive_saved
            and not args.input_file
            and not args.use_api
            and not args.lookup_input_pids
        )
        if final_save_needed:
            db_result = save_seed_to_database(
                seed,
                database_url=database_url,
                source_path="auto_pop:final-merge",
                overwrite=args.overwrite,
            )
            LOGGER.info("Saved final merged seed to database: %s", db_result)
        else:
            LOGGER.info("Skipped final merged DB save because categories were already saved incrementally.")

        if global_checkpoint_started:
            _mark_checkpoint_completed(
                database_url=database_url,
                scope="global",
                scope_key="auto_pop_full_crawl",
                cooldown_hours=max(0.0, float(args.min_run_interval_hours or 0.0)),
                stats={
                    "catalog_records": len(seed.get("pid_catalog", [])),
                    "eox_records": len(seed.get("eox_records", [])),
                    "announcements_seen": len({item.get("announcement_url") for item in seed.get("eox_records", []) if item.get("announcement_url")}),
                    "categories_seen": len(seed.get("categories", {})),
                    "progressive_db_save": progressive_saved,
                },
            )

        LOGGER.info(
            "Done. Catalog=%s, EOX=%s, categories=%s, full_eox_crawl=%s, saved_to_db=%s",
            len(seed.get("pid_catalog", [])),
            len(seed.get("eox_records", [])),
            len(seed.get("categories", {})),
            full_eox_crawl,
            True,
        )
        return 0
    except Exception as exc:
        if global_checkpoint_started:
            try:
                _mark_checkpoint_failed(
                    database_url=database_url,
                    scope="global",
                    scope_key="auto_pop_full_crawl",
                    error=exc,
                    cooldown_hours=max(1.0, float(getattr(args, "min_run_interval_hours", 1.0) or 1.0)),
                    stats={"failure_stage": "main"},
                )
            except Exception:  # pragma: no cover - do not hide the original error
                LOGGER.exception("Could not update global Auto_Pop failure checkpoint")
        LOGGER.exception("Auto-pop failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
