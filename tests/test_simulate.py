from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx

from wp_notify_bot.bot.handlers import DEPS_KEY, AppDeps, cmd_simulate
from wp_notify_bot.config import Settings
from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.pipeline.simulate import newest_core_item, preview_alerts
from wp_notify_bot.sources.base import Source
from wp_notify_bot.sources.wordpress_core import WordpressCoreSource
from wp_notify_bot.sources.wordfence import WordfenceSource
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.passthrough import PassthroughSummarizer


def _offer(version: str) -> dict[str, str]:
    return {
        "response": "upgrade",
        "version": version,
        "download": f"https://example.test/wordpress-{version}.zip",
        "php_version": "7.2.24",
        "mysql_version": "5.5.5",
    }


def _record(record_id: str, score: float) -> dict[str, Any]:
    return {
        "id": record_id,
        "title": f"{record_id} issue",
        "description": "An unauthenticated visitor can change the form recipient.",
        "informational": False,
        "references": [
            f"https://www.wordfence.com/threat-intel/vulnerabilities/id/{record_id}"
        ],
        "cve": "CVE-2026-1234",
        "cvss": {"score": score, "rating": "Critical"},
        "software": [
            {
                "type": "plugin",
                "name": "Contact Form 7",
                "slug": "contact-form-7",
                "affected_versions": {},
                "patched_versions": ["5.9.9"],
            }
        ],
    }


def _core_source(offers: list[dict[str, str]]) -> WordpressCoreSource:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"offers": offers})

    return WordpressCoreSource(
        "https://example.test/version-check",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )


def _feed(
    store: Store, payload: dict[str, Any], cache_path: Path
) -> WordfenceSource:
    async def load() -> dict[str, Any]:
        return payload

    return WordfenceSource(
        api_key="secret-key",
        api_url="https://example.test/feed",
        store=store,
        cache_path=cache_path,
        cache_seconds=0,
        min_cvss=7.0,
        load_payload=load,
    )


async def test_preview_uses_newest_release_and_top_vulnerability(
    tmp_path: Path,
) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    await store.set_meta("last_core_version", "6.8.2")
    await store.set_meta("last_check_at", "2026-09-29T00:00:00+00:00")
    core = _core_source([_offer("6.7.2"), _offer("6.8.3")])
    feed = _feed(
        store,
        {
            "edge": _record("edge", 7.0),
            "top": _record("top", 9.8),
        },
        tmp_path / "wordfence-production.json",
    )
    preview = await preview_alerts([core, feed])
    assert core._client is not None
    await core._client.aclose()
    assert preview.core is not None
    assert preview.core.uid == "6.8.3"
    assert preview.core.kind == "core_release"
    assert preview.vulnerability is not None
    assert preview.vulnerability.uid == "top"
    assert preview.vulnerability.kind == "vulnerability"
    assert not preview.core_error
    assert not preview.vulnerability_disabled
    assert await store.get_meta("last_core_version") == "6.8.2"
    assert await store.get_meta("last_check_at") == "2026-09-29T00:00:00+00:00"
    assert await store.get_meta("wordfence_feed_at") is None
    assert await store.get_meta("wordfence_bootstrapped") is None
    assert not await store.has_seen("wordpress_core", "6.8.3")
    assert not await store.has_seen("wordfence", "top")


async def test_preview_without_wordfence_reports_disabled(tmp_path: Path) -> None:
    core = _core_source([_offer("6.8.3")])
    preview = await preview_alerts([core])
    assert core._client is not None
    await core._client.aclose()
    assert preview.core is not None
    assert preview.vulnerability is None
    assert preview.vulnerability_disabled


async def test_preview_reports_source_failures(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()

    def core_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    core = WordpressCoreSource(
        "https://example.test/version-check",
        client=httpx.AsyncClient(transport=httpx.MockTransport(core_handler)),
    )

    async def load() -> dict[str, Any]:
        raise RuntimeError("feed down")

    feed = WordfenceSource(
        api_key="secret-key",
        api_url="https://example.test/feed",
        store=store,
        cache_path=tmp_path / "wordfence-production.json",
        cache_seconds=0,
        min_cvss=7.0,
        load_payload=load,
    )
    preview = await preview_alerts([core, feed])
    assert core._client is not None
    await core._client.aclose()
    assert preview.core is None
    assert preview.core_error
    assert preview.vulnerability is None
    assert preview.vulnerability_error
    assert await store.get_meta("wordfence_bootstrapped") is None


class _ReplyMessage:
    def __init__(self) -> None:
        self.replies: list[str] = []

    async def reply_text(self, text: str) -> None:
        self.replies.append(text)


class _RecordingBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs: object) -> None:
        self.sent.append((chat_id, text))


def _settings(allowed: set[int], database_path: str) -> Settings:
    return Settings(
        telegram_bot_token="x",
        allowed_user_ids=frozenset(allowed),
        poll_interval_seconds=3600,
        database_path=database_path,
        wordpress_api_url="https://example.test/",
    )


async def _run_simulate(
    tmp_path: Path,
    user_id: int,
    allowed: set[int],
    sources: list[Source],
) -> tuple[_ReplyMessage, _RecordingBot, Store]:
    database_path = str(tmp_path / "bot.db")
    store = Store(database_path)
    await store.init()
    await store.set_meta("last_core_version", "6.8.2")
    message = _ReplyMessage()
    bot = _RecordingBot()
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        effective_chat=SimpleNamespace(id=user_id),
        effective_message=message,
    )
    deps = AppDeps(
        settings=_settings(allowed, database_path),
        store=store,
        sources=sources,
        summarizer=PassthroughSummarizer(),
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={DEPS_KEY: deps}),
        bot=bot,
    )
    await cmd_simulate(update, context)
    return message, bot, store


async def test_simulate_denies_user_outside_allowlist(tmp_path: Path) -> None:
    message, bot, store = await _run_simulate(
        tmp_path, user_id=7, allowed={42}, sources=[]
    )
    assert message.replies == ["Нет доступа."]
    assert bot.sent == []
    assert await store.get_meta("last_core_version") == "6.8.2"


async def test_simulate_sends_release_and_vulnerability_to_caller(
    tmp_path: Path,
) -> None:
    store_path = tmp_path / "bot.db"
    store = Store(str(store_path))
    await store.init()
    core = _core_source([_offer("6.8.3")])
    feed = _feed(store, {"top": _record("top", 9.8)}, tmp_path / "feed.json")
    message, bot, store = await _run_simulate(
        tmp_path, user_id=7, allowed={7}, sources=[core, feed]
    )
    assert core._client is not None
    await core._client.aclose()
    assert [chat_id for chat_id, _text in bot.sent] == [7, 7]
    release, vulnerability = (text for _chat_id, text in bot.sent)
    assert release.startswith(
        "Тест: имитация уведомления."
    )
    assert "WordPress 6.8.3" in release
    assert "PHP: 7.2.24" in release
    assert vulnerability.startswith(
        "Тест: имитация уведомления."
    )
    assert "top issue" in vulnerability
    assert message.replies[0] == "Собираю тестовые уведомления…"
    assert message.replies[1] == (
        "Тестовые уведомления отправлены только вам. База не изменилась."
    )
    assert await store.get_meta("last_core_version") == "6.8.2"
    assert not await store.has_seen("wordfence", "top")


async def test_simulate_without_wordfence_explains_the_gap(tmp_path: Path) -> None:
    core = _core_source([_offer("6.8.3")])
    message, bot, _store = await _run_simulate(
        tmp_path, user_id=7, allowed=set(), sources=[core]
    )
    assert core._client is not None
    await core._client.aclose()
    assert len(bot.sent) == 1
    assert "WordPress 6.8.3" in bot.sent[0][1]
    assert message.replies[1] == (
        "Тестовые уведомления отправлены только вам. База не изменилась.\n"
        "Опрос уязвимостей выключен."
    )


def test_newest_core_item_ignores_other_kinds() -> None:
    older = NormalizedItem(
        source_id="wordpress_core",
        uid="6.7.2",
        title="WordPress 6.7.2",
        url="https://example.test/old.zip",
        kind="core_release",
    )
    newer = NormalizedItem(
        source_id="wordpress_core",
        uid="6.8.3",
        title="WordPress 6.8.3",
        url="https://example.test/new.zip",
        kind="core_release",
    )
    other = NormalizedItem(
        source_id="wordfence",
        uid="9.9.9",
        title="not a release",
        url="https://example.test/vuln",
        kind="vulnerability",
    )
    assert newest_core_item([older, other, newer]) is newer
    assert newest_core_item([other]) is None
