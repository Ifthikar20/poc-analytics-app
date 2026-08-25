from ..config import Settings
from .base import Provider
from .cloudflare import CloudflareProvider
from .ga4 import GA4Provider
from .mock import MockProvider


def make_provider(settings: Settings) -> Provider:
    if settings.provider == "ga4":
        return GA4Provider(settings.ga4_property_id, settings.google_credentials_path)
    if settings.provider == "cloudflare":
        return CloudflareProvider(settings.cf_api_token, settings.cf_zone_id)
    return MockProvider()
