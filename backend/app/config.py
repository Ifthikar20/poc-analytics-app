"""Environment-driven configuration. No database, no config files beyond .env."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]  # repo root
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"

VALID_PROVIDERS = ("mock", "ga4", "cloudflare")

# Strict formats: catches typos early, and (defense in depth) guarantees the
# measurement id is inert when substituted into demo-page HTML.
_MEASUREMENT_ID_RE = re.compile(r"^G-[A-Z0-9]{4,20}$")
_PROPERTY_ID_RE = re.compile(r"^[0-9]{1,20}$")
_ZONE_ID_RE = re.compile(r"^[0-9a-f]{32}$")


@dataclass(frozen=True)
class Settings:
    provider: str
    poll_interval: float
    simulate_traffic: bool
    ga4_property_id: str | None
    google_credentials_path: str | None
    ga4_measurement_id: str | None
    cf_api_token: str | None
    cf_zone_id: str | None


def _env(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")
    provider = (os.environ.get("ANALYTICS_PROVIDER") or "mock").strip().lower()
    interval_raw = _env("POLL_INTERVAL_SECONDS")
    if interval_raw is not None:
        poll_interval = float(interval_raw)
    else:
        # Real providers get a quota-friendly cadence; the local store can go faster.
        poll_interval = 3.0 if provider == "mock" else 15.0
    return Settings(
        provider=provider,
        poll_interval=poll_interval,
        simulate_traffic=os.environ.get("SIMULATE_TRAFFIC", "true").strip().lower()
        not in ("0", "false", "no", "off"),
        ga4_property_id=_env("GA4_PROPERTY_ID"),
        google_credentials_path=_env("GOOGLE_APPLICATION_CREDENTIALS"),
        ga4_measurement_id=_env("GA4_MEASUREMENT_ID"),
        cf_api_token=_env("CF_API_TOKEN"),
        cf_zone_id=_env("CF_ZONE_ID"),
    )


def validate(settings: Settings) -> None:
    """Fail fast at startup with an actionable message if the chosen provider is unusable."""
    if settings.provider not in VALID_PROVIDERS:
        raise RuntimeError(
            f"ANALYTICS_PROVIDER={settings.provider!r} must be one of: {', '.join(VALID_PROVIDERS)}"
        )
    if settings.ga4_measurement_id and not _MEASUREMENT_ID_RE.match(settings.ga4_measurement_id):
        raise RuntimeError(
            "GA4_MEASUREMENT_ID must look like G-XXXXXXXXXX (uppercase letters/digits). "
            "It is substituted into demo-page HTML, so malformed values are rejected outright."
        )
    if settings.provider == "ga4":
        if not settings.ga4_property_id:
            raise RuntimeError(
                "ANALYTICS_PROVIDER=ga4 requires GA4_PROPERTY_ID (the numeric property id)"
            )
        if not _PROPERTY_ID_RE.match(settings.ga4_property_id):
            raise RuntimeError(
                "GA4_PROPERTY_ID must be the numeric property id (digits only), "
                "not a G-… measurement id"
            )
        if not settings.google_credentials_path:
            raise RuntimeError(
                "ANALYTICS_PROVIDER=ga4 requires GOOGLE_APPLICATION_CREDENTIALS — the path to a "
                "service-account JSON key whose email was added as Viewer on the GA4 property"
            )
        if not Path(settings.google_credentials_path).is_file():
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS points to a missing file: "
                f"{settings.google_credentials_path}"
            )
    if settings.provider == "cloudflare":
        if not settings.cf_api_token:
            raise RuntimeError(
                "ANALYTICS_PROVIDER=cloudflare requires CF_API_TOKEN "
                "(an API token scoped Zone -> Analytics -> Read)"
            )
        if not settings.cf_zone_id:
            raise RuntimeError(
                "ANALYTICS_PROVIDER=cloudflare requires CF_ZONE_ID "
                "(the zone tag shown on the Cloudflare dashboard's zone Overview)"
            )
        if not _ZONE_ID_RE.match(settings.cf_zone_id):
            raise RuntimeError("CF_ZONE_ID must be the 32-character hex zone tag")
