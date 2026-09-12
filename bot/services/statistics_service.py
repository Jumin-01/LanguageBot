"""Read-only aggregation over PostgreSQL for the 📊 Статистика screen.

Pure read side: never mutates user_words/answer_history, just summarizes
what SpacedRepetitionService/QuizService have already recorded there.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repositories.answer_history_repository import AnswerHistoryRepository
from bot.database.repositories.user_repository import UserRepository
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.services.dto import StatisticsSummaryDTO

_WEEK = timedelta(days=7)
_MONTH = timedelta(days=30)


class StatisticsService:
    def __init__(self, session: AsyncSession) -> None:
        self._users = UserRepository(session)
        self._user_words = UserWordRepository(session)
        self._history = AnswerHistoryRepository(session)

    async def get_summary(self, user_id: int) -> StatisticsSummaryDTO:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ValueError(f"user {user_id} not found")

        now = datetime.now(UTC)
        end = now + timedelta(seconds=1)  # count_in_period's upper bound is exclusive
        week_ago = now - _WEEK
        month_ago = now - _MONTH

        total_learned = await self._user_words.count_learned(user_id)
        new_this_week = await self._user_words.count_added_since(user_id, week_ago)
        learned_this_week = await self._user_words.count_learned_since(user_id, week_ago)
        learned_this_month = await self._user_words.count_learned_since(user_id, month_ago)

        total_repetitions = await self._history.count_in_period(user_id, user.created_at, end)
        correct_ratio = await self._history.correct_ratio_in_period(user_id, user.created_at, end)
        correct_percentage = round(correct_ratio * 100, 1) if correct_ratio is not None else None

        days_active = max(1, (now - user.created_at).days)
        avg_words_per_day = round(total_learned / days_active, 1)

        return StatisticsSummaryDTO(
            total_learned=total_learned,
            new_this_week=new_this_week,
            total_repetitions=total_repetitions,
            correct_percentage=correct_percentage,
            avg_words_per_day=avg_words_per_day,
            current_level=user.current_level,
            learned_this_week=learned_this_week,
            learned_this_month=learned_this_month,
        )
