from __future__ import annotations

from pathlib import Path

from wp_notify_bot.pipeline.simulate import next_test_version, simulated_core_item
from wp_notify_bot.storage.db import Store


def test_next_test_version_bumps_last_segment() -> None:
    assert next_test_version("6.8.2") == "6.8.3"
    assert next_test_version("6.9") == "6.10"
    assert next_test_version(None) == "0.0.1"
    assert next_test_version("  ") == "0.0.1"


async def test_simulated_item_does_not_touch_store(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    await store.set_meta("last_core_version", "6.8.2")
    await store.set_meta("last_check_at", "2026-09-29T00:00:00+00:00")
    version = next_test_version(await store.get_meta("last_core_version"))
    item = simulated_core_item(version)
    assert item.uid == "6.8.3"
    assert item.kind == "core_release"
    assert item.source_id == "wordpress_core"
    assert "wordpress-6.8.3.zip" in str(item.payload["download"])
    assert await store.get_meta("last_core_version") == "6.8.2"
    assert await store.get_meta("last_check_at") == "2026-09-29T00:00:00+00:00"
    assert not await store.has_seen(item.source_id, item.uid)
