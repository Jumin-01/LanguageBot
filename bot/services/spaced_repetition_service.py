from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repositories.user_word_repository import UserWordRepository
from bot.learning.models import SRSUpdateResult, WordProgress
from bot.learning.srs_algorithm import compute_fast_mastery_state, compute_next_state
from bot.services.knowledge_graph_service import KnowledgeGraphService
from bot.services.mappers import user_word_to_dto
from bot.services.pool_service import PoolService


class SpacedRepetitionService:
    def __init__(
        self,
        session: AsyncSession,
        pool_service: PoolService | None = None,
        knowledge_graph: KnowledgeGraphService | None = None,
    ) -> None:
        self._session = session
        self._user_words = UserWordRepository(session)
        self._pool_service = pool_service
        self._knowledge_graph = knowledge_graph

    @staticmethod
    def compute_update(
        progress: WordProgress, is_correct: bool, now: datetime, *, fast_track: bool = False
    ) -> SRSUpdateResult:
        if fast_track and is_correct:
            return compute_fast_mastery_state(progress, now)
        return compute_next_state(progress, is_correct, now)

    async def apply_answer(
        self, user_id: int, user_word_id: int, is_correct: bool, *, fast_track: bool = False
    ) -> SRSUpdateResult:
        user_word = await self._user_words.get_by_id(user_word_id)
        if user_word is None or user_word.user_id != user_id:
            raise ValueError(f"user_word {user_word_id} not found for user {user_id}")

        progress = WordProgress(
            user_word_id=user_word.id,
            status=user_word.status,
            correct_answers=user_word.correct_answers,
            wrong_answers=user_word.wrong_answers,
            repetitions=user_word.repetitions,
            consecutive_correct=user_word.consecutive_correct,
            ease_factor=user_word.ease_factor,
            current_interval_days=user_word.current_interval_days,
            last_review_at=user_word.last_review_at,
            next_review_at=user_word.next_review_at,
        )

        now = datetime.now(UTC)
        result = self.compute_update(progress, is_correct, now, fast_track=fast_track)

        user_word.status = result.new_status
        user_word.repetitions = result.new_repetitions
        user_word.consecutive_correct = result.new_consecutive_correct
        user_word.ease_factor = result.new_ease_factor
        user_word.current_interval_days = result.new_interval_days
        user_word.next_review_at = result.new_next_review_at
        user_word.last_review_at = now
        if is_correct:
            user_word.correct_answers += 1
        else:
            user_word.wrong_answers += 1
        if result.became_learned:
            user_word.learned_at = now

        await self._user_words.save(user_word)

        if self._knowledge_graph is not None:
            await self._knowledge_graph.sync_word_node(user_id, user_word_to_dto(user_word))

        if result.became_learned and self._pool_service is not None:
            await self._pool_service.mark_learned_and_replace(user_id, user_word_id)

        return result
