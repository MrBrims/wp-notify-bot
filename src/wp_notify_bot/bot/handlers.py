from __future__ import annotations

import logging

from telegram import BotCommand, Update
from telegram.ext import ContextTypes

from wp_notify_bot.config import Settings, is_user_allowed
from wp_notify_bot.notify.telegram import TelegramNotifier
from wp_notify_bot.pipeline.run import run_pipeline
from wp_notify_bot.pipeline.simulate import SimulationPreview, preview_alerts
from wp_notify_bot.sources.base import Source
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.base import Summarizer

logger = logging.getLogger(__name__)

DEPS_KEY = "deps"

BOT_COMMANDS = [
    BotCommand("start", "Подписаться на уведомления о релизах WordPress"),
    BotCommand("stop", "Отписаться от уведомлений"),
    BotCommand("status", "Последняя версия и время проверки"),
    BotCommand("check", "Проверить релизы сейчас"),
    BotCommand("simulate", "Имитировать уведомление о релизе и уязвимости"),
]

_TEST_BANNER = "Тест: имитация уведомления.\n\n"


class AppDeps:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        sources: list[Source],
        summarizer: Summarizer,
    ) -> None:
        self.settings = settings
        self.store = store
        self.sources = sources
        self.summarizer = summarizer


def get_deps(context: ContextTypes.DEFAULT_TYPE) -> AppDeps:
    return context.application.bot_data[DEPS_KEY]


async def _deny_if_needed(
    update: Update, settings: Settings
) -> bool:
    user = update.effective_user
    user_id = user.id if user else None
    if is_user_allowed(settings, user_id):
        return False
    if update.effective_message:
        await update.effective_message.reply_text("Нет доступа.")
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = get_deps(context)
    if await _deny_if_needed(update, deps.settings):
        return
    chat = update.effective_chat
    user = update.effective_user
    if chat is None:
        return
    await deps.store.subscribe(chat.id, user.id if user else None)
    if update.effective_message:
        await update.effective_message.reply_text(
            "Подписка оформлена. Буду присылать уведомления о релизах WordPress core."
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = get_deps(context)
    if await _deny_if_needed(update, deps.settings):
        return
    chat = update.effective_chat
    if chat is None:
        return
    await deps.store.unsubscribe(chat.id)
    if update.effective_message:
        await update.effective_message.reply_text("Подписка отменена.")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = get_deps(context)
    if await _deny_if_needed(update, deps.settings):
        return
    version = await deps.store.get_meta("last_core_version")
    checked = await deps.store.get_meta("last_check_at")
    feed_at = await deps.store.get_meta("wordfence_feed_at")
    version_line = version or "ещё не известно"
    checked_line = checked or "ещё не было"
    feed_line = feed_at or "ещё не разбирался"
    if update.effective_message:
        await update.effective_message.reply_text(
            f"Последняя известная версия WordPress: {version_line}\n"
            f"Последняя проверка: {checked_line}\n"
            f"Фид уязвимостей: {feed_line}"
        )


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = get_deps(context)
    if await _deny_if_needed(update, deps.settings):
        return
    if update.effective_message:
        await update.effective_message.reply_text("Запускаю проверку…")
    delivered = await run_pipeline(
        deps.sources,
        deps.store,
        deps.summarizer,
        TelegramNotifier(context.bot, deps.store),
    )
    if update.effective_message:
        if delivered:
            await update.effective_message.reply_text(
                f"Найдено новых событий: {len(delivered)}."
            )
        else:
            await update.effective_message.reply_text("Новых уведомлений нет.")


async def cmd_simulate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = get_deps(context)
    if await _deny_if_needed(update, deps.settings):
        return
    chat = update.effective_chat
    if chat is None:
        return
    if update.effective_message:
        await update.effective_message.reply_text("Собираю тестовые уведомления…")
    preview = await preview_alerts(deps.sources)
    notifier = TelegramNotifier(context.bot, deps.store)
    sent = 0
    for item in (preview.core, preview.vulnerability):
        if item is None:
            continue
        text = _TEST_BANNER + await deps.summarizer.summarize(item)
        await notifier.send(chat.id, text)
        sent += 1
    if update.effective_message:
        await update.effective_message.reply_text(_simulate_reply(sent, preview))


def _simulate_reply(sent: int, preview: SimulationPreview) -> str:
    if sent:
        lines = [
            "Тестовые уведомления отправлены только вам. База не изменилась."
        ]
    else:
        lines = ["Тестовые уведомления не отправлены. База не изменилась."]
    if preview.core_error:
        lines.append("Релиз ядра не удалось прочитать.")
    elif preview.core_missing:
        lines.append("В ответе WordPress нет релиза.")
    if preview.vulnerability_disabled:
        lines.append("Опрос уязвимостей выключен.")
    elif preview.vulnerability_error:
        lines.append("Фид уязвимостей не удалось прочитать.")
    elif preview.vulnerability_empty:
        lines.append("Серьёзных уязвимостей в фиде нет.")
    return "\n".join(lines)


async def job_poll(context: ContextTypes.DEFAULT_TYPE) -> None:
    deps = get_deps(context)
    logger.info("Scheduled poll")
    await run_pipeline(
        deps.sources,
        deps.store,
        deps.summarizer,
        TelegramNotifier(context.bot, deps.store),
    )
