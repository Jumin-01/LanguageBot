from datetime import time

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message

from bot.database.models.enums import CEFRLevel, OnboardingStatus
from bot.di import Services
from bot.keyboards.level import LEVEL_CALLBACK_PREFIX, level_picker_keyboard
from bot.keyboards.main_menu import main_menu_keyboard

router = Router(name="start")

DEFAULT_SESSION_TIMES = [time(9, 0), time(14, 0), time(20, 0)]


@router.message(CommandStart())
async def cmd_start(message: Message, services: Services) -> None:
    if message.from_user is None:
        return

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )

    if user.onboarding_status == OnboardingStatus.PENDING_LEVEL:
        await message.answer(
            "Привіт! Я допоможу тобі вивчати англійські слова та вирази.\n\n"
            "Спочатку обери свій поточний рівень англійської (CEFR):",
            reply_markup=level_picker_keyboard(),
        )
        return

    await message.answer(
        "З поверненням! Обирай розділ у меню нижче.",
        reply_markup=main_menu_keyboard(),
    )


@router.callback_query(F.data.startswith(f"{LEVEL_CALLBACK_PREFIX}:"))
async def on_level_chosen(callback: CallbackQuery, services: Services) -> None:
    if (
        callback.from_user is None
        or callback.data is None
        or not isinstance(callback.message, Message)
    ):
        await callback.answer()
        return

    level_value = callback.data.split(":", 1)[1]
    try:
        level = CEFRLevel(level_value)
    except ValueError:
        await callback.answer("Невідомий рівень.")
        return

    user = await services.user.get_or_create_user(
        callback.from_user.id, callback.from_user.username, callback.from_user.first_name
    )
    is_first_time = user.onboarding_status == OnboardingStatus.PENDING_LEVEL

    await services.user.set_level(user.id, level)

    if not is_first_time:
        await callback.message.edit_text(f"Рівень оновлено: {level.value}.")
        await callback.answer()
        return

    await services.user.complete_onboarding(user.id)
    await services.pool.ensure_pool_filled(user.id)

    if services.schedule is not None:
        await services.schedule.set_sessions(user.id, DEFAULT_SESSION_TIMES)
        await services.schedule.register_jobs_for_user(user.id)

    await callback.message.edit_text(f"Рівень збережено: {level.value}. Вивчаймо слова!")
    await callback.message.answer(
        'Натисни "📚 Вчити слова", щоб почати.',
        reply_markup=main_menu_keyboard(),
    )
    await callback.answer()
