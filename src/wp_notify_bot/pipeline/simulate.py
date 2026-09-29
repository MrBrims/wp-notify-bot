from __future__ import annotations

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.sources.wordpress_core import RELEASES_URL, SOURCE_ID

_TEST_PHP = "7.2.24"
_TEST_MYSQL = "5.5.5"


def next_test_version(current: str | None) -> str:
    if current is None:
        return "0.0.1"
    raw = current.strip()
    if not raw:
        return "0.0.1"
    parts = raw.split(".")
    last = parts[-1]
    digits = ""
    for char in last:
        if not char.isdigit():
            break
        digits += char
    if not digits:
        return "0.0.1"
    suffix = last[len(digits):]
    parts[-1] = str(int(digits) + 1) + suffix
    return ".".join(parts)


def simulated_core_item(version: str) -> NormalizedItem:
    download = f"https://downloads.wordpress.org/release/wordpress-{version}.zip"
    return NormalizedItem(
        source_id=SOURCE_ID,
        uid=version,
        title=f"WordPress {version}",
        url=download,
        kind="core_release",
        payload={
            "php_version": _TEST_PHP,
            "mysql_version": _TEST_MYSQL,
            "download": download,
            "releases_url": RELEASES_URL,
        },
    )
