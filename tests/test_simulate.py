from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from wp_notify_bot.bot.handlers import DEPS_KEY, AppDeps, cmd_simulate
from wp_notify_bot.config import Settings
from wp_notify_bot.pipeline.simulate import next_test_version, simulated_core_item
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.passthrough import PassthroughSummarizer


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


class _ReplyMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _RecordingBot:
    def __init__(self) -> None:
        self.sent: list[int] = []

    async def send_message(self, chat_id: int, text: str, **kwargs: object) -> None:
        self.sent.append(chat_id)

    async def set_my_commands(self, commands: object, scope: object = None) -> None:
        return None


def _settings(allowed: set[int], admin: set[int], database_path: str) -> Settings:
    return Settings(
        telegram_bot_token="x",
        allowed_user_ids=frozenset(allowed),
        admin_user_ids=frozenset(admin),
        poll_interval_seconds=3600,
        database_path=database_path,
        wordpress_api_url="https://example.test/",
    )


async def _run_simulate(
    tmp_path: Path, user_id: int, allowed: set[int], admin: set[int]
) -> tuple[_ReplyMessage, _RecordingBot]:
    database_path = str(tmp_path / "bot.db")
    store = Store(database_path)
    await store.init()
    message = _ReplyMessage()
    bot = _RecordingBot()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=user_id),
        effective_message=message,
    )
    deps = AppDeps(
        settings=_settings(allowed, admin, database_path),
        store=store,
        sources=[],
        summarizer=PassthroughSummarizer(),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={DEPS_KEY: deps}),
        bot=bot,
    )
    await cmd_simulate(update, context)
    return message, bot


async def test_simulate_denies_admin_outside_allowlist(tmp_path: Path) -> None:
    message, bot = await _run_simulate(tmp_path, user_id=7, allowed={42}, admin={7})
    assert message.replies == ["Нет доступа."]
    assert bot.sent == []


async def test_simulate_allows_admin_on_allowlist(tmp_path: Path) -> None:
    message, bot = await _run_simulate(tmp_path, user_id=7, allowed={7}, admin={7})
    assert bot.sent == [7]
    assert message.replies == [
        "Тестовое уведомление отправлено только вам. Версия в базе не изменилась."
    ]
