from __future__ import annotations

from pathlib import Path

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.notify.telegram import TelegramNotifier
from wp_notify_bot.pipeline.run import run_pipeline
from wp_notify_bot.sources.base import Source
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.passthrough import PassthroughSummarizer


class FakeSource(Source):
    source_id = "wordpress_core"

    def __init__(self, items: list[NormalizedItem]) -> None:
        self._items = items

    async def fetch(self) -> list[NormalizedItem]:
        return list(self._items)


class RecordingNotifier(TelegramNotifier):
    def __init__(self, store: Store) -> None:
        self.store = store
        self.sent: list[str] = []

    async def fanout(self, text: str) -> None:
        self.sent.append(text)


def _item(uid: str) -> NormalizedItem:
    return NormalizedItem(
        source_id="wordpress_core",
        uid=uid,
        title=f"WordPress {uid}",
        url=f"https://example.test/{uid}.zip",
        kind="core_release",
        payload={
            "php_version": "7.2.24",
            "mysql_version": "5.5.5",
            "download": f"https://example.test/{uid}.zip",
            "releases_url": "https://wordpress.org/news/category/releases/",
        },
    )


async def test_seen_items_are_not_delivered_twice(tmp_path: Path) -> None:
    db_path = str(tmp_path / "bot.db")
    store = Store(db_path)
    await store.init()
    item = _item("6.8.2")
    notifier = RecordingNotifier(store)
    first = await run_pipeline(
        [FakeSource([item])],
        store,
        PassthroughSummarizer(),
        notifier,
    )
    second = await run_pipeline(
        [FakeSource([item])],
        store,
        PassthroughSummarizer(),
        notifier,
    )
    assert [entry.uid for entry in first] == ["6.8.2"]
    assert second == []
    assert len(notifier.sent) == 1
    assert await store.has_seen("wordpress_core", "6.8.2")
    assert await store.get_meta("last_core_version") == "6.8.2"


async def test_last_core_version_prefers_newest_not_list_order(
    tmp_path: Path,
) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    notifier = RecordingNotifier(store)
    await run_pipeline(
        [FakeSource([_item("6.9"), _item("6.8.2")])],
        store,
        PassthroughSummarizer(),
        notifier,
    )
    assert await store.get_meta("last_core_version") == "6.9"

    await run_pipeline(
        [FakeSource([_item("6.8.3"), _item("6.10")])],
        store,
        PassthroughSummarizer(),
        notifier,
    )
    assert await store.get_meta("last_core_version") == "6.10"


async def test_last_core_version_does_not_downgrade(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    await store.set_meta("last_core_version", "6.9")
    await run_pipeline(
        [FakeSource([_item("6.8.2")])],
        store,
        PassthroughSummarizer(),
        RecordingNotifier(store),
    )
    assert await store.get_meta("last_core_version") == "6.9"


async def test_subscribe_and_unsubscribe(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    await store.subscribe(100, 1)
    await store.subscribe(200, 2)
    assert set(await store.active_chat_ids()) == {100, 200}
    await store.unsubscribe(100)
    assert await store.active_chat_ids() == [200]
    await store.subscribe(100, 1)
    assert set(await store.active_chat_ids()) == {100, 200}
