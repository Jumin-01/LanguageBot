from aiogram import Router

from bot.handlers import common, learning, review, settings, start, statistics

root_router = Router(name="root")
root_router.include_router(start.router)
root_router.include_router(learning.router)
root_router.include_router(review.router)
root_router.include_router(settings.router)
root_router.include_router(statistics.router)
root_router.include_router(common.router)

__all__ = ["root_router"]
