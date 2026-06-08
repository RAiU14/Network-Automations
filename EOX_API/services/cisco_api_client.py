from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote

import bs4
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from EOX_API.core.config import get_settings
from EOX_API.core.log import get_logger

logger = get_logger("eox.cisco_api")


class CiscoApiError(RuntimeError):
    """Raised when Cisco API credentials or HTTP responses are invalid."""


@dataclass(frozen=True)
class CiscoCredentials:
    client_id: str
    client_secret: str
    grant_type: str = "client_credentials"

    @classmethod
    def from_env_or_file(cls, credentials_file: Path | None = None) -> "CiscoCredentials":
        client_id = os.getenv("CISCO_CLIENT_ID")
        client_secret = os.getenv("CISCO_CLIENT_SECRET")
        grant_type = os.getenv("CISCO_GRANT_TYPE", "client_credentials")

        if client_id and client_secret:
            return cls(client_id=client_id, client_secret=client_secret, grant_type=grant_type)

        file_path = credentials_file
        if file_path and file_path.exists():
            data = json.loads(file_path.read_text(encoding="utf-8"))
            # Supports both the new format and the legacy Crediability.json format.
            payload = data.get("data", data)
            client_id = payload.get("client_id") or payload.get("clientId")
            client_secret = payload.get("client_secret") or payload.get("clientSecret")
            grant_type = payload.get("grant_type", grant_type)
            if client_id and client_secret:
                return cls(client_id=client_id, client_secret=client_secret, grant_type=grant_type)

        raise CiscoApiError(
            "Cisco API credentials not configured. Set CISCO_CLIENT_ID and "
            "CISCO_CLIENT_SECRET, or set CISCO_CREDENTIALS_FILE to a JSON file."
        )


def _chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _nested_value(record: Mapping[str, Any], key: str) -> Any:
    value = record.get(key)
    if isinstance(value, Mapping):
        return value.get("value")
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


@dataclass
class CiscoApiClient:
    """Small Cisco API client for EOX and software recommendation endpoints."""

    timeout: int | None = None
    token_cache_file: Path | None = None
    credentials_file: Path | None = None
    session: requests.Session = field(default_factory=requests.Session, init=False)

    def __post_init__(self) -> None:
        self.settings = get_settings()
        self.timeout = self.timeout or self.settings.http_timeout_seconds
        self.token_cache_file = self.token_cache_file or self.settings.token_cache_file
        self.credentials_file = self.credentials_file or self.settings.credentials_file

        retry = Retry(
            total=self.settings.http_retries,
            connect=self.settings.http_retries,
            read=self.settings.http_retries,
            status=self.settings.http_retries,
            backoff_factor=self.settings.http_backoff_seconds,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": self.settings.user_agent})

    # ------------------------------------------------------------------
    # OAuth token handling
    # ------------------------------------------------------------------
    def _read_token_cache(self) -> dict[str, Any]:
        if not self.token_cache_file or not self.token_cache_file.exists():
            return {}
        try:
            return json.loads(self.token_cache_file.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Ignoring unreadable Cisco token cache: %s", self.token_cache_file)
            return {}

    def _write_token_cache(self, token_data: Mapping[str, Any]) -> None:
        if not self.token_cache_file:
            return
        self.token_cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.token_cache_file.write_text(json.dumps(token_data, indent=2), encoding="utf-8")

    def get_access_token(self, force_refresh: bool = False) -> str:
        cache = self._read_token_cache()
        now = time.time()
        token = cache.get("access_token") or cache.get("token")
        expires_at = float(cache.get("expires_at") or 0)

        if token and not force_refresh and now < (expires_at - 60):
            return str(token)

        credentials = CiscoCredentials.from_env_or_file(self.credentials_file)
        payload = {
            "grant_type": credentials.grant_type,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = self.session.post(
            self.settings.cisco_token_url,
            headers=headers,
            data=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise CiscoApiError(f"Cisco token request failed: HTTP {response.status_code} - {response.text[:200]}")

        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            raise CiscoApiError("Cisco token response did not include access_token")

        expires_in = int(data.get("expires_in") or 3600)
        self._write_token_cache(
            {
                "access_token": access_token,
                "expires_in": expires_in,
                "expires_at": now + expires_in,
                "created_at": now,
            }
        )
        return str(access_token)

    def _auth_headers(self, token: str | None = None) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token or self.get_access_token()}",
            "Accept": "application/json",
        }

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        headers = kwargs.pop("headers", {}) or {}
        headers.update(self._auth_headers(token))
        response = self.session.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        if response.status_code >= 400:
            raise CiscoApiError(f"Cisco API request failed: HTTP {response.status_code} - {response.text[:300]}")
        return response.json()

    # ------------------------------------------------------------------
    # Hardware EOX
    # ------------------------------------------------------------------
    def get_hardware_eox_by_product_id(
        self,
        pids: Sequence[str] | Mapping[str, Any],
        *,
        token: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        pid_list = self._clean_pid_list(pids.keys() if isinstance(pids, Mapping) else pids)
        if not pid_list:
            return {}

        output: dict[str, dict[str, Any]] = {}
        base_url = f"{self.settings.cisco_api_base_url}/supporttools/eox/rest/5/EOXByProductID/1"

        for batch in _chunked(pid_list, 20):
            pid_path = quote(",".join(batch), safe=",-")
            data = self._request_json("GET", f"{base_url}/{pid_path}", token=token)
            for record in _as_list(data.get("EOXRecord")):
                if not isinstance(record, Mapping):
                    continue
                pid = record.get("EOLProductID") or record.get("ProductID") or record.get("EOXExternalAnnouncementID")
                if not pid:
                    continue
                output[str(pid)] = {
                    "EndOfSaleDate": _nested_value(record, "EndOfSaleDate"),
                    "LastDateOfSupport": _nested_value(record, "LastDateOfSupport"),
                    "EndOfRoutineFailureAnalysisDate": _nested_value(record, "EndOfRoutineFailureAnalysisDate"),
                    "EndOfSecurityVulSupportDate": _nested_value(record, "EndOfSecurityVulSupportDate"),
                    "EndOfSWMaintenanceReleases": _nested_value(record, "EndOfSWMaintenanceReleases"),
                    "ProductBulletinNumber": record.get("ProductBulletinNumber"),
                    "ProductBulletinURL": record.get("LinkToProductBulletinURL"),
                }
        return output

    # ------------------------------------------------------------------
    # Software recommendation / software EOX
    # ------------------------------------------------------------------
    def get_software_suggestions(
        self,
        pids: Sequence[str],
        *,
        token: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        pid_list = self._clean_pid_list(pids)
        if not pid_list:
            return {}

        base_url = f"{self.settings.cisco_api_base_url}/software/suggestion/v2/suggestions/software/productIds"
        output: dict[str, list[dict[str, Any]]] = {}

        for batch in _chunked(pid_list, 10):
            pid_path = quote(",".join(batch), safe=",-")
            data = self._request_json("GET", f"{base_url}/{pid_path}", token=token)
            for product in _as_list(data.get("productList")):
                if not isinstance(product, Mapping):
                    continue
                pid = (product.get("product") or {}).get("basePID") or product.get("basePID")
                if not pid:
                    continue
                suggestions = []
                for suggestion in _as_list(product.get("suggestions")):
                    if not isinstance(suggestion, Mapping):
                        continue
                    suggestions.append(
                        {
                            "Suggested S/W Version": suggestion.get("releaseFormat1"),
                            "Suggested S/W Release Date": suggestion.get("releaseDate"),
                            "isSuggested": suggestion.get("isSuggested"),
                        }
                    )
                output[str(pid)] = suggestions
        return output

    def get_compatible_software(
        self,
        pids: Sequence[str],
        *,
        token: str | None = None,
    ) -> dict[str, str | None]:
        pid_list = self._clean_pid_list(pids)
        output: dict[str, str | None] = {}
        base_url = f"{self.settings.cisco_api_base_url}/software/suggestion/v2/suggestions/compatible/productId"

        for pid in pid_list:
            data = self._request_json("GET", f"{base_url}/{quote(pid, safe='-')}", token=token)
            selected_release = None
            for item in _as_list(data.get("suggestions")):
                if not isinstance(item, Mapping):
                    continue
                release = item.get("releaseFormat1")
                if item.get("isSuggested") == "Y" and release:
                    selected_release = str(release)
                    break
                if selected_release is None and release:
                    selected_release = str(release)
            output[pid] = selected_release
        return output

    def get_software_eos_by_release(
        self,
        device_versions: Mapping[str, Iterable[str] | str],
        *,
        token: str | None = None,
    ) -> dict[str, str | None]:
        releases: list[str] = []
        for versions in device_versions.values():
            if isinstance(versions, str):
                versions = [versions]
            for version in versions:
                if version:
                    releases.append(str(version))

        if not releases:
            return {}

        output: dict[str, str | None] = {}
        base_url = f"{self.settings.cisco_api_base_url}/supporttools/eox/rest/5/EOXBySWReleaseString/1"

        for batch in _chunked(releases, 20):
            params = {f"input{index}": release for index, release in enumerate(batch, start=1)}
            data = self._request_json("GET", base_url, token=token, params=params)
            for record in _as_list(data.get("EOXRecord")):
                if not isinstance(record, Mapping):
                    continue
                last_support = _nested_value(record, "LastDateOfSupport")
                version_key = self._software_version_key(record)
                if version_key:
                    output[version_key] = last_support
        return output

    def _software_version_key(self, record: Mapping[str, Any]) -> str | None:
        candidates = [
            record.get("SoftwareReleaseString"),
            record.get("SWReleaseString"),
            record.get("EOXInputValue"),
            record.get("ProductID"),
        ]
        for candidate in candidates:
            if candidate:
                return str(candidate)

        bulletin_url = record.get("LinkToProductBulletinURL")
        if not bulletin_url:
            return None
        try:
            response = self.session.get(str(bulletin_url), timeout=self.timeout)
            response.raise_for_status()
            title = bs4.BeautifulSoup(response.text, "lxml").find("h1", id="fw-pagetitle")
            text = title.get_text(" ", strip=True) if title else ""
            match = re.search(r"\d+\.\d+(?:\.\d+)?\.x", text)
            return match.group(0) if match else None
        except Exception:
            logger.debug("Could not derive software version from bulletin URL", exc_info=True)
            return None

    def software_deferred_check(
        self,
        device_versions: Mapping[str, Iterable[str] | str],
        *,
        token: str | None = None,
    ) -> dict[str, dict[str, bool]]:
        output: dict[str, dict[str, bool]] = {}
        url = f"{self.settings.cisco_api_base_url}/software/v4.0/metadata/pidrelease"
        headers = {"Content-Type": "application/json"}

        for pid, versions in device_versions.items():
            if isinstance(versions, str):
                versions = [versions]
            output[str(pid)] = {}
            for version in versions:
                payload = {
                    "pid": pid,
                    "currentReleaseVersion": version,
                    "outputReleaseVersion": "latest",
                    "pageIndex": "1",
                    "perPage": "1",
                }
                try:
                    data = self._request_json("POST", url, token=token, headers=headers, json=payload)
                    deferred = self._extract_deferred_flag(data)
                    output[str(pid)][str(version)] = bool(deferred)
                except CiscoApiError as exc:
                    # The legacy logic treated non-200 as deferred. Preserve that business behavior,
                    # but keep the reason in logs for troubleshooting.
                    logger.info("Deferred check failed for %s %s: %s", pid, version, exc)
                    output[str(pid)][str(version)] = True
        return output

    @staticmethod
    def _extract_deferred_flag(data: Mapping[str, Any]) -> bool:
        def walk(value: Any) -> bool:
            if isinstance(value, Mapping):
                for key, item in value.items():
                    key_text = str(key).lower().replace("_", "")
                    if key_text in {"deferred", "isdeferred"}:
                        if item is True:
                            return True
                        if isinstance(item, str) and item.strip().lower() in {"y", "yes", "true", "deferred"}:
                            return True
                    if walk(item):
                        return True
            elif isinstance(value, list):
                return any(walk(item) for item in value)
            return False

        return walk(data)

    def software_milestones(
        self,
        device_versions: Mapping[str, Iterable[str] | str],
        *,
        token: str | None = None,
    ) -> dict[str, Any]:
        pid_list = list(device_versions.keys())
        suggestions = self.get_software_suggestions(pid_list, token=token)
        eos_dates = self.get_software_eos_by_release(device_versions, token=token)
        compatible = self.get_compatible_software(pid_list, token=token)
        deferred = self.software_deferred_check(device_versions, token=token)

        output: dict[str, Any] = {}
        for pid in pid_list:
            suggestion_rows = suggestions.get(pid, [])
            output[pid] = {
                "S/W Suggestion": [row.get("Suggested S/W Version") for row in suggestion_rows],
                "S/W Release Date": [row.get("Suggested S/W Release Date") for row in suggestion_rows],
                "Latest S/W Version": compatible.get(pid),
                "Deferred": deferred.get(pid, {}),
            }
        output["S/W EoS Dates"] = eos_dates
        return output

    @staticmethod
    def _clean_pid_list(items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        output: list[str] = []
        for item in items:
            pid = str(item).strip()
            if not pid or pid in seen:
                continue
            seen.add(pid)
            output.append(pid)
        return output
