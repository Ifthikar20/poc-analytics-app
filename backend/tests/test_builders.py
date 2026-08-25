"""Unit tests for the pure snapshot builders — the only logic that can't be
demonstrated live without GA4/Cloudflare credentials. No network, no app."""
from datetime import datetime, timezone

from app.providers.cloudflare import build_cf_snapshot, minutes_ago, unsample
from app.providers.ga4 import build_minute_series, build_top_items, sum_active_users
from app.providers.mock import DemoStore

NOW = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)


def ga4_row(dim: str, value: int) -> dict:
    return {"dimensionValues": [{"value": dim}], "metricValues": [{"value": str(value)}]}


def test_ga4_series_gap_fill():
    # minutesAgo comes back zero-padded and minutes with no traffic are absent.
    rows = [ga4_row("00", 9), ga4_row("07", 2)]
    series = build_minute_series(rows)
    assert len(series) == 30
    assert series[0].minutes_ago == 29 and series[-1].minutes_ago == 0
    assert series[-1].pageviews == 9
    assert series[29 - 7].pageviews == 2
    assert sum(b.pageviews for b in series) == 11


def test_ga4_active_users_sum_and_top_countries():
    rows = [ga4_row(f"Country {i}", 12 - i) for i in range(12)]
    assert sum_active_users(rows) == sum(range(1, 13))
    top = build_top_items(rows)
    assert len(top) == 10
    assert top[0].name == "Country 0" and top[0].value == 12


def test_cf_unsample():
    assert unsample(12, 10) == 120
    assert unsample(12, 0.5) == 12  # intervals below 1 clamp to the raw count
    assert unsample(12, None) == 12
    assert minutes_ago("2026-08-25T11:58:00Z", NOW) == 2


def cf_row(minute_iso: str, country: str, count: int, visits: int, interval: float) -> dict:
    return {
        "count": count,
        "avg": {"sampleInterval": interval},
        "sum": {"visits": visits},
        "dimensions": {"datetimeMinute": minute_iso, "clientCountryName": country},
    }


def test_cf_snapshot_assembly():
    rows = [
        cf_row("2026-08-25T11:58:00Z", "US", 10, 4, 1),  # 2 min ago
        cf_row("2026-08-25T11:58:00Z", "DE", 5, 2, 2),   # 2 min ago, sampled x2
        cf_row("2026-08-25T11:40:00Z", "US", 7, 3, 1),   # 20 min ago
    ]
    paths = [
        {"count": 6, "avg": {"sampleInterval": 2}, "dimensions": {"clientRequestPath": "/"}},
        {"count": 3, "avg": {"sampleInterval": 1}, "dimensions": {"clientRequestPath": "/x"}},
    ]
    snap = build_cf_snapshot(rows, paths, NOW)
    assert len(snap.per_minute) == 30
    assert next(b for b in snap.per_minute if b.minutes_ago == 2).pageviews == 10 + 5 * 2
    assert next(b for b in snap.per_minute if b.minutes_ago == 20).pageviews == 7
    assert snap.active_users == 4 + 2 * 2  # only rows inside the 5-min window
    assert snap.top_pages[0].name == "/" and snap.top_pages[0].value == 12
    assert {c.name for c in snap.top_countries} == {"US", "DE"}
    assert snap.notes


def test_mock_store_active_window():
    store = DemoStore()
    now_ts = NOW.timestamp()
    store.record("old-visitor", "/a", "US", ts=now_ts - 6 * 60)
    store.record("new-visitor", "/b", "US", ts=now_ts - 1 * 60)
    snap = store.build_snapshot(NOW)
    assert snap.active_users == 1  # the 6-min-old visitor is outside the 5-min window
    assert sum(b.pageviews for b in snap.per_minute) == 2  # but still on the 30-min chart
    assert {p.name for p in snap.top_pages} == {"/a", "/b"}
