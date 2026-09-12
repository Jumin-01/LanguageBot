from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.answer_history import AnswerHistory
from bot.database.models.enums import QuestionType
from bot.database.repositories.answer_history_repository import AnswerHistoryRepository


class AnswerHistoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = AnswerHistoryRepository(session)

    async def record(
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
        return await self._repo.create(
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

    async def get_recent_mistakes(self, user_id: int, limit: int = 20) -> list[AnswerHistory]:
        return await self._repo.get_recent_mistakes(user_id, limit)

    async def get_correct_ratio(self, user_id: int, start: datetime, end: datetime) -> float | None:
        return await self._repo.correct_ratio_in_period(user_id, start, end)

    async def count_in_period(self, user_id: int, start: datetime, end: datetime) -> int:
        return await self._repo.count_in_period(user_id, start, end)
