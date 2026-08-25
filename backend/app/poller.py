"""The polling loop.

One upstream fetch per tick feeds every dashboard viewer through the bus —
quota cost is per property, never per viewer. On failure the last good
snapshot keeps being served and the error is surfaced via /api/status.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from .bus import SnapshotBus
from .providers.base import Provider

log = logging.getLogger("poller")


@dataclass
class PollerState:
    last_ok_at: datetime | None = None
    last_error: str | None = None
    ticks: int = 0


async def run_poller(
    provider: Provider, bus: SnapshotBus, interval: float, state: PollerState
) -> None:
    while True:
        try:
            snapshot = await provider.fetch_snapshot()
            bus.publish(snapshot)
            state.last_ok_at = datetime.now(timezone.utc)
            state.last_error = None
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            state.last_error = f"{type(exc).__name__}: {exc}"
            log.warning("poll failed: %s", state.last_error)
        state.ticks += 1
        await asyncio.sleep(interval)
