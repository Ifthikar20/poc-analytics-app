"""In-memory latest-snapshot cache + SSE fan-out.

This is the entire "storage" layer of the PoC: one Snapshot per process plus a
queue per connected dashboard. Google/Cloudflare remain the system of record —
nothing is persisted here.
"""
from __future__ import annotations

import asyncio

from .schema import Snapshot


class SnapshotBus:
    def __init__(self) -> None:
        self._latest: Snapshot | None = None
        self._subscribers: set[asyncio.Queue[Snapshot]] = set()

    def publish(self, snapshot: Snapshot) -> None:
        self._latest = snapshot
        for queue in self._subscribers:
            try:
                queue.put_nowait(snapshot)
            except asyncio.QueueFull:
                # Slow consumer: drop this update for them; they catch up next tick.
                pass

    def latest(self) -> Snapshot | None:
        return self._latest

    def subscribe(self) -> asyncio.Queue[Snapshot]:
        queue: asyncio.Queue[Snapshot] = asyncio.Queue(maxsize=8)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Snapshot]) -> None:
        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
