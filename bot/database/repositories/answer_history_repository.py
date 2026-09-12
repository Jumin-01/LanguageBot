from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.answer_history import AnswerHistory
from bot.database.models.enums import QuestionType


class AnswerHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        word_id: int,
        user_word_id: int,
        question_type: QuestionType,
        question_payload: dict[str, Any],
        user_answer: str,
        correct_answer: str,
        is_correct: bool,
        response_time_ms: int | None = None,
        session_run_id: int | None = None,
    ) -> AnswerHistory:
        entry = AnswerHistory(
            user_id=user_id,
            word_id=word_id,
            user_word_id=user_word_id,
            question_type=question_type,
            question_payload=question_payload,
            user_answer=user_answer,
            correct_answer=correct_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            session_run_id=session_run_id,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def get_recent_mistakes(self, user_id: int, limit: int = 20) -> list[AnswerHistory]:
        result = await self._session.execute(
            select(AnswerHistory)
            .where(AnswerHistory.user_id == user_id, AnswerHistory.is_correct.is_(False))
            .order_by(AnswerHistory.answered_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_in_period(self, user_id: int, start: datetime, end: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(AnswerHistory)
            .where(
                AnswerHistory.user_id == user_id,
                AnswerHistory.answered_at >= start,
                AnswerHistory.answered_at < end,
            )
        )
        return int(result.scalar_one())

    async def correct_ratio_in_period(
        self, user_id: int, start: datetime, end: datetime
    ) -> float | None:
        result = await self._session.execute(
            select(func.count(), func.sum(case((AnswerHistory.is_correct, 1), else_=0)))
            .select_from(AnswerHistory)
            .where(
                AnswerHistory.user_id == user_id,
                AnswerHistory.answered_at >= start,
                AnswerHistory.answered_at < end,
            )
        )
        total, correct = result.one()
        if not total:
            return None
        return float(correct or 0) / float(total)
