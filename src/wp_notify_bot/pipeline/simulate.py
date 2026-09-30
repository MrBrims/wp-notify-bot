from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.pipeline.run import _is_newer_version
from wp_notify_bot.sources.base import Source
from wp_notify_bot.sources.wordpress_core import WordpressCoreSource
from wp_notify_bot.sources.wordfence import WordfenceSource

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimulationPreview:
    core: NormalizedItem | None
    vulnerability: NormalizedItem | None
    core_error: bool
    core_missing: bool
    vulnerability_disabled: bool
    vulnerability_error: bool
    vulnerability_empty: bool


def newest_core_item(items: Sequence[NormalizedItem]) -> NormalizedItem | None:
    newest: NormalizedItem | None = None
    for item in items:
        if item.kind != "core_release":
            continue
        if newest is None or _is_newer_version(item.uid, newest.uid):
            newest = item
    return newest


async def preview_alerts(sources: Sequence[Source]) -> SimulationPreview:
    core_source = next(
        (source for source in sources if isinstance(source, WordpressCoreSource)),
        None,
    )
    feed = next(
        (source for source in sources if isinstance(source, WordfenceSource)),
        None,
    )
    core, core_error, core_missing = await _preview_core(core_source)
    vulnerability, vulnerability_error, vulnerability_empty = await _preview_feed(feed)
    return SimulationPreview(
        core=core,
        vulnerability=vulnerability,
        core_error=core_error,
        core_missing=core_missing,
        vulnerability_disabled=feed is None,
        vulnerability_error=vulnerability_error,
        vulnerability_empty=vulnerability_empty,
    )


async def _preview_core(
    source: WordpressCoreSource | None,
) -> tuple[NormalizedItem | None, bool, bool]:
    if source is None:
        return None, True, False
    try:
        item = newest_core_item(await source.fetch())
    except Exception:
        logger.exception("Simulated core release lookup failed")
        return None, True, False
    return item, False, item is None


async def _preview_feed(
    source: WordfenceSource | None,
) -> tuple[NormalizedItem | None, bool, bool]:
    if source is None:
        return None, False, False
    try:
        items = await source.preview()
    except Exception:
        logger.exception("Simulated vulnerability lookup failed")
        return None, True, False
    if not items:
        return None, False, True
    return items[0], False, False
