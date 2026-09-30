from telegram.error import TelegramError

from wp_notify_bot.bot.handlers import (
    BOT_COMMANDS,
    MAIN_MENU_ROWS,
    MENU_ACTIONS,
    clear_chat_command_menus,
    main_menu_markup,
)


class _CommandsBot:
    def __init__(self, failing: set[int]) -> None:
        self.failing = failing
        self.cleared: list[int] = []

    async def delete_my_commands(self, scope: object) -> bool:
        chat_id = getattr(scope, "chat_id")
        if chat_id in self.failing:
            raise TelegramError("chat not found")
        self.cleared.append(chat_id)
        return True


def test_bot_commands_menu_order() -> None:
    assert [(cmd.command, cmd.description) for cmd in BOT_COMMANDS] == [
        ("start", "Главное меню"),
    ]


def test_main_menu_buttons_match_actions() -> None:
    labels = [label for row in MAIN_MENU_ROWS for label in row]
    assert set(labels) == set(MENU_ACTIONS)
    assert len(labels) == len(set(labels))
    assert [len(row) for row in MAIN_MENU_ROWS] == [2, 2, 1]


def test_main_menu_markup_stays_open() -> None:
    markup = main_menu_markup()
    assert markup.resize_keyboard is True
    assert markup.one_time_keyboard is not True
    assert markup.is_persistent is not True
    texts = [[button.text for button in row] for row in markup.keyboard]
    assert texts == [list(row) for row in MAIN_MENU_ROWS]


async def test_chat_command_menus_are_cleared_once_and_errors_skipped() -> None:
    bot = _CommandsBot(failing={2})
    await clear_chat_command_menus(bot, [3, 1, 2, 3])
    assert bot.cleared == [1, 3]
