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
        vulnerability: Summarizer | None,
    ) -> None:
        self._passthrough = passthrough
        self._vulnerability = vulnerability
        self._missing_key_logged = False

    async def summarize(self, item: NormalizedItem) -> str:
        if item.kind != "vulnerability":
            return await self._passthrough.summarize(item)
        if self._vulnerability is None:
            if not self._missing_key_logged:
                logger.warning(
                    "OPENROUTER_API_KEY is empty; vulnerability alerts omit the summary"
                )
                self._missing_key_logged = True
            return render_vulnerability_message(item, None)
        return await self._vulnerability.summarize(item)
