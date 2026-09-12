from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.ai.provider import AIProvider
from bot.database.session import get_session
from bot.di import build_services
from bot.scheduling.context import SchedulingContext
from bot.scheduling.jobs import SessionJobRunner
from bot.services.vocabulary_generation_service import VocabularyGenerationService


class ServicesMiddleware(BaseMiddleware):
    """Opens one DB session (and therefore one commit/rollback unit) per
    Telegram update, builds the service layer on top of it, and injects both
    into the handler's data so handlers never touch the ORM directly.

    Takes a single shared AIProvider (constructed once at bot startup, since
    it holds its own HTTP client) and wraps it in a fresh
    VocabularyGenerationService per update -- the dedup/level-filtering rules
    live in that service, not in the AI client itself. `obsidian_vault_path`
    is passed straight through to build_services(); pass None to disable the
    Obsidian sync entirely. `scheduling_context`/`job_runner` are likewise
    passed through so handlers can register/update a user's push schedule.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        obsidian_vault_path: str | None = None,
        scheduling_context: SchedulingContext | None = None,
        job_runner: SessionJobRunner | None = None,
    ) -> None:
        self._ai_provider = ai_provider
        self._obsidian_vault_path = obsidian_vault_path
        self._scheduling_context = scheduling_context
        self._job_runner = job_runner

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with get_session() as session:
            vocabulary_provider = VocabularyGenerationService(session, self._ai_provider)
            data["session"] = session
            data["services"] = build_services(
                session,
                vocabulary_provider,
                ai_provider=self._ai_provider,
                obsidian_vault_path=self._obsidian_vault_path,
                scheduling_context=self._scheduling_context,
                job_runner=self._job_runner,
            )
            return await handler(event, data)
