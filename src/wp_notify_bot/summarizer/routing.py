from __future__ import annotations

import logging

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.summarizer.base import Summarizer
from wp_notify_bot.summarizer.vulnerability import render_vulnerability_message

logger = logging.getLogger(__name__)


class RoutingSummarizer(Summarizer):
    def __init__(
        self,
        passthrough: Summarizer,
        openrouter: Summarizer | None,
    ) -> None:
        self._passthrough = passthrough
        self._openrouter = openrouter
        self._missing_key_logged = False

    async def summarize(self, item: NormalizedItem) -> str:
        if item.kind == "vulnerability":
            if self._openrouter is None:
                self._warn_missing_key()
                return render_vulnerability_message(item, None)
            return await self._openrouter.summarize(item)
        if item.kind == "core_release":
            if self._openrouter is None:
                self._warn_missing_key()
            else:
                return await self._openrouter.summarize(item)
        return await self._passthrough.summarize(item)

    def _warn_missing_key(self) -> None:
        if self._missing_key_logged:
            return
        logger.warning("OPENROUTER_API_KEY is empty; alerts omit the summary")
        self._missing_key_logged = True
