from __future__ import annotations

from typing import Any

import httpx

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.sources.base import Source

SOURCE_ID = "wordpress_core"
RELEASES_URL = "https://wordpress.org/news/category/releases/"
DOWNLOAD_FALLBACK = "https://wordpress.org/download/"


def parse_version_check(payload: dict[str, Any]) -> list[NormalizedItem]:
    items: list[NormalizedItem] = []
    seen_versions: set[str] = set()
    for offer in payload.get("offers") or []:
        if not isinstance(offer, dict):
            continue
        if offer.get("response") != "upgrade":
            continue
        version = str(offer.get("version") or "").strip()
        if not version or version in seen_versions:
            continue
        seen_versions.add(version)
        download = str(offer.get("download") or "").strip()
        packages = offer.get("packages") if isinstance(offer.get("packages"), dict) else {}
        items.append(
            NormalizedItem(
                source_id=SOURCE_ID,
                uid=version,
                title=f"WordPress {version}",
                url=download or DOWNLOAD_FALLBACK,
                kind="core_release",
                payload={
                    "php_version": offer.get("php_version"),
                    "mysql_version": offer.get("mysql_version"),
                    "download": download,
                    "packages": packages,
                    "releases_url": RELEASES_URL,
                },
            )
        )
    return items


class WordpressCoreSource(Source):
    source_id = SOURCE_ID

    def __init__(
        self,
        api_url: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_url = api_url
        self._client = client

    async def fetch(self) -> list[NormalizedItem]:
        if self._client is not None:
            response = await self._client.get(self._api_url)
            response.raise_for_status()
            return parse_version_check(response.json())
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self._api_url)
            response.raise_for_status()
            return parse_version_check(response.json())
