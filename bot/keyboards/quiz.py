from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.learning.models import QuizQuestion

QUIZ_CALLBACK_PREFIX = "quiz"
FAST_TRACK_CALLBACK_PREFIX = "fasttrack"
FAST_TRACK_BUTTON_TEXT = "✅ Я вже знаю це слово"


def quiz_callback_data(user_word_id: int, option_index: int) -> str:
    return f"{QUIZ_CALLBACK_PREFIX}:{user_word_id}:{option_index}"


def parse_quiz_callback_data(data: str) -> tuple[int, int] | None:
    parts = data.split(":")
    if len(parts) != 3 or parts[0] != QUIZ_CALLBACK_PREFIX:
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def fast_track_callback_data(user_word_id: int) -> str:
    return f"{FAST_TRACK_CALLBACK_PREFIX}:{user_word_id}"


def parse_fast_track_callback_data(data: str) -> int | None:
    parts = data.split(":")
    if len(parts) != 2 or parts[0] != FAST_TRACK_CALLBACK_PREFIX:
        return None
    try:
        return int(parts[1])
    except ValueError:
        return None


def quiz_options_keyboard(
    question: QuizQuestion, *, show_fast_track: bool = False
) -> InlineKeyboardMarkup | None:
    if not question.options and not show_fast_track:
        return None

    builder = InlineKeyboardBuilder()
    for index, option in enumerate(question.options or []):
        builder.row(
            InlineKeyboardButton(
                text=option,
                callback_data=quiz_callback_data(question.user_word_id, index),
            )
        )
    if show_fast_track:
        builder.row(
            InlineKeyboardButton(
                text=FAST_TRACK_BUTTON_TEXT,
                callback_data=fast_track_callback_data(question.user_word_id),
            )
        )
    return builder.as_markup()
