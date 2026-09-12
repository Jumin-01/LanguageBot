from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, PartOfSpeech, WordSource
from bot.database.models.user_word import UserWord
from bot.database.models.word import Word


class WordRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, word_id: int) -> Word | None:
        return await self._session.get(Word, word_id)

    async def get_by_lemma(self, lemma: str, part_of_speech: PartOfSpeech) -> Word | None:
        normalized = lemma.strip().lower()
        result = await self._session.execute(
            select(Word).where(
                func.lower(func.trim(Word.lemma)) == normalized,
                Word.part_of_speech == part_of_speech,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        lemma: str,
        translation: str,
        example_en: str,
        example_uk: str,
        level: CEFRLevel,
        part_of_speech: PartOfSpeech,
        topic: str | None = None,
        transcription_uk: str | None = None,
        transcription_us: str | None = None,
        synonyms: list[str] | None = None,
        antonyms: list[str] | None = None,
        collocations: list[str] | None = None,
        notes: str | None = None,
        source: str | None = None,
        generation_metadata: dict | None = None,
    ) -> Word:
        word = Word(
            lemma=lemma,
            translation=translation,
            example_en=example_en,
            example_uk=example_uk,
            level=level,
            part_of_speech=part_of_speech,
            topic=topic,
            transcription_uk=transcription_uk,
            transcription_us=transcription_us,
            synonyms=synonyms or [],
            antonyms=antonyms or [],
            collocations=collocations or [],
            notes=notes,
            source=source or WordSource.AI_GENERATED,
            generation_metadata=generation_metadata,
        )
        self._session.add(word)
        await self._session.flush()
        return word

    async def get_distractor_candidates(
        self,
        *,
        exclude_word_id: int,
        part_of_speech: PartOfSpeech | None = None,
        level: CEFRLevel | None = None,
        limit: int = 10,
    ) -> list[Word]:
        query = select(Word).where(Word.id != exclude_word_id)
        if part_of_speech is not None:
            query = query.where(Word.part_of_speech == part_of_speech)
        if level is not None:
            query = query.where(Word.level == level)
        query = query.order_by(func.random()).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def list_by_ids(self, word_ids: list[int]) -> list[Word]:
        if not word_ids:
            return []
        result = await self._session.execute(select(Word).where(Word.id.in_(word_ids)))
        return list(result.scalars().all())

    async def list_by_lemmas(self, lemmas: set[str]) -> list[Word]:
        """Looks words up by normalized lemma (case/whitespace-insensitive).
        Used to find catalog words that are synonyms/antonyms/collocations of
        words a user already knows -- i.e. this user's local "knowledge
        graph" neighbors, derived straight from Word rows already in
        Postgres rather than a separate graph store."""

        if not lemmas:
            return []
        result = await self._session.execute(
            select(Word).where(Word.lemma_normalized.in_(lemmas))
        )
        return list(result.scalars().all())

    async def count_by_level(self, level: CEFRLevel) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(Word).where(Word.level == level)
        )
        return int(result.scalar_one())

    async def get_unlinked_for_user(
        self, user_id: int, limit: int, level: CEFRLevel | None = None
    ) -> list[Word]:
        """Words from the catalog the given user has no user_words row for yet
        (regardless of status), i.e. legitimate candidates to add to their pool.
        Used by the Phase 3 StaticPoolFiller and by the Phase 4 AI generation
        service's dedup step alike."""

        known = select(UserWord.word_id).where(UserWord.user_id == user_id)
        query = select(Word).where(Word.id.not_in(known))
        if level is not None:
            query = query.where(Word.level == level)
        query = query.order_by(func.random()).limit(limit)
        result = await self._session.execute(query)
        return list(result.scalars().all())
