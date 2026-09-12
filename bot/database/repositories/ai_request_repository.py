from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.ai_request import AIRequest


class AIRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        task_type: str,
        model: str,
        latency_ms: int,
        status: str,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        error_code: str | None = None,
        user_id: int | None = None,
    ) -> AIRequest:
        entry = AIRequest(
            user_id=user_id,
            task_type=task_type,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            status=status,
            error_code=error_code,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry

    async def usage_since(self, since: datetime) -> list[AIRequest]:
        result = await self._session.execute(
            select(AIRequest).where(AIRequest.created_at >= since).order_by(AIRequest.created_at)
        )
        return list(result.scalars().all())

    async def summary_by_model_since(self, since: datetime) -> list[tuple[str, int, int]]:
        """Returns (model, request_count, total_tokens) rows since `since`."""

        result = await self._session.execute(
            select(
                AIRequest.model,
                func.count(),
                func.coalesce(func.sum(AIRequest.total_tokens), 0),
            )
            .where(AIRequest.created_at >= since)
            .group_by(AIRequest.model)
        )
        return [(row[0], row[1], row[2]) for row in result.all()]
