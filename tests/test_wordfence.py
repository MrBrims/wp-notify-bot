from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from wp_notify_bot.config import Settings
from wp_notify_bot.sources.registry import default_sources
from wp_notify_bot.sources.wordfence import (
    PRODUCTION_FEED_URL,
    WordfenceSource,
    serious_items,
)
from wp_notify_bot.storage.db import Store


def _software(
    software_type: str = "plugin",
    name: str = "Contact Form 7",
    slug: str = "contact-form-7",
) -> dict[str, Any]:
    return {
        "type": software_type,
        "name": name,
        "slug": slug,
        "affected_versions": {
            "* - 5.9.8": {
                "from_version": "*",
                "from_inclusive": True,
                "to_version": "5.9.8",
                "to_inclusive": True,
            }
        },
        "patched": True,
        "patched_versions": ["5.9.9"],
        "remediation": "Update to version 5.9.9 or newer.",
    }


def _record(
    record_id: str,
    *,
    score: float | None = 9.8,
    rating: str | None = "Critical",
    software_type: str = "plugin",
    informational: bool = False,
    name: str = "Contact Form 7",
    references: list[str] | None = None,
) -> dict[str, Any]:
    cvss: dict[str, Any] | None
    if score is None and rating is None:
        cvss = None
    else:
        cvss = {"vector": "CVSS:3.1/AV:N", "score": score, "rating": rating}
    return {
        "id": record_id,
        "title": f"{name} issue",
        "description": "An unauthenticated visitor can change the form recipient.",
        "informational": informational,
        "references": references
        if references is not None
        else [f"https://www.wordfence.com/threat-intel/vulnerabilities/id/{record_id}"],
        "published": "2026-09-01 00:00:00",
        "cve": "CVE-2026-1234",
        "cvss": cvss,
        "software": [_software(software_type, name=name)],
    }


def test_serious_items_keep_core_and_plugin_at_threshold() -> None:
    payload = {
        "low": _record("low", score=6.9, rating="Medium"),
        "edge": _record("edge", score=7.0, rating="High", name="Edge Plugin"),
        "high": _record("high", score=9.8, rating="Critical"),
        "theme": _record("theme", software_type="theme", name="Astra"),
        "info": _record("info", informational=True),
        "core": _record("core", score=7.5, rating="High", software_type="core", name="WordPress"),
        "unscored": _record("unscored", score=None, rating="Critical", name="No Score"),
        "unknown": _record("unknown", score=None, rating=None, name="Unknown"),
    }
    items = serious_items(payload, 7.0)
    assert [item.uid for item in items] == ["high", "unscored", "core", "edge"]
    by_id = {item.uid: item for item in items}
    assert by_id["high"].payload["affected"] == "до 5.9.8 включительно"
    assert by_id["high"].payload["fixed_in"] == "5.9.9"
    assert by_id["high"].payload["cve"] == "CVE-2026-1234"
    assert by_id["core"].payload["software_type"] == "core"
    assert by_id["high"].published_at == datetime(
        2026, 9, 1, tzinfo=timezone.utc
    )
    assert by_id["unscored"].payload["cvss_score"] is None
    assert by_id["unscored"].payload["cvss_rating"] == "Critical"


def test_missing_wordfence_link_uses_id_url() -> None:
    payload = {
        "plain": _record("plain", references=["https://example.test/advisory"]),
    }
    item = serious_items(payload, 7.0)[0]
    assert (
        item.url
        == "https://www.wordfence.com/threat-intel/vulnerabilities/id/plain"
    )


async def test_first_fetch_marks_archive_without_alerts(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    payload = {
        "low": _record("low", score=4.0, rating="Medium"),
        "high": _record("high"),
        "theme": _record("theme", software_type="theme", name="Astra"),
    }
    holder = {"payload": payload}

    async def load() -> dict[str, Any]:
        return holder["payload"]

    source = WordfenceSource(
        api_key="secret-key",
        api_url=PRODUCTION_FEED_URL,
        store=store,
        cache_path=tmp_path / "wordfence-production.json",
        cache_seconds=21600,
        min_cvss=7.0,
        load_payload=load,
    )
    assert await source.fetch() == []
    assert await store.get_meta("wordfence_bootstrapped") == "1"
    assert await store.get_meta("wordfence_feed_at")
    assert await store.has_seen("wordfence", "low")
    assert await store.has_seen("wordfence", "high")
    assert await store.has_seen("wordfence", "theme")

    holder["payload"] = {
        **payload,
        "newer": _record("newer", score=8.1, rating="High", name="Newer"),
        "mild": _record("mild", score=5.0, rating="Medium", name="Mild"),
    }
    delivered = await source.fetch()
    assert [item.uid for item in delivered] == ["newer"]
    assert not await store.has_seen("wordfence", "mild")


async def test_fresh_cache_skips_download(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    await store.set_meta("wordfence_bootstrapped", "1")
    cache_path = tmp_path / "wordfence-production.json"
    cache_path.write_text(
        json.dumps({"cached": _record("cached", score=8.0, rating="High")}),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    source = WordfenceSource(
        api_key="secret-key",
        api_url=PRODUCTION_FEED_URL,
        store=store,
        cache_path=cache_path,
        cache_seconds=21600,
        min_cvss=7.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    delivered = await source.fetch()
    assert [item.uid for item in delivered] == ["cached"]


async def test_download_uses_bearer_token_and_writes_cache(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    await store.init()
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["Authorization"]
        body = {"remote": _record("remote")}
        return httpx.Response(200, json=body)

    cache_path = tmp_path / "wordfence-production.json"
    source = WordfenceSource(
        api_key="secret-key",
        api_url=PRODUCTION_FEED_URL,
        store=store,
        cache_path=cache_path,
        cache_seconds=21600,
        min_cvss=7.0,
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    assert await source.fetch() == []
    assert seen["authorization"] == "Bearer secret-key"
    assert "cli-" not in seen["authorization"]
    assert json.loads(cache_path.read_text(encoding="utf-8"))["remote"]["id"] == "remote"
    assert await store.has_seen("wordfence", "remote")


def test_registry_adds_wordfence_only_with_key(tmp_path: Path) -> None:
    store = Store(str(tmp_path / "bot.db"))
    base = Settings(
        telegram_bot_token="x",
        allowed_user_ids=frozenset(),
        admin_user_ids=frozenset(),
        poll_interval_seconds=3600,
        database_path=str(tmp_path / "bot.db"),
        wordpress_api_url="https://example.test/",
    )
    assert [source.source_id for source in default_sources(base, store)] == [
        "wordpress_core"
    ]
    with_key = Settings(
        telegram_bot_token="x",
        allowed_user_ids=frozenset(),
        admin_user_ids=frozenset(),
        poll_interval_seconds=3600,
        database_path=str(tmp_path / "bot.db"),
        wordpress_api_url="https://example.test/",
        wordfence_api_key="secret-key",
    )
    assert [source.source_id for source in default_sources(with_key, store)] == [
        "wordpress_core",
        "wordfence",
    ]
