from aiogram.types import BotCommand, KeyboardButton, ReplyKeyboardMarkup

BTN_LEARN = "📚 Вчити слова"
BTN_REVIEW = "🔄 Повторення"

# ⚙️ Налаштування and 📊 Статистика live in the "/" commands menu instead of
# the pinned reply keyboard -- they're occasional actions, not something you
# tap every session, so keeping them off the persistent keyboard leaves more
# room for the actual learning buttons.
BOT_COMMANDS = [
    BotCommand(command="start", description="Почати / перезапустити"),
    BotCommand(command="settings", description="⚙️ Налаштування"),
    BotCommand(command="stats", description="📊 Статистика"),
]


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_LEARN), KeyboardButton(text=BTN_REVIEW)],
        ],
        resize_keyboard=True,
    )
