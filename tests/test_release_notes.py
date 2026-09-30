from __future__ import annotations

import httpx

from wp_notify_bot.sources.release_notes import (
    NEWS_POSTS_URL,
    fetch_release_announcement,
    select_announcement,
)


def _post(slug: str, title: str, html: str, link: str) -> dict[str, object]:
    return {
        "slug": slug,
        "link": link,
        "title": {"rendered": title},
        "content": {"rendered": html},
    }


_POSTS = [
    _post(
        "wordpress-6-8-release-candidate-2",
        "WordPress 6.8 Release Candidate 2",
        "<p>Candidate notes.</p>",
        "https://wordpress.org/news/rc/",
    ),
    _post(
        "wordpress-6-8",
        "WordPress 6.8 &#8220;Cecil&#8221;",
        "<p>Major <b>release</b>.</p>",
        "https://wordpress.org/news/6-8/",
    ),
    _post(
        "wordpress-6-8-3-release",
        "WordPress 6.8.3 Release",
        (
            "<p>Two <b>fixes</b>.</p>"
            "<h2>Thank you to these WordPress contributors</h2><p>Ada</p>"
            "<h2>How to contribute</h2><p>Join Trac.</p>"
        ),
        "https://wordpress.org/news/2025/09/wordpress-6-8-3-release/",
    ),
]


def test_selects_exact_version_and_strips_credits() -> None:
    found = select_announcement("6.8.3", _POSTS)
    assert found is not None
    assert found.url == "https://wordpress.org/news/2025/09/wordpress-6-8-3-release/"
    assert found.text == "Two fixes."
    assert "Ada" not in found.text
    assert "<b>" not in found.text


def test_shorter_version_skips_prerelease_and_patch() -> None:
    found = select_announcement("6.8", _POSTS)
    assert found is not None
    assert found.url == "https://wordpress.org/news/6-8/"
    assert found.text == "Major release."


def test_rejects_release_candidate() -> None:
    posts = [_POSTS[0]]
    assert select_announcement("6.8", posts) is None


def test_ignores_non_objects() -> None:
    assert select_announcement("6.8.3", ["nope", None]) is None


async def test_fetch_queries_news_by_version() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).split("?", 1)[0] == NEWS_POSTS_URL
        assert request.url.params["search"] == "WordPress 6.8.3"
        return httpx.Response(200, json=[_POSTS[2]])

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    found = await fetch_release_announcement("6.8.3", client)
    await client.aclose()
    assert found is not None
    assert found.text == "Two fixes."


async def test_fetch_network_error_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "down"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    found = await fetch_release_announcement("6.8.3", client)
    await client.aclose()
    assert found is None
