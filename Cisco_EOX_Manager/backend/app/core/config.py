from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = PRODUCT_ROOT / "backend"
DATA_DIR_DEFAULT = PRODUCT_ROOT / "data"


def _path_from_env(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    return Path(raw).expanduser().resolve() if raw else default


def _csv_env(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("EOX_APP_NAME", "Cisco EOX Manager")
    api_prefix: str = os.getenv("EOX_API_PREFIX", "/api")
    environment: str = os.getenv("EOX_ENV", "local")

    database_url: str = os.getenv(
        "EOX_DATABASE_URL",
        "postgresql+psycopg://eox_user:eox_password@localhost:5432/eox_cache",
    )
    auto_create_tables: bool = os.getenv("EOX_AUTO_CREATE_TABLES", "true").lower() in {"1", "true", "yes"}

    data_dir: Path = _path_from_env("EOX_DATA_DIR", DATA_DIR_DEFAULT)
    log_dir: Path = _path_from_env("EOX_LOG_DIR", PRODUCT_ROOT / "logs")
    secret_key_file: Path = _path_from_env("EOX_SECRET_KEY_FILE", DATA_DIR_DEFAULT / ".eox_secret.key")

    cisco_base_url: str = os.getenv("CISCO_BASE_URL", "https://www.cisco.com").rstrip("/")
    cisco_api_base_url: str = os.getenv("CISCO_API_BASE_URL", "https://apix.cisco.com").rstrip("/")
    cisco_token_url: str = os.getenv("CISCO_TOKEN_URL", "https://id.cisco.com/oauth2/default/v1/token")
    http_timeout_seconds: int = int(os.getenv("EOX_HTTP_TIMEOUT_SECONDS", "30"))
    http_retries: int = int(os.getenv("EOX_HTTP_RETRIES", "3"))
    http_backoff_seconds: float = float(os.getenv("EOX_HTTP_BACKOFF_SECONDS", "0.5"))
    user_agent: str = os.getenv("EOX_USER_AGENT", "Cisco-EOX-Manager/1.0")

    cors_origins: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "cors_origins",
            _csv_env(
                "EOX_CORS_ORIGINS",
                "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:3000,http://localhost:3000",
            ),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    settings.secret_key_file.parent.mkdir(parents=True, exist_ok=True)
    return settings


SETTINGS = get_settings()
