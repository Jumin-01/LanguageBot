"""Per-update service wiring.

One Services bundle is built per Telegram update (see bot/middlewares.py),
all sharing the same AsyncSession so a single update either fully commits or
fully rolls back together. `schedule` is the one exception in spirit -- it
also holds a reference to the long-lived scheduler/bot (bot/scheduling/
context.py) -- but is still built per-update since it needs the same
short-lived session as everything else to read/write `learning_sessions`.
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from bot.scheduling.context import SchedulingContext
from bot.scheduling.jobs import SessionJobRunner
from bot.services.answer_history_service import AnswerHistoryService
from bot.services.knowledge_graph_service import KnowledgeGraphService
from bot.services.pool_service import PoolService
from bot.services.quiz_service import QuizAIProvider, QuizService
from bot.services.schedule_service import ScheduleService
from bot.services.spaced_repetition_service import SpacedRepetitionService
from bot.services.statistics_service import StatisticsService
from bot.services.user_service import UserService
from bot.services.vocabulary_provider import VocabularyProvider


@dataclass
class Services:
    user: UserService
    pool: PoolService
    srs: SpacedRepetitionService
    quiz: QuizService
    history: AnswerHistoryService
    statistics: StatisticsService
    knowledge_graph: KnowledgeGraphService | None
    schedule: ScheduleService | None


def build_services(
    session: AsyncSession,
    vocabulary_provider: VocabularyProvider,
    ai_provider: QuizAIProvider | None = None,
    obsidian_vault_path: str | None = None,
    scheduling_context: SchedulingContext | None = None,
    job_runner: SessionJobRunner | None = None,
) -> Services:
    knowledge_graph = (
        KnowledgeGraphService(session, obsidian_vault_path) if obsidian_vault_path else None
    )
    user = UserService(session)
    pool = PoolService(
        session, vocabulary_provider=vocabulary_provider, knowledge_graph=knowledge_graph
    )
    srs = SpacedRepetitionService(session, pool_service=pool, knowledge_graph=knowledge_graph)
    history = AnswerHistoryService(session)
    quiz = QuizService(session, srs, history, ai_provider=ai_provider)
    statistics = StatisticsService(session)
    schedule = (
        ScheduleService(session, scheduling_context, job_runner)
        if scheduling_context is not None and job_runner is not None
        else None
    )
    return Services(
        user=user,
        pool=pool,
        srs=srs,
        quiz=quiz,
        history=history,
        statistics=statistics,
        knowledge_graph=knowledge_graph,
        schedule=schedule,
    )
