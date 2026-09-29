from __future__ import annotations

import json

import httpx

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.summarizer.openrouter import OPENROUTER_URL, OpenRouterSummarizer
from wp_notify_bot.summarizer.passthrough import PassthroughSummarizer
from wp_notify_bot.summarizer.routing import RoutingSummarizer


def _item() -> NormalizedItem:
    return NormalizedItem(
        source_id="wordfence",
        uid="abc",
        title="Contact Form 7 issue",
        url="https://www.wordfence.com/threat-intel/vulnerabilities/id/abc",
        kind="vulnerability",
        raw_text="An unauthenticated visitor can change the form recipient.",
        payload={
            "software_type": "plugin",
            "software_name": "Contact Form 7",
            "slug": "contact-form-7",
            "cvss_score": 9.8,
            "cvss_rating": "Critical",
            "cve": "CVE-2026-1234",
            "affected": "до 5.9.8 включительно",
            "fixed_in": "5.9.9",
        },
    )


def _client(handler: httpx.MockTransport) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=handler)


async def test_summary_keeps_feed_facts_and_model_prose() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"summary": "Первое предложение. Второе <b>."},
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
        )

    summarizer = OpenRouterSummarizer(
        "router-key",
        "openai/gpt-6-luna",
        client=_client(httpx.MockTransport(handler)),
    )
    text = await summarizer.summarize(_item())
    body = captured["body"]
    assert captured["url"] == OPENROUTER_URL
    assert isinstance(body, dict)
    assert body["model"] == "openai/gpt-6-luna"
    assert body["temperature"] == 0
    assert body["max_tokens"] == 200
    assert body["reasoning"] == {"effort": "none"}
    assert "CVE-2026-1234" not in str(body["messages"])
    assert "Первое предложение." in text
    assert "Второе &lt;b&gt;." in text
    assert "CVSS: 9.8 (Critical)" in text
    assert "CVE-2026-1234" in text
    assert "Исправлено в: 5.9.9" in text
    assert "до 5.9.8 включительно" in text
    assert "<b>Contact Form 7</b>" in text
    assert "Уязвимость · плагин" in text


async def test_openrouter_error_still_sends_facts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    summarizer = OpenRouterSummarizer(
        "router-key",
        "openai/gpt-6-luna",
        client=_client(httpx.MockTransport(handler)),
    )
    text = await summarizer.summarize(_item())
    assert "Первое предложение" not in text
    assert "CVSS: 9.8 (Critical)" in text
    assert "CVE-2026-1234" in text
    assert 'href="https://www.wordfence.com/threat-intel/vulnerabilities/id/abc"' in text


async def test_router_keeps_core_release_on_template() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(request.url)

    router = RoutingSummarizer(
        PassthroughSummarizer(),
        OpenRouterSummarizer(
            "router-key",
            "openai/gpt-6-luna",
            client=_client(httpx.MockTransport(handler)),
        ),
    )
    text = await router.summarize(
        NormalizedItem(
            source_id="wordpress_core",
            uid="6.8.3",
            title="WordPress 6.8.3",
            url="https://example.test/wordpress-6.8.3.zip",
            kind="core_release",
            payload={
                "php_version": "7.2.24",
                "mysql_version": "5.5.5",
                "download": "https://example.test/wordpress-6.8.3.zip",
            },
        )
    )
    assert "Вышел новый релиз ядра WordPress." in text
    assert "WordPress 6.8.3" in text


async def test_router_without_key_omits_summary() -> None:
    router = RoutingSummarizer(PassthroughSummarizer(), None)
    text = await router.summarize(_item())
    assert "CVSS: 9.8 (Critical)" in text
    assert "Первое предложение" not in text
