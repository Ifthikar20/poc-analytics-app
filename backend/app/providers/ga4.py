"""GA4 Realtime Data API provider.

Three small runRealtimeReport calls per tick (the realtime API has no batch
endpoint), assembled into the common Snapshot. Auth is a service account whose
email the property owner added as Viewer.

Quota context: a standard property allows 40k realtime tokens/hour and 10
concurrent requests. At a 15s interval this provider issues ~720 requests/hour
costing a few tokens each — comfortably inside budget, and one poll feeds every
dashboard viewer via SSE.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2 import service_account

from ..schema import MinuteBucket, Snapshot, TopItem
from .base import Provider

SCOPE = "https://www.googleapis.com/auth/analytics.readonly"
REALTIME_URL = (
    "https://analyticsdata.googleapis.com/v1beta/properties/{pid}:runRealtimeReport"
)

WINDOW_MINUTES = 30
ACTIVE_WINDOW_MINUTES = 5

# activeUsers is deduplicated per row, so the total must come from a dimension
# a user occupies exactly once (country) — never from summing across minutes,
# where one user active in three minutes would count three times.
ACTIVE_AND_COUNTRIES_BODY = {
    "dimensions": [{"name": "country"}],
    "metrics": [{"name": "activeUsers"}],
    "minuteRanges": [{"startMinutesAgo": ACTIVE_WINDOW_MINUTES - 1, "endMinutesAgo": 0}],
    "orderBys": [{"metric": {"metricName": "activeUsers"}, "desc": True}],
    "limit": 250,
    "returnPropertyQuota": True,
}
SERIES_BODY = {
    "dimensions": [{"name": "minutesAgo"}],
    "metrics": [{"name": "screenPageViews"}],
    "minuteRanges": [{"startMinutesAgo": WINDOW_MINUTES - 1, "endMinutesAgo": 0}],
}
TOP_PAGES_BODY = {
    "dimensions": [{"name": "unifiedScreenName"}],
    "metrics": [{"name": "screenPageViews"}],
    "minuteRanges": [{"startMinutesAgo": WINDOW_MINUTES - 1, "endMinutesAgo": 0}],
    "orderBys": [{"metric": {"metricName": "screenPageViews"}, "desc": True}],
    "limit": 10,
}


def build_minute_series(rows: list[dict], window: int = WINDOW_MINUTES) -> list[MinuteBucket]:
    # minutesAgo arrives as zero-padded strings ("00".."29") and minutes with
    # no traffic are simply absent from the response — fill the gaps with 0.
    by_minute: dict[int, int] = {}
    for row in rows:
        minute = int(row["dimensionValues"][0]["value"])
        by_minute[minute] = int(row["metricValues"][0]["value"])
    return [
        MinuteBucket(minutes_ago=m, pageviews=by_minute.get(m, 0))
        for m in range(window - 1, -1, -1)
    ]


def build_top_items(rows: list[dict], limit: int = 10) -> list[TopItem]:
    return [
        TopItem(
            name=row["dimensionValues"][0]["value"],
            value=int(row["metricValues"][0]["value"]),
        )
        for row in rows[:limit]
    ]


def sum_active_users(rows: list[dict]) -> int:
    return sum(int(row["metricValues"][0]["value"]) for row in rows)


class GA4Provider(Provider):
    name = "ga4"

    def __init__(self, property_id: str, credentials_path: str) -> None:
        self._url = REALTIME_URL.format(pid=property_id)
        self._creds = service_account.Credentials.from_service_account_file(
            credentials_path, scopes=[SCOPE]
        )
        self._client = httpx.AsyncClient(timeout=10)

    async def _token(self) -> str:
        if not self._creds.valid:
            # google-auth's refresh is blocking; keep it off the event loop.
            await asyncio.to_thread(self._creds.refresh, GoogleAuthRequest())
        return self._creds.token

    async def _run_report(self, body: dict) -> dict:
        token = await self._token()
        response = await self._client.post(
            self._url, json=body, headers={"Authorization": f"Bearer {token}"}
        )
        response.raise_for_status()
        return response.json()

    async def fetch_snapshot(self) -> Snapshot:
        actives, series, pages = await asyncio.gather(
            self._run_report(ACTIVE_AND_COUNTRIES_BODY),
            self._run_report(SERIES_BODY),
            self._run_report(TOP_PAGES_BODY),
        )
        country_rows = actives.get("rows", [])
        return Snapshot(
            source="ga4",
            fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            window_minutes=WINDOW_MINUTES,
            active_users=sum_active_users(country_rows),
            active_window_minutes=ACTIVE_WINDOW_MINUTES,
            per_minute=build_minute_series(series.get("rows", [])),
            top_pages=build_top_items(pages.get("rows", [])),
            top_countries=build_top_items(country_rows),
            notes=["GA4 realtime reports page titles, not paths (realtime API limitation)."],
        )
