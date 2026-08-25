"""Cloudflare GraphQL Analytics provider.

One POST per tick with two aliased selections over httpRequestsAdaptiveGroups
(the zone must be orange-cloud proxied through Cloudflare). The dataset is
adaptively sampled: every number here is raw x avg.sampleInterval and therefore
an estimate — the snapshot's notes say so out loud.

Quota context: the GraphQL API allows ~300 queries per 5 minutes. At a 15s
interval this provider sends 20 POSTs per 5 minutes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from ..schema import MinuteBucket, Snapshot, TopItem
from .base import Provider

CF_GQL_URL = "https://api.cloudflare.com/client/v4/graphql"

WINDOW_MINUTES = 30
ACTIVE_WINDOW_MINUTES = 5

# edgeResponseContentTypeName:"html" keeps `count` close to "page loads"
# instead of counting every asset/API request the zone serves.
TRAFFIC_QUERY = """
query Traffic($zoneTag: String!, $since: Time!) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      series: httpRequestsAdaptiveGroups(
        limit: 500
        filter: { datetime_geq: $since, edgeResponseContentTypeName: "html" }
      ) {
        count
        avg { sampleInterval }
        sum { visits }
        dimensions { datetimeMinute clientCountryName }
      }
      paths: httpRequestsAdaptiveGroups(
        limit: 200
        filter: { datetime_geq: $since, edgeResponseContentTypeName: "html" }
      ) {
        count
        avg { sampleInterval }
        dimensions { clientRequestPath }
      }
    }
  }
}
"""

NOTES = [
    "Cloudflare figures are sampled estimates (raw counts x sampleInterval).",
    f"Active users approximated from estimated visits in the last {ACTIVE_WINDOW_MINUTES} min.",
    "Cloudflare analytics lag the edge by roughly 1-5 minutes.",
]


def unsample(raw: float, sample_interval: float | None) -> int:
    """Adaptive sampling: a row with sampleInterval=10 represents ~10x its raw count."""
    return round(raw * max(sample_interval or 1.0, 1.0))


def minutes_ago(datetime_minute_iso: str, now: datetime) -> int:
    dt = datetime.fromisoformat(datetime_minute_iso.replace("Z", "+00:00"))
    return int((now - dt).total_seconds() // 60)


def build_cf_snapshot(series_rows: list[dict], path_rows: list[dict], now: datetime) -> Snapshot:
    by_minute: dict[int, int] = {}
    by_country: dict[str, int] = {}
    active_users = 0
    for row in series_rows:
        interval = (row.get("avg") or {}).get("sampleInterval", 1.0)
        m = minutes_ago(row["dimensions"]["datetimeMinute"], now)
        if not 0 <= m < WINDOW_MINUTES:
            continue
        est_requests = unsample(row.get("count", 0), interval)
        est_visits = unsample((row.get("sum") or {}).get("visits", 0), interval)
        by_minute[m] = by_minute.get(m, 0) + est_requests
        country = row["dimensions"].get("clientCountryName") or "Unknown"
        by_country[country] = by_country.get(country, 0) + est_visits
        if m < ACTIVE_WINDOW_MINUTES:
            active_users += est_visits

    per_minute = [
        MinuteBucket(minutes_ago=m, pageviews=by_minute.get(m, 0))
        for m in range(WINDOW_MINUTES - 1, -1, -1)
    ]
    # Countries/pages cover the whole 30-min window (the sampled 5-min slice is
    # too sparse to rank), sorted here rather than trusting GraphQL ordering.
    top_countries = sorted(by_country.items(), key=lambda kv: kv[1], reverse=True)[:10]

    by_path: dict[str, int] = {}
    for row in path_rows:
        interval = (row.get("avg") or {}).get("sampleInterval", 1.0)
        path = row["dimensions"].get("clientRequestPath") or "/"
        by_path[path] = by_path.get(path, 0) + unsample(row.get("count", 0), interval)
    top_pages = sorted(by_path.items(), key=lambda kv: kv[1], reverse=True)[:10]

    return Snapshot(
        source="cloudflare",
        fetched_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        window_minutes=WINDOW_MINUTES,
        active_users=active_users,
        active_window_minutes=ACTIVE_WINDOW_MINUTES,
        per_minute=per_minute,
        top_pages=[TopItem(name=p, value=v) for p, v in top_pages],
        top_countries=[TopItem(name=c, value=v) for c, v in top_countries],
        notes=list(NOTES),
    )


class CloudflareProvider(Provider):
    name = "cloudflare"

    def __init__(self, api_token: str, zone_id: str) -> None:
        self._zone_id = zone_id
        self._client = httpx.AsyncClient(
            timeout=15, headers={"Authorization": f"Bearer {api_token}"}
        )

    async def fetch_snapshot(self) -> Snapshot:
        now = datetime.now(timezone.utc)
        since = (now - timedelta(minutes=WINDOW_MINUTES)).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = await self._client.post(
            CF_GQL_URL,
            json={
                "query": TRAFFIC_QUERY,
                "variables": {"zoneTag": self._zone_id, "since": since},
            },
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"Cloudflare GraphQL error: {payload['errors']}")
        zones = payload["data"]["viewer"]["zones"]
        if not zones:
            raise RuntimeError(
                "Cloudflare returned no zone for CF_ZONE_ID (check the token scope and zone id)"
            )
        zone = zones[0]
        return build_cf_snapshot(zone.get("series") or [], zone.get("paths") or [], now)
