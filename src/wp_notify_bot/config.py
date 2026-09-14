from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    poll_interval_seconds: int
    database_path: str
    wordpress_api_url: str


def _parse_user_ids(raw: str) -> frozenset[int]:
    ids: list[int] = []
    for chunk in raw.split(","):
        value = chunk.strip()
        if not value:
            continue
        ids.append(int(value))
    return frozenset(ids)


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    interval_raw = os.environ.get("POLL_INTERVAL_SECONDS", "3600").strip() or "3600"
    return Settings(
        telegram_bot_token=token,
        allowed_user_ids=_parse_user_ids(
            os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
        ),
        poll_interval_seconds=max(60, int(interval_raw)),
        database_path=os.environ.get("DATABASE_PATH", "/app/data/bot.db").strip()
        or "/app/data/bot.db",
        wordpress_api_url=os.environ.get(
            "WORDPRESS_API_URL",
            "https://api.wordpress.org/core/version-check/1.7/",
        ).strip()
        or "https://api.wordpress.org/core/version-check/1.7/",
    )


def is_user_allowed(settings: Settings, user_id: int | None) -> bool:
    if not settings.allowed_user_ids:
        return True
    if user_id is None:
        return False
    return user_id in settings.allowed_user_ids
