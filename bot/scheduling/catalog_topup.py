"""Background catalog top-up (spec section 8, "batch generation" -- scaled
down for a bot used by one or two people).

Runs once a day, off the same AIProvider and the same validation path
VocabularyGenerationService uses, and tops up any CEFR level whose catalog
has gotten thin. The point is the same as the spec's fuller "background job
+ candidate buffer" design -- decouple a user's request from live Gemini
latency -- but for this scale, simply keeping the shared `words` catalog
well-stocked per level is enough: PoolService's catalog-reuse-first
selection (see VocabularyGenerationService) already prefers these
pre-generated rows over a live AI call whenever they're available.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.exceptions import AIGenerationError
from bot.ai.provider import AIProvider, GenerateWordsRequest
from bot.ai.validators import sanitize_transcriptions, validate_generated_word
from bot.database.models.enums import CEFRLevel, WordSource
from bot.database.repositories.word_repository import WordRepository
from bot.database.session import get_session
from bot.utils.logging import get_logger

logger = get_logger(__name__)

MIN_CATALOG_SIZE_PER_LEVEL = 30
TOPUP_BATCH_SIZE = 8


class CatalogTopUpJob:
    def __init__(
        self,
        ai_provider: AIProvider,
        session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] | None = None,
    ) -> None:
        self._ai = ai_provider
        self._session_factory = session_factory or get_session

    async def run(self) -> None:
        for level in CEFRLevel:
            await self._top_up_level(level)

    async def _top_up_level(self, level: CEFRLevel) -> None:
        async with self._session_factory() as session:
            words = WordRepository(session)
            current_count = await words.count_by_level(level)
            if current_count >= MIN_CATALOG_SIZE_PER_LEVEL:
                return

            request = GenerateWordsRequest(level=level, count=TOPUP_BATCH_SIZE)
            try:
                generated = await self._ai.generate_words(request)
            except AIGenerationError:
                logger.warning("catalog_topup_ai_call_failed", level=level.value)
                return

            added = 0
            for item in generated:
                if await words.get_by_lemma(item.lemma, item.part_of_speech) is not None:
                    continue
                problems = validate_generated_word(item)
                if problems:
                    logger.warning(
                        "catalog_topup_candidate_rejected", lemma=item.lemma, problems=problems
                    )
                    continue

                transcription_uk, transcription_us = sanitize_transcriptions(item)
                await words.create(
                    lemma=item.lemma,
                    translation=item.translation,
                    example_en=item.example_en,
                    example_uk=item.example_uk,
                    level=item.level,
                    part_of_speech=item.part_of_speech,
                    topic=item.topic,
                    transcription_uk=transcription_uk,
                    transcription_us=transcription_us,
                    synonyms=item.synonyms,
                    antonyms=item.antonyms,
                    collocations=item.collocations,
                    source=WordSource.AI_GENERATED,
                )
                added += 1

            logger.info(
                "catalog_topped_up", level=level.value, added=added, before=current_count
            )
