from datetime import datetime, time

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import SessionRunStatus
from bot.database.models.learning_session import LearningSession, LearningSessionRun


class LearningSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_enabled(self, user_id: int) -> list[LearningSession]:
        result = await self._session.execute(
            select(LearningSession)
            .where(LearningSession.user_id == user_id, LearningSession.enabled.is_(True))
            .order_by(LearningSession.time_of_day)
        )
        return list(result.scalars().all())

    async def replace_all(self, user_id: int, times: list[time]) -> list[LearningSession]:
        """Atomically replaces the user's whole schedule with `times`."""

        await self._session.execute(
            delete(LearningSession).where(LearningSession.user_id == user_id)
        )
        sessions = [LearningSession(user_id=user_id, time_of_day=t) for t in times]
        self._session.add_all(sessions)
        await self._session.flush()
        return sessions


class LearningSessionRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: int,
        scheduled_for: datetime,
        status: SessionRunStatus,
        sent_at: datetime | None = None,
        deferred_reason: str | None = None,
    ) -> LearningSessionRun:
        run = LearningSessionRun(
            user_id=user_id,
            scheduled_for=scheduled_for,
            status=status,
            sent_at=sent_at,
            deferred_reason=deferred_reason,
        )
        self._session.add(run)
        await self._session.flush()
        return run
