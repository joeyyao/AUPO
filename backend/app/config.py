"""Application configuration.

All secrets are read from environment variables (loaded from a local .env that is
git-ignored). Nothing sensitive is ever exposed to the browser: the frontend only
talks to this API.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"

load_dotenv(BASE_DIR / ".env")


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    return value.strip() if value is not None else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


class Settings:
    """Runtime settings resolved from environment variables."""

    def __init__(self) -> None:
        self.host: str = _env_str("APP_HOST", "127.0.0.1")
        self.port: int = _env_int("APP_PORT", 8000)
        self.env: str = _env_str("APP_ENV", "development")

        self.auspost_api_base: str = _env_str(
            "AUSPOST_API_BASE", "https://digitalapi.auspost.com.au/test/shipping/v1"
        ).rstrip("/")
        self.auspost_api_key: str = _env_str("AUSPOST_API_KEY")
        self.auspost_api_password: str = _env_str("AUSPOST_API_PASSWORD")

        self.tnt_username: str = _env_str("TNT_USERNAME")
        self.tnt_password: str = _env_str("TNT_PASSWORD")
        self.tnt_account: str = _env_str("TNT_ACCOUNT")
        self.tnt_weblinking_username: str = _env_str("TNT_WEBLINKING_USERNAME")
        self.tnt_weblinking_password: str = _env_str("TNT_WEBLINKING_PASSWORD")

        self.enable_live_tracking: bool = _env_bool("ENABLE_LIVE_TRACKING", True)
        self.tracking_timeout_seconds: float = float(
            _env_int("TRACKING_TIMEOUT_SECONDS", 8)
        )
        self.tracking_cache_seconds: int = _env_int("TRACKING_CACHE_SECONDS", 120)

        self.shipping_origin_postcode: str = _env_str("SHIPPING_ORIGIN_POSTCODE", "2111")

    @property
    def auspost_configured(self) -> bool:
        return bool(self.auspost_api_key)


settings = Settings()
