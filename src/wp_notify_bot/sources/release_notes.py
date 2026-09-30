from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from html import unescape
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NEWS_POSTS_URL = "https://wordpress.org/news/wp-json/wp/v2/posts"
TEXT_LIMIT = 8000
_PRERELEASE = re.compile(r"\b(?:beta|rc|release candidate)\b", re.IGNORECASE)
_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_CUT_MARKERS = (
    "thank you to these wordpress contributors",
    "how to contribute",
)


@dataclass(frozen=True)
class ReleaseAnnouncement:
    url: str
    text: str


def select_announcement(
    version: str, posts: Sequence[object]
) -> ReleaseAnnouncement | None:
    needle = version.strip()
    if not needle:
        return None
    preferred = _version_slug(needle)
    fallback: ReleaseAnnouncement | None = None
    for post in posts:
        if not isinstance(post, dict):
            continue
        title = _rendered(post.get("title"))
        if not _title_matches(needle, title):
            continue
        text = plain_text(_rendered(post.get("content")))
        if not text:
            continue
        announcement = ReleaseAnnouncement(
            url=str(post.get("link") or "").strip(),
            text=text,
        )
        slug = str(post.get("slug") or "")
        if slug == preferred or slug == f"{preferred}-release":
            return announcement
        if fallback is None:
            fallback = announcement
    return fallback


def plain_text(html: str) -> str:
    text = unescape(html)
    text = _TAG.sub(" ", text)
    text = _WHITESPACE.sub(" ", text).strip()
    lowered = text.lower()
    cut_at = len(text)
    for marker in _CUT_MARKERS:
        index = lowered.find(marker)
        if index != -1:
            cut_at = min(cut_at, index)
    text = text[:cut_at].strip()
    if len(text) > TEXT_LIMIT:
        text = text[:TEXT_LIMIT].rstrip()
    return text


async def fetch_release_announcement(
    version: str,
    client: httpx.AsyncClient | None = None,
) -> ReleaseAnnouncement | None:
    params = {
        "search": f"WordPress {version}",
        "per_page": "5",
        "_fields": "slug,link,title,content",
    }
    try:
        payload = await _get_posts(params, client)
    except Exception:
        logger.exception(
            "WordPress release announcement lookup failed for %s", version
        )
        return None
    if not isinstance(payload, list):
        logger.warning(
            "WordPress release announcement for %s is not a list", version
        )
        return None
    return select_announcement(version, payload)


def _title_matches(version: str, title: str) -> bool:
    if not title or _PRERELEASE.search(title):
        return False
    pattern = rf"(?<![\d.]){re.escape(version)}(?![\d.])"
    return re.search(pattern, title) is not None


def _version_slug(version: str) -> str:
    return "wordpress-" + version.replace(".", "-")


def _rendered(value: object) -> str:
    if isinstance(value, dict):
        rendered = value.get("rendered")
        if isinstance(rendered, str):
            return unescape(rendered)
    if isinstance(value, str):
        return unescape(value)
    return ""


async def _get_posts(
    params: dict[str, str],
    client: httpx.AsyncClient | None,
) -> Any:
    if client is not None:
        response = await client.get(NEWS_POSTS_URL, params=params)
        response.raise_for_status()
        return response.json()
    async with httpx.AsyncClient(timeout=30.0) as owned:
        response = await owned.get(NEWS_POSTS_URL, params=params)
        response.raise_for_status()
        return response.json()
