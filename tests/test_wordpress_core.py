from __future__ import annotations

import json
from pathlib import Path

from wp_notify_bot.sources.wordpress_core import parse_version_check

FIXTURE = Path(__file__).parent / "fixtures" / "version-check.json"


def test_parse_version_check_keeps_unique_upgrade_offers() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    items = parse_version_check(payload)
    assert len(items) == 1
    item = items[0]
    assert item.source_id == "wordpress_core"
    assert item.uid == "6.8.2"
    assert item.kind == "core_release"
    assert item.payload["php_version"] == "7.2.24"
    assert "6.8.2.zip" in item.url


def test_parse_version_check_empty() -> None:
    assert parse_version_check({}) == []
    assert parse_version_check({"offers": []}) == []
    assert parse_version_check({"offers": [{"response": "latest"}]}) == []
