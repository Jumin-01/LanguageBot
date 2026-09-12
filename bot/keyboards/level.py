from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.database.models.enums import CEFRLevel

LEVEL_CALLBACK_PREFIX = "level"


def level_picker_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for level in CEFRLevel:
        builder.button(text=level.value, callback_data=f"{LEVEL_CALLBACK_PREFIX}:{level.value}")
    builder.adjust(3)
    return builder.as_markup()
