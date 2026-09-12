from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.database.models.enums import OnboardingStatus
from bot.di import Services
from bot.handlers.learning import send_card_message
from bot.keyboards.main_menu import BTN_REVIEW
from bot.rendering.quiz_cards import end_card_fetch, try_begin_card_fetch

router = Router(name="review")

_FETCH_IN_PROGRESS_MESSAGE = "⏳ Слово вже шукається, зачекай трохи..."
_FETCHING_MESSAGE = "⏳ Шукаю слово для повторення..."


@router.message(F.text == BTN_REVIEW)
async def on_review_pressed(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    if not try_begin_card_fetch(telegram_id):
        await message.answer(_FETCH_IN_PROGRESS_MESSAGE)
        return

    try:
        user = await services.user.get_or_create_user(
            telegram_id, message.from_user.username, message.from_user.first_name
        )
        if user.onboarding_status == OnboardingStatus.PENDING_LEVEL:
            await message.answer("Спочатку обери свій рівень командою /start.")
            return

        status_message = await message.answer(_FETCHING_MESSAGE)
        due_words = await services.pool.get_due_words(user.id, limit=1)
        if not due_words:
            await status_message.edit_text(
                'Зараз немає слів для повторення -- усе, що потрібно, вже актуальне. '
                'Нові слова можна вчити через "📚 Вчити слова".'
            )
            return

        await status_message.delete()
        await send_card_message(message, services, state, due_words[0])
    finally:
        end_card_fetch(telegram_id)
