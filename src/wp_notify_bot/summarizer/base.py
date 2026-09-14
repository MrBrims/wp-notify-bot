from __future__ import annotations

from abc import ABC, abstractmethod

from wp_notify_bot.models import NormalizedItem


class Summarizer(ABC):
    @abstractmethod
    async def summarize(self, item: NormalizedItem) -> str:
        raise NotImplementedError
