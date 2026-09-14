from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler

from wp_notify_bot.bot.handlers import (
    AppDeps,
    DEPS_KEY,
    cmd_check,
    cmd_start,
    cmd_status,
    cmd_stop,
    job_poll,
)
from wp_notify_bot.config import Settings, load_settings
from wp_notify_bot.sources.registry import default_sources
from wp_notify_bot.storage.db import Store
from wp_notify_bot.summarizer.passthrough import PassthroughSummarizer


def build_application(settings: Settings) -> Application:
    store = Store(settings.database_path)
    deps = AppDeps(
        settings=settings,
        store=store,
        sources=default_sources(settings),
        summarizer=PassthroughSummarizer(),
    )
    application = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .build()
    )
    application.bot_data[DEPS_KEY] = deps
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("stop", cmd_stop))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("check", cmd_check))
    return application


async def _post_init(application: Application) -> None:
    deps: AppDeps = application.bot_data[DEPS_KEY]
    await deps.store.init()
    interval = deps.settings.poll_interval_seconds
    job_queue = application.job_queue
    if job_queue is None:
        raise RuntimeError("JobQueue is unavailable; install python-telegram-bot[job-queue]")
    job_queue.run_repeating(job_poll, interval=interval, first=15)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = load_settings()
    application = build_application(settings)
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
