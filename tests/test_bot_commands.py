import re
from types import SimpleNamespace

import pytest
from telegram.error import TelegramError

from wp_notify_bot.bot.handlers import (
    BOT_COMMANDS,
    DEPS_KEY,
    MAIN_MENU_ROWS,
    MENU_ACTIONS,
    WELCOME_IMAGE_PATH,
    WELCOME_TEXT,
    clear_chat_command_menus,
    cmd_start,
    main_menu_markup,
)
from wp_notify_bot.config import Settings


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


def test_welcome_text_lists_buttons_and_fits_caption() -> None:
    for label in MENU_ACTIONS:
        assert f"«{label}»" in WELCOME_TEXT
    assert WELCOME_TEXT.endswith("Выберите нужный раздел в меню ниже.")
    assert len(re.sub(r"<[^>]+>", "", WELCOME_TEXT)) <= 1024
    assert WELCOME_IMAGE_PATH.is_file()


class _StartMessage:
    def __init__(self, photo_error: Exception | None = None) -> None:
        self.photo_error = photo_error
        self.photos: list[dict[str, object]] = []
        self.texts: list[tuple[str, dict[str, object]]] = []

    async def reply_photo(self, photo: object, **kwargs: object) -> None:
        if self.photo_error is not None:
            raise self.photo_error
        self.photos.append(kwargs)

    async def reply_text(self, text: str, **kwargs: object) -> None:
        self.texts.append((text, kwargs))


def _start_call(message: _StartMessage) -> tuple[object, object]:
    settings = Settings(
        telegram_bot_token="token",
        allowed_user_ids=frozenset(),
        poll_interval_seconds=3600,
        database_path=":memory:",
        wordpress_api_url="https://example.test",
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=1),
        effective_chat=SimpleNamespace(id=10),
        effective_message=message,
    )
    context = SimpleNamespace(
        bot=_CommandsBot(failing=set()),
        application=SimpleNamespace(
            bot_data={DEPS_KEY: SimpleNamespace(settings=settings)}
        ),
    )
    return update, context


async def test_start_sends_welcome_photo_with_menu() -> None:
    message = _StartMessage()
    await cmd_start(*_start_call(message))
    assert message.texts == []
    assert len(message.photos) == 1
    sent = message.photos[0]
    assert sent["caption"] == WELCOME_TEXT
    assert sent["parse_mode"] == "HTML"
    assert sent["reply_markup"] == main_menu_markup()


@pytest.mark.parametrize(
    "error", [TelegramError("bad photo"), FileNotFoundError("welcome.jpg")]
)
async def test_start_falls_back_to_text(error: Exception) -> None:
    message = _StartMessage(photo_error=error)
    await cmd_start(*_start_call(message))
    assert message.photos == []
    assert len(message.texts) == 1
    text, kwargs = message.texts[0]
    assert text == WELCOME_TEXT
    assert kwargs["parse_mode"] == "HTML"
    assert kwargs["reply_markup"] == main_menu_markup()
