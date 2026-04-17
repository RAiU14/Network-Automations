import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    # Database Configuration
    DB_TYPE: str = "sqlite"
    DB_FILE: str = str(ROOT_DIR / "db" / "nms.db")
    DB_URL: Optional[str] = None

    # Cisco Device Credentials (Global)
    CISCO_USERNAME: str = "admin"
    CISCO_PASSWORD: str = "password"
    CISCO_SECRET: Optional[str] = None

    # Jump Host Credentials
    JUMP_HOST: Optional[str] = None

    # SNMP Global Configuration
    SNMP_COMMUNITY: str = "public"
    SNMP_VERSION: str = "2"

    # Application Settings
    DEBUG: bool = True
    HOST: str = "127.0.0.1" # Change to 127.0.0.1 for local testing
    PORT: int = 8000
    MOCK_MODE: bool = True

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"), 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        if self.DB_TYPE == "postgresql" and self.DB_URL:
            return self.DB_URL
        return f"sqlite:///{self.DB_FILE}"

settings = Settings()
