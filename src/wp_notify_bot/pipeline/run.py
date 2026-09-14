from __future__ import annotations

import logging
from datetime import datetime, timezone

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.notify.telegram import TelegramNotifier
from wp_notify_bot.sources.base import Source
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.base import Summarizer

logger = logging.getLogger(__name__)


def _version_tuple(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in version.split("."):
        digits = ""
        for char in chunk:
            if char.isdigit():
                digits += char
            else:
                break
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_newer_version(candidate: str, current: str) -> bool:
    return _version_tuple(candidate) > _version_tuple(current)


async def _remember_newest_core_version(
    store: Store, items: list[NormalizedItem]
) -> None:
    newest: str | None = None
    for item in items:
        if item.kind != "core_release":
            continue
        if newest is None or _is_newer_version(item.uid, newest):
            newest = item.uid
    if newest is None:
        return
    current = await store.get_meta("last_core_version")
    if current is None or _is_newer_version(newest, current):
        await store.set_meta("last_core_version", newest)


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
        await _remember_newest_core_version(store, items)
        for item in items:
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
