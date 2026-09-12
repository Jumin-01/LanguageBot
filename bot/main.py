import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.triggers.cron import CronTrigger

from bot.ai.gemini_provider import GeminiAIProvider
from bot.ai.router import AIRouter
from bot.config import settings
from bot.database.repositories.user_repository import UserRepository
from bot.database.session import get_session
from bot.handlers import root_router
from bot.keyboards.main_menu import BOT_COMMANDS
from bot.middlewares import ServicesMiddleware
from bot.scheduling.catalog_topup import CatalogTopUpJob
from bot.scheduling.context import SchedulingContext
from bot.scheduling.jobs import SessionJobRunner
from bot.scheduling.scheduler import build_scheduler
from bot.services.schedule_service import ScheduleService
from bot.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)


async def _register_all_user_jobs(context: SchedulingContext, job_runner: SessionJobRunner) -> None:
    """Startup bootstrap: since jobs live only in memory (see
    bot/scheduling/scheduler.py), every active user's schedule must be
    re-registered from `learning_sessions` each time the process starts."""

    async with get_session() as session:
        users = UserRepository(session)
        schedule_service = ScheduleService(session, context, job_runner)
        active_users = await users.list_active_users()
        for user in active_users:
            await schedule_service.register_jobs_for_user(user.id)
        logger.info("scheduled_jobs_registered", user_count=len(active_users))


async def main() -> None:
    configure_logging(settings.log_level)
    logger.info("starting_bot", environment=settings.environment)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    ai_router = AIRouter(
        default_model=settings.gemini_default_model, advanced_model=settings.gemini_advanced_model
    )
    ai_provider = GeminiAIProvider(settings.gemini_api_key, ai_router)
    scheduler = build_scheduler()
    scheduling_context = SchedulingContext(
        bot=bot,
        scheduler=scheduler,
        ai_provider=ai_provider,
        obsidian_vault_path=settings.obsidian_vault_path,
    )
    job_runner = SessionJobRunner(scheduling_context)

    dp.update.middleware(
        ServicesMiddleware(
            ai_provider,
            obsidian_vault_path=settings.obsidian_vault_path,
            scheduling_context=scheduling_context,
            job_runner=job_runner,
        )
    )
    dp.include_router(root_router)

    catalog_topup_job = CatalogTopUpJob(ai_provider)
    scheduler.add_job(
        catalog_topup_job.run,
        trigger=CronTrigger(hour=3, minute=0),  # once a day, off-peak (UTC)
        id="catalog-topup",
        replace_existing=True,
    )

    scheduler.start()
    try:
        await _register_all_user_jobs(scheduling_context, job_runner)
        await bot.set_my_commands(BOT_COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
