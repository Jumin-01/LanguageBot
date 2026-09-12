"""The actual work done when a scheduled learning-session job fires.

Mirrors what the manual "📚 Вчити слова" handler does (build the same
services, get the next card, send it) but adds the one thing a push
notification needs that an on-demand tap doesn't: a fresh quiet-hours check
at fire time, since the user's quiet hours may have changed since this job
was registered.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import SessionRunStatus
from bot.database.models.user_settings import UserSettings
from bot.database.repositories.learning_session_repository import LearningSessionRunRepository
from bot.database.repositories.user_repository import UserRepository
from bot.database.session import get_session
from bot.keyboards.quiz import quiz_options_keyboard
from bot.rendering.quiz_cards import format_card_message, register_pending_question
from bot.scheduling.context import SchedulingContext
from bot.scheduling.quiet_hours import is_within_quiet_hours, next_allowed_time
from bot.services.answer_history_service import AnswerHistoryService
from bot.services.knowledge_graph_service import KnowledgeGraphService
from bot.services.pool_service import PoolService
from bot.services.quiz_service import QuizService
from bot.services.spaced_repetition_service import SpacedRepetitionService
from bot.services.vocabulary_generation_service import VocabularyGenerationService
from bot.utils.logging import get_logger
from bot.utils.time import offset_timezone

logger = get_logger(__name__)

DEFERRED_JOB_ID_PREFIX = "session-deferred"


class SessionJobRunner:
    def __init__(
        self,
        context: SchedulingContext,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    ) -> None:
        self._context = context
        # Overridable so tests can point this at an isolated test database
        # instead of the process-wide engine get_session() binds to.
        self._session_factory = session_factory or get_session

    async def run(self, user_id: int) -> None:
        async with self._session_factory() as session:
            users = UserRepository(session)
            runs = LearningSessionRunRepository(session)

            user = await users.get_by_id(user_id)
            settings = await users.get_settings(user_id)
            if user is None or settings is None:
                return

            now_utc = datetime.now(UTC)
            now_local = now_utc.astimezone(offset_timezone(settings.utc_offset_minutes))

            if is_within_quiet_hours(
                now_local.time(), settings.quiet_hours_start, settings.quiet_hours_end
            ):
                await self._defer(user_id, now_utc, now_local, settings, runs)
                return

            knowledge_graph = (
                KnowledgeGraphService(session, self._context.obsidian_vault_path)
                if self._context.obsidian_vault_path
                else None
            )
            vocabulary_provider = VocabularyGenerationService(session, self._context.ai_provider)
            pool = PoolService(
                session, vocabulary_provider=vocabulary_provider, knowledge_graph=knowledge_graph
            )
            srs = SpacedRepetitionService(
                session, pool_service=pool, knowledge_graph=knowledge_graph
            )
            history = AnswerHistoryService(session)
            quiz = QuizService(session, srs, history, ai_provider=self._context.ai_provider)

            card = await pool.get_next_card(user_id)
            if card is None:
                await runs.create(
                    user_id=user_id,
                    scheduled_for=now_utc,
                    status=SessionRunStatus.SKIPPED,
                    deferred_reason="no_words_due",
                )
                logger.info("session_skipped_no_words", user_id=user_id)
                return

            question = await quiz.generate_question(card)
            register_pending_question(user.telegram_id, card, question)

            await self._context.bot.send_message(
                user.telegram_id,
                format_card_message(card, question),
                reply_markup=quiz_options_keyboard(question, show_fast_track=True),
            )
            await runs.create(
                user_id=user_id,
                scheduled_for=now_utc,
                status=SessionRunStatus.SENT,
                sent_at=now_utc,
            )
            logger.info("session_sent", user_id=user_id, word=card.word.lemma)

    async def _defer(
        self,
        user_id: int,
        now_utc: datetime,
        now_local: datetime,
        settings: UserSettings,
        runs: LearningSessionRunRepository,
    ) -> None:
        deferred_local = next_allowed_time(
            now_local, settings.quiet_hours_start, settings.quiet_hours_end
        )
        deferred_utc = deferred_local.astimezone(UTC)

        self._context.scheduler.add_job(
            self.run,
            trigger="date",
            run_date=deferred_utc,
            args=[user_id],
            id=f"{DEFERRED_JOB_ID_PREFIX}:{user_id}:{deferred_utc.isoformat()}",
            replace_existing=True,
        )
        await runs.create(
            user_id=user_id,
            scheduled_for=now_utc,
            status=SessionRunStatus.DEFERRED,
            deferred_reason="quiet_hours",
        )
        logger.info("session_deferred", user_id=user_id, deferred_to=deferred_utc.isoformat())
