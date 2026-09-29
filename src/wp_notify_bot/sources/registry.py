from __future__ import annotations

from pathlib import Path

from wp_notify_bot.config import Settings
from wp_notify_bot.sources.base import Source
from wp_notify_bot.sources.wordpress_core import WordpressCoreSource
from wp_notify_bot.sources.wordfence import WordfenceSource
from wp_notify_bot.storage.db import Store


def default_sources(settings: Settings, store: Store) -> list[Source]:
    sources: list[Source] = [WordpressCoreSource(settings.wordpress_api_url)]
    api_key = settings.wordfence_api_key.strip()
    if not api_key:
        return sources
    cache_path = Path(settings.database_path).parent / "wordfence-production.json"
    sources.append(
        WordfenceSource(
            api_key=api_key,
            api_url=settings.wordfence_api_url,
            store=store,
            cache_path=cache_path,
            cache_seconds=settings.vuln_feed_cache_seconds,
            min_cvss=settings.vuln_min_cvss,
        )
    )
    return sources
