"""Builds the process's single AsyncIOScheduler.

Uses the default in-memory job store rather than a persistent one
(SQLAlchemyJobStore, as originally sketched): our job callables are bound
methods holding live objects (a Bot, an AIProvider) that aren't meaningfully
picklable, and MemoryJobStore needs no pickling since jobs never leave the
process. Durability across restarts is instead handled by re-registering
every active user's jobs from `learning_sessions` on every startup (see
bot/main.py) -- simpler and just as correct for a single-instance MVP bot.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def build_scheduler() -> AsyncIOScheduler:
    return AsyncIOScheduler(timezone="UTC")
