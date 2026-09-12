from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, OnboardingStatus, SessionRunStatus
from bot.database.models.learning_session import LearningSessionRun
from bot.database.models.user import User
from bot.database.models.user_settings import UserSettings
from bot.database.repositories.learning_session_repository import LearningSessionRunRepository
from bot.database.repositories.user_repository import UserRepository
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.database.repositories.word_repository import WordRepository
from bot.scheduling.context import SchedulingContext
from bot.scheduling.jobs import SessionJobRunner
from bot.services.schedule_service import ScheduleService
from tests.conftest import FakeAIProvider
from tests.fixtures.seed_words import insert_seed_words


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, reply_markup: object = None) -> None:
        self.sent.append((chat_id, text))


async def _create_user_with_settings(
    session: AsyncSession,
    *,
    telegram_id: int = 999,
    utc_offset_minutes: int = 120,
    quiet_start: time = time(22, 0),
    quiet_end: time = time(8, 0),
) -> User:
    user = User(
        telegram_id=telegram_id,
        current_level=CEFRLevel.B1,
        onboarding_status=OnboardingStatus.ACTIVE,
    )
    session.add(user)
    await session.flush()
    settings = UserSettings(
        user_id=user.id,
        utc_offset_minutes=utc_offset_minutes,
        quiet_hours_start=quiet_start,
        quiet_hours_end=quiet_end,
    )
    session.add(settings)
    await session.flush()
    return user


@asynccontextmanager
async def _reuse_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """SessionJobRunner normally opens its own DB session per run (it fires
    outside any request/response cycle); reusing the test's own transactional
    `db_session` here keeps this test on the isolated test database instead
    of the app's real engine, and keeps writes visible/rollback-safe."""

    yield session


def _build_context(fake_ai_provider: FakeAIProvider) -> tuple[SchedulingContext, FakeBot]:
    bot = FakeBot()
    scheduler = AsyncIOScheduler()
    context = SchedulingContext(
        bot=bot, scheduler=scheduler, ai_provider=fake_ai_provider, obsidian_vault_path=None
    )
    return context, bot


async def test_register_jobs_creates_one_cron_job_per_session_time(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user_with_settings(db_session)
    context, _ = _build_context(fake_ai_provider)
    schedule = ScheduleService(db_session, context, SessionJobRunner(context))

    await schedule.set_sessions(user.id, [time(9, 0), time(14, 0)])
    await schedule.register_jobs_for_user(user.id)

    job_ids = {job.id for job in context.scheduler.get_jobs()}
    assert job_ids == {f"session:{user.id}:09:00:00", f"session:{user.id}:14:00:00"}


async def test_register_jobs_is_idempotent(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user_with_settings(db_session)
    context, _ = _build_context(fake_ai_provider)
    schedule = ScheduleService(db_session, context, SessionJobRunner(context))

    await schedule.set_sessions(user.id, [time(9, 0)])
    await schedule.register_jobs_for_user(user.id)
    await schedule.register_jobs_for_user(user.id)

    assert len(context.scheduler.get_jobs()) == 1


async def test_on_settings_changed_replaces_the_schedule(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user_with_settings(db_session)
    context, _ = _build_context(fake_ai_provider)
    schedule = ScheduleService(db_session, context, SessionJobRunner(context))

    await schedule.set_sessions(user.id, [time(9, 0)])
    await schedule.register_jobs_for_user(user.id)
    await schedule.set_sessions(user.id, [time(10, 0), time(20, 0)])
    await schedule.on_settings_changed(user.id)

    job_ids = {job.id for job in context.scheduler.get_jobs()}
    assert job_ids == {f"session:{user.id}:10:00:00", f"session:{user.id}:20:00:00"}


async def test_job_runner_sends_card_when_not_in_quiet_hours(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    # A zero-length quiet window is never "quiet" (see quiet_hours.py), which
    # keeps this test deterministic regardless of when it actually runs.
    await insert_seed_words(db_session)
    user = await _create_user_with_settings(
        db_session, quiet_start=time(0, 0), quiet_end=time(0, 0)
    )
    word = (await WordRepository(db_session).get_unlinked_for_user(user.id, 1))[0]
    await UserWordRepository(db_session).create(user.id, word.id)

    context, bot = _build_context(fake_ai_provider)
    runner = SessionJobRunner(context, session_factory=lambda: _reuse_session(db_session))

    await runner.run(user.id)

    assert len(bot.sent) == 1
    chat_id, text = bot.sent[0]
    assert chat_id == user.telegram_id
    assert word.lemma in text

    result = await db_session.execute(
        select(LearningSessionRun).where(LearningSessionRun.user_id == user.id)
    )
    run = result.scalar_one()
    assert run.status == SessionRunStatus.SENT


async def test_job_runner_defers_and_does_not_send_during_quiet_hours(
    db_session: AsyncSession, fake_ai_provider: FakeAIProvider
) -> None:
    user = await _create_user_with_settings(
        db_session, utc_offset_minutes=0, quiet_start=time(22, 0), quiet_end=time(8, 0)
    )
    settings = await UserRepository(db_session).get_settings(user.id)
    assert settings is not None

    context, bot = _build_context(fake_ai_provider)
    runner = SessionJobRunner(context)
    runs_repo = LearningSessionRunRepository(db_session)

    now_utc = datetime.now(UTC)
    # Force a moment that is unambiguously inside the 22:00-08:00 window,
    # regardless of when this test actually runs.
    now_local = now_utc.astimezone(ZoneInfo("UTC")).replace(hour=23, minute=0)

    await runner._defer(user.id, now_utc, now_local, settings, runs_repo)

    assert bot.sent == []
    deferred_jobs = [
        job for job in context.scheduler.get_jobs() if job.id.startswith("session-deferred:")
    ]
    assert len(deferred_jobs) == 1

    result = await db_session.execute(
        select(LearningSessionRun).where(LearningSessionRun.user_id == user.id)
    )
    run = result.scalar_one()
    assert run.status == SessionRunStatus.DEFERRED
