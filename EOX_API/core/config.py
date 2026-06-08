from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parent


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser().resolve() if raw else default


@dataclass(frozen=True)
class Settings:
    cisco_base_url: str = os.getenv("CISCO_BASE_URL", "https://www.cisco.com").rstrip("/")
    cisco_token_url: str = os.getenv(
        "CISCO_TOKEN_URL",
        "https://id.cisco.com/oauth2/default/v1/token",
    )
    cisco_api_base_url: str = os.getenv("CISCO_API_BASE_URL", "https://apix.cisco.com").rstrip("/")
    http_timeout_seconds: int = int(os.getenv("EOX_HTTP_TIMEOUT_SECONDS", "30"))
    http_retries: int = int(os.getenv("EOX_HTTP_RETRIES", "3"))
    http_backoff_seconds: float = float(os.getenv("EOX_HTTP_BACKOFF_SECONDS", "0.5"))
    user_agent: str = os.getenv("EOX_USER_AGENT", "Network-Automation-EOX/2.0")
    data_dir: Path = _path_from_env("EOX_DATA_DIR", REPO_ROOT / "Database" / "JSON_Files")
    log_dir: Path = _path_from_env("EOX_LOG_DIR", PACKAGE_ROOT / "logs")
    token_cache_file: Path = _path_from_env(
        "CISCO_TOKEN_CACHE_FILE",
        _path_from_env("EOX_DATA_DIR", REPO_ROOT / "Database" / "JSON_Files") / ".cisco_token_cache.json",
    )
    credentials_file: Path | None = (
        Path(os.getenv("CISCO_CREDENTIALS_FILE", "")).expanduser().resolve()
        if os.getenv("CISCO_CREDENTIALS_FILE")
        else None
    )

    @property
    def default_eox_db_path(self) -> Path:
        return self.data_dir / "eox_pid.json"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.token_cache_file.parent.mkdir(parents=True, exist_ok=True)
    return settings


SETTINGS = get_settings()
CISCO_BASE_URL = SETTINGS.cisco_base_url
CISCO_API_BASE_URL = SETTINGS.cisco_api_base_url
CISCO_TOKEN_URL = SETTINGS.cisco_token_url
HTTP_TIMEOUT_SECONDS = SETTINGS.http_timeout_seconds
USER_AGENT = SETTINGS.user_agent
DEFAULT_EOX_DB_PATH = SETTINGS.default_eox_db_path
