from __future__ import annotations

import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from wp_notify_bot.models import NormalizedItem
from wp_notify_bot.sources.base import Source
from wp_notify_bot.storage.db import Store

logger = logging.getLogger(__name__)

SOURCE_ID = "wordfence"
PRODUCTION_FEED_URL = (
    "https://www.wordfence.com/api/intelligence/v3/vulnerabilities/production"
)
FEED_TIMEOUT_SECONDS = 180.0
DESCRIPTION_LIMIT = 1500
BOOTSTRAP_META = "wordfence_bootstrapped"
FEED_AT_META = "wordfence_feed_at"
_SERIOUS_RATINGS = frozenset({"high", "critical"})

PayloadLoader = Callable[[], Awaitable[dict[str, Any]]]


def serious_items(payload: dict[str, Any], min_cvss: float) -> list[NormalizedItem]:
    items: list[NormalizedItem] = []
    for record_id, record in _iter_records(payload):
        item = _to_item(record_id, record, min_cvss)
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: (-_sort_score(item), item.uid))
    return items


def feed_ids(payload: dict[str, Any]) -> list[str]:
    return [record_id for record_id, _record in _iter_records(payload)]


class WordfenceSource(Source):
    source_id = SOURCE_ID

    def __init__(
        self,
        api_key: str,
        api_url: str,
        store: Store,
        cache_path: Path,
        cache_seconds: int,
        min_cvss: float,
        load_payload: PayloadLoader | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url
        self._store = store
        self._cache_path = cache_path
        self._cache_seconds = cache_seconds
        self._min_cvss = min_cvss
        self._load_payload_override = load_payload
        self._client = client

    async def fetch(self) -> list[NormalizedItem]:
        payload = await self._load_payload()
        await self._store.set_meta(FEED_AT_META, _utc_now())
        if await self._store.get_meta(BOOTSTRAP_META) != "1":
            await self._store.mark_seen_many(SOURCE_ID, feed_ids(payload))
            await self._store.set_meta(BOOTSTRAP_META, "1")
            return []
        seen = await self._store.seen_uids(SOURCE_ID)
        return [
            item
            for item in serious_items(payload, self._min_cvss)
            if item.uid not in seen
        ]

    async def preview(self) -> list[NormalizedItem]:
        payload = await self._load_payload()
        return serious_items(payload, self._min_cvss)

    async def _load_payload(self) -> dict[str, Any]:
        if self._load_payload_override is not None:
            return await self._load_payload_override()
        if _cache_is_fresh(self._cache_path, self._cache_seconds):
            try:
                return _read_json(self._cache_path)
            except (OSError, json.JSONDecodeError, ValueError):
                logger.warning("Wordfence feed cache is unreadable")
        try:
            return await self._download()
        except Exception as exc:
            if self._cache_path.is_file():
                logger.warning(
                    "Wordfence feed download failed (%s); using cached feed",
                    exc,
                )
                return _read_json(self._cache_path)
            raise

    async def _download(self) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        tmp = self._cache_path.with_suffix(".json.part")
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        client = self._client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=httpx.Timeout(FEED_TIMEOUT_SECONDS))
        try:
            async with client.stream(
                "GET", self._api_url, headers=headers
            ) as response:
                response.raise_for_status()
                with tmp.open("wb") as handle:
                    async for chunk in response.aiter_bytes():
                        handle.write(chunk)
        finally:
            if owns_client:
                await client.aclose()
        try:
            payload = _read_json(tmp)
        except (OSError, json.JSONDecodeError, ValueError):
            tmp.unlink(missing_ok=True)
            raise
        tmp.replace(self._cache_path)
        return payload


def _iter_records(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    records: list[tuple[str, dict[str, Any]]] = []
    for key, record in payload.items():
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("id") or key).strip()
        if not record_id:
            continue
        records.append((record_id, record))
    return records


def _to_item(
    record_id: str, record: dict[str, Any], min_cvss: float
) -> NormalizedItem | None:
    if record.get("informational") is True:
        return None
    software = _choose_software(record)
    if software is None:
        return None
    score, rating = _cvss_parts(record)
    if not _is_serious(score, rating, min_cvss):
        return None
    description = str(record.get("description") or "").strip()
    if len(description) > DESCRIPTION_LIMIT:
        description = description[:DESCRIPTION_LIMIT]
    cve = str(record.get("cve") or "").strip()
    patched = software.get("patched_versions")
    fixed_versions = (
        [str(version).strip() for version in patched if str(version).strip()]
        if isinstance(patched, list)
        else []
    )
    affected_raw = software.get("affected_versions")
    affected = (
        _format_affected(affected_raw) if isinstance(affected_raw, dict) else ""
    )
    return NormalizedItem(
        source_id=SOURCE_ID,
        uid=record_id,
        title=str(record.get("title") or software.get("name") or record_id),
        url=_record_url(record_id, record),
        kind="vulnerability",
        raw_text=description,
        published_at=_parse_published(record.get("published")),
        payload={
            "software_type": str(software.get("type") or ""),
            "software_name": str(software.get("name") or ""),
            "slug": str(software.get("slug") or ""),
            "cvss_score": score,
            "cvss_rating": rating,
            "cve": cve,
            "affected": affected,
            "fixed_in": ", ".join(fixed_versions),
        },
    )


def _choose_software(record: dict[str, Any]) -> dict[str, Any] | None:
    software = record.get("software")
    if not isinstance(software, list):
        return None
    for entry in software:
        if isinstance(entry, dict) and entry.get("type") in {"core", "plugin"}:
            return entry
    return None


def _cvss_parts(record: dict[str, Any]) -> tuple[float | None, str]:
    cvss = record.get("cvss")
    if not isinstance(cvss, dict):
        return None, ""
    raw_score = cvss.get("score")
    score = float(raw_score) if isinstance(raw_score, (int, float)) else None
    rating = str(cvss.get("rating") or "").strip()
    return score, rating


def _is_serious(score: float | None, rating: str, min_cvss: float) -> bool:
    if score is not None:
        return score >= min_cvss
    return rating.strip().lower() in _SERIOUS_RATINGS


def _sort_score(item: NormalizedItem) -> float:
    score = item.payload.get("cvss_score")
    if isinstance(score, (int, float)):
        return float(score)
    rating = str(item.payload.get("cvss_rating") or "").strip().lower()
    if rating == "critical":
        return 9.0
    if rating == "high":
        return 7.0
    return 0.0


def _format_affected(ranges: dict[str, Any]) -> str:
    parts: list[str] = []
    for spec in ranges.values():
        if not isinstance(spec, dict):
            continue
        piece = _format_range(spec)
        if piece:
            parts.append(piece)
    return ", ".join(parts)


def _format_range(spec: dict[str, Any]) -> str:
    start = str(spec.get("from_version") or "").strip()
    end = str(spec.get("to_version") or "").strip()
    start_any = start in {"", "*"}
    end_any = end in {"", "*"}
    if start_any and not end_any:
        piece = f"до {end}"
        if spec.get("to_inclusive"):
            piece += " включительно"
        return piece
    if end_any and not start_any:
        piece = f"от {start}"
        if spec.get("from_inclusive"):
            piece += " включительно"
        return piece
    if start_any or end_any:
        return ""
    left = f"от {start}" if spec.get("from_inclusive") else f"после {start}"
    right = f"до {end}"
    if spec.get("to_inclusive"):
        right += " включительно"
    return f"{left} {right}"


def _record_url(record_id: str, record: dict[str, Any]) -> str:
    references = record.get("references")
    if isinstance(references, list):
        for ref in references:
            if isinstance(ref, str) and "wordfence.com" in ref:
                cleaned = ref.strip()
                if cleaned:
                    return cleaned
    return (
        "https://www.wordfence.com/threat-intel/vulnerabilities/id/"
        + record_id
    )


def _parse_published(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace(" ", "T")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _cache_is_fresh(path: Path, ttl_seconds: int) -> bool:
    if ttl_seconds <= 0 or not path.is_file():
        return False
    return time.time() - path.stat().st_mtime < ttl_seconds


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Wordfence feed is not an object")
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
