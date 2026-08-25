"""Demo mode: a local stand-in for GA4's realtime store.

Beacons from tracker.js (and an optional simulator) land in an in-memory
30-minute rolling window with the same semantics the real providers expose:
active users over the last 5 minutes, per-minute pageviews over the last 30.
Nothing is persisted — restart the process and the window starts empty, just
like a "no database" deployment would.
"""
from __future__ import annotations

import asyncio
import math
import random
import time
from collections import Counter, deque
from dataclasses import dataclass
from datetime import datetime, timezone

from ..schema import MinuteBucket, Snapshot, TopItem
from .base import Provider

WINDOW_MINUTES = 30
ACTIVE_WINDOW_MINUTES = 5

SIM_PATHS = ["/", "/pricing", "/about", "/blog", "/contact"]
SIM_PATH_WEIGHTS = [40, 25, 15, 12, 8]
SIM_COUNTRIES = [
    "United States", "India", "Germany", "United Kingdom", "Brazil",
    "Japan", "France", "Canada", "Australia", "Netherlands",
]
SIM_COUNTRY_WEIGHTS = [30, 15, 10, 10, 8, 7, 6, 6, 4, 4]


@dataclass
class PageEvent:
    ts: float
    visitor_id: str
    path: str
    country: str


class DemoStore:
    def __init__(self, max_events: int = 50_000) -> None:
        self._events: deque[PageEvent] = deque(maxlen=max_events)

    def record(
        self, visitor_id: str, path: str, country: str, ts: float | None = None
    ) -> None:
        self._events.append(
            PageEvent(
                ts=ts if ts is not None else time.time(),
                visitor_id=visitor_id,
                path=path,
                country=country,
            )
        )

    def prune(self, now_ts: float) -> None:
        cutoff = now_ts - (WINDOW_MINUTES + 1) * 60
        while self._events and self._events[0].ts < cutoff:
            self._events.popleft()

    def build_snapshot(self, now: datetime) -> Snapshot:
        now_ts = now.timestamp()
        self.prune(now_ts)
        window = [e for e in self._events if 0 <= now_ts - e.ts < WINDOW_MINUTES * 60]
        active_cutoff = now_ts - ACTIVE_WINDOW_MINUTES * 60
        active_events = [e for e in window if e.ts >= active_cutoff]

        by_minute = Counter(int((now_ts - e.ts) // 60) for e in window)
        per_minute = [
            MinuteBucket(minutes_ago=m, pageviews=by_minute.get(m, 0))
            for m in range(WINDOW_MINUTES - 1, -1, -1)
        ]

        pages = Counter(e.path for e in window).most_common(10)

        country_visitors: dict[str, set[str]] = {}
        for e in active_events:
            country_visitors.setdefault(e.country, set()).add(e.visitor_id)
        countries = sorted(
            ((c, len(v)) for c, v in country_visitors.items()),
            key=lambda kv: kv[1],
            reverse=True,
        )[:10]

        return Snapshot(
            source="demo",
            fetched_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            window_minutes=WINDOW_MINUTES,
            active_users=len({e.visitor_id for e in active_events}),
            active_window_minutes=ACTIVE_WINDOW_MINUTES,
            per_minute=per_minute,
            top_pages=[TopItem(name=p, value=n) for p, n in pages],
            top_countries=[TopItem(name=c, value=n) for c, n in countries],
            notes=["Demo mode: data comes from local beacons and the built-in traffic simulator."],
        )


# One store per process, shared by /api/track, the mock provider and the simulator.
store = DemoStore()


class MockProvider(Provider):
    name = "demo"

    async def fetch_snapshot(self) -> Snapshot:
        return store.build_snapshot(datetime.now(timezone.utc))


async def run_simulator(target: DemoStore) -> None:
    """Background fake traffic so the dashboard is alive with zero setup.

    Real beacons from the demo site flow into the same store (as country
    "Local"), so opening extra tabs still visibly moves the numbers.
    """
    visitor_serial = 0
    # A visitor keeps one country for life — otherwise per-country visitor
    # counts would exceed the overall active-user count.
    pool: deque[tuple[str, str]] = deque(maxlen=20)
    while True:
        # A ~19-minute swell so the live counter wanders instead of flatlining.
        p = 0.35 + 0.3 * math.sin(time.time() / 180)
        if random.random() < p:
            for _ in range(random.randint(1, 3)):
                if not pool or random.random() < 0.15:
                    visitor_serial += 1
                    pool.append((
                        f"sim-{visitor_serial}",
                        random.choices(SIM_COUNTRIES, weights=SIM_COUNTRY_WEIGHTS)[0],
                    ))
                visitor_id, country = random.choice(pool)
                target.record(
                    visitor_id=visitor_id,
                    path=random.choices(SIM_PATHS, weights=SIM_PATH_WEIGHTS)[0],
                    country=country,
                )
        await asyncio.sleep(1)
