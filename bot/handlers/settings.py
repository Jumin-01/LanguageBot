import re
from datetime import UTC, datetime
from datetime import time as time_cls

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.di import Services
from bot.keyboards.level import level_picker_keyboard
from bot.keyboards.settings import (
    FIELD_DAILY_GOAL,
    FIELD_LOCAL_TIME,
    FIELD_QUIET_HOURS,
    FIELD_SESSIONS,
    SETTINGS_CALLBACK_PREFIX,
    settings_menu_keyboard,
)
from bot.states.settings_states import SettingsFlow
from bot.utils.time import format_offset, parse_local_time_to_offset

router = Router(name="settings")

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
_QUIET_HOURS_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")

_PROMPTS = {
    FIELD_DAILY_GOAL: (
        SettingsFlow.awaiting_daily_goal,
        "Скільки нових слів на день ти хочеш вивчати? Введи число від 1 до 20.",
    ),
    FIELD_SESSIONS: (
        SettingsFlow.awaiting_sessions,
        "Введи час навчальних сесій через кому, у форматі ГГ:ХХ "
        "(наприклад: 09:00,14:00,20:00). Максимум 5 сесій на день.",
    ),
    FIELD_QUIET_HOURS: (
        SettingsFlow.awaiting_quiet_hours,
        "Введи тихі години у форматі ГГ:ХХ-ГГ:ХХ (наприклад: 22:00-08:00).",
    ),
    FIELD_LOCAL_TIME: (
        SettingsFlow.awaiting_local_time,
        "Напиши, котра зараз година у тебе (формат ГГ:ХХ, наприклад 14:30) -- "
        "я порівняю це з часом за Гринвічем і визначу твій часовий пояс.",
    ),
}


@router.message(Command("settings"))
async def on_settings_pressed(message: Message, services: Services) -> None:
    if message.from_user is None:
        return

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    s = await services.user.get_settings(user.id)

    quiet_range = f"{s.quiet_hours_start.strftime('%H:%M')} - {s.quiet_hours_end.strftime('%H:%M')}"
    text = (
        "⚙️ Налаштування\n\n"
        f"Рівень: {user.current_level.value}\n"
        f"Нових слів на день: {s.daily_new_words_goal}\n"
        f"Сесій на день: {s.sessions_per_day}\n"
        f"Тихі години: {quiet_range}\n"
        f"Часовий пояс: {format_offset(s.utc_offset_minutes)}\n\n"
        "Що змінити?"
    )
    await message.answer(text, reply_markup=settings_menu_keyboard())


@router.callback_query(F.data.startswith(f"{SETTINGS_CALLBACK_PREFIX}:"))
async def on_settings_field_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data is None or not isinstance(callback.message, Message):
        await callback.answer()
        return

    field = callback.data.split(":", 1)[1]

    if field not in _PROMPTS:
        # "level" is handled by bot/handlers/start.py's shared level-picker flow.
        await callback.message.answer("Обери новий рівень:", reply_markup=level_picker_keyboard())
        await callback.answer()
        return

    target_state, prompt = _PROMPTS[field]
    await state.set_state(target_state)
    await callback.message.answer(prompt)
    await callback.answer()


@router.message(SettingsFlow.awaiting_daily_goal)
async def on_daily_goal_input(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return

    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Це має бути ціле число від 1 до 20. Спробуй ще раз.")
        return

    if not (1 <= value <= 20):
        await message.answer("Число має бути від 1 до 20. Спробуй ще раз.")
        return

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    await services.user.update_settings(user.id, daily_new_words_goal=value)
    await state.clear()
    await message.answer(f"Готово! Нових слів на день: {value}.")


@router.message(SettingsFlow.awaiting_sessions)
async def on_sessions_input(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return

    raw_parts = [p.strip() for p in message.text.split(",") if p.strip()]
    if not raw_parts or len(raw_parts) > 5:
        await message.answer("Вкажи від 1 до 5 часів через кому, у форматі ГГ:ХХ. Спробуй ще раз.")
        return

    times: list[time_cls] = []
    for part in raw_parts:
        match = _TIME_RE.match(part)
        if match is None:
            await message.answer(f'Не розумію час "{part}". Формат: ГГ:ХХ (наприклад 09:00).')
            return
        times.append(time_cls(int(match.group(1)), int(match.group(2))))

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    await services.user.update_settings(user.id, sessions_per_day=len(times))
    if services.schedule is not None:
        await services.schedule.set_sessions(user.id, times)
        await services.schedule.on_settings_changed(user.id)

    await state.clear()
    formatted = ", ".join(t.strftime("%H:%M") for t in times)
    await message.answer(f"Готово! Розклад сесій: {formatted}.")


@router.message(SettingsFlow.awaiting_quiet_hours)
async def on_quiet_hours_input(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return

    match = _QUIET_HOURS_RE.match(message.text.strip())
    if match is None:
        await message.answer("Формат: ГГ:ХХ-ГГ:ХХ (наприклад 22:00-08:00). Спробуй ще раз.")
        return

    start = time_cls(int(match.group(1)), int(match.group(2)))
    end = time_cls(int(match.group(3)), int(match.group(4)))

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    await services.user.update_settings(user.id, quiet_hours_start=start, quiet_hours_end=end)
    await state.clear()
    await message.answer(
        f"Готово! Тихі години: {start.strftime('%H:%M')} - {end.strftime('%H:%M')}."
    )


@router.message(SettingsFlow.awaiting_local_time)
async def on_local_time_input(message: Message, services: Services, state: FSMContext) -> None:
    if message.from_user is None or message.text is None:
        return

    offset_minutes = parse_local_time_to_offset(message.text, datetime.now(UTC))
    if offset_minutes is None:
        await message.answer("Формат: ГГ:ХХ (наприклад 14:30). Спробуй ще раз.")
        return

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    await services.user.update_settings(user.id, utc_offset_minutes=offset_minutes)
    if services.schedule is not None:
        await services.schedule.on_settings_changed(user.id)

    await state.clear()
    await message.answer(f"Готово! Твій часовий пояс: {format_offset(offset_minutes)}.")
