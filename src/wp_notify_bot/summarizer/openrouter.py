from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.sources.release_notes import (
    ReleaseAnnouncement,
    fetch_release_announcement,
)
from wp_notify_bot.summarizer.base import Summarizer
from wp_notify_bot.summarizer.passthrough import core_release_message
from wp_notify_bot.summarizer.vulnerability import render_vulnerability_message

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
SYSTEM_PROMPT = (
    "Ты пишешь короткие уведомления об уязвимостях WordPress на русском языке. "
    "Ответь JSON-объектом с единственным полем summary: ровно два предложения. "
    "Первое — что произошло, второе — чем это грозит. "
    "Не добавляй CVE, номера версий, оценки CVSS и шаги эксплуатации. "
    "Используй только факты из переданного описания. "
    "Если описания недостаточно, не выдумывай детали."
)
RELEASE_SYSTEM_PROMPT = (
    "Ты пишешь короткие уведомления о релизах ядра WordPress на русском языке. "
    "Ответь JSON-объектом с единственным полем summary: ровно два предложения. "
    "Первое — что изменилось, второе — что это значит для сайта. "
    "Не добавляй CVE, списки файлов и номера версий, которых нет в анонсе. "
    "Используй только факты из переданного анонса. "
    "Если анонса недостаточно, не выдумывай детали."
)
AnnouncementLoader = Callable[[str], Awaitable[ReleaseAnnouncement | None]]



class OpenRouterSummarizer(Summarizer):
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient | None = None,
        announcement_loader: AnnouncementLoader | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = client
        self._announcement_loader = announcement_loader

    async def summarize(self, item: NormalizedItem) -> str:
        if item.kind == "core_release":
            return await self._summarize_release(item)
        summary = await self._try_summary(
            item.uid, SYSTEM_PROMPT, _user_prompt(item), "vulnerability_summary"
        )
        return render_vulnerability_message(item, summary)

    async def _summarize_release(self, item: NormalizedItem) -> str:
        announcement = await self._load_announcement(item.uid)
        if announcement is None or not announcement.text.strip():
            return core_release_message(item)
        summary = await self._try_summary(
            item.uid,
            RELEASE_SYSTEM_PROMPT,
            _release_user_prompt(item, announcement.text),
            "release_summary",
        )
        return core_release_message(item, summary, announcement.url)

    async def _load_announcement(self, version: str) -> ReleaseAnnouncement | None:
        loader = self._announcement_loader or fetch_release_announcement
        try:
            return await loader(version)
        except Exception:
            logger.exception("Release announcement failed for %s", version)
            return None

    async def _try_summary(
        self,
        uid: str,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> str | None:
        try:
            payload = await self._complete(system_prompt, user_prompt, schema_name)
            return _parse_summary(_message_text(payload))
        except Exception:
            logger.exception("OpenRouter summary failed for %s", uid)
            return None

    async def _complete(
        self,
        system_prompt: str,
        user_prompt: str,
        schema_name: str,
    ) -> dict[str, Any]:
        body = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": 200,
            "reasoning": {"effort": "none"},
            "response_format": _response_format(schema_name),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._client is not None:
            response = await self._client.post(
                OPENROUTER_URL, headers=headers, json=body
            )
            response.raise_for_status()
            data = response.json()
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    OPENROUTER_URL, headers=headers, json=body
                )
                response.raise_for_status()
                data = response.json()
        if not isinstance(data, dict):
            raise ValueError("OpenRouter response is not an object")
        return data


def _response_format(name: str) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
        },
    }


def _release_user_prompt(item: NormalizedItem, announcement: str) -> str:
    return (
        f"Версия: {item.uid}\n"
        f"Заголовок: {item.title}\n\n"
        f"Анонс:\n{announcement}"
    )


def _user_prompt(item: NormalizedItem) -> str:
    name = str(item.payload.get("software_name") or item.title)
    software_type = str(item.payload.get("software_type") or "")
    return (
        f"Продукт: {name}\n"
        f"Тип: {software_type}\n"
        f"Заголовок: {item.title}\n\n"
        f"Описание:\n{item.raw_text}"
    )


def _message_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenRouter response has no choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise ValueError("OpenRouter choice is not an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise ValueError("OpenRouter message is not an object")
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts)
    raise ValueError("OpenRouter message content is empty")


def _parse_summary(content: str) -> str | None:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    if not isinstance(summary, str):
        return None
    cleaned = summary.strip()
    return cleaned or None
