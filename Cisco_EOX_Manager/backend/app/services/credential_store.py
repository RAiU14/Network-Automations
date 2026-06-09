from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import AppSetting
from app.services.normalization import mask_secret


class CredentialStore:
    def __init__(self, db: Session):
        self.db = db
        self.settings = get_settings()
        self._fernet = Fernet(self._load_or_create_key())

    def _load_or_create_key(self) -> bytes:
        env_key = os.getenv("EOX_SECRET_KEY")
        if env_key:
            return env_key.encode("utf-8")

        key_file = self.settings.secret_key_file
        if key_file.exists():
            return key_file.read_bytes().strip()

        key = Fernet.generate_key()
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(key)
        return key

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def _decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")

    def set_value(self, key: str, value: str | None, *, secret: bool = False) -> None:
        existing = self.db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
        encoded_value = self._encrypt(value) if secret and value else value
        if existing:
            existing.value = encoded_value
            existing.is_secret = secret
        else:
            self.db.add(AppSetting(key=key, value=encoded_value, is_secret=secret))

    def get_value(self, key: str, default: str | None = None) -> str | None:
        existing = self.db.query(AppSetting).filter(AppSetting.key == key).one_or_none()
        if not existing or existing.value is None:
            return default
        if existing.is_secret:
            return self._decrypt(existing.value)
        return existing.value

    def setup_cisco_credentials(
        self,
        *,
        client_id: str | None,
        client_secret: str | None,
        access_token: str | None = None,
        token_expires_in_seconds: int | None = None,
        api_base_url: str | None = None,
        token_url: str | None = None,
        grant_type: str = "client_credentials",
    ) -> None:
        if client_id is not None:
            self.set_value("cisco_client_id", client_id.strip(), secret=True)
        if client_secret is not None:
            self.set_value("cisco_client_secret", client_secret.strip(), secret=True)
        if access_token is not None:
            self.set_value("cisco_access_token", access_token.strip(), secret=True)
            expires_in = token_expires_in_seconds or 3600
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            self.set_value("cisco_token_expires_at", str(expires_at.timestamp()), secret=False)
        if api_base_url is not None:
            self.set_value("cisco_api_base_url", api_base_url.rstrip("/"), secret=False)
        if token_url is not None:
            self.set_value("cisco_token_url", token_url, secret=False)
        if grant_type is not None:
            self.set_value("cisco_grant_type", grant_type, secret=False)
        self.db.commit()

    def cisco_credentials_configured(self) -> bool:
        client_id = self.get_value("cisco_client_id") or os.getenv("CISCO_CLIENT_ID")
        client_secret = self.get_value("cisco_client_secret") or os.getenv("CISCO_CLIENT_SECRET")
        access_token = self.get_valid_access_token()
        return bool((client_id and client_secret) or access_token)

    def get_cisco_client_id(self) -> str | None:
        return self.get_value("cisco_client_id") or os.getenv("CISCO_CLIENT_ID")

    def get_cisco_client_secret(self) -> str | None:
        return self.get_value("cisco_client_secret") or os.getenv("CISCO_CLIENT_SECRET")

    def get_cisco_api_base_url(self) -> str:
        return self.get_value("cisco_api_base_url") or os.getenv("CISCO_API_BASE_URL") or self.settings.cisco_api_base_url

    def get_cisco_token_url(self) -> str:
        return self.get_value("cisco_token_url") or os.getenv("CISCO_TOKEN_URL") or self.settings.cisco_token_url

    def get_cisco_grant_type(self) -> str:
        return self.get_value("cisco_grant_type") or "client_credentials"

    def get_valid_access_token(self) -> str | None:
        token = self.get_value("cisco_access_token") or os.getenv("CISCO_ACCESS_TOKEN")
        if not token:
            return None
        expires_at_raw = self.get_value("cisco_token_expires_at")
        if not expires_at_raw:
            # Assume environment tokens are intentionally managed outside the app.
            return token if os.getenv("CISCO_ACCESS_TOKEN") else None
        try:
            if time.time() < float(expires_at_raw) - 60:
                return token
        except ValueError:
            return None
        return None

    def cache_access_token(self, token: str, expires_in: int) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        self.set_value("cisco_access_token", token, secret=True)
        self.set_value("cisco_token_expires_at", str(expires_at.timestamp()), secret=False)
        self.db.commit()

    def status(self) -> dict[str, object]:
        client_id = self.get_cisco_client_id()
        return {
            "configured": self.cisco_credentials_configured(),
            "client_id_hint": mask_secret(client_id),
            "api_base_url": self.get_cisco_api_base_url(),
            "token_url": self.get_cisco_token_url(),
            "has_cached_token": bool(self.get_valid_access_token()),
        }
