from __future__ import annotations

from html import escape

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.summarizer.base import Summarizer


class PassthroughSummarizer(Summarizer):
    async def summarize(self, item: NormalizedItem) -> str:
        if item.kind == "core_release":
            return _core_release_message(item)
        title = escape(item.title)
        url = escape(item.url, quote=True)
        return f"<b>{title}</b>\n\n{url}"


def _core_release_message(item: NormalizedItem) -> str:
    payload = item.payload
    php = escape(str(payload.get("php_version") or "—"))
    mysql = escape(str(payload.get("mysql_version") or "—"))
    download = escape(str(payload.get("download") or item.url), quote=True)
    releases = escape(
        str(payload.get("releases_url") or "https://wordpress.org/news/category/releases/"),
        quote=True,
    )
    version = escape(item.uid)
    return (
        f"<b>WordPress {version}</b>\n\n"
        "Вышел новый релиз ядра WordPress.\n\n"
        f"PHP: {php}\n"
        f"MySQL: {mysql}\n\n"
        f'<a href="{download}">Скачать</a>\n'
        f'<a href="{releases}">Анонсы релизов</a>'
    )
