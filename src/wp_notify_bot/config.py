from __future__ import annotations

import os
from dataclasses import dataclass

from wp_notify_bot.sources.wordfence import PRODUCTION_FEED_URL

DEFAULT_OPENROUTER_MODEL = "openai/gpt-6-luna"
DEFAULT_VULN_MIN_CVSS = 7.0
DEFAULT_VULN_FEED_CACHE_SECONDS = 21600


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    allowed_user_ids: frozenset[int]
    admin_user_ids: frozenset[int]
    poll_interval_seconds: int
    database_path: str
    wordpress_api_url: str
    openrouter_api_key: str = ""
    openrouter_model: str = DEFAULT_OPENROUTER_MODEL
    wordfence_api_key: str = ""
    wordfence_api_url: str = PRODUCTION_FEED_URL
    vuln_min_cvss: float = DEFAULT_VULN_MIN_CVSS
    vuln_feed_cache_seconds: int = DEFAULT_VULN_FEED_CACHE_SECONDS


def _parse_float(raw: str, default: float) -> float:
    text = raw.strip()
    if not text:
        return default
    return float(text)


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
        admin_user_ids=_parse_user_ids(
            os.environ.get("TELEGRAM_ADMIN_USER_IDS", "")
        ),
        poll_interval_seconds=max(60, int(interval_raw)),
        database_path=os.environ.get("DATABASE_PATH", "/app/data/bot.db").strip()
        or "/app/data/bot.db",
        wordpress_api_url=os.environ.get(
            "WORDPRESS_API_URL",
            "https://api.wordpress.org/core/version-check/1.7/",
        ).strip()
        or "https://api.wordpress.org/core/version-check/1.7/",
        openrouter_api_key=os.environ.get("OPENROUTER_API_KEY", "").strip(),
        openrouter_model=os.environ.get(
            "OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL
        ).strip()
        or DEFAULT_OPENROUTER_MODEL,
        wordfence_api_key=os.environ.get("WORDFENCE_API_KEY", "").strip(),
        wordfence_api_url=os.environ.get(
            "WORDFENCE_API_URL", PRODUCTION_FEED_URL
        ).strip()
        or PRODUCTION_FEED_URL,
        vuln_min_cvss=_parse_float(
            os.environ.get("VULN_MIN_CVSS", ""), DEFAULT_VULN_MIN_CVSS
        ),
        vuln_feed_cache_seconds=max(
            0,
            int(
                os.environ.get(
                    "VULN_FEED_CACHE_SECONDS",
                    str(DEFAULT_VULN_FEED_CACHE_SECONDS),
                ).strip()
                or str(DEFAULT_VULN_FEED_CACHE_SECONDS)
            ),
        ),
    )


def is_user_allowed(settings: Settings, user_id: int | None) -> bool:
    if not settings.allowed_user_ids:
        return True
    if user_id is None:
        return False
    return user_id in settings.allowed_user_ids


def is_user_admin(settings: Settings, user_id: int | None) -> bool:
    if user_id is None:
        return False
    return user_id in settings.admin_user_ids
