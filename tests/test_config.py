from __future__ import annotations

from wp_notify_bot.config import Settings, is_user_allowed


def test_empty_allowlist_permits_everyone() -> None:
    settings = Settings(
        telegram_bot_token="x",
        allowed_user_ids=frozenset(),
        poll_interval_seconds=3600,
        database_path="bot.db",
        wordpress_api_url="https://example.test/",
    )
    assert is_user_allowed(settings, 1)
    assert is_user_allowed(settings, None)


def test_allowlist_filters_users() -> None:
    settings = Settings(
        telegram_bot_token="x",
        allowed_user_ids=frozenset({42}),
        poll_interval_seconds=3600,
        database_path="bot.db",
        wordpress_api_url="https://example.test/",
    )
    assert is_user_allowed(settings, 42)
    assert not is_user_allowed(settings, 1)
    assert not is_user_allowed(settings, None)
