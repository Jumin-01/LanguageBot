"""The interface PoolService depends on to source new words for a user's pool.

Kept separate from any concrete implementation so PoolService (and its tests)
never need to know whether words come from a static seed catalog (Phase
2/3's StaticPoolFiller) or the AI-backed VocabularyGenerationService (Phase 4)
-- both satisfy this Protocol.
"""

from typing import Protocol

from bot.services.dto import WordDTO


class VocabularyProvider(Protocol):
    async def generate_candidate_words(self, user_id: int, count: int) -> list[WordDTO]: ...
