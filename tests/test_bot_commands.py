from wp_notify_bot.bot.handlers import BOT_COMMANDS


def test_bot_commands_menu_order() -> None:
    assert [(cmd.command, cmd.description) for cmd in BOT_COMMANDS] == [
        ("start", "Подписаться на уведомления о релизах WordPress"),
        ("stop", "Отписаться от уведомлений"),
        ("status", "Последняя версия и время проверки"),
        ("check", "Проверить релизы сейчас"),
    ]
