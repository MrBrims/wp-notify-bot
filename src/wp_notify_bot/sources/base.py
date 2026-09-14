from __future__ import annotations

from abc import ABC, abstractmethod

from wp_notify_bot.models import NormalizedItem


class Source(ABC):
    source_id: str

    @abstractmethod
    async def fetch(self) -> list[NormalizedItem]:
        raise NotImplementedError
