from __future__ import annotations

from wp_notify_bot.config import Settings
from wp_notify_bot.sources.base import Source
from wp_notify_bot.sources.wordpress_core import WordpressCoreSource

# Future plugin-vulnerability sources (WPScan, Patchstack, Wordfence, …)
# register here next to WordpressCoreSource without changing the pipeline.


def default_sources(settings: Settings) -> list[Source]:
    return [WordpressCoreSource(settings.wordpress_api_url)]
