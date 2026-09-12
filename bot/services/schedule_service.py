"""Owns each user's push-notification schedule: the configured session
times (learning_sessions) and translating them into live APScheduler jobs.

The actual quiet-hours deferral happens at fire time in the job itself
(bot/scheduling/jobs.py), not here -- this service only ever registers a
recurring CronTrigger per configured time-of-day, at the user's fixed UTC
offset (see bot/utils/time.py).
"""

from datetime import time

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repositories.learning_session_repository import LearningSessionRepository
from bot.database.repositories.user_repository import UserRepository
from bot.scheduling.context import SchedulingContext
from bot.scheduling.jobs import SessionJobRunner
from bot.services.dto import SessionTimeDTO
from bot.utils.time import offset_timezone

JOB_ID_PREFIX = "session"


class ScheduleService:
    def __init__(
        self, session: AsyncSession, context: SchedulingContext, job_runner: SessionJobRunner
    ) -> None:
        self._sessions = LearningSessionRepository(session)
        self._users = UserRepository(session)
        self._context = context
        self._job_runner = job_runner

    async def get_sessions(self, user_id: int) -> list[SessionTimeDTO]:
        rows = await self._sessions.list_enabled(user_id)
        return [SessionTimeDTO(time_of_day=r.time_of_day, enabled=r.enabled) for r in rows]

    async def set_sessions(self, user_id: int, times: list[time]) -> list[SessionTimeDTO]:
        rows = await self._sessions.replace_all(user_id, times)
        return [SessionTimeDTO(time_of_day=r.time_of_day, enabled=r.enabled) for r in rows]

    def _remove_existing_jobs(self, user_id: int) -> None:
        prefix = f"{JOB_ID_PREFIX}:{user_id}:"
        for job in self._context.scheduler.get_jobs():
            if job.id.startswith(prefix):
                job.remove()

    async def register_jobs_for_user(self, user_id: int) -> None:
        self._remove_existing_jobs(user_id)

        settings = await self._users.get_settings(user_id)
        if settings is None:
            return

        sessions = await self._sessions.list_enabled(user_id)
        tz = offset_timezone(settings.utc_offset_minutes)

        for entry in sessions:
            trigger = CronTrigger(
                hour=entry.time_of_day.hour, minute=entry.time_of_day.minute, timezone=tz
            )
            self._context.scheduler.add_job(
                self._job_runner.run,
                trigger=trigger,
                args=[user_id],
                id=f"{JOB_ID_PREFIX}:{user_id}:{entry.time_of_day.isoformat()}",
                replace_existing=True,
                misfire_grace_time=3600,
            )

    async def on_settings_changed(self, user_id: int) -> None:
        await self.register_jobs_for_user(user_id)
