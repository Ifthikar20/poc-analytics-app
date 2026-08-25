"""The Snapshot contract: poller -> cache -> SSE -> dashboard.

Every provider (demo, GA4, Cloudflare) fills the same shape, so the UI never
cares where the numbers came from. Gaps a provider cannot fill are expressed
as empty lists plus a human-readable entry in `notes`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class MinuteBucket(BaseModel):
    minutes_ago: int  # 29 (oldest) .. 0 (current minute)
    pageviews: int


class TopItem(BaseModel):
    name: str  # page path/title, or country name
    value: int


class Snapshot(BaseModel):
    source: Literal["demo", "ga4", "cloudflare"]
    fetched_at: str  # UTC ISO-8601
    window_minutes: int = 30  # chart window
    active_users: int
    active_window_minutes: int = 5  # what "active" means
    per_minute: list[MinuteBucket]  # always exactly window_minutes entries, ordered 29 -> 0
    top_pages: list[TopItem]  # <= 10; [] when the source can't provide it
    top_countries: list[TopItem]  # <= 10
    notes: list[str] = []  # caveats, rendered as footnotes in the UI
