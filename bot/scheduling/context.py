"""Long-lived objects the scheduler needs, constructed once at bot startup
(bot/main.py) and shared by every scheduled job run -- unlike the per-update
`Services` bundle (bot/di.py), which is rebuilt fresh for every Telegram
update with its own short-lived DB session.
"""

from dataclasses import dataclass

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot.ai.provider import AIProvider


@dataclass
class SchedulingContext:
    bot: Bot
    scheduler: AsyncIOScheduler
    ai_provider: AIProvider
    obsidian_vault_path: str | None
