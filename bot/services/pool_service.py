"""Owns the 20-word active pool: the hard MAX_ACTIVE_WORDS cap, no-duplicate
linking, and auto-replacement of learned words are all enforced here in code,
never delegated to whatever supplies new words (see vocabulary_provider.py).
"""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repositories.user_word_repository import UserWordRepository
from bot.learning import pool_rules
from bot.services.dto import UserWordDTO, WordDTO
from bot.services.knowledge_graph_service import KnowledgeGraphService
from bot.services.mappers import user_word_to_dto
from bot.services.vocabulary_provider import VocabularyProvider


class PoolService:
    def __init__(
        self,
        session: AsyncSession,
        vocabulary_provider: VocabularyProvider | None = None,
        knowledge_graph: KnowledgeGraphService | None = None,
    ) -> None:
        self._session = session
        self._user_words = UserWordRepository(session)
        self._vocabulary_provider = vocabulary_provider
        self._knowledge_graph = knowledge_graph

    async def get_active_pool(self, user_id: int) -> list[UserWordDTO]:
        rows = await self._user_words.get_active_pool(user_id)
        return [user_word_to_dto(row) for row in rows]

    async def get_due_words(
        self, user_id: int, limit: int, now: datetime | None = None
    ) -> list[UserWordDTO]:
        rows = await self._user_words.get_due(user_id, now or datetime.now(UTC), limit=limit)
        return [user_word_to_dto(row) for row in rows]

    async def add_words_to_pool(self, user_id: int, words: list[WordDTO]) -> list[UserWordDTO]:
        """Links up to `slots_free` of the given words to the user, skipping any
        the user is already linked to (new, learning, review, or learned)."""

        active_count = await self._user_words.count_active(user_id)
        available = pool_rules.slots_free(active_count)
        if available <= 0:
            return []

        known_ids = await self._user_words.list_known_word_ids(user_id)

        added: list[UserWordDTO] = []
        for word in words:
            if len(added) >= available:
                break
            if word.id in known_ids:
                continue
            user_word = await self._user_words.create(user_id, word.id)
            known_ids.add(word.id)
            user_word_dto = user_word_to_dto(user_word)
            added.append(user_word_dto)

            if self._knowledge_graph is not None:
                await self._knowledge_graph.sync_word_node(user_id, user_word_dto)
        return added

    async def ensure_pool_filled(self, user_id: int) -> list[UserWordDTO]:
        """Tops the pool up to MAX_ACTIVE_WORDS via the configured vocabulary
        provider. Returns only the newly-added words (empty if the pool was
        already full or no provider is configured)."""

        active_count = await self._user_words.count_active(user_id)
        slots = pool_rules.slots_free(active_count)
        if slots <= 0 or self._vocabulary_provider is None:
            return []

        candidates = await self._vocabulary_provider.generate_candidate_words(user_id, slots)
        return await self.add_words_to_pool(user_id, candidates)

    async def mark_learned_and_replace(self, user_id: int, user_word_id: int) -> UserWordDTO | None:
        """Called after a word's status has already been set to LEARNED
        elsewhere (SpacedRepetitionService); tops the pool back up to 20 and
        returns the replacement word, if one was added."""

        newly_added = await self.ensure_pool_filled(user_id)
        return newly_added[0] if newly_added else None

    async def get_next_card(self, user_id: int) -> UserWordDTO | None:
        await self.ensure_pool_filled(user_id)

        now = datetime.now(UTC)
        due = await self._user_words.get_due(user_id, now, limit=1)
        if due:
            return user_word_to_dto(due[0])

        new_words = await self._user_words.get_new(user_id, limit=1)
        if new_words:
            return user_word_to_dto(new_words[0])

        return None
