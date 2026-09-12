"""Phase 3 stand-in for the AI-backed VocabularyGenerationService (Phase 4):
tops up a user's pool from the static seed catalog instead of calling an LLM.

Satisfies the same VocabularyProvider Protocol PoolService depends on, so the
handlers and PoolService require zero changes when this is swapped for the
real AI-backed service later -- only bot/di.py's wiring changes.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel
from bot.database.repositories.user_repository import UserRepository
from bot.database.repositories.word_repository import WordRepository
from bot.services.dto import WordDTO
from bot.services.mappers import word_to_dto


class StaticPoolFiller:
    def __init__(self, session: AsyncSession) -> None:
        self._words = WordRepository(session)
        self._users = UserRepository(session)

    async def generate_candidate_words(self, user_id: int, count: int) -> list[WordDTO]:
        level = await self._user_level(user_id)

        candidates = await self._words.get_unlinked_for_user(user_id, count, level=level)
        if len(candidates) < count:
            # Not enough words at the user's exact level in the seed catalog --
            # broaden to any level rather than under-filling the pool.
            extra = await self._words.get_unlinked_for_user(user_id, count - len(candidates))
            seen_ids = {word.id for word in candidates}
            candidates += [word for word in extra if word.id not in seen_ids]

        return [word_to_dto(word) for word in candidates]

    async def _user_level(self, user_id: int) -> CEFRLevel | None:
        user = await self._users.get_by_id(user_id)
        return user.current_level if user is not None else None
