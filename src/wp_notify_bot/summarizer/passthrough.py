from __future__ import annotations

from html import escape

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.summarizer.base import Summarizer


class PassthroughSummarizer(Summarizer):
    async def summarize(self, item: NormalizedItem) -> str:
        if item.kind == "core_release":
            return core_release_message(item)
        title = escape(item.title)
        url = escape(item.url, quote=True)
        return f"<b>{title}</b>\n\n{url}"


def core_release_message(
    item: NormalizedItem,
    summary: str | None = None,
    announcement_url: str | None = None,
) -> str:
    payload = item.payload
    php = escape(str(payload.get("php_version") or "—"))
    mysql = escape(str(payload.get("mysql_version") or "—"))
    download = escape(str(payload.get("download") or item.url), quote=True)
    releases = escape(
        str(payload.get("releases_url") or "https://wordpress.org/news/category/releases/"),
        quote=True,
    )
    version = escape(item.uid)
    lines = [
        f"🆕 <b>WordPress {version}</b>",
        "",
        "Вышел новый релиз ядра WordPress.",
        "",
    ]
    prose = (summary or "").strip()
    if prose:
        lines.append(escape(prose))
        lines.append("")
    lines.append(f"🐘 PHP: {php}")
    lines.append(f"🐬 MySQL: {mysql}")
    lines.append("")
    lines.append(f'⬇️ <a href="{download}">Скачать</a>')
    announcement = (announcement_url or "").strip()
    if announcement:
        href = escape(announcement, quote=True)
        lines.append(f'📰 <a href="{href}">Анонс</a>')
    lines.append(f'📋 <a href="{releases}">Анонсы релизов</a>')
    return "\n".join(lines)
