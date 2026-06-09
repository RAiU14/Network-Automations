from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from sqlalchemy.orm import Session
from urllib3.util.retry import Retry

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.credential_store import CredentialStore
from app.services.normalization import clean_pid_list

logger = get_logger("eox_manager.cisco_api")


class CiscoApiError(RuntimeError):
    pass


def _chunked(items: Sequence[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _nested_value(record: Mapping[str, Any], key: str) -> Any:
    value = record.get(key)
    if isinstance(value, Mapping):
        return value.get("value")
    return value


@dataclass
class CiscoApiClient:
    db: Session
    timeout: int | None = None
    session: requests.Session = field(default_factory=requests.Session, init=False)

    def __post_init__(self) -> None:
        self.settings = get_settings()
        self.timeout = self.timeout or self.settings.http_timeout_seconds
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
        self.store = CredentialStore(self.db)

    def get_access_token(self, force_refresh: bool = False) -> str:
        cached = self.store.get_valid_access_token()
        if cached and not force_refresh:
            return cached

        client_id = self.store.get_cisco_client_id()
        client_secret = self.store.get_cisco_client_secret()
        if not client_id or not client_secret:
            raise CiscoApiError("Cisco API credentials are not configured. Use Setup first.")

        payload = {
            "grant_type": self.store.get_cisco_grant_type(),
            "client_id": client_id,
            "client_secret": client_secret,
        }
        response = self.session.post(
            self.store.get_cisco_token_url(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise CiscoApiError(f"Cisco token request failed: HTTP {response.status_code} - {response.text[:200]}")

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise CiscoApiError("Cisco token response did not include access_token")

        expires_in = int(data.get("expires_in") or 3600)
        self.store.cache_access_token(str(token), expires_in)
        logger.info("Cached Cisco access token for %s seconds", expires_in)
        return str(token)

    def _request_json(self, method: str, url: str, *, token: str | None = None, **kwargs: Any) -> dict[str, Any]:
        headers = kwargs.pop("headers", {}) or {}
        headers.update({"Authorization": f"Bearer {token or self.get_access_token()}", "Accept": "application/json"})
        response = self.session.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
        if response.status_code >= 400:
            raise CiscoApiError(f"Cisco API request failed: HTTP {response.status_code} - {response.text[:300]}")
        return response.json()

    def test_connection(self) -> bool:
        self.get_access_token(force_refresh=True)
        return True

    def get_hardware_eox_by_product_id(self, pids: Sequence[str]) -> dict[str, dict[str, Any]]:
        pid_list = clean_pid_list(pids)
        if not pid_list:
            return {}

        output: dict[str, dict[str, Any]] = {}
        base_url = f"{self.store.get_cisco_api_base_url().rstrip('/')}/supporttools/eox/rest/5/EOXByProductID/1"

        for batch in _chunked(pid_list, 20):
            pid_path = quote(",".join(batch), safe=",-")
            data = self._request_json("GET", f"{base_url}/{pid_path}")
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
                    "raw": dict(record),
                }
        return output
