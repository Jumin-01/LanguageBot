from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

SETTINGS_CALLBACK_PREFIX = "settings"

FIELD_LEVEL = "level"
FIELD_DAILY_GOAL = "daily_goal"
FIELD_SESSIONS = "sessions"
FIELD_QUIET_HOURS = "quiet_hours"
FIELD_LOCAL_TIME = "local_time"

_LABELS = {
    FIELD_LEVEL: "Рівень англійської",
    FIELD_DAILY_GOAL: "Нових слів на день",
    FIELD_SESSIONS: "Розклад сесій",
    FIELD_QUIET_HOURS: "Тихі години",
    FIELD_LOCAL_TIME: "Мій поточний час",
}


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field, label in _LABELS.items():
        builder.button(text=label, callback_data=f"{SETTINGS_CALLBACK_PREFIX}:{field}")
    builder.adjust(1)
    return builder.as_markup()
