from __future__ import annotations

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.summarizer.base import Summarizer

# Wire this implementation when OPENROUTER_API_KEY is set; keep PassthroughSummarizer
# for core releases until vulnerability feeds need LLM summaries.


class OpenRouterSummarizer(Summarizer):
    def __init__(self, api_key: str, model: str) -> None:
        self._api_key = api_key
        self._model = model

    async def summarize(self, item: NormalizedItem) -> str:
        raise NotImplementedError("OpenRouter summarizer is not wired yet")
