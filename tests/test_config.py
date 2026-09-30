from __future__ import annotations

from pytest import MonkeyPatch

from wp_notify_bot.config import Settings, is_user_allowed, load_settings


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


def test_vulnerability_settings_defaults(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    for key in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "WORDFENCE_API_KEY",
        "WORDFENCE_API_URL",
        "VULN_MIN_CVSS",
        "VULN_FEED_CACHE_SECONDS",
        "TELEGRAM_ALLOWED_USER_IDS",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = load_settings()
    assert settings.openrouter_api_key == ""
    assert settings.openrouter_model == "openai/gpt-6-luna"
    assert settings.wordfence_api_key == ""
    assert settings.wordfence_api_url.endswith("/vulnerabilities/production")
    assert settings.vuln_min_cvss == 7.0
    assert settings.vuln_feed_cache_seconds == 21600


def test_vulnerability_settings_from_env(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("OPENROUTER_API_KEY", " router ")
    monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-6-luna")
    monkeypatch.setenv("WORDFENCE_API_KEY", " wf ")
    monkeypatch.setenv("VULN_MIN_CVSS", "8.5")
    monkeypatch.setenv("VULN_FEED_CACHE_SECONDS", "60")
    settings = load_settings()
    assert settings.openrouter_api_key == "router"
    assert settings.wordfence_api_key == "wf"
    assert settings.vuln_min_cvss == 8.5
    assert settings.vuln_feed_cache_seconds == 60
