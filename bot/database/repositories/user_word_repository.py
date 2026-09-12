from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models.enums import ACTIVE_POOL_STATUSES, WordStatus
from bot.database.models.user_word import UserWord
from bot.database.models.word import Word


class UserWordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_word_id: int) -> UserWord | None:
        return await self._session.get(
            UserWord, user_word_id, options=[selectinload(UserWord.word)]
        )

    async def get_by_user_and_word(self, user_id: int, word_id: int) -> UserWord | None:
        result = await self._session.execute(
            select(UserWord).where(UserWord.user_id == user_id, UserWord.word_id == word_id)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, word_id: int) -> UserWord:
        user_word = UserWord(user_id=user_id, word_id=word_id, status=WordStatus.NEW)
        self._session.add(user_word)
        await self._session.flush()
        # Populate the `word` relationship explicitly: under the async ORM, a
        # freshly-created instance's relationships aren't auto-loaded just
        # because the relationship is `lazy="joined"` (that only affects
        # SELECT queries) -- plain lazy attribute access would raise
        # MissingGreenlet, so we eagerly refresh it here instead.
        await self._session.refresh(user_word, attribute_names=["word"])
        return user_word

    async def count_active(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserWord)
            .where(UserWord.user_id == user_id, UserWord.status.in_(ACTIVE_POOL_STATUSES))
        )
        return int(result.scalar_one())

    async def get_active_pool(self, user_id: int) -> list[UserWord]:
        result = await self._session.execute(
            select(UserWord)
            .options(selectinload(UserWord.word))
            .where(UserWord.user_id == user_id, UserWord.status.in_(ACTIVE_POOL_STATUSES))
            .order_by(UserWord.added_at)
        )
        return list(result.scalars().all())

    async def get_due(self, user_id: int, now: datetime, limit: int = 20) -> list[UserWord]:
        result = await self._session.execute(
            select(UserWord)
            .options(selectinload(UserWord.word))
            .where(
                UserWord.user_id == user_id,
                UserWord.status.in_((WordStatus.LEARNING, WordStatus.REVIEW)),
                UserWord.next_review_at.is_not(None),
                UserWord.next_review_at <= now,
            )
            .order_by(UserWord.next_review_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_new(self, user_id: int, limit: int = 20) -> list[UserWord]:
        result = await self._session.execute(
            select(UserWord)
            .options(selectinload(UserWord.word))
            .where(UserWord.user_id == user_id, UserWord.status == WordStatus.NEW)
            .order_by(UserWord.added_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_known_word_ids(self, user_id: int) -> set[int]:
        """All word_ids the user has ever been linked to (any status) -- used to
        avoid re-adding a word they already learned, are learning, or dropped."""

        result = await self._session.execute(
            select(UserWord.word_id).where(UserWord.user_id == user_id)
        )
        return set(result.scalars().all())

    async def list_learned_words(self, user_id: int, limit: int = 200) -> list[Word]:
        result = await self._session.execute(
            select(Word)
            .join(UserWord, UserWord.word_id == Word.id)
            .where(UserWord.user_id == user_id, UserWord.status == WordStatus.LEARNED)
            .order_by(UserWord.learned_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_learned(self, user_id: int) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserWord)
            .where(UserWord.user_id == user_id, UserWord.status == WordStatus.LEARNED)
        )
        return int(result.scalar_one())

    async def count_added_since(self, user_id: int, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserWord)
            .where(UserWord.user_id == user_id, UserWord.added_at >= since)
        )
        return int(result.scalar_one())

    async def count_learned_since(self, user_id: int, since: datetime) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(UserWord)
            .where(
                UserWord.user_id == user_id,
                UserWord.status == WordStatus.LEARNED,
                UserWord.learned_at.is_not(None),
                UserWord.learned_at >= since,
            )
        )
        return int(result.scalar_one())

    async def save(self, user_word: UserWord) -> None:
        self._session.add(user_word)
        await self._session.flush()
