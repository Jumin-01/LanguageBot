from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.di import Services
from bot.services.dto import StatisticsSummaryDTO

router = Router(name="statistics")


def _format_summary(summary: StatisticsSummaryDTO) -> str:
    correct_pct = (
        f"{summary.correct_percentage:.0f}%" if summary.correct_percentage is not None else "—"
    )
    return (
        "📊 Твоя статистика\n\n"
        f"Всього вивчено: {summary.total_learned}\n"
        f"Нових цього тижня: {summary.new_this_week}\n"
        f"Повторень: {summary.total_repetitions}\n"
        f"Правильних відповідей: {correct_pct}\n\n"
        f"Середня швидкість: {summary.avg_words_per_day} слова/день\n"
        f"Поточний рівень: {summary.current_level.value}\n\n"
        f"Прогрес за тиждень: +{summary.learned_this_week} вивчено\n"
        f"Прогрес за місяць: +{summary.learned_this_month} вивчено"
    )


@router.message(Command("stats"))
async def on_stats_pressed(message: Message, services: Services) -> None:
    if message.from_user is None:
        return

    user = await services.user.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.first_name
    )
    summary = await services.statistics.get_summary(user.id)

    await message.answer(_format_summary(summary))
