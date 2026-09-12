"""Test-facing wrapper around the dev seed catalog (scripts/seed_dev_words.py)
so unit/integration tests exercise the same ~40-word A1-B1 catalog a fresh
dev environment gets, without duplicating the data."""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.word import Word
from scripts.seed_dev_words import SEED_WORDS, build_word


async def insert_seed_words(session: AsyncSession) -> list[Word]:
    words = [build_word(item) for item in SEED_WORDS]
    session.add_all(words)
    await session.flush()
    return words
