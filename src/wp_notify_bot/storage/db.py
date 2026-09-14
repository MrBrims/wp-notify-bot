from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    chat_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seen_items (
    source_id TEXT NOT NULL,
    uid TEXT NOT NULL,
    seen_at TEXT NOT NULL,
    PRIMARY KEY (source_id, uid)
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Store:
    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        Path(self._database_path).parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                await db.executescript(SCHEMA)
                await db.commit()

    async def subscribe(self, chat_id: int, user_id: int | None) -> None:
        now = _utc_now()
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                await db.execute(
                    """
                    INSERT INTO subscribers (chat_id, user_id, active, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?)
                    ON CONFLICT(chat_id) DO UPDATE SET
                        user_id = excluded.user_id,
                        active = 1,
                        updated_at = excluded.updated_at
                    """,
                    (chat_id, user_id, now, now),
                )
                await db.commit()

    async def unsubscribe(self, chat_id: int) -> None:
        now = _utc_now()
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                await db.execute(
                    """
                    UPDATE subscribers
                    SET active = 0, updated_at = ?
                    WHERE chat_id = ?
                    """,
                    (now, chat_id),
                )
                await db.commit()

    async def deactivate(self, chat_id: int) -> None:
        await self.unsubscribe(chat_id)

    async def active_chat_ids(self) -> list[int]:
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                cursor = await db.execute(
                    "SELECT chat_id FROM subscribers WHERE active = 1"
                )
                rows = await cursor.fetchall()
        return [int(row[0]) for row in rows]

    async def has_seen(self, source_id: str, uid: str) -> bool:
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                cursor = await db.execute(
                    """
                    SELECT 1 FROM seen_items
                    WHERE source_id = ? AND uid = ?
                    """,
                    (source_id, uid),
                )
                row = await cursor.fetchone()
        return row is not None

    async def mark_seen(self, source_id: str, uid: str) -> None:
        now = _utc_now()
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                await db.execute(
                    """
                    INSERT INTO seen_items (source_id, uid, seen_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(source_id, uid) DO NOTHING
                    """,
                    (source_id, uid, now),
                )
                await db.commit()

    async def get_meta(self, key: str) -> str | None:
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                cursor = await db.execute(
                    "SELECT value FROM meta WHERE key = ?",
                    (key,),
                )
                row = await cursor.fetchone()
        if row is None:
            return None
        return str(row[0])

    async def set_meta(self, key: str, value: str) -> None:
        async with self._lock:
            async with aiosqlite.connect(self._database_path) as db:
                await db.execute(
                    """
                    INSERT INTO meta (key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )
                await db.commit()
