"""Startup validation: malformed vendor identifiers must be rejected before
the server serves anything (typo-catching + defense in depth for the value
substituted into demo-page HTML)."""
import pytest

from app.config import Settings, validate


def make(provider: str = "mock", **overrides) -> Settings:
    base = dict(
        provider=provider,
        poll_interval=3.0,
        simulate_traffic=True,
        ga4_property_id=None,
        google_credentials_path=None,
        ga4_measurement_id=None,
        cf_api_token=None,
        cf_zone_id=None,
    )
    base.update(overrides)
    return Settings(**base)


def test_measurement_id_html_breakout_rejected():
    with pytest.raises(RuntimeError):
        validate(make(ga4_measurement_id='G-ABC"><script>alert(1)</script>'))


def test_measurement_id_valid_format_accepted():
    validate(make(ga4_measurement_id="G-ABC123XYZ0"))


def test_ga4_provider_requires_creds():
    with pytest.raises(RuntimeError):
        validate(make(provider="ga4"))


def test_ga4_property_id_must_be_numeric():
    with pytest.raises(RuntimeError):
        validate(make(provider="ga4", ga4_property_id="G-ABC123XYZ0",
                      google_credentials_path="/nonexistent.json"))


def test_cloudflare_zone_id_format():
    with pytest.raises(RuntimeError):
        validate(make(provider="cloudflare", cf_api_token="token", cf_zone_id="not-hex"))
    validate(make(provider="cloudflare", cf_api_token="token",
                  cf_zone_id="0123456789abcdef0123456789abcdef"))
