from __future__ import annotations

from abc import ABC, abstractmethod

from ..schema import Snapshot


class Provider(ABC):
    """A provider answers one question per tick: what does traffic look like right now?"""

    name: str

    @abstractmethod
    async def fetch_snapshot(self) -> Snapshot: ...
