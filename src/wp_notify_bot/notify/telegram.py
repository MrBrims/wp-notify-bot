from __future__ import annotations

import logging

from telegram import Bot
from telegram.error import Forbidden, TelegramError

from wp_notify_bot.storage.db import Store

logger = logging.getLogger(__name__)


class TelegramNotifier:
    def __init__(self, bot: Bot, store: Store) -> None:
        self._bot = bot
        self._store = store

    async def send(self, chat_id: int, text: str) -> None:
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=False,
            )
        except Forbidden:
            logger.warning("Chat %s blocked the bot; deactivating subscriber", chat_id)
            await self._store.deactivate(chat_id)
        except TelegramError:
            logger.exception("Failed to send message to chat %s", chat_id)

    async def fanout(self, text: str) -> None:
        chat_ids = await self._store.active_chat_ids()
        for chat_id in chat_ids:
            await self.send(chat_id, text)
