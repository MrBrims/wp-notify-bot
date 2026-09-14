from __future__ import annotations

import logging
from datetime import datetime, timezone

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.notify.telegram import TelegramNotifier
from wp_notify_bot.sources.base import Source
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.base import Summarizer

logger = logging.getLogger(__name__)


async def run_pipeline(
    sources: list[Source],
    store: Store,
    summarizer: Summarizer,
    notifier: TelegramNotifier,
) -> list[NormalizedItem]:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    await store.set_meta("last_check_at", now)
    delivered: list[NormalizedItem] = []
    for source in sources:
        try:
            items = await source.fetch()
        except Exception:
            logger.exception("Source %s failed", getattr(source, "source_id", source))
            continue
        for item in items:
            if item.kind == "core_release":
                await store.set_meta("last_core_version", item.uid)
            if await store.has_seen(item.source_id, item.uid):
                continue
            try:
                text = await summarizer.summarize(item)
                await notifier.fanout(text)
                await store.mark_seen(item.source_id, item.uid)
                delivered.append(item)
            except Exception:
                logger.exception(
                    "Failed to process %s/%s", item.source_id, item.uid
                )
    return delivered
